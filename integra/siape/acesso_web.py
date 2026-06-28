"""Início de acesso ao SIAPE pela web (portal SIAPENet) — certificado + OTP.

Abre o portal SIAPENet, aciona o **certificado digital** e **espera você
autenticar** (PIN no token físico ou push no celular — a biblioteca **não**
digita credencial), trata os popups, aciona o **menu SIAPE** (que dispara o
download do módulo HOD) e **captura o código OTP** exibido na página, que precisa
ser informado ao Terminal 3270 (tela ``COD. SEGURANCA``).

Esta camada é **só Selenium** (não usa pywinauto). Use com um driver criado por
:func:`integra.sei.criar_driver_chrome` ou o seu próprio::

    from integra.sei import criar_driver_chrome
    from integra.siape import AcessoSiapeWeb, ConexaoTerminal3270

    driver = criar_driver_chrome()
    otp = AcessoSiapeWeb(driver).executar()        # você autentica; devolve o OTP
    # ... abra o HOD (módulo de lançamento) ...
    ConexaoTerminal3270(codigo_seguranca=otp).conectar()
"""

from __future__ import annotations

import logging
import re
import time

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import AcessoSiapeError, TokenOtpError

_log = logging.getLogger(__name__)


class AcessoSiapeWeb:
    """Acesso web ao SIAPENet com certificado digital + captura do OTP.

    .. warning::
       Ao navegar, este módulo desativa a **verificação de certificado TLS** do
       navegador (via CDP) para tolerar telas self-signed do SIAPENet. Isso vale
       para toda a sessão do driver, não só o domínio do SIAPENet — use um driver
       dedicado a esta automação.

    Args:
        driver: WebDriver do Selenium (ex.: de ``criar_driver_chrome()``).
        base_url: URL do portal SIAPENet (nacional; parametrizável).
        timeout: espera por elemento, em segundos.
        timeout_autenticacao: espera máxima (s) pela sua autenticação no
            certificado (PIN/push). Padrão 180 s (3 min).
    """

    URL_PADRAO = "https://www1.siapenet.gov.br/orgao/Login.do?method=inicio"
    MARCADOR_POS_LOGIN = "PaginaInicial.do"

    XPATH_CERTIFICADO = '//*[@id="linkCD"]/img'
    XPATH_MENU_SIAPE = '//*[@id="menu"]/ul[3]/li[1]/a/span'
    XPATH_DETAILS = '//*[@id="details-button"]'
    XPATH_PROCEED = '//*[@id="proceed-link"]'
    ID_IFRAME_CONFIRMAR = "GB_frame"
    ID_BOTAO_CONFIRMAR = "btConfirmar"
    ID_TOKEN = "token"

    OTP_DIGITOS = 6
    TIMEOUT_POPUP = 2
    INTERVALO_AUTENTICACAO = 0.5

    def __init__(
        self,
        driver,
        base_url: str = URL_PADRAO,
        timeout: float = 10,
        timeout_autenticacao: float = 180,
    ):
        self.driver = driver
        self.base_url = base_url
        self.timeout = timeout
        self.timeout_autenticacao = timeout_autenticacao
        self.token_otp: str | None = None

    def executar(self) -> str:
        """Executa o acesso web completo e devolve o código OTP.

        Fluxo: navega → aciona o certificado → **espera você autenticar** →
        trata popups → aciona o menu SIAPE → captura o OTP.

        Returns:
            O código OTP (6 dígitos) a informar ao Terminal 3270.

        Raises:
            AcessoSiapeError: se a navegação, o certificado ou a autenticação
                falharem.
            TokenOtpError: se o OTP não puder ser capturado/validado.
        """
        self._navegar()
        self._clicar_certificado()
        self._aguardar_autenticacao()
        self._tratar_popup_confirmacao()
        self._clicar_menu_siape()
        self._tratar_aviso_certificado_chrome()
        self.token_otp = self._capturar_otp()
        _log.info("Acesso web ao SIAPE concluído; OTP capturado")
        return self.token_otp

    # ----- passos -----

    def _navegar(self) -> None:
        # ⚠️ Desativa a verificação de certificado TLS para ESTA sessão do driver
        # (telas self-signed do SIAPENet). Vale para todo o navegador, não só o
        # domínio do SIAPENet — ver nota na docstring da classe.
        try:
            self.driver.execute_cdp_cmd(
                "Security.setIgnoreCertificateErrors", {"ignore": True}
            )
        except WebDriverException:
            _log.debug("Não foi possível aplicar setIgnoreCertificateErrors")
        _log.info("Navegando para o SIAPENet: %s", self.base_url)
        try:
            self.driver.get(self.base_url)
        except WebDriverException as exc:
            raise AcessoSiapeError(
                f"falha ao navegar para {self.base_url}"
            ) from exc

    def _clicar_certificado(self) -> None:
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_CERTIFICADO))
            ).click()
        except TimeoutException as exc:
            raise AcessoSiapeError(
                "botão de certificado digital não encontrado no SIAPENet"
            ) from exc
        _log.info("Certificado digital acionado — aguardando autenticação")

    def _aguardar_autenticacao(self) -> None:
        """Espera você concluir a autenticação (PIN no token ou push no celular).

        Detecta o sucesso pela transição da URL para a página pós-login. A
        biblioteca não interage com o diálogo de certificado — isso é com você.
        """
        decorrido = 0.0
        while decorrido < self.timeout_autenticacao:
            try:
                if self.MARCADOR_POS_LOGIN in (self.driver.current_url or ""):
                    _log.info("Autenticação detectada (página pós-login)")
                    return
            except WebDriverException:
                pass  # leitura de URL falhou; segue aguardando
            time.sleep(self.INTERVALO_AUTENTICACAO)
            decorrido += self.INTERVALO_AUTENTICACAO
        raise AcessoSiapeError(
            f"autenticação não concluída em {self.timeout_autenticacao:.0f}s "
            f"(página '{self.MARCADOR_POS_LOGIN}' não detectada)"
        )

    def _tratar_popup_confirmacao(self) -> None:
        """Fecha o popup de confirmação (iframe), se aparecer (tolerante)."""
        try:
            WebDriverWait(self.driver, self.TIMEOUT_POPUP).until(
                EC.frame_to_be_available_and_switch_to_it(
                    (By.ID, self.ID_IFRAME_CONFIRMAR)
                )
            )
            WebDriverWait(self.driver, self.TIMEOUT_POPUP).until(
                EC.element_to_be_clickable((By.ID, self.ID_BOTAO_CONFIRMAR))
            ).click()
            _log.info("Popup de confirmação tratado")
        except TimeoutException:
            _log.debug("Popup de confirmação não apareceu")
        finally:
            self.driver.switch_to.default_content()

    def _clicar_menu_siape(self) -> None:
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_MENU_SIAPE))
            ).click()
        except TimeoutException as exc:
            raise AcessoSiapeError("menu SIAPE não encontrado após o login") from exc
        _log.info("Menu SIAPE acionado (dispara o download do módulo HOD)")

    def _tratar_aviso_certificado_chrome(self) -> None:
        """Passa pelo aviso de página não segura do Chrome, se aparecer."""
        try:
            WebDriverWait(self.driver, self.TIMEOUT_POPUP).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_DETAILS))
            ).click()
            WebDriverWait(self.driver, self.TIMEOUT_POPUP).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_PROCEED))
            ).click()
            _log.info("Aviso de certificado do Chrome tratado")
        except TimeoutException:
            _log.debug("Aviso de certificado do Chrome não apareceu")

    def _capturar_otp(self) -> str:
        try:
            elemento = WebDriverWait(self.driver, self.timeout).until(
                EC.visibility_of_element_located((By.ID, self.ID_TOKEN))
            )
        except TimeoutException as exc:
            raise TokenOtpError(
                "página do código OTP (#token) não carregou"
            ) from exc

        token = "".join((elemento.text or "").split())
        # ASCII estrito: ``isdigit()`` aceitaria dígitos unicode (sobrescritos,
        # algarismos árabes/devanágari) que o terminal 3270 não consegue digitar.
        if not re.fullmatch(r"[0-9]{%d}" % self.OTP_DIGITOS, token):
            raise TokenOtpError(
                f"código OTP inválido: esperados {self.OTP_DIGITOS} dígitos "
                f"ASCII, obtido {token!r}"
            )
        # Não loga nenhum dígito do OTP (código curto de uso único).
        _log.info("Código OTP capturado (%d dígitos)", self.OTP_DIGITOS)
        return token
