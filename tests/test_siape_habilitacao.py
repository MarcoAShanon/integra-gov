"""Testes de ``integra.siape.habilitacao`` — controle de terminal mockado."""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from integra.siape import habilitacao as mod
from integra.siape.controle import ControleTerminal3270
from integra.siape.exceptions import HabilitacaoNaoEncontrada, TerminalError
from integra.siape.habilitacao import TrocaHabilitacao

LARGURA = TrocaHabilitacao.CARACTERES_POR_LINHA


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)


def _tela_com_texto_na_linha(texto: str, linha: int, extra: str = "") -> str:
    """Monta uma tela onde ``texto`` começa na coluna 1 da ``linha`` indicada."""
    prefixo = "." * ((linha - 1) * LARGURA)
    return prefixo + texto + extra


def _controle(menu_ok=True):
    c = MagicMock(spec=ControleTerminal3270)
    # _linha_comando_disponivel: extrair_texto devolve a linha de comando.
    c.extrair_texto.return_value = (
        TrocaHabilitacao.TEXTO_COMANDO_LINHA if menu_ok else "OUTRA TELA"
    )
    return c


def test_orgao_upag_obrigatorios():
    with pytest.raises(ValueError):
        TrocaHabilitacao(_controle(), "", "987654")


def test_nao_troca_se_ja_na_habilitacao_destino():
    c = _controle()
    troca = TrocaHabilitacao(c, "26232", "987654")
    troca._ultimo_orgao, troca._ultima_upag = "26232", "987654"
    troca.trocar()
    # Não enviou TROCAHAB (troca evitada).
    assert call("TROCAHAB") not in c.enviar_teclas.call_args_list


def test_troca_encontra_na_primeira_pagina_seleciona():
    c = _controle()
    texto_busca = "26232 000987654"  # orgao + upag.zfill(9)
    # Habilitação na linha 13 → 1 TAB a partir da linha 12.
    tela = _tela_com_texto_na_linha(texto_busca, 13)
    c.copiar_tela.return_value = tela

    TrocaHabilitacao(c, "26232", "987654").trocar()

    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert "TROCAHAB" in enviados
    assert enviados.count("{TAB}") == 1  # linha 13 - 12
    assert "X" in enviados  # marca seleção
    assert "S" in enviados  # confirma
    assert "{F2}" in enviados  # volta ao menu


def test_troca_pagina_seguinte_quando_ha_continua():
    c = _controle()
    texto_busca = "26232 000987654"
    pagina1 = _tela_com_texto_na_linha(
        TrocaHabilitacao.TEXTO_CONTINUA, 20
    )  # sem o alvo, mas com "CONTINUA ==>"
    pagina2 = _tela_com_texto_na_linha(texto_busca, 12)  # alvo na 1ª linha da lista
    # copiar_tela: 1ª chamada (checagem de menu) + página1 + página2.
    c.copiar_tela.side_effect = ["tela-menu", pagina1, pagina2]

    TrocaHabilitacao(c, "26232", "987654").trocar()

    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert "{F8}" in enviados  # avançou de página
    assert "X" in enviados  # selecionou na página 2


def test_habilitacao_nao_encontrada_levanta():
    c = _controle()
    # Tela sem o alvo e sem "CONTINUA ==>" → não há próxima página.
    c.copiar_tela.return_value = "tela sem alvo e sem continua"
    with pytest.raises(HabilitacaoNaoEncontrada):
        TrocaHabilitacao(c, "26232", "987654").trocar()


def test_menu_nao_alcancavel_levanta():
    c = _controle(menu_ok=False)  # linha de comando nunca disponível
    c.copiar_tela.return_value = "qualquer"
    with pytest.raises(TerminalError):
        TrocaHabilitacao(c, "26232", "987654").trocar()


def test_match_acima_da_lista_e_ignorado():
    c = _controle()
    # Eco do ÓRGÃO/UPAG numa linha ACIMA da lista (linha 5) + sem CONTINUA:
    # não deve ser selecionado (evita num_tabs negativo) → não encontrada.
    c.copiar_tela.return_value = _tela_com_texto_na_linha("26232 000987654", 5)
    with pytest.raises(HabilitacaoNaoEncontrada):
        TrocaHabilitacao(c, "26232", "987654").trocar()


def test_busca_tolera_espacamento_e_zeros():
    c = _controle()
    # Espaçamento diferente (3 espaços) e UPAG sem zeros à esquerda, na lista.
    c.copiar_tela.return_value = _tela_com_texto_na_linha("26232   987654", 13)
    TrocaHabilitacao(c, "26232", "987654").trocar()
    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert "X" in enviados  # encontrou e selecionou apesar do formato diferente


def test_selecionar_na_linha_antes_da_lista_levanta():
    troca = TrocaHabilitacao(_controle(), "26232", "987654")
    with pytest.raises(TerminalError):
        troca._selecionar_na_linha(10)  # 10 < LINHA_INICIO_LISTA (12)
