"""Nível de acesso de processos e documentos no SEI (componente compartilhado).

O widget de **nível de acesso** (Público / Restrito + hipótese legal) se repete
em várias telas do SEI — criação de processo, inclusão de documento, etc. Esta
função o configura de forma reutilizável, para não duplicar a lógica em cada
módulo que a consome.

Generalização (pacote serve a qualquer órgão): o nível é **parâmetro**
(``"publico"``/``"restrito"``) e, quando restrito, a **hipótese legal** também —
nada específico de órgão é embutido. Cada servidor informa o que vale na
realidade do seu SEI.
"""

from __future__ import annotations

import logging
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import NivelAcessoError

_log = logging.getLogger(__name__)

NIVEL_PUBLICO = "publico"
NIVEL_RESTRITO = "restrito"
NIVEIS = (NIVEL_PUBLICO, NIVEL_RESTRITO)

# Seletores do widget de nível de acesso (iguais em processo e documento).
XPATH_OPT_PUBLICO = '//*[@id="divOptPublico"]/div/label'
XPATH_OPT_RESTRITO = '//*[@id="divOptRestrito"]/div/label'
ID_HIPOTESE_LEGAL = "selHipoteseLegal"

# O dropdown de hipótese legal é populado via AJAX após marcar "restrito"; as
# opções podem demorar a chegar. Reconsulta o <select> até esgotar o timeout.
INTERVALO_HIPOTESE = 0.5


def _normalizar(texto: str) -> str:
    """Colapsa espaços (inclui NBSP) para comparar textos tolerando diferenças
    de espaçamento entre o valor informado e a opção do dropdown."""
    return " ".join((texto or "").replace("\xa0", " ").split())


def validar_nivel_acesso(nivel: str, hipotese_legal: str | None) -> str:
    """Valida e normaliza o nível de acesso (use no ``__init__`` de quem consome).

    Args:
        nivel: ``"publico"`` ou ``"restrito"`` (case-insensitive).
        hipotese_legal: texto da hipótese legal — obrigatório quando restrito.

    Returns:
        O nível normalizado em minúsculas.

    Raises:
        ValueError: nível não-string ou inválido, ou restrito sem hipótese legal
            (incluindo hipótese só com espaços).
    """
    if not isinstance(nivel, str):
        raise ValueError("nivel_acesso deve ser uma string")
    nivel = nivel.lower()
    if nivel not in NIVEIS:
        raise ValueError(
            f"nivel_acesso inválido: {nivel!r} "
            f"(use {NIVEL_PUBLICO!r} ou {NIVEL_RESTRITO!r})"
        )
    # Hipótese só com espaços é tão inválida quanto vazia — rejeita cedo
    # (senão falharia tarde no dropdown como NivelAcessoError).
    if isinstance(hipotese_legal, str):
        hipotese_legal = hipotese_legal.strip()
    if nivel == NIVEL_RESTRITO and not hipotese_legal:
        raise ValueError(
            "hipotese_legal é obrigatória quando nivel_acesso='restrito'"
        )
    return nivel


def configurar_nivel_acesso(
    driver,
    nivel: str = NIVEL_PUBLICO,
    *,
    hipotese_legal: str | None = None,
    timeout: float = 10,
) -> None:
    """Marca o nível de acesso na tela atual do SEI (processo ou documento).

    O SEI **exige** uma escolha explícita de nível; por isso o radio é sempre
    marcado (inclusive ``"publico"``).

    Args:
        driver: WebDriver na tela que contém o widget de nível de acesso.
        nivel: ``"publico"`` (padrão) ou ``"restrito"``.
        hipotese_legal: texto **exato** da hipótese legal no dropdown;
            obrigatório quando ``nivel="restrito"``.
        timeout: espera máxima por elemento, em segundos.

    Raises:
        ValueError: nível inválido ou restrito sem hipótese legal.
        NivelAcessoError: se o radio/dropdown não for encontrado, ou a hipótese
            legal não estiver no dropdown.
    """
    nivel = validar_nivel_acesso(nivel, hipotese_legal)
    if nivel == NIVEL_PUBLICO:
        _marcar_radio(driver, XPATH_OPT_PUBLICO, "público", timeout)
        return
    _marcar_radio(driver, XPATH_OPT_RESTRITO, "restrito", timeout)
    _selecionar_hipotese_legal(driver, hipotese_legal, timeout)


def _marcar_radio(driver, xpath: str, nome: str, timeout: float) -> None:
    # Espera o rótulo ficar clicável (pode renderizar com atraso), em vez de um
    # find_element direto que viraria erro num timing transitório.
    try:
        label = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
    except TimeoutException as exc:
        raise NivelAcessoError(
            f"opção de nível de acesso {nome!r} não encontrada"
        ) from exc
    label.click()
    _log.info("Nível de acesso: %s", nome)


def _selecionar_hipotese_legal(
    driver, hipotese_legal: str, timeout: float
) -> None:
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, ID_HIPOTESE_LEGAL))
        )
    except TimeoutException as exc:
        raise NivelAcessoError(
            "dropdown de hipótese legal não encontrado"
        ) from exc

    # A presença do <select> não garante que as <option> (AJAX) já chegaram, e
    # o SEI pode re-renderizá-lo ao popular. Reconsulta o elemento a cada
    # tentativa, até esgotar o `timeout`.
    deadline = time.monotonic() + timeout
    ultimo_erro: Exception | None = None
    opcoes: list[str] = []
    while True:
        try:
            select = Select(driver.find_element(By.ID, ID_HIPOTESE_LEGAL))
            opcoes = [o.text for o in select.options]
            if _tentar_selecionar(select, hipotese_legal, opcoes):
                _log.info("Hipótese legal: %r", hipotese_legal)
                return
        except (NoSuchElementException, StaleElementReferenceException) as exc:
            ultimo_erro = exc  # elemento sumiu/re-renderizou; tenta de novo
        if time.monotonic() >= deadline:
            break
        time.sleep(INTERVALO_HIPOTESE)

    disponiveis = [o.strip() for o in opcoes if o and o.strip()]
    dica = (
        "; opções disponíveis: " + ", ".join(repr(o) for o in disponiveis)
        if disponiveis
        else " (dropdown ainda vazio — pode não ter carregado)"
    )
    raise NivelAcessoError(
        f"hipótese legal {hipotese_legal!r} não encontrada no dropdown{dica}"
    ) from ultimo_erro


def _tentar_selecionar(select: Select, alvo: str, opcoes: list[str]) -> bool:
    """Seleciona a opção de texto ``alvo``, tolerando diferenças de espaçamento.

    Tenta o casamento exato do Selenium; se falhar, compara normalizando espaços
    (inclui NBSP), o que cobre opções do SEI com espaços/entidades diferentes do
    valor informado. Retorna ``True`` se selecionou, ``False`` caso a opção ainda
    não esteja presente (deixa o chamador tentar de novo enquanto há tempo).
    """
    try:
        select.select_by_visible_text(alvo)
        return True
    except NoSuchElementException:
        pass
    alvo_norm = _normalizar(alvo)
    for i, texto in enumerate(opcoes):
        if _normalizar(texto) == alvo_norm:
            select.select_by_index(i)
            return True
    return False
