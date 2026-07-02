"""Testes de ``integra_gov.siape.acesso_web`` — sem navegador real (Selenium mockado).

``WebDriverWait`` vira um fake cujo ``.until(cond)`` chama ``cond(driver)``; os
``EC.*`` viram condições que fazem ``driver.find_element(*locator)`` (ou um
sentinela para o ``frame_to_be_available``).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)

from integra_gov.siape import acesso_web as mod
from integra_gov.siape.acesso_web import AcessoSiapeWeb
from integra_gov.siape.exceptions import AcessoSiapeError, TokenOtpError


class _FakeWait:
    def __init__(self, driver, timeout):
        self.driver = driver

    def until(self, cond):
        try:
            res = cond(self.driver)
        except NoSuchElementException:
            res = False
        if res:
            return res
        raise TimeoutException("condição não satisfeita")


@pytest.fixture
def selenium(monkeypatch):
    monkeypatch.setattr(mod, "WebDriverWait", _FakeWait)
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod.EC,
        "element_to_be_clickable",
        lambda locator: (lambda d: d.find_element(*locator)),
    )
    monkeypatch.setattr(
        mod.EC,
        "visibility_of_element_located",
        lambda locator: (lambda d: d.find_element(*locator)),
    )
    # frame_to_be_available: por padrão "não há iframe" (popup ausente).
    monkeypatch.setattr(
        mod.EC,
        "frame_to_be_available_and_switch_to_it",
        lambda locator: (lambda d: False),
    )
    return monkeypatch


def _driver(url_pos_login=True, token="123456"):
    driver = MagicMock()
    driver.current_url = (
        "https://www1.siapenet.gov.br/PaginaInicial.do" if url_pos_login else "x"
    )
    token_el = MagicMock()
    token_el.text = token

    def _find(by, value):
        if value == AcessoSiapeWeb.ID_TOKEN:
            return token_el
        return MagicMock()

    driver.find_element.side_effect = _find
    return driver


def test_executar_fluxo_feliz_retorna_otp(selenium):
    driver = _driver(token="654321")
    assert AcessoSiapeWeb(driver).executar() == "654321"
    driver.get.assert_called_once()  # navegou


def test_autenticacao_nao_concluida_levanta(selenium):
    driver = _driver(url_pos_login=False)  # URL nunca vira PaginaInicial.do
    with pytest.raises(AcessoSiapeError):
        AcessoSiapeWeb(driver, timeout_autenticacao=1).executar()


def test_otp_invalido_levanta(selenium):
    driver = _driver(token="abc")  # não são 6 dígitos
    with pytest.raises(TokenOtpError):
        AcessoSiapeWeb(driver).executar()


def test_otp_com_espacos_e_normalizado(selenium):
    driver = _driver(token="12 34 56")
    assert AcessoSiapeWeb(driver).executar() == "123456"


def test_certificado_ausente_levanta(selenium):
    driver = _driver()
    driver.find_element.side_effect = NoSuchElementException("sem botão")
    with pytest.raises(AcessoSiapeError):
        AcessoSiapeWeb(driver).executar()


def test_token_capturado_fica_em_token_otp(selenium):
    driver = _driver(token="111222")
    acesso = AcessoSiapeWeb(driver)
    acesso.executar()
    assert acesso.token_otp == "111222"


def test_otp_unicode_digit_levanta(selenium):
    # "²³⁴⁵⁶⁷": isdigit() retornaria True, mas não são dígitos ASCII digitáveis
    # no terminal 3270 — devem ser rejeitados.
    driver = _driver(token="²³⁴⁵⁶⁷")
    with pytest.raises(TokenOtpError):
        AcessoSiapeWeb(driver).executar()


def test_navegacao_falha_levanta_acesso_error(selenium):
    driver = _driver()
    driver.get.side_effect = WebDriverException("driver fora do ar")
    with pytest.raises(AcessoSiapeError):
        AcessoSiapeWeb(driver).executar()
