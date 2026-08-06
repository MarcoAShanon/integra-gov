"""Testes do laço multi-órgão — colaboradores mockados, laço real."""

from __future__ import annotations

from pathlib import Path  # noqa: F401
from unittest.mock import patch

import pytest

from integra_gov.esiape import navegacao as nav
from integra_gov.esiape.dados_funcionais import DadosFuncionais
from integra_gov.esiape.ficha_anual import ResultadoFichaEsiape
from integra_gov.esiape.ficha_multi_orgao import (
    FichaMultiOrgao,
    ResultadoMultiOrgao,  # noqa: F401
)
from tests.test_esiape_ficha_anual import pdf_minimo
from tests.test_esiape_navegacao import DriverFake, FrameFake


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    from integra_gov.esiape import ficha_multi_orgao as mmod

    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(mmod.time, "sleep", lambda *_a, **_k: None)


def _driver():
    d = DriverFake(FrameFake())
    d.resultado_script = False
    return d


def _resultado_ficha(tmp_path, matricula, ano_de, ano_ate):
    # PDF REAL mínimo: a mesclagem final usa pypdf de verdade
    pdf = pdf_minimo(tmp_path / f"ficha_{matricula}_{ano_de}_{ano_ate}.pdf")
    return ResultadoFichaEsiape(pdf=pdf, pdfs_blocos=[pdf],
                                blocos_com_dados=[(ano_de, ano_ate)])


def test_um_salto_com_ano_da_virada_nos_dois_orgaos(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)
    dados = {
        ("0000001", "22222"): DadosFuncionais("11111", "0000001", 2014,
                                              "11DEZ2014"),
        ("0000001", "11111"): DadosFuncionais(None, None, 2001, "05JAN2001"),
    }
    faixas = []

    def consultar(self, matricula, orgao):
        return dados[(matricula, orgao)]

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        faixas.append((ano_inicial, ano_final))
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", lambda self: None):
        r = multi.extrair("0000001", 2008, 2026)

    # faixa do órgão atual: 2014-2026; a do anterior INCLUI o ano da virada
    assert faixas == [(2014, 2026), (2008, 2014)]
    assert r.trilha == [("22222", "0000001", 2014, 2026),
                        ("11111", "0000001", 2008, 2014)]
    assert r.lacunas == []
    assert r.pdf is not None and r.pdf.exists()
    assert r.voltou_ao_orgao_inicial is True


def test_sem_orgao_anterior_declara_lacuna(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)

    def consultar(self, matricula, orgao):
        return DadosFuncionais(None, None, 2014, "11DEZ2014")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", lambda self: None):
        r = multi.extrair("0000001", 2008, 2026)

    assert r.pdf is not None
    assert any("2008-2013" in lac for lac in r.lacunas)


def test_relogin_pendente_rehabilita_antes_de_consultar(tmp_path):
    driver = _driver()
    driver._esiape_relogin_pendente = True
    multi = FichaMultiOrgao(driver, orgao_inicial="22222",
                            pasta_saida=tmp_path)
    trocas = []

    def trocar(self):
        trocas.append(self.orgao)
        nav.limpar_flag_relogin(driver)

    def consultar(self, matricula, orgao):
        assert not nav.relogin_pendente(driver)  # re-habilitou ANTES
        return DadosFuncionais(None, None, 2008, "01JAN2008")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", trocar):
        r = multi.extrair("0000001", 2008, 2026)
    assert "22222" in trocas  # re-habilitação aconteceu
    assert r.pdf is not None


def test_falha_intermitente_retenta_faixa(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)
    chamadas = {"n": 0}

    def consultar(self, matricula, orgao):
        return DadosFuncionais(None, None, 2008, "01JAN2008")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise RuntimeError("Browser window not found")
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", lambda self: None):
        r = multi.extrair("0000001", 2008, 2026)
    assert chamadas["n"] == 2  # 1 falha + 1 retry com sucesso
    assert r.pdf is not None
    assert r.falhas_tecnicas == []


def test_faixa_falha_2x_vira_lacuna_e_falha_tecnica(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)

    def consultar(self, matricula, orgao):
        return DadosFuncionais(None, None, 2008, "01JAN2008")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        raise RuntimeError("sessao caiu")

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", lambda self: None):
        r = multi.extrair("0000001", 2008, 2026)
    assert r.pdf is None
    assert len(r.falhas_tecnicas) == 1
    assert any("2008-2026" in f for f in r.falhas_tecnicas)


def test_ciclo_detectado_para(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)

    def consultar(self, matricula, orgao):
        # 22222 -> 11111 -> 22222 (ciclo)
        anterior = "11111" if orgao == "22222" else "22222"
        return DadosFuncionais(anterior, matricula, 2015, "01JAN2015")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", lambda self: None):
        r = multi.extrair("0000001", 2008, 2026)
    assert len(r.trilha) <= 2  # parou no ciclo, não loopou até max_saltos


def test_sem_habilitacao_no_anterior_declara_lacuna_e_entrega(tmp_path):
    from integra_gov.esiape.exceptions import HabilitacaoNaoEncontrada

    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)

    def consultar(self, matricula, orgao):
        return DadosFuncionais("11111", matricula, 2014, "11DEZ2014")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    def trocar(self):
        if self.orgao == "11111":  # usuário NÃO possui o órgão anterior
            raise HabilitacaoNaoEncontrada("11111", ["22222"])

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", trocar):
        r = multi.extrair("0000001", 2008, 2026)

    assert r.pdf is not None                       # entrega o que cobriu
    assert any("sem habilitação no órgão 11111" in lac for lac in r.lacunas)
    assert r.voltou_ao_orgao_inicial is True       # nunca saiu do 22222


def test_retorno_ao_orgao_inicial_falha_sinaliza(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)

    def consultar(self, matricula, orgao):
        if orgao == "22222":
            return DadosFuncionais("11111", matricula, 2014, "11DEZ2014")
        return DadosFuncionais(None, None, 2001, "05JAN2001")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    def trocar(self):
        if self.orgao == "22222":  # só o RETORNO falha (ida ao 11111 ok)
            raise HabilitacaoNaoEncontrada("22222", ["11111"])

    from integra_gov.esiape.exceptions import HabilitacaoNaoEncontrada

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", trocar):
        r = multi.extrair("0000001", 2008, 2026)

    assert r.pdf is not None
    assert r.voltou_ao_orgao_inicial is False
    assert any("não voltou" in f for f in r.falhas_tecnicas)
