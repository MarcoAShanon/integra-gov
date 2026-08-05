"""Testes de ``integra_gov.esiape.acesso`` — DriverFake roteirizado."""

from __future__ import annotations

import pytest

from integra_gov.esiape import acesso as ac
from integra_gov.esiape import navegacao as nav
from integra_gov.esiape.acesso import AcessoEsiape
from integra_gov.esiape.exceptions import (
    AutenticacaoNaoConfirmada,
    MenuInacessivel,
)
from tests.test_esiape_navegacao import DriverFake, ElementoFake, FrameFake


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(ac.time, "sleep", lambda *_a, **_k: None)


def _driver_pos_login():
    """Após a confirmação no app: tela de AVANÇAR presente; clicá-lo revela
    a lupa (menu)."""
    raiz = FrameFake()
    botao_cert = ElementoFake()
    raiz.elementos[AcessoEsiape.XPATH_BOTAO_CERTIFICADO] = [botao_cert]
    wa1 = FrameFake("WA1", visivel=True)
    avancar = ElementoFake()
    wa1.elementos[nav.SELETOR_BTN_AVANCAR] = [avancar]
    raiz.filhos = [wa1]

    _click = avancar.click

    def avancar_click():
        _click()
        del wa1.elementos[nav.SELETOR_BTN_AVANCAR]
        wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]

    avancar.click = avancar_click
    driver = DriverFake(raiz)
    driver.resultado_script = False
    return driver, botao_cert


def test_executar_aciona_certificado_e_chega_ao_menu():
    driver, botao_cert = _driver_pos_login()
    AcessoEsiape(driver, timeout_confirmacao=1).executar()
    assert driver.url == AcessoEsiape.URL_ESIAPE
    assert botao_cert.cliques == 1
    # o relogin de ENTRADA não deixa pendência: o acesso limpa a flag
    assert nav.relogin_pendente(driver) is False


def test_timeout_do_app_levanta_autenticacao_nao_confirmada():
    raiz = FrameFake()
    raiz.elementos[AcessoEsiape.XPATH_BOTAO_CERTIFICADO] = [ElementoFake()]
    driver = DriverFake(raiz)  # nenhuma tela pós-login jamais aparece
    driver.resultado_script = False
    with pytest.raises(AutenticacaoNaoConfirmada):
        AcessoEsiape(driver, timeout_confirmacao=0.05).executar()


def test_menu_inacessivel_apos_login_levanta(monkeypatch):
    raiz = FrameFake()
    raiz.elementos[AcessoEsiape.XPATH_BOTAO_CERTIFICADO] = [ElementoFake()]
    wa1 = FrameFake("WA1", visivel=True)
    wa1.elementos[nav.SELETOR_BTN_PULAR] = [ElementoFake()]  # detectado...
    raiz.filhos = [wa1]
    driver = DriverFake(raiz)
    driver.resultado_script = False
    # ...mas garantir_menu nunca converge (Pular não revela nada)
    monkeypatch.setattr(ac, "garantir_menu", lambda d, timeout=60: False)
    with pytest.raises(MenuInacessivel):
        AcessoEsiape(driver, timeout_confirmacao=1).executar()
