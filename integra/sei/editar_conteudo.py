"""Edição do conteúdo de um documento interno via API do CKEditor (injeção).

O editor "WYSIWYG" do SEI é o **CKEditor**: o conteúdo do documento é HTML e a
janela do editor expõe a API JavaScript ``CKEDITOR.instances``. Em vez de
simular teclado e "localizar/substituir" na tela (lento e frágil), este módulo
**lê o HTML** de cada seção (``getData()``), faz as substituições como string no
Python e **devolve o documento pronto** (``setData()``) — determinístico e
rápido, usando apenas a sessão logada comum (nenhuma habilitação institucional,
API ou web service é necessária).

Estrutura do editor, verificada ao vivo no pacote de origem: **4 instâncias**
CKEditor (cabeçalho, identificação, corpo do texto, rodapé). Este módulo aplica
as substituições em **todas as instâncias editáveis** — onde quer que o
placeholder esteja — e ignora as somente-leitura.

Fluxo pensado para os **modelos pré-definidos**: crie o documento com
:class:`~integra.sei.incluir_documento_interno.IncluirDocumentoInterno` usando
``documento_modelo=`` (clona um documento base com placeholders, ex.:
``{{NOME}}``), depois aplique :class:`EditarConteudo` com o dicionário de
``substituicoes``. Rede de segurança: se algum placeholder pedido **não** for
encontrado, o módulo **fecha o editor sem salvar** e falha listando o que
faltou — nada é gravado pela metade.

A confirmação do salvamento usa o comportamento real do editor do SEI: o botão
"Salvar" (um ``<a>``, não ``<button>``) **fica desabilitado** quando a gravação
conclui.
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
from datetime import datetime

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from .barra_icones import clicar_icone_barra
from .exceptions import EditarConteudoError, SeiNavegacaoError

_log = logging.getLogger(__name__)

#: Meses em pt-BR para :func:`data_por_extenso` (independe de locale instalado).
MESES_PT = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def data_por_extenso(data: datetime | None = None) -> str:
    """Data em pt-BR por extenso (ex.: ``"2 de julho de 2026"``).

    Helper para o placeholder de data dos modelos — evita depender do locale
    ``pt_BR`` estar instalado na máquina.

    Args:
        data: data a formatar; se omitida, usa a data de hoje.
    """
    d = data or datetime.now()
    return f"{d.day} de {MESES_PT[d.month - 1]} de {d.year}"


class EditarConteudo:
    """Substitui placeholders no conteúdo de um documento aberto no SEI.

    Opera sobre o documento **atualmente selecionado na árvore** (ex.: o
    recém-criado por ``IncluirDocumentoInterno``): aciona "Editar Conteúdo",
    espera o editor (janela nova) carregar, injeta as substituições via
    CKEditor, salva, fecha o editor e devolve o driver à janela principal.

    Args:
        driver: WebDriver com o SEI autenticado e o documento selecionado na
            árvore do processo.
        substituicoes: mapeamento ``placeholder → valor`` (ex.:
            ``{"{{NOME}}": "MARIA", "{{CPF}}": "111.111.111-11"}``). A sintaxe
            do placeholder é livre — é uma busca por texto exato.
        exigir_todas: se ``True`` (padrão), todo placeholder do dicionário
            **deve** existir no documento; faltando algum, fecha o editor sem
            salvar e levanta :class:`EditarConteudoError` com a lista. Use
            ``False`` para tolerar placeholders opcionais.
        escapar_html: se ``True`` (padrão), os **valores** são escapados
            (``&``, ``<``, ``>``) antes de entrar no HTML — o texto aparece
            literalmente no documento. Use ``False`` para injetar HTML cru
            (por sua conta: precisa ser válido e usar as classes CSS do SEI).
        timeout: espera máxima por elemento/janela, em segundos.

    Raises:
        ValueError: se ``substituicoes`` for vazio ou tiver chave/valor inválido.
    """

    ICONE_EDITAR = "Editar Conteúdo"
    XPATH_BOTAO_SALVAR = '//a[contains(@title, "Salvar")]'
    CLASSE_BOTAO_DESABILITADO = "cke_button_disabled"

    # O editor (janela nova) é pesado; espera própria, maior que o timeout base.
    TIMEOUT_EDITOR = 30
    # Ao reabrir um documento já salvo, o editor abre "limpo" e o Salvar nasce
    # desabilitado; após marcar como alterado (evento `change`), espera-se ele
    # habilitar por até este tempo.
    TIMEOUT_HABILITAR_SALVAR = 10
    # Confirmação do save: o botão "Salvar" volta a ficar desabilitado.
    TIMEOUT_SALVAR = 20
    INTERVALO_SALVAR = 0.5
    # setData é assíncrono no CKEditor; pausa curta após cada escrita.
    INTERVALO_SETDATA = 0.5
    # Aviso (não erro) se sobrar algo com cara de placeholder após substituir.
    PADRAO_PLACEHOLDER = re.compile(r"\{\{[^{}]+\}\}")

    JS_EDITORES_PRONTOS = """
        if (typeof CKEDITOR === 'undefined') { return false; }
        var ks = Object.keys(CKEDITOR.instances);
        if (ks.length === 0) { return false; }
        for (var i = 0; i < ks.length; i++) {
            if (CKEDITOR.instances[ks[i]].status !== 'ready') { return false; }
        }
        return true;
    """
    JS_LER_INSTANCIAS = """
        var out = {};
        var ks = Object.keys(CKEDITOR.instances);
        for (var i = 0; i < ks.length; i++) {
            var ed = CKEDITOR.instances[ks[i]];
            out[ks[i]] = {conteudo: ed.getData(), somenteLeitura: !!ed.readOnly};
        }
        return JSON.stringify(out);
    """
    # setData deixa o editor "limpo" (não-sujo); o callback dispara `change`
    # para o SEI reconhecer a alteração e habilitar o botão Salvar.
    JS_ESCREVER_INSTANCIA = """
        var ed = CKEDITOR.instances[arguments[0]];
        ed.setData(arguments[1], { callback: function () { ed.fire('change'); } });
    """
    # Defensivo: re-dispara `change` nas instâncias alteradas (garante o evento
    # mesmo que o callback assíncrono do setData não tenha corrido a tempo).
    JS_MARCAR_ALTERADO = """
        var nomes = arguments[0];
        for (var i = 0; i < nomes.length; i++) {
            var ed = CKEDITOR.instances[nomes[i]];
            if (ed) { ed.fire('change'); }
        }
    """

    def __init__(
        self,
        driver,
        substituicoes: dict[str, str],
        *,
        exigir_todas: bool = True,
        escapar_html: bool = True,
        timeout: float = 10,
    ):
        if not substituicoes or not isinstance(substituicoes, dict):
            raise ValueError("substituicoes deve ser um dict não-vazio")
        for chave, valor in substituicoes.items():
            if not isinstance(chave, str) or not chave.strip():
                raise ValueError(f"placeholder inválido: {chave!r}")
            if not isinstance(valor, str):
                raise ValueError(
                    f"valor de {chave!r} deve ser string (recebi {type(valor).__name__})"
                )

        self.driver = driver
        self.substituicoes = dict(substituicoes)
        self.exigir_todas = exigir_todas
        self.escapar_html = escapar_html
        self.timeout = timeout

    def editar(self) -> dict[str, int]:
        """Executa o fluxo completo: abre o editor, substitui, salva e fecha.

        Returns:
            Mapeamento ``placeholder → nº de ocorrências substituídas`` (útil
            para logs/planilhas de quem automatiza em escala).

        Raises:
            EditarConteudoError: se o editor não abrir/carregar, algum
                placeholder não for encontrado (com ``exigir_todas=True``;
                nesse caso **nada é salvo**) ou o botão Salvar não existir.
        """
        janela_principal = self.driver.current_window_handle
        janelas_antes = set(self.driver.window_handles)

        try:
            clicar_icone_barra(self.driver, self.ICONE_EDITAR, timeout=self.timeout)
        except SeiNavegacaoError as exc:
            raise EditarConteudoError(str(exc)) from exc

        self._entrar_no_editor(janelas_antes)
        try:
            contagens = self._substituir()
            self._salvar()
        except Exception:
            # Deixa o driver são para o chamador: fecha o editor (sem salvar,
            # se a falha veio antes do save) e volta à janela principal.
            self._fechar_editor_e_voltar(janela_principal)
            raise
        self._fechar_editor_e_voltar(janela_principal)
        _log.info("Conteúdo editado: %s", contagens)
        return contagens

    # ----- passos -----

    def _entrar_no_editor(self, janelas_antes: set) -> None:
        try:
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: set(d.window_handles) - janelas_antes
            )
        except TimeoutException as exc:
            raise EditarConteudoError(
                "a janela do editor não abriu após 'Editar Conteúdo'"
            ) from exc
        janela_editor = (set(self.driver.window_handles) - janelas_antes).pop()
        self.driver.switch_to.window(janela_editor)
        try:
            WebDriverWait(self.driver, self.TIMEOUT_EDITOR).until(
                lambda d: d.execute_script(self.JS_EDITORES_PRONTOS)
            )
        except TimeoutException as exc:
            self._fechar_editor_e_voltar_apos_falha()
            raise EditarConteudoError(
                "o editor abriu, mas as instâncias do CKEditor não ficaram "
                f"prontas em {self.TIMEOUT_EDITOR}s"
            ) from exc
        _log.info("Editor aberto e pronto")

    def _substituir(self) -> dict[str, int]:
        """Lê todas as instâncias, substitui no Python e grava as alteradas.

        A contagem é feita **antes** de gravar: com ``exigir_todas=True``, um
        placeholder ausente aborta sem tocar no documento.
        """
        bruto = self.driver.execute_script(self.JS_LER_INSTANCIAS)
        instancias = json.loads(bruto)
        editaveis = {
            nome: dados["conteudo"]
            for nome, dados in instancias.items()
            if not dados["somenteLeitura"]
        }
        if not editaveis:
            raise EditarConteudoError(
                "nenhuma instância editável no editor (todas somente-leitura?)"
            )

        contagens = {ph: 0 for ph in self.substituicoes}
        novos: dict[str, str] = {}
        for nome, conteudo in editaveis.items():
            novo = conteudo
            for ph, valor in self.substituicoes.items():
                ocorrencias = novo.count(ph)
                if not ocorrencias:
                    continue
                contagens[ph] += ocorrencias
                texto = html.escape(valor, quote=False) if self.escapar_html else valor
                novo = novo.replace(ph, texto)
            if novo != conteudo:
                novos[nome] = novo

        faltantes = [ph for ph, n in contagens.items() if n == 0]
        if faltantes and self.exigir_todas:
            raise EditarConteudoError(
                "placeholder(s) não encontrado(s) no documento (nada foi salvo): "
                + ", ".join(repr(p) for p in faltantes)
                + " — confira o texto do modelo (placeholder fragmentado por "
                "formatação parcial também não é encontrado)"
            )
        if not novos:
            _log.warning("Nenhuma substituição aplicada (nada a salvar)")
            return contagens

        for nome, conteudo in novos.items():
            self.driver.execute_script(self.JS_ESCREVER_INSTANCIA, nome, conteudo)
            time.sleep(self.INTERVALO_SETDATA)
            _log.info("Instância %r atualizada", nome)
        # Garante que o editor reconheça a alteração (habilita o Salvar).
        self.driver.execute_script(self.JS_MARCAR_ALTERADO, list(novos))

        sobras = sorted(
            {m for c in novos.values() for m in self.PADRAO_PLACEHOLDER.findall(c)}
        )
        if sobras:
            _log.warning(
                "Restaram trechos com cara de placeholder após substituir: %s",
                ", ".join(sobras),
            )
        return contagens

    def _salvar(self) -> None:
        """Espera o botão Salvar habilitar, clica e confirma pela desabilitação.

        Comportamento real do editor do SEI: o "Salvar" é um ``<a>`` com a classe
        ``cke_button_disabled`` quando não há nada a salvar. Ao **reabrir** um
        documento já salvo, ele nasce desabilitado; só habilita depois que o
        editor reconhece a alteração (o evento `change` disparado no
        :meth:`_substituir`). Por isso **esperamos** ele habilitar antes de
        clicar — a volta ao estado desabilitado após o clique confirma a
        gravação.
        """
        self.driver.switch_to.default_content()
        botao = self._esperar_salvar_habilitado()
        if botao is None:
            raise EditarConteudoError(
                "o botão Salvar não habilitou após a substituição — o editor "
                "não reconheceu a alteração (nada foi salvo)"
            )
        # Clique via JS: o botão do CKEditor nem sempre responde ao click nativo.
        self.driver.execute_script("arguments[0].click();", botao)

        limite = time.monotonic() + self.TIMEOUT_SALVAR
        while time.monotonic() < limite:
            try:
                classes = botao.get_attribute("class") or ""
            except WebDriverException:
                classes = ""
            if self.CLASSE_BOTAO_DESABILITADO in classes:
                _log.info("Documento salvo (botão Salvar desabilitado)")
                return
            time.sleep(self.INTERVALO_SALVAR)
        _log.warning(
            "Salvamento não confirmado em %ss (botão não desabilitou); "
            "prosseguindo — confira o documento",
            self.TIMEOUT_SALVAR,
        )

    def _esperar_salvar_habilitado(self):
        """Aguarda um botão "Salvar" habilitado (sem a classe de desabilitado)
        aparecer, por até :attr:`TIMEOUT_HABILITAR_SALVAR`; devolve-o ou ``None``.
        """
        limite = time.monotonic() + self.TIMEOUT_HABILITAR_SALVAR
        while time.monotonic() < limite:
            for cand in self.driver.find_elements(
                By.XPATH, self.XPATH_BOTAO_SALVAR
            ):
                classes = cand.get_attribute("class") or ""
                if self.CLASSE_BOTAO_DESABILITADO not in classes:
                    return cand
            time.sleep(self.INTERVALO_SALVAR)
        return None

    def _fechar_editor_e_voltar(self, janela_principal: str) -> None:
        try:
            self.driver.close()
        except WebDriverException as exc:
            _log.debug("Falha ao fechar o editor: %s", str(exc).splitlines()[0])
        self.driver.switch_to.window(janela_principal)
        _log.info("Editor fechado; de volta à janela principal")

    def _fechar_editor_e_voltar_apos_falha(self) -> None:
        """Fecha o editor e volta à primeira janela restante (melhor esforço,
        para não deixar o driver preso numa janela morta após uma falha)."""
        try:
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
        except WebDriverException:
            pass
