"""Acesso a um processo existente no SEI via pesquisa rápida.

Abre um processo pelo número (campo "Pesquisar..." do topo do SEI) e oferece
navegação até a raiz da árvore de documentos. Requer uma sessão do SEI já
autenticada — o login não é feito por este módulo.
"""

from __future__ import annotations

import logging
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import ProcessoNaoEncontrado, SeiNavegacaoError
from .iframes import IframesSei

_log = logging.getLogger(__name__)


def _apenas_digitos(texto: str) -> str:
    """Retorna só os dígitos de ``texto`` (para comparar números tolerando
    formatação diferente: pontos, barra, hífen)."""
    return "".join(c for c in texto if c.isdigit())


class ProcessoSei:
    """Operações com um processo do SEI.

    Args:
        driver: instância do Selenium WebDriver, com o SEI já autenticado.
        numero_processo: número do processo (ex.: ``"00000.000000/0000-00"``).
            Opcional aqui — pode ser informado em :meth:`acessar`.
        timeout: tempo máximo de espera por elemento/iframe, em segundos.
    """

    XPATH_CAMPO_PESQUISA = '//*[@id="txtPesquisaRapida"]'
    CSS_NO_SELECIONADO = ".infraArvoreNoSelecionado"
    CSS_NO_VISITADO = ".noVisitado"
    CSS_NOS_ARVORE = f"{CSS_NO_SELECIONADO}, {CSS_NO_VISITADO}"
    # Pausa após digitar, antes do ENTER: a pesquisa rápida do SEI usa um
    # autocomplete via AJAX, e o ENTER imediato pode disparar antes de o valor
    # ser registrado (a busca então não navega).
    INTERVALO_AUTOCOMPLETE = 1.0

    def __init__(self, driver, numero_processo: str | None = None, timeout: float = 10):
        self.driver = driver
        self.numero_processo = numero_processo
        self.timeout = timeout

    @property
    def numero(self) -> str | None:
        """Número do processo atualmente associado a esta instância."""
        return self.numero_processo

    def acessar(self, numero_processo: str | None = None) -> str:
        """Abre o processo pelo número, via pesquisa rápida.

        Args:
            numero_processo: número a acessar; se omitido, usa o do construtor.

        Returns:
            O número do processo acessado.

        Raises:
            ValueError: se nenhum número for informado.
            SeiNavegacaoError: se o campo de pesquisa não for encontrado
                (sessão não autenticada? página inesperada?).
            ProcessoNaoEncontrado: se o processo não for aberto (não encontrado
                ou número divergente).
        """
        numero = numero_processo or self.numero_processo
        if not numero:
            raise ValueError("número do processo não informado")

        self.driver.switch_to.default_content()
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_CAMPO_PESQUISA))
            )
        except TimeoutException as exc:
            raise SeiNavegacaoError(
                "campo de pesquisa rápida não encontrado — a sessão do SEI "
                "está autenticada?"
            ) from exc

        campo.clear()
        campo.send_keys(numero)
        time.sleep(self.INTERVALO_AUTOCOMPLETE)  # deixa o autocomplete registrar
        campo.send_keys(Keys.ENTER)

        self._validar_acesso(numero)
        self.numero_processo = numero
        _log.info("Processo %s acessado", numero)
        return numero

    def ir_para_raiz(self) -> None:
        """Posiciona o driver na raiz da árvore de documentos do processo.

        Raises:
            SeiNavegacaoError: se a árvore ou o nó raiz não forem encontrados.
        """
        self.driver.switch_to.default_content()
        try:
            IframesSei(self.driver, IframesSei.ARVORE, self.timeout).navegar()
        except TimeoutException as exc:
            raise SeiNavegacaoError(
                "não foi possível acessar a árvore do processo (ifrArvore)"
            ) from exc

        try:
            no_raiz = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.CSS_NOS_ARVORE))
            )
        except TimeoutException as exc:
            raise SeiNavegacaoError("nó raiz da árvore não encontrado") from exc

        no_raiz.click()
        _log.info("Posicionado na raiz do processo")

    def _validar_acesso(self, numero: str) -> None:
        """Confirma que o processo foi aberto.

        Espera o título da aba refletir o número do processo (o SEI muda o
        ``<title>`` para ``"SEI - <numero>"`` ao abrir um processo). Substitui o
        antigo stub que sempre retornava ``True`` sem validar nada.
        """
        alvo = _apenas_digitos(numero)
        try:
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: alvo in _apenas_digitos(d.title or "")
            )
        except TimeoutException as exc:
            raise ProcessoNaoEncontrado(
                f"processo {numero} não foi acessado "
                "(não encontrado ou número divergente)"
            ) from exc
