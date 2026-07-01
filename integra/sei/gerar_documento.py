"""Tela "Gerar Documento" do SEI (componente compartilhado).

Clicar no ícone **"Incluir Documento"** leva à tela **Gerar Documento**
("Escolha o Tipo do Documento"), comum à inclusão de documento **externo**
(upload) e de documentos **internos** (Despacho, Nota Técnica, …). Este
componente encapsula esse preâmbulo — aciona o ícone, espera a tela carregar e
seleciona o tipo pelo **texto exato** — para não duplicá-lo em cada módulo.

Robustezes verificadas ao vivo no SEI 4.1.5 (extraídas do
``inserir_documento_externo``, sem mudança de comportamento):

  - a tela carrega via AJAX e a troca de conteúdo pode deixar o contexto do
    driver obsoleto → **reentra no iframe** de visualização até o campo de
    filtro aparecer;
  - o clique no ícone às vezes não "pega" (fica pressionado e não navega) →
    **reclica o ícone** e tenta abrir a tela de novo.
"""

from __future__ import annotations

import logging
import time

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .barra_icones import clicar_icone_barra
from .exceptions import SeiNavegacaoError
from .iframes import IframesSei

_log = logging.getLogger(__name__)

ICONE_INCLUIR = "Incluir Documento"
ID_FILTRO = "txtFiltro"
# Na lista "Escolha o Tipo do Documento", cada tipo é um link; clica-se o de
# texto EXATO (dentro de tblSeries; com fallback fora dele — o container pode
# variar por versão). Mais robusto que a posição da linha, que muda conforme o
# filtro/favoritos.
XPATH_TIPO = '//*[@id="tblSeries"]//a[normalize-space()="{tipo}"]'
XPATH_TIPO_FALLBACK = '//a[normalize-space()="{tipo}"]'
XPATH_TIPOS_VISIVEIS = '//*[@id="tblSeries"]//a'

# A lista de tipos filtra via AJAX ao digitar; espera curta antes de clicar.
INTERVALO_FILTRO = 1.0
# A tela "Gerar Documento" carrega via AJAX após o clique no ícone; intervalo
# entre tentativas de reentrar no iframe e localizar o campo de filtro.
INTERVALO_FORM = 0.5
# Orçamento total (s) para a tela aparecer (o SEI às vezes demora).
TIMEOUT_FORM = 12
# O clique no ícone às vezes não "pega" (fica pressionado e não navega); nesse
# caso reclica-se o ícone e tenta-se abrir a tela de novo.
TENTATIVAS_INCLUIR = 2


def abrir_gerar_documento(driver, tipo: str, *, timeout: float = 10) -> None:
    """Abre a tela "Gerar Documento" e seleciona o ``tipo`` pelo texto exato.

    Ao retornar, o driver está no iframe de visualização, com o formulário do
    tipo escolhido carregando — quem chama segue preenchendo os campos.

    Args:
        driver: WebDriver com o SEI autenticado e um **processo aberto**.
        tipo: texto **exato** do tipo na lista (ex.: ``"Externo"``,
            ``"Despacho"``, ``"Nota Técnica"``).
        timeout: espera máxima por elemento/iframe, em segundos.

    Raises:
        SeiNavegacaoError: se a tela não carregar ou o ``tipo`` não aparecer na
            lista (a mensagem inclui os tipos visíveis, quando houver).
    """
    filtro = _incluir_documento_e_abrir_form(driver, timeout)
    _selecionar_tipo(driver, filtro, tipo, timeout)


def _incluir_documento_e_abrir_form(driver, timeout: float):
    """Clica em "Incluir Documento" e devolve o campo de filtro da tela.

    Reclica o ícone se a tela não abrir na 1ª vez (o clique nem sempre navega —
    o ícone pode ficar "pressionado" sem efeito).
    """
    ultimo_erro: SeiNavegacaoError | None = None
    for tentativa in range(1, TENTATIVAS_INCLUIR + 1):
        clicar_icone_barra(driver, ICONE_INCLUIR, timeout=timeout)
        try:
            return _abrir_formulario_e_esperar_filtro(driver)
        except SeiNavegacaoError as exc:
            ultimo_erro = exc
            _log.warning(
                "Tela de inclusão não abriu (tentativa %d/%d); reclicando o "
                "ícone",
                tentativa,
                TENTATIVAS_INCLUIR,
            )
    raise ultimo_erro


def _abrir_formulario_e_esperar_filtro(driver):
    """Espera a tela "Gerar Documento" carregar e devolve o campo de filtro.

    Clicar no ícone recarrega o iframe de visualização (AJAX) com a tela de
    seleção de tipo. A troca de conteúdo pode deixar o contexto do driver
    obsoleto, então **reentra no iframe** e procura o ``txtFiltro`` a cada
    tentativa, até o campo aparecer ou esgotar :data:`TIMEOUT_FORM`.
    """
    deadline = time.monotonic() + TIMEOUT_FORM
    ultimo_erro: Exception | None = None
    while True:
        try:
            driver.switch_to.default_content()
            IframesSei(driver, IframesSei.VISUALIZACAO, timeout=3).navegar()
            return WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.ID, ID_FILTRO))
            )
        except (TimeoutException, StaleElementReferenceException) as exc:
            ultimo_erro = exc  # iframe ainda não trocou / contexto obsoleto
        if time.monotonic() >= deadline:
            break
        time.sleep(INTERVALO_FORM)
    raise SeiNavegacaoError(
        "tela de inclusão de documento não carregou (campo de filtro ausente "
        "após 'Incluir Documento' — o ícone pode não ter navegado)"
    ) from ultimo_erro


def _selecionar_tipo(driver, filtro, tipo: str, timeout: float) -> None:
    filtro.clear()
    filtro.send_keys(tipo)
    time.sleep(INTERVALO_FILTRO)  # deixa a lista filtrar (AJAX)
    # Tenta o link do tipo dentro da tabela de tipos e, se não achar (o
    # container pode variar por versão), o mesmo link em qualquer lugar.
    for xpath in (
        XPATH_TIPO.format(tipo=tipo),
        XPATH_TIPO_FALLBACK.format(tipo=tipo),
    ):
        try:
            WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            ).click()
            _log.info("Tipo de documento selecionado: %r", tipo)
            return
        except TimeoutException:
            continue
    raise SeiNavegacaoError(
        f"tipo de documento {tipo!r} não apareceu na lista após o filtro"
        f"{_dica_tipos_visiveis(driver)}"
    )


def _dica_tipos_visiveis(driver, limite: int = 15) -> str:
    """Lista os tipos visíveis na tela para a mensagem de erro (diagnóstico:
    diferencia texto divergente de lista vazia/não carregada)."""
    try:
        tipos = [
            a.text.strip()
            for a in driver.find_elements(By.XPATH, XPATH_TIPOS_VISIVEIS)
            if (a.text or "").strip()
        ]
    except WebDriverException:
        return ""
    if not tipos:
        return " (nenhum tipo visível — a lista pode não ter carregado)"
    return "; tipos visíveis: " + ", ".join(repr(t) for t in tipos[:limite])
