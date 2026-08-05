"""Testes de ``integra_gov.esiape`` — navegação CIS com DriverFake."""

from __future__ import annotations

from integra_gov.esiape.exceptions import (
    AutenticacaoNaoConfirmada,
    EsiapeError,
    HabilitacaoNaoEncontrada,
    MenuInacessivel,
    TransacaoNaoAbriu,
)


def test_excecoes_sao_esiape_error():
    for exc in (MenuInacessivel, AutenticacaoNaoConfirmada,
                TransacaoNaoAbriu, HabilitacaoNaoEncontrada):
        assert issubclass(exc, EsiapeError)


def test_transacao_nao_abriu_carrega_contexto():
    exc = TransacaoNaoAbriu("TROCAHAB", '[data-testtoolid="x"]')
    assert exc.transacao == "TROCAHAB"
    assert exc.seletor_confirmacao == '[data-testtoolid="x"]'
    assert "TROCAHAB" in str(exc)


def test_habilitacao_nao_encontrada_lista_codigos():
    exc = HabilitacaoNaoEncontrada("00000", ["11111", "22222"])
    assert exc.orgao == "00000"
    assert exc.codigos_visiveis == ["11111", "22222"]
    assert "11111" in str(exc)
