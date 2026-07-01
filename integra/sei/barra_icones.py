"""Ícones da barra de ferramentas do documento no SEI (componente compartilhado).

Ao selecionar um nó na árvore do processo, o SEI mostra uma barra de ícones
(``Incluir Documento``, ``Editar Conteúdo``, ``Enviar Processo``, ``Assinar``…).
Acioná-los exige o mesmo preâmbulo de navegação toda vez: selecionar o nó na
árvore (``ifrArvore``), descer para o iframe de visualização e clicar no ``img``
cujo ``title`` casa com o ícone. Esta função encapsula esse preâmbulo para não
duplicá-lo em cada módulo de documento que o consome.

Verificado ao vivo no SEI 4.1.5: os ícones do documento moram em
``ifrConteudoVisualizacao`` — justamente onde :class:`IframesSei` posiciona no
destino ``VISUALIZACAO``. A descida para o ``ifrVisualizacao`` aninhado é apenas
um *fallback* defensivo (lá mora o conteúdo do documento, não os ícones).
"""

from __future__ import annotations

import logging

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import SeiNavegacaoError
from .iframes import IframesSei

_log = logging.getLogger(__name__)

# Nó atualmente selecionado na árvore (o processo, após ser acessado, fica
# selecionado). É nele que a barra de ícones opera.
CSS_NO_SELECIONADO = ".infraArvoreNoSelecionado"
# Iframe aninhado com o CONTEÚDO do documento; usado só no fallback abaixo.
NOME_IFRAME_CONTEUDO = "ifrVisualizacao"


def clicar_icone_barra(
    driver,
    titulo: str,
    *,
    timeout: float = 10,
    selecionar_no: bool = True,
) -> None:
    """Clica num ícone da barra de ferramentas do documento no SEI.

    Args:
        driver: WebDriver com o SEI autenticado e um processo aberto.
        titulo: texto **exato** do ``title`` do ícone, como no SEI (ex.:
            ``"Incluir Documento"``, ``"Editar Conteúdo"``).
        timeout: espera máxima por elemento/iframe, em segundos.
        selecionar_no: se ``True`` (padrão), seleciona o nó atual da árvore
            antes de procurar a barra. Passe ``False`` se o nó já estiver
            selecionado e você quiser evitar o clique extra.

    Raises:
        SeiNavegacaoError: se a árvore, o nó ou o ícone não forem encontrados.
    """
    if selecionar_no:
        _selecionar_no_arvore(driver, timeout)
    _ir_para_visualizacao(driver, timeout)
    _clicar_icone(driver, titulo, timeout)


def _selecionar_no_arvore(driver, timeout: float) -> None:
    driver.switch_to.default_content()
    try:
        IframesSei(driver, IframesSei.ARVORE, timeout).navegar()
    except TimeoutException as exc:
        raise SeiNavegacaoError(
            "não foi possível acessar a árvore do processo (ifrArvore)"
        ) from exc
    try:
        no = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, CSS_NO_SELECIONADO))
        )
    except TimeoutException as exc:
        raise SeiNavegacaoError(
            "nenhum nó selecionado na árvore — abra/selecione um processo antes"
        ) from exc
    no.click()
    _log.debug("Nó da árvore selecionado")


def _ir_para_visualizacao(driver, timeout: float) -> None:
    driver.switch_to.default_content()
    try:
        IframesSei(driver, IframesSei.VISUALIZACAO, timeout).navegar()
    except TimeoutException as exc:
        raise SeiNavegacaoError(
            "iframe de visualização (barra de ícones) não encontrado"
        ) from exc


def _clicar_icone(driver, titulo: str, timeout: float) -> None:
    xpath = f'//img[@title="{titulo}"]'
    # Caso normal: o ícone está no frame de visualização. Se não estiver, desce
    # uma camada até o conteúdo aninhado (fallback defensivo) e tenta de novo.
    if not driver.find_elements(By.XPATH, xpath):
        try:
            WebDriverWait(driver, timeout).until(
                EC.frame_to_be_available_and_switch_to_it(
                    (By.NAME, NOME_IFRAME_CONTEUDO)
                )
            )
        except TimeoutException:
            pass  # segue a tentativa direta abaixo; o erro real vem do until
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        ).click()
    except TimeoutException as exc:
        raise SeiNavegacaoError(
            f"ícone {titulo!r} não encontrado ou não clicável na barra"
        ) from exc
    _log.info("Ícone da barra acionado: %r", titulo)
