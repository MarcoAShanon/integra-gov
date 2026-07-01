"""Testes de ``integra.sei.nivel_acesso`` — sem navegador real (Selenium mockado).

``WebDriverWait`` vira um fake cujo ``.until(cond)`` chama ``cond(driver)``; os
``EC.*`` viram condições que fazem ``driver.find_element(*locator)``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from integra.sei import nivel_acesso as mod
from integra.sei.exceptions import NivelAcessoError
from integra.sei.nivel_acesso import configurar_nivel_acesso, validar_nivel_acesso


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


def _make_driver(missing=()):
    driver = MagicMock()
    els: dict[str, MagicMock] = {}

    def _find(by, value):
        if value in missing:
            raise NoSuchElementException(value)
        if value not in els:
            els[value] = MagicMock(name=value)
        return els[value]

    driver.find_element.side_effect = _find
    driver.els = els
    return driver


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
        "presence_of_element_located",
        lambda locator: (lambda d: d.find_element(*locator)),
    )
    monkeypatch.setattr(mod, "Select", MagicMock())
    return monkeypatch


# ----- validar_nivel_acesso -----


def test_validar_normaliza_para_minusculas():
    assert validar_nivel_acesso("PUBLICO", None) == "publico"


def test_validar_restrito_com_hipotese():
    assert validar_nivel_acesso("restrito", "Informação Pessoal") == "restrito"


def test_validar_restrito_sem_hipotese_levanta():
    with pytest.raises(ValueError):
        validar_nivel_acesso("restrito", None)


def test_validar_restrito_hipotese_so_espacos_levanta():
    with pytest.raises(ValueError):
        validar_nivel_acesso("restrito", "   ")


def test_validar_nivel_invalido_levanta():
    with pytest.raises(ValueError):
        validar_nivel_acesso("sigiloso", None)


def test_validar_nao_string_levanta():
    with pytest.raises(ValueError):
        validar_nivel_acesso(None, None)


# ----- configurar_nivel_acesso -----


def test_publico_marca_o_radio_publico(selenium):
    driver = _make_driver()
    configurar_nivel_acesso(driver, "publico")
    driver.els[mod.XPATH_OPT_PUBLICO].click.assert_called_once()


def test_restrito_marca_radio_e_seleciona_hipotese(selenium):
    driver = _make_driver()
    configurar_nivel_acesso(driver, "restrito", hipotese_legal="Informação Pessoal")
    driver.els[mod.XPATH_OPT_RESTRITO].click.assert_called_once()
    mod.Select.return_value.select_by_visible_text.assert_called_once_with(
        "Informação Pessoal"
    )


def test_radio_publico_ausente_levanta(selenium):
    driver = _make_driver(missing=(mod.XPATH_OPT_PUBLICO,))
    with pytest.raises(NivelAcessoError):
        configurar_nivel_acesso(driver, "publico")


def test_radio_restrito_ausente_levanta(selenium):
    driver = _make_driver(missing=(mod.XPATH_OPT_RESTRITO,))
    with pytest.raises(NivelAcessoError):
        configurar_nivel_acesso(driver, "restrito", hipotese_legal="X")


def test_dropdown_hipotese_ausente_levanta(selenium):
    driver = _make_driver(missing=(mod.ID_HIPOTESE_LEGAL,))
    with pytest.raises(NivelAcessoError):
        configurar_nivel_acesso(driver, "restrito", hipotese_legal="X")


def test_hipotese_inexistente_no_dropdown_levanta(selenium):
    driver = _make_driver()
    mod.Select.return_value.select_by_visible_text.side_effect = (
        NoSuchElementException("opção inexistente")
    )
    with pytest.raises(NivelAcessoError):
        configurar_nivel_acesso(driver, "restrito", hipotese_legal="Inexistente")
    # Esgotou o retry do AJAX antes de desistir.
    assert (
        mod.Select.return_value.select_by_visible_text.call_count
        == mod.TENTATIVAS_HIPOTESE
    )


def test_restrito_sem_hipotese_levanta_valueerror(selenium):
    with pytest.raises(ValueError):
        configurar_nivel_acesso(MagicMock(), "restrito")
