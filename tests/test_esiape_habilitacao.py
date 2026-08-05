"""Testes de ``integra_gov.esiape.habilitacao`` — DriverFake roteirizado."""

from __future__ import annotations

import pytest

from integra_gov.esiape import navegacao as nav
from integra_gov.esiape import habilitacao as hab
from integra_gov.esiape.exceptions import (
    EsiapeError,
    HabilitacaoNaoEncontrada,
    TransacaoNaoAbriu,
)
from integra_gov.esiape.habilitacao import TrocaHabilitacaoEsiape
from tests.test_esiape_navegacao import DriverFake, ElementoFake, FrameFake


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(hab.time, "sleep", lambda *_a, **_k: None)


def _cabecalho(orgao_texto):
    return [ElementoFake(texto=orgao_texto)]


def _driver_menu_com_cabecalho(orgao_texto):
    raiz = FrameFake()
    wa1 = FrameFake("WA1", visivel=True)
    wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]
    wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_ORGAO_ATIVO] = \
        _cabecalho(orgao_texto)
    raiz.filhos = [wa1]
    driver = DriverFake(raiz)
    driver.resultado_script = False
    return driver, wa1


def test_idempotente_limpa_flag_e_nao_navega():
    driver, _ = _driver_menu_com_cabecalho("11111 - ORGAO DE TESTE")
    driver._esiape_relogin_pendente = True
    troca = TrocaHabilitacaoEsiape(driver, orgao="11111")
    troca.trocar()  # cabeçalho já no destino
    assert nav.relogin_pendente(driver) is False


def test_troca_completa_com_modal_e_confirmacao():
    driver, wa1 = _driver_menu_com_cabecalho("11111 - ORIGEM")
    troca = TrocaHabilitacaoEsiape(driver, orgao="22222")

    # tela TROCAHAB: grade com cabeçalho + 2 linhas
    linha_alvo = ElementoFake(texto="  22222  ORGAO  DESTINO")
    grade = [ElementoFake(texto="CABECALHO"),
             ElementoFake(texto="  11111  ORGAO  ORIGEM"), linha_alvo]
    sim = ElementoFake()
    home = ElementoFake()

    _click_alvo = linha_alvo.click

    def alvo_click():
        _click_alvo()
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_BTN_SIM] = [sim]

    linha_alvo.click = alvo_click

    _click_sim = sim.click

    def sim_click():
        _click_sim()
        # o CIS efetiva: cabeçalho passa a refletir o destino
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_ORGAO_ATIVO] = \
            _cabecalho("22222 - DESTINO")
        wa1.elementos[nav.SELETOR_HOME] = [home]

    sim.click = sim_click

    # navegar_para_transacao abre a grade (via clique no Ir)
    ir = ElementoFake()
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_GRADE_LINHAS] = grade

    ir.click = ir_click

    troca.trocar()
    assert linha_alvo.cliques == 1
    assert sim.cliques == 1
    assert troca.orgao_atual() == "22222"


def test_orgao_ausente_na_grade_levanta_com_codigos():
    driver, wa1 = _driver_menu_com_cabecalho("11111 - ORIGEM")
    grade = [ElementoFake(texto="CABECALHO"),
             ElementoFake(texto="  11111  ORGAO  ORIGEM")]
    ir = ElementoFake()
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_GRADE_LINHAS] = grade

    ir.click = ir_click

    with pytest.raises(HabilitacaoNaoEncontrada) as exc:
        TrocaHabilitacaoEsiape(driver, orgao="99999").trocar()
    assert "11111" in str(exc.value)


def test_transacao_nao_abriu_levanta():
    driver, wa1 = _driver_menu_com_cabecalho("11111 - ORIGEM")
    # sem campo/Ir: navegar_para_transacao devolve False
    with pytest.raises(TransacaoNaoAbriu):
        TrocaHabilitacaoEsiape(driver, orgao="22222").trocar()


def test_cabecalho_nao_refletiu_nao_declara_sucesso(monkeypatch):
    driver, wa1 = _driver_menu_com_cabecalho("11111 - ORIGEM")
    monkeypatch.setattr(TrocaHabilitacaoEsiape, "TIMEOUT_CONFIRMACAO", 0.05)
    troca = TrocaHabilitacaoEsiape(driver, orgao="22222")

    linha_alvo = ElementoFake(texto="  22222  ORGAO  DESTINO")
    grade = [ElementoFake(texto="CABECALHO"), linha_alvo]
    sim = ElementoFake()

    _click_alvo = linha_alvo.click

    def alvo_click():
        _click_alvo()
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_BTN_SIM] = [sim]

    linha_alvo.click = alvo_click
    # sim.click NÃO muda o cabeçalho — troca não efetivou

    ir = ElementoFake()
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_GRADE_LINHAS] = grade

    ir.click = ir_click

    with pytest.raises(EsiapeError):
        troca.trocar()
