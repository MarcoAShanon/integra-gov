"""Testes de ``integra_gov.esiape._campos`` (máscara e data SIAPE).

Vieram de ``test_esiape_dados_pessoais.py`` quando as funções saíram de lá
para serem compartilhadas com o módulo de pensionista.
"""

from __future__ import annotations

import pytest

from integra_gov.esiape._campos import (
    data_siape,
    mascarar_digitos,
    mascarar_matricula,
)


def test_mascarar_matricula_curta_nao_expoe_tudo():
    assert mascarar_matricula("5") == "******5"


def test_mascarar_matricula_comum():
    assert mascarar_matricula("0000000") == "*****00"


@pytest.mark.parametrize("bruto, esperado", [
    ("MATRICULA 1234567 NAO CADASTRADA", "MATRICULA *****67 NAO CADASTRADA"),
    ("000.000-0", "*****00"),
    ("123.456.789-00", "*****00"),
    ("1234", "*****34"),
    ("UF 12", "UF 12"),
    ("ORGAO 40806 - X", "ORGAO *****06 - X"),
])
def test_mascarar_digitos(bruto, esperado):
    assert mascarar_digitos(bruto) == esperado


@pytest.mark.parametrize("bruto, esperado", [
    ("15AGO1960", "15/08/1960"),
    ("01JAN2001", "01/01/2001"),
    ("15XYZ1960", None),
    ("1960-08-15", None),
    ("", None),
    (None, None),
])
def test_data_siape(bruto, esperado):
    assert data_siape(bruto) == esperado
