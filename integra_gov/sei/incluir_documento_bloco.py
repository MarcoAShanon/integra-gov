"""Inclusão de documentos em um bloco de assinatura no SEI.

Com um processo aberto e um documento **selecionado na árvore** (ex.: via
:meth:`~integra_gov.sei.documentos_arvore.DocumentosArvore.selecionar`), aciona
o ícone **"Incluir em Bloco de Assinatura"**, escolhe o bloco no dropdown
(``selBloco``), marca os checkboxes dos protocolos pedidos e confirma.

Blocos de assinatura são o mecanismo do SEI para **assinatura em lote**: os
documentos entram num bloco e o(s) signatário(s) — inclusive de outra unidade —
assinam tudo de uma vez.

Confiabilidade (padrão do pacote): nada de ``bool`` silencioso — sucesso retorna
``None``, falha levanta :class:`~integra_gov.sei.exceptions.BlocoAssinaturaError`.
Estrito nos pontos frágeis: se **qualquer** protocolo pedido não aparecer na
tela, **nada é incluído** (erro antes de confirmar); um diálogo pós-Incluir é
**dispensado** (``dismiss``) e tratado como recusa — nunca aceito, pois um
``confirm()`` de prosseguimento aceito confirmaria a inclusão junto com um erro
falso.

**Confirmação — verificada ao vivo no SEI 4.1.5:** ao incluir com sucesso, o SEI
**não muda a tela** (o formulário do bloco continua, o documento continua na
lista, e não há mensagem de sucesso). Não existe, portanto, um sinal positivo a
esperar. A confirmação é **pela ausência de recusa**: o submit recarrega o
iframe (a âncora do formulário fica *stale* — prova de que a ação foi
processada); uma recusa apareceria como **alerta** (imediato ou tardio) ou como
**mensagem de erro inline** (``#divInfraExcecoes``). Sem nenhum desses, a
inclusão é dada por aceita. O ``bloco`` casa pelo **value** da opção (id
numérico) ou pelo **texto** visível; se não existir, o erro lista os blocos
disponíveis.
"""

from __future__ import annotations

import logging
import re
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    UnexpectedAlertPresentException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .barra_icones import clicar_icone_barra
from .exceptions import BlocoAssinaturaError, SeiNavegacaoError
from .iframes import descer_para_conteudo_documento, switch_to_iframe_visualizacao

_log = logging.getLogger(__name__)

#: Pausa (s) após (re)selecionar o nó, antes de clicar o ícone — evita o clique
#: "engolido" pelo reload da visualização (ver clicar_icone_barra/enviar_processo).
SETTLE_APOS_NO = 1.2
#: Pausa (s) após selecionar o bloco: no módulo-fonte original havia um sleep com
#: o comentário "Aguardar carregamento dos checkboxes" — evidência de que a troca
#: do ``selBloco`` pode re-renderizar a lista. Sem a pausa, um checkbox localizado
#: antes do re-render ficaria *stale* (ou a marcação se perderia).
ESTABILIZACAO_POS_BLOCO = 0.5


class IncluirDocumentoBloco:
    """Inclui documento(s) do processo aberto em um bloco de assinatura.

    Pré-condição: o documento-alvo deve estar **selecionado na árvore** (a tela
    do bloco lista os documentos assináveis do processo; os ``protocolos``
    dizem quais marcar — normalmente o próprio documento selecionado).

    Args:
        driver: WebDriver com o SEI autenticado e um processo aberto.
        bloco: o bloco de assinatura — o **value** da opção do dropdown (id
            numérico, ex.: ``"123"``) ou o **texto** visível da opção.
        protocolos: números dos documentos a marcar (só dígitos, como aparecem
            na tela do bloco — ex.: ``["35551895"]``). **Não** é o número do
            processo formatado.
        timeout: espera máxima por elemento/iframe, em segundos.

    Raises:
        ValueError: se ``bloco`` for vazio, ``protocolos`` não tiver nenhum
            protocolo não-vazio, ou algum protocolo não for numérico.
    """

    ICONE = "Incluir em Bloco de Assinatura"
    ID_BLOCO = "selBloco"
    ID_INCLUIR = "sbmIncluir"
    #: Espera curta do alerta de erro após Incluir.
    TIMEOUT_ALERTA = 2
    #: Fallback genérico do botão (o SEI varia ids/markup com versão/tema).
    XPATH_INCLUIR_GENERICO = (
        '//button[contains(normalize-space(.), "Incluir")]'
        ' | //input[@type="submit"][contains(@value, "Incluir")]'
    )
    #: Values de opção que são placeholder ("selecione…"), não blocos reais.
    VALUES_PLACEHOLDER = ("", "null")
    #: Containers de **erro** de validação inline do SEI (recusa sem alerta).
    #: Só de erro — mensagens neutras/de sucesso não entram, para não confundir
    #: sucesso com recusa.
    SELETORES_ERRO = (
        "#divInfraExcecoes",
        "div.infraExcecao",
        "div.alert-danger",
    )

    def __init__(
        self,
        driver,
        bloco: str,
        protocolos: list[str],
        *,
        timeout: float = 10,
    ):
        if not bloco or not str(bloco).strip():
            raise ValueError("bloco é obrigatório")
        limpos = [p.strip() for p in protocolos if p and p.strip()]
        if not limpos:
            raise ValueError("protocolos deve ter ao menos um protocolo não-vazio")
        for p in limpos:
            if not re.fullmatch(r"\d+", p):
                raise ValueError(
                    f"protocolo {p!r} inválido — use o número do documento, só "
                    "dígitos (ex.: '35551895'), não o número do processo formatado"
                )
        self.driver = driver
        self.bloco = str(bloco).strip()
        self.protocolos = limpos
        self.timeout = timeout

    def incluir(self) -> None:
        """Inclui os :attr:`protocolos` no :attr:`bloco` de assinatura.

        Raises:
            BlocoAssinaturaError: se o ícone/formulário não for encontrado, o
                bloco não existir no dropdown (o erro lista as opções), algum
                protocolo não aparecer na tela (**nada é incluído**), o SEI
                recusar a inclusão (diálogo, imediato ou tardio, ou validação
                inline), ou a confirmação não acontecer.
        """
        try:
            self._acionar_icone()
            self._ir_para_formulario()
            self._selecionar_bloco()
            self._marcar_protocolos()
            self._confirmar()
        except BlocoAssinaturaError:
            self._voltar_default()
            raise
        except WebDriverException as exc:
            # Exceção crua do Selenium — honra o contrato "Raises:
            # BlocoAssinaturaError" e não deixa o driver preso num iframe.
            self._voltar_default()
            raise BlocoAssinaturaError(
                f"falha inesperada na inclusão em bloco: {exc}"
            ) from exc
        _log.info(
            "Incluído(s) no bloco %r: %s", self.bloco, ", ".join(self.protocolos)
        )

    # ----- passos -----

    def _acionar_icone(self) -> None:
        try:
            clicar_icone_barra(
                self.driver,
                self.ICONE,
                timeout=self.timeout,
                estabilizar_apos_no=SETTLE_APOS_NO,
            )
        except SeiNavegacaoError as exc:
            raise BlocoAssinaturaError(
                f"não foi possível acionar '{self.ICONE}': {exc}"
            ) from exc

    def _ir_para_formulario(self) -> None:
        """Posiciona no formulário do bloco (dropdown ``selBloco`` acessível).

        A tela pode carregar no wrapper de visualização, no ``ifrVisualizacao``
        aninhado (SEI 4.0 — mesma lição do ``download_documento``) ou no
        contexto principal; tenta nessa ordem. O wrapper — o local verificado no
        módulo original — recebe o timeout cheio; os fallbacks, espera curta."""
        curto = min(self.timeout, 5)
        self.driver.switch_to.default_content()
        try:
            switch_to_iframe_visualizacao(self.driver, timeout=self.timeout)
            if self._formulario_presente(self.timeout):
                return
            descer_para_conteudo_documento(self.driver, timeout=self.timeout)
            if self._formulario_presente(curto):
                return
        except WebDriverException:
            pass
        self.driver.switch_to.default_content()
        if self._formulario_presente(curto):
            return
        raise BlocoAssinaturaError(
            f"o formulário do bloco não carregou (dropdown {self.ID_BLOCO!r} ausente)"
        )

    def _formulario_presente(self, timeout: float) -> bool:
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_BLOCO))
            )
            return True
        except (TimeoutException, WebDriverException):
            return False

    def _selecionar_bloco(self) -> None:
        """Seleciona o bloco no dropdown, casando pelo ``value`` (id) ou pelo
        texto visível **exato**; erro lista as opções disponíveis (sem
        placeholders). Após selecionar, aguarda a lista de documentos
        estabilizar (ver :data:`ESTABILIZACAO_POS_BLOCO`)."""
        dropdown = self.driver.find_element(By.ID, self.ID_BLOCO)
        opcoes = dropdown.find_elements(By.TAG_NAME, "option")
        for opcao in opcoes:
            valor = (opcao.get_attribute("value") or "").strip()
            texto = (opcao.text or "").strip()
            if valor in self.VALUES_PLACEHOLDER:
                continue
            if self.bloco in (valor, texto):
                opcao.click()
                _log.debug("Bloco selecionado: %s (%r)", valor, texto)
                time.sleep(ESTABILIZACAO_POS_BLOCO)
                return
        disponiveis = (
            "; ".join(
                f"{(o.get_attribute('value') or '').strip()}"
                f"={((o.text or '').strip())!r}"
                for o in opcoes
                if (o.get_attribute("value") or "").strip()
                not in self.VALUES_PLACEHOLDER
            )
            or "nenhum"
        )
        raise BlocoAssinaturaError(
            f"bloco {self.bloco!r} não encontrado no dropdown — "
            f"blocos disponíveis: {disponiveis}"
        )

    def _marcar_protocolos(self) -> None:
        """Localiza TODOS os checkboxes antes de marcar: se qualquer protocolo
        estiver ausente, levanta **sem marcar nem confirmar nada** (estrito).
        Protocolo já marcado é aceito sem re-clicar (idempotente); um checkbox
        *stale* (re-render tardio da lista) é re-localizado uma vez."""
        achados: dict[str, object] = {}
        ausentes: list[str] = []
        for protocolo in self.protocolos:
            try:
                achados[protocolo] = WebDriverWait(self.driver, self.timeout).until(
                    EC.presence_of_element_located(
                        (By.XPATH, self._xpath_checkbox(protocolo))
                    )
                )
            except TimeoutException:
                ausentes.append(protocolo)
        if ausentes:
            raise BlocoAssinaturaError(
                "protocolo(s) não encontrado(s) na tela do bloco: "
                f"{', '.join(ausentes)} — nada foi incluído (o documento é "
                f"assinável e pertence a este processo?){self._titulos_na_tela()}"
            )
        for protocolo, checkbox in achados.items():
            try:
                self._marcar_um(protocolo, checkbox)
            except StaleElementReferenceException:
                _log.debug("checkbox %s ficou stale; re-localizando", protocolo)
                checkbox = self.driver.find_element(
                    By.XPATH, self._xpath_checkbox(protocolo)
                )
                self._marcar_um(protocolo, checkbox)

    @staticmethod
    def _xpath_checkbox(protocolo: str) -> str:
        # protocolo é validado como só-dígitos no __init__ (sem injeção).
        return f'//input[@type="checkbox"][@title="{protocolo}"]'

    def _marcar_um(self, protocolo: str, checkbox) -> None:
        if checkbox.is_selected():
            _log.debug("Protocolo %s já estava marcado", protocolo)
            return
        # O input do SEI (infraCheckbox) fica coberto pelo <label>: clique via
        # JS para não ser interceptado.
        self.driver.execute_script("arguments[0].click();", checkbox)
        if not checkbox.is_selected():
            raise BlocoAssinaturaError(
                f"não foi possível marcar o protocolo {protocolo}"
            )
        _log.debug("Protocolo %s marcado", protocolo)

    def _titulos_na_tela(self) -> str:
        """Sufixo (best-effort) com os titles de checkbox visíveis — ajuda a
        diagnosticar protocolo errado sem reabrir a tela."""
        try:
            els = self.driver.find_elements(
                By.XPATH, '//input[@type="checkbox"][@title]'
            )
            titulos = [t for t in ((e.get_attribute("title") or "").strip()
                                   for e in els[:20]) if t]
        except WebDriverException:
            return ""
        return f" Protocolos na tela: {', '.join(titulos)}." if titulos else ""

    def _confirmar(self) -> None:
        """Clica Incluir e confirma **pela ausência de recusa** (ver o docstring
        do módulo: no SEI 4.1.5 a tela não muda no sucesso). Passos: captura a
        âncora do formulário; clica; um alerta imediato é recusa; espera o submit
        ser processado (a âncora fica *stale* com o reload do iframe); um erro
        inline é recusa. Sem alerta e sem erro → aceito."""
        botao = self._primeiro_presente(
            (By.ID, self.ID_INCLUIR),
            (By.XPATH, self.XPATH_INCLUIR_GENERICO),
        )
        if botao is None:
            raise BlocoAssinaturaError(
                f"botão Incluir ({self.ID_INCLUIR}) não encontrado"
            )
        ancora = self._primeiro_presente((By.ID, self.ID_BLOCO))
        self.driver.execute_script("arguments[0].click();", botao)
        self._checar_alerta_erro()
        self._aguardar_processamento(ancora)
        self._checar_recusa_inline()
        self.driver.switch_to.default_content()

    def _checar_alerta_erro(self) -> None:
        try:
            alerta = WebDriverWait(
                self.driver, min(self.TIMEOUT_ALERTA, self.timeout)
            ).until(EC.alert_is_present())
        except TimeoutException:
            return  # sem diálogo imediato; a espera e o erro inline decidem
        texto = alerta.text
        # dismiss (cancelar) é o seguro: se for um confirm() de prosseguimento,
        # accept() CONFIRMARIA a inclusão junto com um erro falso.
        alerta.dismiss()
        raise BlocoAssinaturaError(
            f"o SEI exibiu um diálogo após Incluir (tratado como recusa): {texto}"
        )

    def _aguardar_processamento(self, ancora) -> None:
        """Espera o SEI processar o submit. O submit recarrega o iframe → a
        ``ancora`` (o ``selBloco`` de antes do clique) fica *stale*: isso prova
        que a ação foi processada. Um alerta **tardio** (fora da janela do
        :meth:`_checar_alerta_erro`) aparece aqui e é recusa. Se a âncora não
        ficar *stale* (submit sem reload detectável), segue mesmo assim — a
        checagem de erro inline vem em seguida."""
        if ancora is None:
            return
        try:
            WebDriverWait(self.driver, self.timeout).until(EC.staleness_of(ancora))
        except UnexpectedAlertPresentException as exc:
            texto = getattr(exc, "alert_text", None) or str(exc)
            self._dispensar_alerta_residual()
            raise BlocoAssinaturaError(
                f"o SEI recusou a inclusão no bloco (diálogo tardio): {texto}"
            ) from exc
        except TimeoutException:
            _log.debug(
                "âncora do formulário não ficou stale; seguindo para a checagem "
                "de erro inline"
            )

    def _checar_recusa_inline(self) -> None:
        """Recusa via mensagem de erro inline do SEI (validação sem alerta). Só
        levanta se houver texto num container de **erro** (``#divInfraExcecoes``
        etc.) — mensagens neutras não contam, para não ler sucesso como recusa."""
        for css in self.SELETORES_ERRO:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, css):
                    texto = (el.text or "").strip()
                    if texto:
                        raise BlocoAssinaturaError(
                            f"o SEI recusou a inclusão no bloco: {texto[:300]}"
                        )
            except WebDriverException:
                continue

    def _dispensar_alerta_residual(self) -> None:
        try:
            self.driver.switch_to.alert.dismiss()
        except WebDriverException:
            pass  # o chromedriver pode já ter descartado (dismiss and notify)

    # ----- utilitários -----

    def _primeiro_presente(self, *locators):
        """Primeiro elemento presente entre os localizadores; ``None`` se nenhum."""
        for by, value in locators:
            try:
                return self.driver.find_element(by, value)
            except NoSuchElementException:
                continue
        return None

    def _voltar_default(self) -> None:
        try:
            self.driver.switch_to.default_content()
        except WebDriverException:
            pass
