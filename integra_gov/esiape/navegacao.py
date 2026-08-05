"""Navegação nas telas CIS do e-SIAPE (frames, popups, relogin, transações).

Mecânicas validadas ao vivo (03-04/08/2026):
- os iframes WA0/WA1/WA2 se REVEZAM e o CIS mantém as telas anteriores vivas
  nos ocultos — só o frame VISÍVEL é a tela atual;
- popups modais (ex.: aviso "UORG DO CORREIO...") fecham pelo X da barra de
  título, que fica no documento do TOPO — esconder via CSS não libera;
- a tela de relogin do SERPRO (AVANÇAR) significa sessão nova: a habilitação
  volta ao padrão do usuário e fica PENDENTE de re-troca (flag no driver).
"""

from __future__ import annotations

import logging
import time

from selenium.webdriver.common.by import By

_log = logging.getLogger(__name__)

SELETOR_LUPA = '[data-testtoolid="onMenuClickPesqTrans"]'
SELETOR_CAMPO_TRANSACAO = '[data-testtoolid="w_transacao"]'
SELETOR_BTN_IR = '[data-testtoolid="onMenuClickBtnIr"]'
SELETOR_HOME = '[data-testtoolid="onMenuClickHome"]'
SELETOR_OVERLAY = "#OPA, .FLASHPageSwitch"
SELETOR_BTN_AVANCAR = '[data-testtoolid="meucert.onCheck"]'
SELETOR_BTN_PULAR = '[data-testtoolid="onClickBtnPular"]'
SELETOR_POPUP_FECHAR = "td[id^='TITLEBAR'][id$='CLOSE']"

_PROFUNDIDADE_MAXIMA = 4


def frames_visiveis(driver, caminho=(), saida=None, prof=0):
    """Caminhos (tuplas de nomes) de todos os frames VISÍVEIS, em profundidade.

    Frames ocultos guardam telas ANTIGAS com dados velhos — são ignorados.
    """
    saida = saida if saida is not None else []
    saida.append(caminho)
    if prof > _PROFUNDIDADE_MAXIMA:
        return saida
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
    except Exception:
        return saida
    for i, frame in enumerate(iframes):
        try:
            if not frame.is_displayed():
                continue
            nome = (frame.get_attribute("name")
                    or frame.get_attribute("id") or f"idx{i}")
            driver.switch_to.frame(frame)
            frames_visiveis(driver, caminho + (nome,), saida, prof + 1)
            driver.switch_to.parent_frame()
        except Exception:
            try:
                driver.switch_to.parent_frame()
            except Exception:
                pass
    return saida


def ir_para_frame(driver, caminho) -> bool:
    """Posiciona o driver no frame do ``caminho``; ``False`` se ele sumiu."""
    driver.switch_to.default_content()
    for nome in caminho:
        try:
            driver.switch_to.frame(nome)
        except Exception:
            achou = False
            for el in driver.find_elements(By.TAG_NAME, "iframe"):
                if (el.get_attribute("name") or el.get_attribute("id")) == nome:
                    driver.switch_to.frame(el)
                    achou = True
                    break
            if not achou:
                return False
    return True


def procurar_em_frames(driver, seletor_css: str):
    """1º frame VISÍVEL contendo o seletor (deixa o driver NELE) ou ``None``.

    Sempre re-enumera do topo: uma busca anterior deixa o driver dentro de um
    frame, e enumerar dali produziria caminhos relativos inválidos.
    """
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    for caminho in frames_visiveis(driver):
        if not ir_para_frame(driver, caminho):
            continue
        try:
            if driver.find_elements(By.CSS_SELECTOR, seletor_css):
                return caminho
        except Exception:
            continue
    return None


def esperar_seletor(driver, seletor_css: str, timeout: float = 20,
                    intervalo: float = 0.5):
    """Espera o seletor aparecer em algum frame visível; caminho ou ``None``."""
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        caminho = procurar_em_frames(driver, seletor_css)
        if caminho is not None:
            return caminho
        time.sleep(intervalo)
    return None
