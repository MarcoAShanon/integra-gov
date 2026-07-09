"""Envio de um processo a outra unidade no SEI.

Com um processo aberto, aciona o ícone **"Enviar Processo"**, preenche a unidade
destino (campo de **autocomplete** do SEI) e envia — opcionalmente mantendo o
processo aberto na unidade atual.

Confiabilidade: nada de ``bool`` silencioso — sucesso retorna ``None``, falha
levanta :class:`~integra_gov.sei.exceptions.EnviarProcessoError`. O passo mais
frágil é o **autocomplete** da unidade destino (varia com versão/tema do SEI); o
módulo tenta clicar a sugestão (vários seletores) e, se não bastar, confirma com
**TAB** — e só dá o envio por bom quando a unidade **entra na lista de destinos**
(``selUnidades``), evitando enviar para o lugar errado. Depois de enviar, checa o
alerta de erro do SEI. Reusa
:func:`~integra_gov.sei.barra_icones.clicar_icone_barra` e
:func:`~integra_gov.sei.iframes.switch_to_iframe_visualizacao`.
"""

from __future__ import annotations

import logging

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    UnexpectedTagNameException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from .barra_icones import clicar_icone_barra
from .exceptions import EnviarProcessoError, SeiNavegacaoError
from .iframes import switch_to_iframe_visualizacao

_log = logging.getLogger(__name__)

#: Pausa (s) após (re)selecionar o nó, antes de clicar o ícone — evita o clique
#: "engolido" pelo reload da visualização (ver clicar_icone_barra/gerar_documento).
SETTLE_APOS_NO = 1.2


class EnviarProcesso:
    """Envia o processo aberto a outra unidade no SEI.

    Args:
        driver: WebDriver com o SEI autenticado e um processo aberto.
        unidade_destino: sigla da unidade destino, como aparece no autocomplete
            do SEI (ex.: ``"MGI-SGP-DECIPEX-CGBEN"``).
        orgao: (opcional) texto **exato** da opção do dropdown ``selOrgao``. Se
            ``None``, deriva da sigla (primeiro token) — mas o ``selOrgao`` costuma
            exibir o **nome** do órgão, não a sigla, então a derivação raramente
            casa (best-effort, não fatal). Passe ``orgao=`` explícito para envio
            **entre órgãos**, onde selecionar o órgão é necessário para o
            autocomplete achar a unidade.
        manter_aberto: se ``True``, marca "Manter processo aberto na unidade
            atual".
        timeout: espera máxima por elemento/iframe, em segundos.

    Raises:
        ValueError: se ``unidade_destino`` for vazia.
    """

    ICONE = "Enviar Processo"
    ID_ORGAO = "selOrgao"
    ID_UNIDADE = "txtUnidade"
    ID_LISTA_UNIDADES = "selUnidades"
    ID_MANTER_ABERTO = "chkSinManterAberto"
    ID_ENVIAR = "sbmEnviar"
    #: Espera do dropdown do autocomplete popular a sugestão.
    TIMEOUT_AUTOCOMPLETE = 8
    #: Espera curta do alerta de erro após Enviar.
    TIMEOUT_ALERTA = 2
    #: Fallbacks genéricos (o SEI varia os ids/classes com versão/tema).
    XPATH_MANTER_GENERICO = (
        '//input[@type="checkbox"]'
        '[contains(@id, "Manter") or contains(@id, "aberto")]'
    )
    XPATH_ENVIAR_GENERICO = (
        '//button[contains(normalize-space(.), "Enviar")]'
        ' | //input[@type="submit"][contains(@value, "Enviar")]'
    )

    def __init__(
        self,
        driver,
        unidade_destino: str,
        *,
        orgao: str | None = None,
        manter_aberto: bool = False,
        timeout: float = 10,
    ):
        if not unidade_destino or not unidade_destino.strip():
            raise ValueError("unidade_destino é obrigatória")
        self.driver = driver
        self.unidade_destino = unidade_destino.strip()
        self.orgao = orgao
        self.manter_aberto = manter_aberto
        self.timeout = timeout

    def enviar(self) -> None:
        """Envia o processo aberto para :attr:`unidade_destino`.

        Raises:
            EnviarProcessoError: se o ícone/formulário/campo não for encontrado, a
                unidade destino não puder ser selecionada (o autocomplete não a
                inseriu em ``selUnidades``), ou o SEI recusar o envio (alerta).
        """
        try:
            self._acionar_icone()
            self._ir_para_formulario()
            self._selecionar_orgao()
            self._preencher_unidade()
            if self.manter_aberto:
                self._marcar_manter_aberto()
            self._clicar_enviar()
            self._checar_alerta_erro()
        except EnviarProcessoError:
            self._voltar_default()
            raise
        except WebDriverException as exc:
            # Exceção crua do Selenium (stale/click interceptado/etc.) — honra o
            # contrato "Raises: EnviarProcessoError" e não deixa o driver preso.
            self._voltar_default()
            raise EnviarProcessoError(f"falha inesperada no envio: {exc}") from exc
        _log.info("Processo enviado para %r", self.unidade_destino)

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
            raise EnviarProcessoError(
                f"não foi possível acionar '{self.ICONE}': {exc}"
            ) from exc

    def _ir_para_formulario(self) -> None:
        """Posiciona no formulário de envio (campo ``txtUnidade`` acessível)."""
        self.driver.switch_to.default_content()
        try:
            switch_to_iframe_visualizacao(self.driver, timeout=self.timeout)
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_UNIDADE))
            )
            return
        except WebDriverException:
            pass
        # Fallback: o formulário pode estar no contexto principal.
        self.driver.switch_to.default_content()
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_UNIDADE))
            )
        except TimeoutException as exc:
            raise EnviarProcessoError(
                "o formulário de envio não carregou "
                f"(campo {self.ID_UNIDADE!r} ausente)"
            ) from exc

    def _selecionar_orgao(self) -> None:
        """Seleciona o órgão no ``selOrgao`` (best-effort — não fatal)."""
        orgao = self.orgao or self._orgao_da_sigla(self.unidade_destino)
        if not orgao:
            return
        try:
            Select(
                self.driver.find_element(By.ID, self.ID_ORGAO)
            ).select_by_visible_text(orgao)
            _log.debug("Órgão destino selecionado: %r", orgao)
        except (NoSuchElementException, UnexpectedTagNameException) as exc:
            # Sem o órgão certo o autocomplete ainda pode achar a unidade (envio
            # no mesmo órgão). Só avisa; o selUnidades confirma o acerto.
            _log.warning("não selecionei o órgão %r (best-effort): %s", orgao, exc)

    def _preencher_unidade(self) -> None:
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.ID, self.ID_UNIDADE))
            )
        except TimeoutException as exc:
            raise EnviarProcessoError(
                f"campo da unidade destino ({self.ID_UNIDADE}) não encontrado"
            ) from exc
        campo.clear()
        campo.send_keys(self.unidade_destino)
        # 1) tenta clicar a sugestão do autocomplete (best-effort, vários seletores).
        self._tentar_clicar_sugestao()
        if self._unidade_na_lista(min(self.timeout, 5)):
            return
        # 2) fallback robusto a versão/tema: TAB confirma a sugestão destacada.
        _log.debug("autocomplete não populou a lista; confirmando com TAB")
        campo.send_keys(Keys.TAB)
        if self._unidade_na_lista(min(self.timeout, 5)):
            return
        raise EnviarProcessoError(
            f"a unidade destino {self.unidade_destino!r} não entrou na lista de "
            "envio — o autocomplete não a selecionou (confira a sigla exata)"
        )

    def _tentar_clicar_sugestao(self) -> None:
        """Espera a sugestão EXATA no dropdown do autocomplete e clica nela;
        silencioso se não vier — o ``selUnidades`` é a prova final."""
        try:
            WebDriverWait(
                self.driver, min(self.TIMEOUT_AUTOCOMPLETE, self.timeout)
            ).until(
                EC.element_to_be_clickable((By.XPATH, self._xpath_sugestao()))
            ).click()
        except TimeoutException:
            _log.debug("sugestão do autocomplete não veio pelo seletor conhecido")

    def _xpath_sugestao(self) -> str:
        # Estrutura verificada ao vivo (SEI 4.1.5): o dropdown é
        # ``div.infraAjaxAutoCompletar > ul > li > a``; o texto do ``<a>`` é
        # "SIGLA - Descrição". Casar a SIGLA seguida de " - " pega a unidade
        # EXATA e não uma sub-unidade (cuja sigla continua com "-XXX", sem espaço).
        sep = f'"{self.unidade_destino} - "'
        return (
            '//div[contains(@class, "infraAjaxAutoCompletar")]'
            f"//a[contains(normalize-space(.), {sep})]"
        )

    def _unidade_na_lista(self, timeout: float) -> bool:
        """``True`` se a unidade destino **exata** aparece em ``selUnidades``
        (prova de que o autocomplete a selecionou)."""

        def _tem(driver) -> bool:
            try:
                lista = driver.find_element(By.ID, self.ID_LISTA_UNIDADES)
            except NoSuchElementException:
                return False
            return any(
                self._eh_a_unidade((o.text or "").strip())
                for o in lista.find_elements(By.TAG_NAME, "option")
            )

        try:
            return bool(WebDriverWait(self.driver, timeout).until(_tem))
        except TimeoutException:
            return False

    def _eh_a_unidade(self, texto: str) -> bool:
        """Casa a unidade destino EXATA (a sigla, ou "sigla " + descrição) e não
        uma sub-unidade cuja sigla é prefixada pela nossa (``CGPAG`` ⊂
        ``CGPAG-ANICAD``)."""
        return (
            texto == self.unidade_destino
            or texto.startswith(self.unidade_destino + " ")
        )

    def _marcar_manter_aberto(self) -> None:
        checkbox = self._primeiro_presente(
            (By.ID, self.ID_MANTER_ABERTO),
            (By.XPATH, self.XPATH_MANTER_GENERICO),
        )
        if checkbox is None:
            raise EnviarProcessoError(
                "não foi possível manter o processo aberto: checkbox "
                f"({self.ID_MANTER_ABERTO}) não encontrado"
            )
        if not checkbox.is_selected():
            # O input do SEI (infraCheckbox) fica coberto pelo <label>: clique via
            # JS para não ser interceptado pelo label.
            self.driver.execute_script("arguments[0].click();", checkbox)
            _log.debug("'Manter processo aberto na unidade atual' marcado")

    def _clicar_enviar(self) -> None:
        botao = self._primeiro_presente(
            (By.ID, self.ID_ENVIAR),
            (By.XPATH, self.XPATH_ENVIAR_GENERICO),
        )
        if botao is None:
            raise EnviarProcessoError(f"botão Enviar ({self.ID_ENVIAR}) não encontrado")
        # Clique via JS: o botão/label do SEI às vezes intercepta o click nativo.
        self.driver.execute_script("arguments[0].click();", botao)

    def _checar_alerta_erro(self) -> None:
        """Se o SEI mostrar um alerta após Enviar, é erro — aceita e levanta."""
        try:
            alerta = WebDriverWait(
                self.driver, min(self.TIMEOUT_ALERTA, self.timeout)
            ).until(EC.alert_is_present())
        except TimeoutException:
            # Sem alerta = envio aceito. Sinal positivo verificado ao vivo (SEI
            # 4.1.5): a visualização passa a "Processo aberto nas unidades:
            # <destino> …". Confirmar esse sinal programaticamente é endurecimento
            # futuro — exige fixar o frame da mensagem (como no concluir_processo).
            self.driver.switch_to.default_content()
            return
        texto = alerta.text
        alerta.accept()
        self.driver.switch_to.default_content()
        raise EnviarProcessoError(f"o SEI recusou o envio: {texto}")

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

    @staticmethod
    def _orgao_da_sigla(unidade: str) -> str | None:
        """Órgão = primeiro token da sigla (``"MGI-SGP-…"`` → ``"MGI"``); ``None``
        se não houver ``-``."""
        return unidade.split("-", 1)[0] if "-" in unidade else None
