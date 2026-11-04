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
:class:`~integra_gov.sei.incluir_documento_interno.IncluirDocumentoInterno` usando
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
from collections.abc import Iterable
from datetime import datetime

from selenium.common.exceptions import (
    JavascriptException,
    TimeoutException,
    WebDriverException,
)
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


def montar_link_documento(id_documento: str, protocolo: str) -> str:
    """Monta o HTML de um **link para outro documento** do SEI (âncora nativa).

    No editor do SEI, um link para outro documento **não** é um ``<a href>``
    comum: é uma âncora especial (classe ``ancora_sei``, id ``lnkSei<id>``, sem
    ``href``) que o próprio SEI resolve em tempo de visualização. O **texto
    visível** é o *protocolo* (número SEI) e o **id embute o `id_documento`**
    (id interno) — dois identificadores distintos do mesmo documento.

    Use o retorno como **valor de uma substituição sem escape** no
    :class:`EditarConteudo` (liste o placeholder em ``chaves_html``); assim o
    link entra no documento como HTML, não como texto literal.

    O ``id_documento`` sai do ``href`` do nó na árvore
    (``...&id_documento=XXXX``) — ver ``DocumentoNo.id_documento`` em
    :mod:`~integra_gov.sei.documentos_arvore`.

    Args:
        id_documento: id interno do documento (numérico).
        protocolo: número (protocolo) do documento — o texto visível do link.

    Raises:
        ValueError: se ``id_documento`` não for numérico ou ``protocolo`` faltar.
    """
    id_doc = str(id_documento).strip()
    proto = str(protocolo).strip()
    if not id_doc.isdigit():
        raise ValueError(f"id_documento deve ser numérico (recebi {id_documento!r})")
    if not proto:
        raise ValueError("protocolo é obrigatório")
    return (
        '<span contenteditable="false" style="text-indent:0;">'
        f'<a class="ancora_sei" id="lnkSei{id_doc}" style="text-indent:0;">'
        f"{html.escape(proto, quote=False)}</a></span>"
    )


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
        chaves_html: subconjunto de ``substituicoes`` cujos **valores** são
            injetados como **HTML cru** (sem escape), mesmo com
            ``escapar_html=True`` — para inserir links/marcações prontos (ex.: a
            âncora de :func:`montar_link_documento`) junto de campos de texto
            escapados, numa **única** passada. Placeholders fora de
            ``substituicoes`` levantam ``ValueError``.
        timeout: espera máxima por elemento/janela, em segundos.

    Raises:
        ValueError: se ``substituicoes`` for vazio ou tiver chave/valor inválido.
    """

    ICONE_EDITAR = "Editar Conteúdo"
    # SEI 4.x (CKEditor 4): <a title="Salvar">, desabilitado com cke_button_disabled.
    # SEI 5.0.4 (CKEditor 5): <button class="... salvar__buttonview">, com ck-disabled.
    XPATH_BOTAO_SALVAR = (
        '//a[contains(@title, "Salvar")]'
        ' | //button[contains(@class, "salvar__buttonview")]'
    )
    CLASSE_BOTAO_DESABILITADO = "cke_button_disabled"
    CLASSE_BOTAO_DESABILITADO_CK5 = "ck-disabled"
    # CKEditor 5: gravação em andamento (o botão já vem com ck-disabled).
    CLASSE_GRAVANDO_CK5 = "salvar__loading"

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

    # Dois editores, conforme a versão do SEI:
    #   - SEI 4.x: CKEditor 4 — CKEDITOR.instances, uma instância por seção;
    #   - SEI 5.0.4: CKEditor 5 MULTI-RAIZ (InfraEditor) — NÃO há
    #     CKEDITOR.instances; um único editor, preso em .ckeditorInstance das
    #     divs .ck-editor__editable, e cada seção é uma raiz com o nome do id
    #     da div (txaEditor_NNNN); seção somente-leitura tem a classe
    #     ck-read-only. Conferido ao vivo em 28/10/2026 (1ª Nota Técnica no
    #     5.0.4: o Object.keys(CKEDITOR.instances) quebrava a espera).
    # _ck5() devolve o editor do CKEditor 5 (ou null).
    _JS_CK5 = """
        function _ck5() {
            var els = document.querySelectorAll('.ck-editor__editable');
            for (var i = 0; i < els.length; i++) {
                if (els[i].ckeditorInstance) { return els[i].ckeditorInstance; }
            }
            return null;
        }
        var ck4 = typeof CKEDITOR !== 'undefined' && !!CKEDITOR.instances;
    """
    JS_EDITORES_PRONTOS = _JS_CK5 + """
        if (typeof CKEDITOR === 'undefined') { return false; }
        if (ck4) {
            var ks = Object.keys(CKEDITOR.instances);
            if (ks.length === 0) { return false; }
            for (var i = 0; i < ks.length; i++) {
                if (CKEDITOR.instances[ks[i]].status !== 'ready') { return false; }
            }
            return true;
        }
        var ed = _ck5();
        if (!ed || ed.state !== 'ready') { return false; }
        return typeof infraEditor === 'undefined' || infraEditor.isReady !== false;
    """
    JS_LER_INSTANCIAS = _JS_CK5 + """
        var out = {};
        if (ck4) {
            var ks = Object.keys(CKEDITOR.instances);
            for (var i = 0; i < ks.length; i++) {
                var ed4 = CKEDITOR.instances[ks[i]];
                out[ks[i]] = {conteudo: ed4.getData(), somenteLeitura: !!ed4.readOnly};
            }
        } else {
            var ed = _ck5();
            ed.model.document.getRootNames().forEach(function (nome) {
                var el = ed.ui.getEditableElement(nome);
                out[nome] = {
                    conteudo: ed.getData({rootName: nome}),
                    somenteLeitura: ed.isReadOnly || !el || el.classList.contains('ck-read-only')
                };
            });
        }
        return JSON.stringify(out);
    """
    # CKEditor 4: setData deixa o editor "limpo" (não-sujo); o callback dispara
    # `change` para o SEI reconhecer a alteração e habilitar o botão Salvar.
    # CKEditor 5: setData só da raiz pedida (as demais ficam intactas).
    JS_ESCREVER_INSTANCIA = _JS_CK5 + """
        if (ck4) {
            var ed4 = CKEDITOR.instances[arguments[0]];
            ed4.setData(arguments[1], { callback: function () { ed4.fire('change'); } });
        } else {
            var dados = {};
            dados[arguments[0]] = arguments[1];
            _ck5().setData(dados);
        }
    """
    # Defensivo (CKEditor 4): re-dispara `change` nas instâncias alteradas
    # (garante o evento mesmo que o callback assíncrono do setData não tenha
    # corrido a tempo). No CKEditor 5 a alteração do modelo já basta.
    JS_MARCAR_ALTERADO = _JS_CK5 + """
        if (!ck4) { return; }
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
        chaves_html: Iterable[str] | None = None,
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
        chaves_html = set(chaves_html or ())
        desconhecidas = chaves_html - set(substituicoes)
        if desconhecidas:
            raise ValueError(
                "chaves_html tem placeholder(s) ausente(s) de substituicoes: "
                + ", ".join(repr(c) for c in sorted(desconhecidas))
            )

        self.driver = driver
        self.substituicoes = dict(substituicoes)
        self.exigir_todas = exigir_todas
        self.escapar_html = escapar_html
        self.chaves_html = chaves_html
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

        self._entrar_no_editor(janelas_antes, janela_principal)
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

    def _entrar_no_editor(self, janelas_antes: set, janela_principal: str) -> None:
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

        def prontos(d) -> bool:
            # Com a janela ainda carregando, o script do editor pode dar erro
            # de JavaScript (objetos do editor pela metade): ainda não pronto.
            try:
                return bool(d.execute_script(self.JS_EDITORES_PRONTOS))
            except JavascriptException:
                return False

        try:
            WebDriverWait(self.driver, self.TIMEOUT_EDITOR).until(prontos)
        except WebDriverException as exc:  # inclui TimeoutException
            # Volta à janela PRINCIPAL (não à 1ª da lista, que pode ser o
            # e-SIAPE): preso no editor, o fluxo seguinte falha em cascata.
            self._fechar_editor_e_voltar(janela_principal)
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
                escapar = self.escapar_html and ph not in self.chaves_html
                texto = html.escape(valor, quote=False) if escapar else valor
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

        # Confere relendo: o CKEditor 5 converte o HTML no setData; se a escrita
        # não pegou numa seção, o placeholder segue lá — aborta sem salvar.
        relidos = json.loads(self.driver.execute_script(self.JS_LER_INSTANCIAS))
        nao_gravados = sorted({
            ph for nome in novos for ph, n in contagens.items()
            if n and ph in relidos.get(nome, {}).get("conteudo", "")
        })
        if nao_gravados:
            raise EditarConteudoError(
                "a substituição não ficou no editor (nada foi salvo): "
                + ", ".join(repr(p) for p in nao_gravados)
            )

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

        # CKEditor 5 (SEI 5.0.4): ck-disabled aparece JÁ na gravação, junto com
        # salvar__loading; só sem ele está gravado. Fechar antes interrompia a
        # gravação (processo real da EXANTE, 04/11/2026: Nota Técnica sem os dados).
        limite = time.monotonic() + self.TIMEOUT_SALVAR
        while time.monotonic() < limite:
            try:
                classes = botao.get_attribute("class") or ""
            except WebDriverException:
                classes = ""
            if (self._botao_desabilitado(classes)
                    and self.CLASSE_GRAVANDO_CK5 not in classes.split()):
                _log.info("Documento salvo (botão Salvar desabilitado)")
                return
            time.sleep(self.INTERVALO_SALVAR)
        # Sem confirmação NÃO é sucesso: o chamador daria por salvo um
        # documento que pode ter ficado com os placeholders.
        raise EditarConteudoError(
            f"salvamento não confirmado em {self.TIMEOUT_SALVAR}s (o botão Salvar "
            "não voltou ao estado de gravado) — confira o documento"
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
                if not self._botao_desabilitado(classes):
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

    def _botao_desabilitado(self, classes: str) -> bool:
        return (self.CLASSE_BOTAO_DESABILITADO in classes
                or self.CLASSE_BOTAO_DESABILITADO_CK5 in classes.split())
