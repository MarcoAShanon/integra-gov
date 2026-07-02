"""Testes de ``integra_gov.sei.tela_aviso`` — sem navegador real.

``WebDriverWait`` é trocado por um fake que consome uma fila de eventos
(``("ret", botao)`` retorna o botão; ``("raise", exc)`` levanta ``exc``).
"""

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
)

from integra_gov.sei import tela_aviso as mod
from integra_gov.sei.tela_aviso import fechar_tela_aviso


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


def test_sem_aviso_retorna_zero(fila):
    fila.append(("raise", TimeoutException()))
    assert fechar_tela_aviso(MagicMock()) == 0


def test_fecha_um_aviso(fila):
    botao = MagicMock()
    fila.extend([("ret", botao), ("raise", TimeoutException())])
    assert fechar_tela_aviso(MagicMock()) == 1
    botao.click.assert_called_once()


def test_fecha_multiplos_avisos(fila):
    fila.extend([
        ("ret", MagicMock()),
        ("ret", MagicMock()),
        ("raise", TimeoutException()),
    ])
    assert fechar_tela_aviso(MagicMock()) == 2


def test_fallback_para_javascript_quando_clique_interceptado(fila):
    botao = MagicMock()
    botao.click.side_effect = ElementClickInterceptedException("coberto")
    driver = MagicMock()
    fila.extend([("ret", botao), ("raise", TimeoutException())])
    assert fechar_tela_aviso(driver) == 1
    driver.execute_script.assert_called_once()  # caiu no clique via JS
