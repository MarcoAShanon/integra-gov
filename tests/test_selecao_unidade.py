"""Testes de ``integra_gov.sei.selecao_unidade`` — sem navegador real.

``WebDriverWait`` é trocado por um fake que consome uma fila de eventos
(``("ret", v)`` retorna ``v``; ``("raise", exc)`` levanta ``exc``). As chamadas
a ``driver.find_elements`` são configuradas por teste (por ``side_effect``).
"""

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import TimeoutException

from integra_gov.sei import selecao_unidade as mod
from integra_gov.sei.exceptions import SeiNavegacaoError, UnidadeNaoEncontrada
from integra_gov.sei.selecao_unidade import SelecaoUnidade


@pytest.fixture
def fila(monkeypatch):
    eventos = []

    class _FilaWait:
        def __init__(self, driver, timeout):
            pass

        def until(self, _cond):
            tipo, payload = eventos.pop(0)
            if tipo == "raise":
                raise payload
            return payload

    monkeypatch.setattr(mod, "WebDriverWait", _FilaWait)
    return eventos


def _elemento(texto):
    el = MagicMock()
    el.text = texto
    el.is_displayed.return_value = True
    return el


def test_ja_na_unidade_retorna_false(fila):
    driver = MagicMock()
    driver.find_elements.return_value = [_elemento("MGI-X")]
    fila.append(("ret", MagicMock()))  # presença em unidade_atual
    assert SelecaoUnidade(driver).selecionar("MGI-X") is False


def test_troca_unidade_sucesso(fila):
    driver = MagicMock()
    driver.find_elements.side_effect = [
        [_elemento("MGI-ATUAL")],  # _ler_unidade_atual (unidade_atual)
        [_elemento("MGI-ATUAL")],  # _abrir_tela_troca (link)
    ]
    fila.extend([
        ("ret", MagicMock()),  # presença em unidade_atual
        ("ret", MagicMock()),  # radio da unidade alvo
        ("ret", True),         # confirmação da troca
    ])
    assert SelecaoUnidade(driver).selecionar("MGI-ALVO") is True
    driver.execute_script.assert_called_once()  # clicou no radio via JS


def test_unidade_inexistente_levanta_unidadenaoencontrada(fila):
    driver = MagicMock()
    driver.find_elements.side_effect = [
        [_elemento("MGI-ATUAL")],  # _ler_unidade_atual
        [_elemento("MGI-ATUAL")],  # _abrir_tela_troca (link)
    ]
    fila.extend([
        ("ret", MagicMock()),           # presença em unidade_atual
        ("raise", TimeoutException()),  # radio da unidade não existe
    ])
    with pytest.raises(UnidadeNaoEncontrada):
        SelecaoUnidade(driver).selecionar("MGI-ALVO")


def test_sem_link_de_troca_levanta_navegacao(fila):
    driver = MagicMock()
    driver.find_elements.side_effect = [
        [_elemento("MGI-ATUAL")],  # _ler_unidade_atual (unidade_atual)
        [],                         # _abrir_tela_troca: sem lnkInfraUnidade
    ]
    fila.append(("ret", MagicMock()))  # presença em unidade_atual
    with pytest.raises(SeiNavegacaoError):
        SelecaoUnidade(driver).selecionar("MGI-ALVO")


def _radio(sigla, descricao, orgao, valor):
    radio = MagicMock()
    radio.get_attribute.side_effect = lambda attr: {
        "title": sigla,
        "value": valor,
    }.get(attr, "")
    celulas = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
    celulas[2].text = descricao
    celulas[3].text = orgao
    tr = MagicMock()
    tr.find_elements.return_value = celulas
    radio.find_element.return_value = tr
    return radio


def test_listar_unidades_devolve_dados_estruturados(fila):
    driver = MagicMock()
    link = _elemento("MGI-ATUAL")
    r1 = _radio("MGI-A", "Unidade A", "MGI", "1")
    r2 = _radio("MGI-B", "Unidade B", "MGI", "2")
    # 1ª chamada: _abrir_tela_troca (link); 2ª: radios da lista
    driver.find_elements.side_effect = [[link], [r1, r2]]
    fila.append(("ret", MagicMock()))  # presença de ao menos um radio

    unidades = SelecaoUnidade(driver).listar_unidades()

    assert [u.sigla for u in unidades] == ["MGI-A", "MGI-B"]
    assert unidades[0].descricao == "Unidade A"
    assert unidades[1].id == "2"
