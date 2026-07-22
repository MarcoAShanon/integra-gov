"""Testes de ``integra_gov.siape.habilitacao`` — controle de terminal mockado."""

from __future__ import annotations

import re
from unittest.mock import MagicMock, call

import pytest

from integra_gov.siape import _menu
from integra_gov.siape import habilitacao as mod
from integra_gov.siape.controle import ControleTerminal3270
from integra_gov.siape.exceptions import HabilitacaoNaoEncontrada, TerminalError
from integra_gov.siape.habilitacao import TrocaHabilitacao

LARGURA = TrocaHabilitacao.CARACTERES_POR_LINHA


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)
    # O "garantir menu" agora vive em _menu — neutraliza o sleep dele também.
    monkeypatch.setattr(_menu.time, "sleep", lambda *_a, **_k: None)


def _tela_com_texto_na_linha(texto: str, linha: int, extra: str = "") -> str:
    """Monta uma tela onde ``texto`` começa na coluna 1 da ``linha`` indicada."""
    prefixo = "." * ((linha - 1) * LARGURA)
    return prefixo + texto + extra


def _controle(menu_ok=True):
    c = MagicMock(spec=ControleTerminal3270)
    # linha_comando_disponivel (_menu): extrair_texto devolve a linha de comando.
    c.extrair_texto.return_value = (
        _menu.TEXTO_LINHA_COMANDO if menu_ok else "OUTRA TELA"
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


# ----- habilitação a nível de ÓRGÃO (upag opcional, SIAPE desde 22/07/2026) -----


def _tela_com_linhas(conteudos: dict[int, str]) -> str:
    """Monta uma tela com um texto por linha indicada (as demais, em branco)."""
    max_linha = max(conteudos)
    linhas = ["." * LARGURA for _ in range(max_linha)]
    for linha, texto in conteudos.items():
        linhas[linha - 1] = texto.ljust(LARGURA, ".")[:LARGURA]
    return "".join(linhas)


def test_upag_e_opcional_chamada_apenas_com_orgao():
    troca = TrocaHabilitacao(_controle(), "40805")
    assert troca.upag == ""


@pytest.mark.parametrize("upag_bruto", [None, "", "   "])
def test_upag_normaliza_valores_vazios(upag_bruto):
    troca = TrocaHabilitacao(_controle(), "40805", upag_bruto)
    assert troca.upag == ""


def test_candidatos_busca_com_upag_tem_dois_exato_primeiro():
    troca = TrocaHabilitacao(_controle(), "40805", "000000002")
    candidatos = troca._candidatos_busca()
    assert len(candidatos) == 2
    assert candidatos[0][1].startswith("ÓRGÃO+UPAG")
    assert candidatos[1][1].startswith("nível ÓRGÃO")


def test_candidatos_busca_sem_upag_tem_um_nivel_orgao():
    troca = TrocaHabilitacao(_controle(), "40805")
    candidatos = troca._candidatos_busca()
    assert len(candidatos) == 1
    assert candidatos[0][1].startswith("nível ÓRGÃO")


def test_tela_antiga_com_upag_acha_exato_mesmo_com_nivel_orgao_presente():
    """Ordem dos candidatos: o exato ÓRGÃO+UPAG tem prioridade sobre o nível
    ÓRGÃO mesmo quando as DUAS linhas existem na tela (não pode inverter — quem
    tem os dois tipos de acesso não pode "subir de nível" silenciosamente)."""
    c = _controle()
    tela = _tela_com_linhas(
        {
            12: "40805      ORGAO             OPERAC    22JUL2026            NAO",
            13: "40805 000000002 UNIDADE       OPERAC    01JAN2026            NAO",
        }
    )
    c.copiar_tela.return_value = tela

    TrocaHabilitacao(c, "40805", "000000002").trocar()

    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert enviados.count("{TAB}") == 1  # linha 13 (exato), não a 12 (nível órgão)


def test_tela_nova_nivel_orgao_via_fallback_quando_exato_nao_existe():
    """Tela nova (habilitação a nível de ÓRGÃO, SIAPE 22/07/2026): o exato
    ÓRGÃO+UPAG não existe mais, mas o fallback de nível ÓRGÃO encontra — e o
    regex não confunde com órgãos vizinhos (40804/40806)."""
    c = _controle()
    tela = _tela_com_linhas(
        {
            12: "26000           ORGAO             OPERAC    22JUL2026            NAO",
            13: "40806           ORGAO             OPERAC    22JUL2026            NAO",
            14: "40805           ORGAO             OPERAC    22JUL2026            NAO",
            15: "40804           ORGAO             OPERAC    22JUL2026            NAO",
        }
    )
    c.copiar_tela.return_value = tela

    # o regex de nível ÓRGÃO casa exatamente 1 vez na tela (não pega 40804/40806)
    padrao = re.compile(re.escape("40805") + r"\s+ORGAO\b")
    assert len(padrao.findall(tela)) == 1

    TrocaHabilitacao(c, "40805", "000000002").trocar()

    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert enviados.count("{TAB}") == 2  # linha 14 - 12


def test_tela_nova_sem_upag_encontra_direto():
    c = _controle()
    tela = _tela_com_linhas(
        {12: "40805           ORGAO             OPERAC    22JUL2026            NAO"}
    )
    c.copiar_tela.return_value = tela

    TrocaHabilitacao(c, "40805").trocar()

    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert "X" in enviados
    assert enviados.count("{TAB}") == 0  # linha 12 - 12


def test_habilitacao_nao_encontrada_lista_candidatos_tentados():
    c = _controle()
    c.copiar_tela.return_value = "tela sem nenhum candidato e sem continua"
    with pytest.raises(HabilitacaoNaoEncontrada) as exc_info:
        TrocaHabilitacao(c, "40805", "000000002").trocar()
    mensagem = str(exc_info.value)
    assert "ÓRGÃO+UPAG" in mensagem
    assert "nível ÓRGÃO" in mensagem


def test_retrocompat_chamada_posicional_antiga():
    """Assinatura posicional antiga (controle, orgao, upag) continua válida."""
    c = _controle()
    tela = _tela_com_texto_na_linha("40805 000000002", 13)
    c.copiar_tela.return_value = tela

    TrocaHabilitacao(c, "40805", "000000002").trocar()

    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert "X" in enviados
