"""Autenticação no SEI pela página de login do SIP (``login_especial``).

A URL base da instância e a sigla do órgão **variam por órgão**, por isso são
parâmetros — não constantes embutidas. Assim a biblioteca serve a qualquer
órgão, não só a um.

Segurança da senha:
  - forneça-a de forma segura (``getpass``, variável de ambiente, cofre de
    segredos); **nunca** a escreva no código nem a versione;
  - este módulo não a registra em log nem a persiste.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import CredenciaisInvalidas, SeiLoginError

_log = logging.getLogger(__name__)

_XPATH_PAGINA_INICIAL = "//img[@title='Controle de Processos']"
_XPATH_ERRO = (
    "//div[@id='divInfraBarraLocalizacao' and contains(text(), 'Erro')]"
)


def montar_url_login(base_url: str, orgao: str) -> str:
    """Monta a URL padrão de login do SEI (módulo SIP ``login_especial``).

    Args:
        base_url: URL base da instância (ex.: ``"https://sei.exemplo.gov.br"``).
        orgao: sigla do órgão (ex.: ``"MGI"``).
    """
    base = base_url.rstrip("/")
    return (
        f"{base}/sip/modulos/MF/login_especial/login_especial.php"
        f"?sigla_orgao_sistema={quote(orgao)}&sigla_sistema=SEI"
    )


class LoginSei:
    """Login no SEI.

    Args:
        driver: instância do Selenium WebDriver.
        base_url: URL base da instância do SEI
            (ex.: ``"https://sei.exemplo.gov.br"``).
        orgao: sigla do seu órgão (ex.: ``"MGI"``).
        usuario: nome de usuário.
        senha: senha (obtenha de forma segura; nunca versione).
        timeout: tempo máximo de espera por elemento, em segundos.
        url_login: opcional — sobrescreve a URL de login, para instâncias cuja
            página de login fuja do padrão ``login_especial``.
    """

    TXT_USUARIO = "txtUsuario"
    PWD_SENHA = "pwdSenha"
    SEL_ORGAO = "selOrgao"
    BTN_ACESSAR = "Acessar"
    TIMEOUT_ALERTA = 2

    def __init__(
        self,
        driver,
        base_url: str,
        orgao: str,
        usuario: str,
        senha: str,
        timeout: float = 10,
        url_login: str | None = None,
    ):
        self.driver = driver
        self.orgao = orgao
        self.usuario = usuario
        self._senha = senha
        self.timeout = timeout
        self.url_login = url_login or montar_url_login(base_url, orgao)

    def logar(self) -> None:
        """Faz login no SEI.

        Raises:
            CredenciaisInvalidas: se o SEI rejeitar usuário/senha.
            SeiLoginError: se o formulário não carregar ou o login não puder
                ser confirmado.
        """
        _log.info("Acessando a página de login do SEI")
        self.driver.get(self.url_login)
        self._preencher_formulario()
        self._confirmar_login()

    def _preencher_formulario(self) -> None:
        wait = WebDriverWait(self.driver, self.timeout)
        try:
            wait.until(
                EC.element_to_be_clickable((By.ID, self.TXT_USUARIO))
            ).send_keys(self.usuario)
            wait.until(
                EC.element_to_be_clickable((By.ID, self.PWD_SENHA))
            ).send_keys(self._senha)
        except TimeoutException as exc:
            raise SeiLoginError(
                "formulário de login não carregou — confira a URL/instância do SEI"
            ) from exc

        # Seleção de órgão: presente no login_especial padrão; tolerante a
        # instâncias que não exibem esse campo.
        try:
            WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable((By.ID, self.SEL_ORGAO))
            ).send_keys(self.orgao)
        except TimeoutException:
            _log.debug("Campo de órgão '%s' ausente; prosseguindo", self.SEL_ORGAO)

        try:
            wait.until(
                EC.element_to_be_clickable((By.ID, self.BTN_ACESSAR))
            ).click()
        except TimeoutException as exc:
            raise SeiLoginError("botão de acesso não encontrado") from exc

    def _confirmar_login(self) -> None:
        # Credenciais inválidas no SEI disparam um alerta JavaScript.
        try:
            alerta = WebDriverWait(self.driver, self.TIMEOUT_ALERTA).until(
                EC.alert_is_present()
            )
            alerta.accept()
            raise CredenciaisInvalidas("usuário ou senha inválidos")
        except TimeoutException:
            pass  # sem alerta → segue para confirmar o sucesso

        if not self._pagina_inicial_carregou():
            raise SeiLoginError(
                "login não confirmado (página inicial do SEI não detectada)"
            )
        _log.info("Login no SEI realizado com sucesso")

    def _pagina_inicial_carregou(self) -> bool:
        """True se a página inicial do SEI (Controle de Processos) carregou."""
        if self.driver.find_elements(By.XPATH, _XPATH_ERRO):
            return False
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.XPATH, _XPATH_PAGINA_INICIAL))
            )
            return True
        except TimeoutException:
            return False
