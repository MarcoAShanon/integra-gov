"""Testes de ``integra_gov.esiape.dados_funcionais`` (CDCOINDFUN)."""

from __future__ import annotations

import pytest

from integra_gov.esiape import navegacao as nav
from integra_gov.esiape.dados_funcionais import (
    DadosFuncionais,
    DadosFuncionaisOrgao,
)
from integra_gov.esiape.exceptions import TransacaoNaoAbriu
from tests.test_esiape_navegacao import DriverFake, ElementoFake, FrameFake


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    from integra_gov.esiape import dados_funcionais as dmod

    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(dmod.time, "sleep", lambda *_a, **_k: None)


TEXTO_TELA_3 = """
DADOS INDIVIDUAIS FUNCIONAIS
Cadastramento no SIAPE: 11DEZ2014
INGRESSO NO ORGAO
DATA OCORRENCIA : 01DEZ2014
ORGAO/MATRIC ANTER.: 11111 / 0000000
"""

TEXTO_TELA_2 = "SELECIONE:\nINGRESSO NO ORGAO\nORGAO ATUAL/ANTERIOR"


def test_extrair_parseia_orgao_anterior_e_ingresso():
    d = DadosFuncionaisOrgao._extrair(TEXTO_TELA_3)
    assert d.orgao_anterior == "11111"
    assert d.matricula_anterior == "0000000"
    assert d.ano_ingresso == 2014
    assert d.cadastramento_siape == "11DEZ2014"


def test_extrair_sem_orgao_anterior_devolve_none():
    d = DadosFuncionaisOrgao._extrair("Cadastramento no SIAPE: 05JAN2001")
    assert d.orgao_anterior is None
    assert d.matricula_anterior is None
    assert d.ano_ingresso == 2001  # cai no cadastramento sem a ocorrência


def test_extrair_texto_ilegivel_tudo_none():
    d = DadosFuncionaisOrgao._extrair("tela irreconhecivel")
    assert d == DadosFuncionais(None, None, None, None)


def test_consultar_tela_nao_abre_levanta():
    from unittest.mock import patch

    driver = DriverFake(FrameFake())
    driver.resultado_script = ""
    with patch.object(nav, "garantir_menu", lambda d, timeout=60: False):
        with pytest.raises(TransacaoNaoAbriu):
            DadosFuncionaisOrgao(driver).consultar("0000000", orgao="00000")


def test_consultar_fluxo_completo_3_telas_com_armadilha_do_rotulo():
    """As 3 telas felizes — e a prova do marcador em disputa REAL: após o
    clique de Pesquisar 2, o CIS continua mostrando o texto da tela 2 (com
    o rótulo-armadilha 'INGRESSO NO ORGAO') por algumas leituras antes de
    finalmente trocar para a tela 3 — simulando a transição lenta real do
    CIS. Se o marcador aceitasse o texto da tela 2, o parse aconteceria
    cedo demais e as asserções de órgão/ano quebrariam."""
    raiz = FrameFake()
    wa1 = FrameFake("WA1", visivel=True)
    wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    ir = ElementoFake()
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]
    raiz.filhos = [wa1]

    matricula, orgao_campo = ElementoFake(), ElementoFake()
    pesquisar_1, pesquisar_2 = ElementoFake(), ElementoFake()
    checkboxes = {tid: ElementoFake()
                  for tid in DadosFuncionaisOrgao.CHECKBOXES}
    estado = {"tela": 1}

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos[DadosFuncionaisOrgao.SEL_MATRICULA] = [matricula]
        wa1.elementos[DadosFuncionaisOrgao.SEL_ORGAO] = [orgao_campo]
        wa1.elementos[DadosFuncionaisOrgao.SEL_PESQUISAR_1] = [pesquisar_1]

    ir.click = ir_click

    _click_p1 = pesquisar_1.click

    def p1_click():
        _click_p1()
        estado["tela"] = 2
        for tid, cb in checkboxes.items():
            wa1.elementos[f'[data-testtoolid="{tid}"]'] = [cb]
        wa1.elementos[DadosFuncionaisOrgao.SEL_PESQUISAR_2] = [pesquisar_2]

    pesquisar_1.click = p1_click

    _click_p2 = pesquisar_2.click

    def p2_click():
        _click_p2()
        estado["tela"] = 3
        estado["leituras_pos_p2"] = 0

    pesquisar_2.click = p2_click

    driver = DriverFake(raiz)

    def texto_da_tela(script, *args):
        if "innerText" not in script:
            return False  # overlay_presente e afins
        if estado["tela"] == 2:
            return TEXTO_TELA_2
        if estado["tela"] == 3:
            estado["leituras_pos_p2"] += 1
            if estado["leituras_pos_p2"] <= 3:
                return TEXTO_TELA_2  # transição: o CIS ainda mostra a tela 2
            return TEXTO_TELA_3
        return ""

    driver.resultado_script = texto_da_tela

    d = DadosFuncionaisOrgao(driver).consultar("0000000", orgao="22222")
    assert d.orgao_anterior == "11111"
    assert d.ano_ingresso == 2014
    assert "22222" in orgao_campo.teclas       # órgão EXPLÍCITO preenchido
    assert all(cb.cliques == 1 for cb in checkboxes.values())
    assert estado["leituras_pos_p2"] > 3  # o texto-armadilha foi LIDO e rejeitado antes da tela 3
