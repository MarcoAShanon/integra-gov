"""Fechamento da tela de aviso do SEI.

O SEI quase sempre exibe uma tela de aviso logo após o login que, se não for
fechada, **bloqueia a interação com os demais campos**. Esta função fecha o(s)
aviso(s), se houver — é idempotente (não faz nada quando não há aviso).
"""

from __future__ import annotations

import logging

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

_log = logging.getLogger(__name__)

# Botão "Fechar" do aviso, nas várias formas que o SEI usa — combinados num
# único seletor CSS (evita esperar o timeout uma vez por estratégia).
_SELETOR_FECHAR = ", ".join((
    "img[title*='Fechar']",
    "img[alt*='Fechar']",
    "a.infraFechar img",
    "div.infraMensagemAlerta img",
))


def fechar_tela_aviso(driver, timeout: float = 3, max_avisos: int = 3) -> int:
    """Fecha a(s) tela(s) de aviso do SEI, se houver.

    Idempotente: retorna ``0`` se não houver aviso. Útil logo após o login,
    quando o SEI costuma exibir um aviso que bloqueia os demais campos.

    Args:
        driver: instância do Selenium WebDriver.
        timeout: espera por aviso, em segundos.
        max_avisos: máximo de avisos consecutivos a fechar.

    Returns:
        Quantidade de avisos fechados.
    """
    fechados = 0
    for _ in range(max_avisos):
        try:
            botao = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, _SELETOR_FECHAR))
            )
        except TimeoutException:
            break  # não há (mais) aviso
        if not _clicar(driver, botao):
            break
        fechados += 1
    if fechados:
        _log.info("Tela(s) de aviso do SEI fechada(s): %d", fechados)
    return fechados


def _clicar(driver, elemento) -> bool:
    """Clica no elemento; em caso de clique interceptado, tenta via JavaScript."""
    try:
        elemento.click()
        return True
    except WebDriverException:
        try:
            driver.execute_script("arguments[0].click();", elemento)
            return True
        except WebDriverException:
            return False
