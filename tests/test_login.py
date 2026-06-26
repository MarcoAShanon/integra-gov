"""Testes de ``integra.sei.login`` — sem navegador real.

``WebDriverWait`` é trocado por um fake que, a cada ``.until(...)``, consome o
próximo evento de uma fila configurada pelo teste: ``("ret", valor)`` retorna
``valor``; ``("raise", exc)`` levanta ``exc``. Isso desacopla os testes dos
detalhes das condições do Selenium e exercita o mapeamento de fluxo/exceções.
A ordem dos eventos segue a ordem das chamadas ``.until`` em ``logar()``.
"""

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import TimeoutException

from integra.sei import login as mod
from integra.sei.exceptions import CredenciaisInvalidas, SeiLoginError
from integra.sei.login import LoginSei


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


def _login(driver):
    return LoginSei(driver, "https://sei.exemplo.gov.br", "MGI", "user", "senha")


def test_montar_url_login():
    assert mod.montar_url_login("https://sei.exemplo.gov.br/", "MGI") == (
        "https://sei.exemplo.gov.br/sip/modulos/MF/login_especial/"
        "login_especial.php?sigla_orgao_sistema=MGI&sigla_sistema=SEI"
    )


def test_logar_sucesso(fila):
    driver = MagicMock()
    driver.find_elements.return_value = []  # sem div de erro
    fila.extend([
        ("ret", MagicMock()),            # txtUsuario
        ("ret", MagicMock()),            # pwdSenha
        ("ret", MagicMock()),            # selOrgao
        ("ret", MagicMock()),            # Acessar
        ("raise", TimeoutException()),   # sem alerta de erro
        ("ret", MagicMock()),            # página inicial confirmada
    ])
    _login(driver).logar()  # não levanta = sucesso


def test_logar_credenciais_invalidas(fila):
    driver = MagicMock()
    alerta = MagicMock()
    fila.extend([
        ("ret", MagicMock()),  # txtUsuario
        ("ret", MagicMock()),  # pwdSenha
        ("ret", MagicMock()),  # selOrgao
        ("ret", MagicMock()),  # Acessar
        ("ret", alerta),       # alerta presente → credenciais inválidas
    ])
    with pytest.raises(CredenciaisInvalidas):
        _login(driver).logar()
    alerta.accept.assert_called_once()


def test_logar_formulario_nao_carrega(fila):
    driver = MagicMock()
    fila.extend([("raise", TimeoutException())])  # txtUsuario não aparece
    with pytest.raises(SeiLoginError):
        _login(driver).logar()


def test_logar_nao_confirmado(fila):
    driver = MagicMock()
    driver.find_elements.return_value = []
    fila.extend([
        ("ret", MagicMock()),            # txtUsuario
        ("ret", MagicMock()),            # pwdSenha
        ("ret", MagicMock()),            # selOrgao
        ("ret", MagicMock()),            # Acessar
        ("raise", TimeoutException()),   # sem alerta
        ("raise", TimeoutException()),   # página inicial não confirma
    ])
    with pytest.raises(SeiLoginError):
        _login(driver).logar()


def test_logar_tolera_orgao_ausente(fila):
    driver = MagicMock()
    driver.find_elements.return_value = []
    fila.extend([
        ("ret", MagicMock()),            # txtUsuario
        ("ret", MagicMock()),            # pwdSenha
        ("raise", TimeoutException()),   # selOrgao ausente → tolerado
        ("ret", MagicMock()),            # Acessar
        ("raise", TimeoutException()),   # sem alerta
        ("ret", MagicMock()),            # confirma
    ])
    _login(driver).logar()  # não levanta
