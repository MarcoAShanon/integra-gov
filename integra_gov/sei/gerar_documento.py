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

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .barra_icones import clicar_icone_barra
from .exceptions import SeiNavegacaoError
from .iframes import IframesSei

_log = logging.getLogger(__name__)

ICONE_INCLUIR = "Incluir Documento"
ID_FILTRO = "txtFiltro"
# SEI 4.0: a tela "Gerar Documento" cai no ifrVisualizacao ANINHADO (dentro do
# wrapper ifrConteudoVisualizacao), não no wrapper — descemos até ele.
NOME_IFRAME_CONTEUDO = "ifrVisualizacao"
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
# Orçamento total (s) para a tela aparecer na ÚLTIMA tentativa (o SEI às vezes
# demora) — a rede de segurança usa o budget cheio.
TIMEOUT_FORM = 12
# Orçamento (s) nas tentativas NÃO-finais: curto de propósito. Se a 1ª tentativa
# perder a corrida com o reload, caímos rápido na retentativa (que reclica o
# ícone SEM re-selecionar o nó, já na visualização estável), em vez de gastar os
# 12s à toa.
TIMEOUT_FORM_TENTATIVA = 4
# Pausa (s) após (re)selecionar o nó na 1ª tentativa, para o reload AJAX da
# visualização assentar antes do clique no ícone — evita que o clique seja
# "engolido" pelo reload (ícone pressionado sem navegar). Ver clicar_icone_barra.
SETTLE_APOS_NO = 1.2
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

    Na 1ª tentativa, :func:`clicar_icone_barra` **seleciona o nó** da árvore
    antes de clicar no ícone. Re-clicar um nó já selecionado dispara um reload
    AJAX da área de visualização; quando o chamador acabou de navegar (ex.:
    ``ir_para_raiz_processo`` antes de criar a Nota Técnica), esse reload ocorre
    logo antes do clique no ícone e o "engole" — o ícone fica pressionado e não
    navega. Por isso, nas **retentativas** NÃO re-selecionamos o nó
    (``selecionar_no=False``): a essa altura o nó já está selecionado e a
    visualização estável, então apenas reclicar o ícone navega de forma
    confiável. (Antes, a retentativa re-selecionava o nó e recriava a mesma
    corrida — a tela nunca chegava a abrir.)
    """
    ultimo_erro: SeiNavegacaoError | None = None
    for tentativa in range(1, TENTATIVAS_INCLUIR + 1):
        primeira = tentativa == 1
        # Numa RETENTATIVA, a tela pode já ter aberto (o clique anterior navegou,
        # porém devagar): o campo de filtro já existe e a barra de ícones não —
        # nesse caso NÃO reclicamos (o ícone não existe mais), só devolvemos o
        # campo. Não checamos na 1ª tentativa (ainda não clicamos nada).
        if not primeira:
            campo = _localizar_filtro(driver)
            if campo is not None:
                return campo
        clicar_icone_barra(
            driver,
            ICONE_INCLUIR,
            timeout=timeout,
            selecionar_no=primeira,
            # Só a 1ª tentativa re-seleciona o nó (e sofre a corrida com o
            # reload); damos a ela a pausa de estabilização.
            estabilizar_apos_no=SETTLE_APOS_NO if primeira else 0.0,
        )
        # Orçamento curto nas tentativas iniciais; cheio só na última.
        orcamento = (
            TIMEOUT_FORM
            if tentativa == TENTATIVAS_INCLUIR
            else TIMEOUT_FORM_TENTATIVA
        )
        try:
            return _abrir_formulario_e_esperar_filtro(driver, orcamento)
        except SeiNavegacaoError as exc:
            ultimo_erro = exc
            _log.warning(
                "Tela de inclusão não abriu (tentativa %d/%d); reclicando o "
                "ícone (sem re-selecionar o nó)",
                tentativa,
                TENTATIVAS_INCLUIR,
            )
    raise ultimo_erro


def _abrir_formulario_e_esperar_filtro(driver, timeout_form: float = TIMEOUT_FORM):
    """Espera a tela "Gerar Documento" carregar e devolve o campo de filtro.

    Clicar no ícone recarrega a área de visualização (AJAX) com a tela de
    seleção de tipo. Conforme a versão do SEI, o formulário cai em frames
    diferentes — direto no topo (SEI < 4.0), no wrapper de visualização, ou no
    ``ifrVisualizacao`` **aninhado** dentro do wrapper (SEI 4.0). Por isso o
    ``txtFiltro`` é procurado nos três a cada tentativa, até aparecer ou esgotar
    ``timeout_form`` (padrão :data:`TIMEOUT_FORM`).
    """
    deadline = time.monotonic() + timeout_form
    while True:
        campo = _localizar_filtro(driver)
        if campo is not None:
            return campo
        if time.monotonic() >= deadline:
            break
        time.sleep(INTERVALO_FORM)
    raise SeiNavegacaoError(
        "tela de inclusão de documento não carregou (campo de filtro ausente "
        "após 'Incluir Documento' — o ícone pode não ter navegado)"
    )


def _localizar_filtro(driver):
    """Procura o ``txtFiltro`` nos frames onde a tela pode carregar; devolve o
    elemento ou ``None`` (sem levantar — o chamador reitera até o deadline).

    Ordem: topo → wrapper de visualização → ``ifrVisualizacao`` aninhado.
    """
    # 1. Direto no topo (SEI < 4.0, ou formulário fora de iframe).
    try:
        driver.switch_to.default_content()
        achado = driver.find_elements(By.ID, ID_FILTRO)
        if achado:
            return achado[0]
    except WebDriverException:
        pass
    # 2. No wrapper de visualização (ifrConteudoVisualizacao no SEI 4.0).
    try:
        driver.switch_to.default_content()
        IframesSei(driver, IframesSei.VISUALIZACAO, timeout=2).navegar()
    except (TimeoutException, WebDriverException):
        return None
    achado = driver.find_elements(By.ID, ID_FILTRO)
    if achado:
        return achado[0]
    # 3. No ifrVisualizacao ANINHADO dentro do wrapper (SEI 4.0).
    try:
        driver.switch_to.frame(NOME_IFRAME_CONTEUDO)
    except WebDriverException:
        return None
    achado = driver.find_elements(By.ID, ID_FILTRO)
    return achado[0] if achado else None


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
