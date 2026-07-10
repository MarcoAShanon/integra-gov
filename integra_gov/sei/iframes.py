"""Navegação entre os iframes do SEI (Sistema Eletrônico de Informações).

O SEI organiza a tela em iframes aninhados, e a estrutura mudou na versão 4.0:
o conteúdo de visualização passou a ficar dentro de um wrapper novo
(``ifrConteudoVisualizacao``). O SEI 4.0 **não renomeou** o iframe antigo —
apenas o envolveu. Estrutura real, verificada ao vivo no SEI 4.1.5::

    top
    ├── ifrArvore                 (árvore de documentos + ícones do processo)
    └── ifrConteudoVisualizacao   (wrapper; barra de ícones do documento)
        └── ifrVisualizacao       (conteúdo do documento: tabelas, parágrafos)

Em SEI < 4.0 não há o wrapper: ``ifrVisualizacao`` fica direto sob ``top``.

API:
    - :func:`switch_to_iframe_visualizacao` — posiciona o driver no iframe de
      visualização, tolerando ambas as versões (desce UMA camada, até o wrapper
      no SEI 4.0).
    - :class:`IframesSei` — navegação por destinos nomeados, com retry para
      falhas transitórias.
"""

from __future__ import annotations

import functools
import logging
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    NoSuchFrameException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

_log = logging.getLogger(__name__)

#: Nomes do iframe principal de visualização, em ordem de tentativa.
#: SEI 4.0+: ``ifrConteudoVisualizacao``; SEI < 4.0: ``ifrVisualizacao``.
NOMES_IFRAME_VISUALIZACAO = ("ifrConteudoVisualizacao", "ifrVisualizacao")

#: Iframe de CONTEÚDO do documento (tabelas, andamento, ``ifrArvoreHtml``). No
#: SEI 4.0 fica ANINHADO dentro do wrapper ``ifrConteudoVisualizacao``.
NOME_IFRAME_CONTEUDO = "ifrVisualizacao"

# Exceções que o ChromeDriver pode lançar ao trocar de iframe — captura ampla
# porque a mensagem costuma vir vazia em algumas dessas situações.
_EXCECOES_IFRAME = (
    TimeoutException,
    NoSuchFrameException,
    StaleElementReferenceException,
    WebDriverException,
)


def switch_to_iframe_visualizacao(driver, timeout: float = 10) -> str:
    """Posiciona o driver no iframe de visualização do SEI.

    Tolera a mudança estrutural do SEI 4.0: tenta ``ifrConteudoVisualizacao``
    (o wrapper novo) e, se não existir, cai para ``ifrVisualizacao`` (SEI < 4.0).
    Desce **apenas uma camada** e termina no wrapper — quem precisa do CONTEÚDO
    do documento (tabelas, parágrafos, andamento) deve descer mais uma camada,
    até o ``ifrVisualizacao`` aninhado.

    Antes de cada tentativa força ``default_content()`` para partir de um ponto
    limpo.

    Args:
        driver: instância do Selenium WebDriver.
        timeout: tempo máximo de espera por candidato, em segundos.

    Returns:
        O nome do iframe em que o driver ficou posicionado.

    Raises:
        TimeoutException: se nenhum dos candidatos for encontrado.
    """
    erros = []
    for nome in NOMES_IFRAME_VISUALIZACAO:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass  # reset defensivo; um erro aqui não é relevante
        try:
            WebDriverWait(driver, timeout).until(
                EC.frame_to_be_available_and_switch_to_it((By.NAME, nome))
            )
            _log.debug("Switch para iframe '%s' OK", nome)
            return nome
        except _EXCECOES_IFRAME as exc:
            erros.append(f"{nome}={type(exc).__name__}")
            _log.debug("iframe '%s' indisponível: %s", nome, type(exc).__name__)
    raise TimeoutException(
        "Nenhum iframe de visualização encontrado. Tentativas: " + "; ".join(erros)
    )


def descer_para_conteudo_documento(driver, timeout: float = 10) -> None:
    """Desce até o iframe que contém o **conteúdo** do documento.

    :func:`switch_to_iframe_visualizacao` para no wrapper de visualização; no SEI
    4.0 o conteúdo do documento (o HTML renderizado e o ``ifrArvoreHtml``, cujo
    ``src`` é a URL de download de um anexo) fica no ``ifrVisualizacao``
    **aninhado** dentro do wrapper ``ifrConteudoVisualizacao``. Este helper entra
    nessa camada extra. Em SEI < 4.0 (sem wrapper) já estamos no
    ``ifrVisualizacao`` e não há o que descer — o iframe aninhado não existe e a
    operação é um **no-op**.

    Pré-condição: o driver já deve estar posicionado no iframe de visualização
    (via :func:`switch_to_iframe_visualizacao`).

    Args:
        driver: instância do Selenium WebDriver.
        timeout: mantido por simetria da API; a busca do frame aninhado é
            imediata (não espera).
    """
    try:
        aninhado = driver.find_element(By.NAME, NOME_IFRAME_CONTEUDO)
    except NoSuchElementException:
        return  # SEI < 4.0: já estamos no ifrVisualizacao
    driver.switch_to.frame(aninhado)


def _retry_iframe(max_tentativas: int = 3, intervalo: float = 1.0):
    """Repete uma operação de navegação em falhas transitórias.

    Reposiciona em ``default_content()`` antes de cada nova tentativa. **Não**
    usa ``driver.refresh()`` — recarregar a página costuma piorar o estado do
    SEI em vez de recuperá-lo.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            ultima_exc = None
            for tentativa in range(1, max_tentativas + 1):
                try:
                    return func(self, *args, **kwargs)
                except (TimeoutException, StaleElementReferenceException) as exc:
                    ultima_exc = exc
                    _log.debug(
                        "Tentativa %d/%d de navegação falhou: %s",
                        tentativa,
                        max_tentativas,
                        type(exc).__name__,
                    )
                    try:
                        self.driver.switch_to.default_content()
                    except Exception:
                        pass
                    if tentativa < max_tentativas:
                        time.sleep(intervalo)
            raise ultima_exc

        return wrapper

    return decorator


class IframesSei:
    """Navegação entre os iframes do SEI por destino nomeado.

    Args:
        driver: instância do Selenium WebDriver.
        destino: um de :attr:`ARVORE`, :attr:`VISUALIZACAO` ou
            :attr:`DOCUMENTO_HTML`.
        timeout: tempo máximo de espera por iframe, em segundos.
    """

    #: Árvore de documentos do processo (``ifrArvore``).
    ARVORE = "arvore"
    #: Iframe de visualização (wrapper no SEI 4.0; ver
    #: :func:`switch_to_iframe_visualizacao`).
    VISUALIZACAO = "visualizacao"
    #: Conteúdo HTML de um documento interno (``ifrArvoreHtml``, aninhado na
    #: visualização). Presente apenas para certos tipos de documento.
    DOCUMENTO_HTML = "documento_html"

    def __init__(self, driver, destino: str, timeout: float = 10):
        self.driver = driver
        self.destino = destino
        self.timeout = timeout

    @_retry_iframe()
    def navegar(self) -> bool:
        """Posiciona o driver no iframe de destino.

        Returns:
            ``True`` em caso de sucesso.

        Raises:
            ValueError: se ``destino`` for desconhecido.
            TimeoutException: se o iframe não ficar disponível a tempo.
        """
        if self.destino == self.ARVORE:
            self.driver.switch_to.default_content()
            WebDriverWait(self.driver, self.timeout).until(
                EC.frame_to_be_available_and_switch_to_it((By.NAME, "ifrArvore"))
            )
            return True

        if self.destino == self.VISUALIZACAO:
            self.driver.switch_to.default_content()
            switch_to_iframe_visualizacao(self.driver, self.timeout)
            return True

        if self.destino == self.DOCUMENTO_HTML:
            self.driver.switch_to.default_content()
            switch_to_iframe_visualizacao(self.driver, self.timeout)
            descer_para_conteudo_documento(self.driver, self.timeout)
            WebDriverWait(self.driver, self.timeout).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, "ifrArvoreHtml"))
            )
            return True

        raise ValueError(f"destino de iframe desconhecido: {self.destino!r}")
