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


def overlay_presente(driver) -> bool:
    """True se a cortina de transição do CIS está visível no topo."""
    try:
        driver.switch_to.default_content()
        return bool(driver.execute_script(
            """
            return [...document.querySelectorAll(arguments[0])].some(e => {
                const s = getComputedStyle(e);
                return s.display !== 'none' && s.visibility !== 'hidden' &&
                       e.offsetWidth > 0 && e.offsetHeight > 0;
            });
            """,
            SELETOR_OVERLAY,
        ))
    except Exception:
        return False


def limpar_overlay(driver, timeout: float = 10) -> bool:
    """Espera a cortina do CIS sumir; se ficar presa, esconde via JS.

    A cortina presa intercepta TODO clique ("element click intercepted") e
    derruba o lote inteiro; escondê-la é seguro — é decorativa.
    """
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if not overlay_presente(driver):
            return True
        time.sleep(0.3)
    try:
        driver.switch_to.default_content()
        escondidos = driver.execute_script(
            """
            const els = [...document.querySelectorAll(arguments[0])];
            els.forEach(e => { e.style.display = 'none'; });
            return els.length;
            """,
            SELETOR_OVERLAY,
        )
        _log.warning("Cortina de transição presa — escondida via JS "
                     "(%s elemento(s))", escondidos)
        return not overlay_presente(driver)
    except Exception as exc:
        _log.error("Falha ao limpar a cortina: %s", exc)
        return False


def fechar_janelas_extras(driver, handle_principal=None):
    """Fecha toda janela além da principal e devolve o foco a ela.

    Janelas de impressão órfãs acumulam e quebram a sessão ("Browser window
    not found" + cortina presa). Retorna o handle principal (ou ``None``).
    """
    try:
        handles = driver.window_handles
        if not handles:
            return None
        principal = (handle_principal if handle_principal in handles
                     else handles[0])
        extras = [h for h in handles if h != principal]
        for handle in extras:
            try:
                driver.switch_to.window(handle)
                driver.close()
            except Exception:
                pass
        driver.switch_to.window(principal)
        if extras:
            _log.warning("%d janela(s) extra(s) fechada(s)", len(extras))
        return principal
    except Exception as exc:
        _log.warning("Falha ao fechar janelas extras: %s", exc)
        return handle_principal


def fechar_popups_cis(driver) -> int:
    """Fecha page-popups modais do CIS pelo X da barra de título (no TOPO).

    O aviso "UORG DO CORREIO DO USUARIO DESATIVADA" (e afins) bloqueia a
    navegação até ser FECHADO — esconder via CSS não conta como lido.
    Retorna quantos popups foram fechados.
    """
    try:
        driver.switch_to.default_content()
        fechados = 0
        for el in driver.find_elements(By.CSS_SELECTOR, SELETOR_POPUP_FECHAR):
            try:
                if el.is_displayed():
                    el.click()
                    fechados += 1
                    time.sleep(0.5)
            except Exception:
                pass
        if fechados:
            _log.info("%d popup(s) modal(is) fechado(s) pelo X", fechados)
        return fechados
    except Exception:
        return 0
