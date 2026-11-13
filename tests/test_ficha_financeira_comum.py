"""Testes de ``integra_gov.ficha_financeira._comum``."""

from __future__ import annotations

from decimal import Decimal

import pytest

from integra_gov.ficha_financeira._comum import para_decimal


@pytest.mark.parametrize(("texto", "esperado"), [
    ("1.931,56", "1931.56"),
    ("0,00", "0.00"),
    ("999,99", "999.99"),
    ("1.234.567,89", "1234567.89"),
    ("  2.629,31  ", "2629.31"),   # a célula vem com o preenchimento da coluna
    ("1931,56", "1931.56"),        # sem separador de milhar
])
def test_para_decimal_le_o_formato_pt_br(texto, esperado):
    assert para_decimal(texto) == Decimal(esperado)


@pytest.mark.parametrize("texto", [
    "1.931",       # valor truncado: sem os centavos, viraria 1931
    "1.931,5",     # um centavo só: valor cortado no meio
    ",56",         # perdeu a parte inteira
    "1,234.56",    # formato en-US: viraria 1,23456
    "1.2.3,4",     # milhar malformado
    "19.31,56",    # grupo de milhar com dois dígitos
    "1E3",         # notação científica que o Decimal aceitaria
    "1_000,00",    # sublinhado que o Decimal aceitaria
    "NaN",
    "Infinity",
    "",
    "ABC,DE",
])
def test_para_decimal_recusa_o_que_nao_e_valor_pt_br_completo(texto):
    with pytest.raises(ValueError, match="pt-BR"):
        para_decimal(texto)


@pytest.mark.parametrize("texto", ["-1.000,00", "1.000,00-"])
def test_para_decimal_recusa_negativo_com_mensagem_propria(texto):
    with pytest.raises(ValueError, match="negativo"):
        para_decimal(texto)
