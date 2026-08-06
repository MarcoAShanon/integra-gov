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
from tests.test_esiape_navegacao import DriverFake, FrameFake


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
