"""Testes de ``integra_gov.esiape.ficha_anual`` — DriverFake estendido."""

from __future__ import annotations

from pathlib import Path

import pytest

from integra_gov.esiape import navegacao as nav
from integra_gov.esiape.exceptions import (
    EsiapeError,
    ExtracaoFichaEsiapeInterrompida,
    FichaEsiapeIndisponivel,
)
from integra_gov.esiape.ficha_anual import (
    FichaAnualServidor,
    ResultadoFichaEsiape,
)
from tests.test_esiape_navegacao import DriverFake, ElementoFake, FrameFake


def test_excecoes_novas_sao_esiape_error():
    assert issubclass(ExtracaoFichaEsiapeInterrompida, EsiapeError)
    assert issubclass(FichaEsiapeIndisponivel, EsiapeError)


def test_extracao_interrompida_carrega_blocos_e_causa():
    causa = RuntimeError("popup sumiu")
    exc = ExtracaoFichaEsiapeInterrompida([(2008, 2022)], causa)
    assert exc.blocos_processados == [(2008, 2022)]
    assert exc.causa is causa
    assert "2008" in str(exc)


def test_pypdf_disponivel():
    from pypdf import PdfReader, PdfWriter  # noqa: F401


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    from integra_gov.esiape import ficha_anual as fmod

    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(fmod.time, "sleep", lambda *_a, **_k: None)


class DriverFicha(DriverFake):
    """DriverFake + refresh() (a impressão exige refresh pós-popup)."""

    def __init__(self, raiz):
        super().__init__(raiz)
        self.refreshes = 0

    def refresh(self):
        self.refreshes += 1


def pdf_minimo(caminho: Path) -> Path:
    """PDF real de 1 página em branco (pypdf) para testes de mesclagem."""
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    with open(caminho, "wb") as f:
        w.write(f)
    return caminho


def test_dividir_blocos_respeita_limite_de_15():
    assert FichaAnualServidor._dividir_blocos(2008, 2026) == [
        (2008, 2022), (2023, 2026)]
    assert FichaAnualServidor._dividir_blocos(2020, 2026) == [(2020, 2026)]
    assert FichaAnualServidor._dividir_blocos(2010, 2010) == [(2010, 2010)]


def test_construtor_cria_pastas(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()),
                               pasta_saida=tmp_path / "saida")
    assert (tmp_path / "saida").is_dir()
    assert ficha.pasta_download == tmp_path / "saida" / "_download_esiape"
    assert ficha.pasta_download.is_dir()


def test_extrair_valida_parametros(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)
    with pytest.raises(ValueError):
        ficha.extrair("", 2008, 2026)
    with pytest.raises(ValueError):
        ficha.extrair("0000000", 2026, 2008)


def test_resultado_dataclass():
    r = ResultadoFichaEsiape()
    assert r.pdf is None
    assert r.pdfs_blocos == []
    assert r.blocos_com_dados == []
    assert r.blocos_sem_dados == []
    assert r.duracao_s == 0.0


def _arvore_fpemfichaf():
    """Menu com lupa; clicar Ir abre a tela do FPEMFICHAF completa."""
    raiz = FrameFake()
    wa1 = FrameFake("WA1", visivel=True)
    wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    ir = ElementoFake()
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]
    raiz.filhos = [wa1]

    consulta_online = ElementoFake()
    matricula = ElementoFake()
    ano_ini, ano_fim = ElementoFake(), ElementoFake()
    pesquisar_seletores = {
        FichaAnualServidor.SEL_CONSULTA_ONLINE: [consulta_online],
        FichaAnualServidor.SEL_MATRICULA: [matricula],
        FichaAnualServidor.SEL_ANO_INICIO: [ano_ini],
        FichaAnualServidor.SEL_ANO_FIM: [ano_fim],
    }

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos.update(pesquisar_seletores)

    ir.click = ir_click
    return raiz, wa1, matricula


def test_consultar_bloco_com_dados(tmp_path):
    raiz, wa1, matricula = _arvore_fpemfichaf()
    driver = DriverFicha(raiz)
    driver.resultado_script = ""  # texto da tela sem MSG_SEM_DADOS
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)
    # após a consulta, o botão Gerar Relatório aparece = tem dados
    _click_mat = matricula.send_keys

    def mat_keys(*teclas):
        _click_mat(*teclas)
        wa1.elementos[FichaAnualServidor.SEL_GERAR_RELATORIO] = [ElementoFake()]

    matricula.send_keys = mat_keys
    assert ficha._consultar_bloco("0000000", 2008, 2022) is True
    assert "0000000" in matricula.teclas


def test_consultar_bloco_sem_dados_devolve_false(tmp_path):
    from unittest.mock import patch

    raiz, wa1, matricula = _arvore_fpemfichaf()
    driver = DriverFicha(raiz)

    def roteiro(script, *args):
        if "innerText" in script:
            return "mensagem: NAO HOUVE DADOS PARA CRITERIO SOLICITADO"
        return False  # overlay_presente e afins

    driver.resultado_script = roteiro
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)
    with patch.object(FichaAnualServidor, "TIMEOUT_CONSULTA", 0.05):
        assert ficha._consultar_bloco("0000000", 2008, 2022) is False


def test_consultar_bloco_tela_nao_abre_levanta(tmp_path):
    from unittest.mock import patch

    driver = DriverFicha(FrameFake())  # sem lupa, sem nada
    driver.resultado_script = ""
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)
    from integra_gov.esiape.exceptions import TransacaoNaoAbriu

    # garantir_menu tem timeout REAL de 60s (monotonic) — atalha p/ o teste
    with patch.object(nav, "garantir_menu", lambda d, timeout=60: False):
        with pytest.raises(TransacaoNaoAbriu):
            ficha._consultar_bloco("0000000", 2008, 2022)
