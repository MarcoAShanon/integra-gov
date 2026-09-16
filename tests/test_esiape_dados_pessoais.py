"""Testes de ``integra_gov.esiape.dados_pessoais`` (CDCOINDPES)."""

from __future__ import annotations

from pathlib import Path

import pytest

from integra_gov.esiape.exceptions import DadosPessoaisIndisponiveis, EsiapeError
from integra_gov.ficha_financeira import PdfIlegivelError
from tests._pdf_sintetico import pdf_bytes

# Rótulos reais da tela CDCOINDPES; valores fictícios.
LINHAS_PDF = [
    "DADOS INDIVIDUAIS PESSOAIS",
    "MATRICULA: 0000000     NOME: FULANO DE TAL",
    "SIT.SER.: 02 APOSENTADO     NUMERO DO CPF: 000.000.000-00",
    "DATA NASCIMENTO: 15AGO1960     E-MAIL PESSOAL: FULANO@EXEMPLO.GOV.BR",
    "MUNICIPIO: CIDADE EXEMPLO     UF: XX",
    "ORGAO SOLICITADO: 00000 - ORGAO/TESTE",
]
TEXTO = "\n".join(LINHAS_PDF)


def pdf_cadastral(caminho: Path, linhas=LINHAS_PDF) -> Path:
    caminho.write_bytes(pdf_bytes([linhas]))
    return caminho


def test_excecao_nova_e_esiape_error():
    exc = DadosPessoaisIndisponiveis("0000000", "botão Imprimir não apareceu")
    assert isinstance(exc, EsiapeError)
    assert exc.matricula == "0000000"
    assert exc.motivo == "botão Imprimir não apareceu"
    assert "*****00" in str(exc) and "0000000" not in str(exc)
    assert "Imprimir" in str(exc)


# ----------------------------------------------------------------- parsing
def test_extrair_campos_le_os_9_rotulos():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos(TEXTO)
    assert c == {
        "matricula": "0000000",
        "nome": "FULANO DE TAL",
        "situacao": "APOSENTADO",
        "cpf": "000.000.000-00",
        "data_nascimento": "15/08/1960",
        "email": "fulano@exemplo.gov.br",
        "municipio": "Cidade Exemplo",
        "uf": "XX",
        "orgao": "ORGAO/TESTE",
    }


def test_extrair_campos_rotulo_ausente_vira_none():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos("MATRICULA: 0000000\nNOME: FULANO DE TAL")
    assert c["matricula"] == "0000000"
    assert c["nome"] == "FULANO DE TAL"
    for k in ("situacao", "cpf", "data_nascimento", "email", "municipio", "uf", "orgao"):
        assert c[k] is None


def test_extrair_campos_corta_no_proximo_rotulo_da_mesma_linha():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos("NOME: FULANO DE TAL  SIT.SER.: 01 ATIVO PERMANENTE")
    assert c["nome"] == "FULANO DE TAL"
    assert c["situacao"] == "ATIVO PERMANENTE"


def test_extrair_campos_matricula_so_digitos():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    assert extrair_campos("MATRICULA: 00.000-00")["matricula"] == "0000000"


def test_extrair_campos_texto_irreconhecivel_tudo_none():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    assert all(v is None for v in extrair_campos("tela irreconhecivel").values())


@pytest.mark.parametrize("bruto, esperado", [
    ("15AGO1960", "15/08/1960"),
    ("01JAN2001", "01/01/2001"),
    ("15XYZ1960", None),
    ("1960-08-15", None),
    ("", None),
])
def test_data_siape(bruto, esperado):
    from integra_gov.esiape.dados_pessoais import _data_siape

    assert _data_siape(bruto) == esperado


@pytest.mark.parametrize("bruto, esperado", [
    ("02 APOSENTADO", "APOSENTADO"),
    ("APOSENTADO", "APOSENTADO"),
    ("", None),
])
def test_situacao(bruto, esperado):
    from integra_gov.esiape.dados_pessoais import _situacao

    assert _situacao(bruto) == esperado


@pytest.mark.parametrize("bruto, esperado", [
    ("00000 - ORGAO/TESTE", "ORGAO/TESTE"),
    ("ORGAO/TESTE", "ORGAO/TESTE"),
    ("", None),
])
def test_orgao(bruto, esperado):
    from integra_gov.esiape.dados_pessoais import _orgao

    assert _orgao(bruto) == esperado


# ------------------------------------------------------ ler_dados_pessoais
def test_ler_dados_pessoais_devolve_dataclass_com_pdf_e_texto(tmp_path):
    from integra_gov.esiape.dados_pessoais import DadosPessoais, ler_dados_pessoais

    pdf = pdf_cadastral(tmp_path / "x.pdf")
    d = ler_dados_pessoais(pdf)
    assert isinstance(d, DadosPessoais)
    assert d.pdf == pdf
    assert d.matricula == "0000000"
    assert d.nome == "FULANO DE TAL"
    assert d.email == "fulano@exemplo.gov.br"
    assert "NUMERO DO CPF" in d.texto


def test_ler_dados_pessoais_pdf_sem_texto_levanta(tmp_path):
    from integra_gov.esiape.dados_pessoais import ler_dados_pessoais

    pdf = tmp_path / "vetor.pdf"
    pdf.write_bytes(pdf_bytes([None], com_fonte=False))
    with pytest.raises(PdfIlegivelError):
        ler_dados_pessoais(pdf)


def test_ler_dados_pessoais_arquivo_que_nao_abre_levanta(tmp_path):
    from integra_gov.esiape.dados_pessoais import ler_dados_pessoais

    pdf = tmp_path / "lixo.pdf"
    pdf.write_bytes(b"isto nao e um PDF")
    with pytest.raises(PdfIlegivelError):
        ler_dados_pessoais(pdf)


def test_ler_dados_pessoais_le_todas_as_paginas(tmp_path):
    from integra_gov.esiape.dados_pessoais import ler_dados_pessoais

    pdf = tmp_path / "duas.pdf"
    pdf.write_bytes(pdf_bytes([LINHAS_PDF[:3], LINHAS_PDF[3:]]))
    d = ler_dados_pessoais(pdf)
    assert d.uf == "XX" and d.orgao == "ORGAO/TESTE"
