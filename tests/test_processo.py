"""Testes de ``integra_gov.sei.processo`` — sem navegador real (Selenium mockado).

``WebDriverWait`` é trocado por um fake cujo ``.until(cond)`` chama
``cond(driver)``: resultado *truthy* é sucesso; *falsy* ou ``NoSuchElement``
viram ``TimeoutException``. ``EC.element_to_be_clickable`` é trocado por uma
condição que apenas faz ``driver.find_element(*locator)``.
"""

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from integra_gov.sei import processo as mod
from integra_gov.sei.exceptions import (
    ProcessoNaoEncontrado,
    SeiNavegacaoError,
    SessaoExpiradaError,
)
from integra_gov.sei.processo import ProcessoSei


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
    return monkeypatch


def test_acessar_sucesso(selenium):
    driver = MagicMock()
    driver.title = "SEI - 19975.120202/2023-82"
    campo = MagicMock()
    driver.find_element.return_value = campo
    p = ProcessoSei(driver, "19975.120202/2023-82")
    assert p.acessar() == "19975.120202/2023-82"
    campo.send_keys.assert_any_call("19975.120202/2023-82")
    driver.switch_to.default_content.assert_called()
    assert p.numero == "19975.120202/2023-82"


def test_acessar_processo_nao_encontrado(selenium):
    driver = MagicMock()
    driver.title = "SEI - Pesquisa Rápida"  # título não contém o número
    driver.find_element.return_value = MagicMock()
    driver.find_elements.return_value = []
    p = ProcessoSei(driver, "00000.000000/0000-00")
    with pytest.raises(ProcessoNaoEncontrado):
        p.acessar()


def test_acessar_campo_pesquisa_ausente_levanta_navegacao(selenium):
    driver = MagicMock()
    driver.find_element.side_effect = NoSuchElementException("sem campo")
    driver.find_elements.return_value = []
    p = ProcessoSei(driver, "19975.120202/2023-82")
    with pytest.raises(SeiNavegacaoError):
        p.acessar()


def test_acessar_sem_numero_levanta_valueerror(selenium):
    p = ProcessoSei(MagicMock())
    with pytest.raises(ValueError):
        p.acessar()


def test_validacao_tolera_formatacao_diferente(selenium):
    driver = MagicMock()
    driver.title = "SEI - 19975.120202/2023-82"  # formatado
    driver.find_element.return_value = MagicMock()
    p = ProcessoSei(driver, "19975120202202382")  # apenas dígitos
    assert p.acessar() == "19975120202202382"


def test_ir_para_raiz_sucesso(selenium):
    driver = MagicMock()
    no_raiz = MagicMock()
    driver.find_element.return_value = no_raiz
    fake_iframes = MagicMock()
    fake_iframes.ARVORE = "arvore"
    selenium.setattr(mod, "IframesSei", fake_iframes)
    ProcessoSei(driver, "19975.120202/2023-82").ir_para_raiz()
    no_raiz.click.assert_called_once()
    fake_iframes.return_value.navegar.assert_called_once()


def _driver_login(ids_presentes):
    """Driver fake com find_element falhando (campo ausente) e find_elements
    configurado (página de login ou não)."""
    driver = MagicMock()
    driver.find_element.side_effect = NoSuchElementException("sem campo")
    presentes = set(ids_presentes)
    driver.find_elements.side_effect = (
        lambda by, valor: ["el"] if valor in presentes else []
    )
    return driver


def test_acessar_sessao_caida_levanta_sessao_expirada(selenium):
    driver = _driver_login({"txtUsuario", "pwdSenha"})
    with pytest.raises(SessaoExpiradaError):
        ProcessoSei(driver, "19975.120202/2023-82").acessar()


def test_acessar_sessao_viva_mantem_navegacao_error(selenium):
    """Regressão: campo ausente SEM página de login segue SeiNavegacaoError."""
    driver = _driver_login(set())
    with pytest.raises(SeiNavegacaoError):
        ProcessoSei(driver, "19975.120202/2023-82").acessar()


def test_acessar_pos_enter_sessao_caida_levanta_sessao_expirada(selenium):
    """Expiração REAL: a página antiga segue renderizada (campo de pesquisa OK),
    o ENTER faz round-trip sem sessão e o SIP redireciona ao login — a falha
    aparece na CONFIRMAÇÃO (título), que também precisa do guard (achado da
    verificação ao vivo)."""
    driver = MagicMock()
    driver.title = "SEI - Pesquisa Rápida"  # título nunca vira o do processo
    driver.find_element.return_value = MagicMock()  # campo AINDA existe
    presentes = {"txtUsuario", "pwdSenha"}  # pós-ENTER: página de login
    driver.find_elements.side_effect = (
        lambda by, valor: ["el"] if valor in presentes else []
    )
    with pytest.raises(SessaoExpiradaError):
        ProcessoSei(driver, "19975.120202/2023-82").acessar()


def test_ir_para_raiz_propaga_sessao_expirada(selenium):
    """Prova de propagação fim-a-fim: SessaoExpiradaError vinda do funil de
    iframes ATRAVESSA o módulo (o `except TimeoutException` do ir_para_raiz não
    a captura — ela não é TimeoutException nem SeiNavegacaoError)."""
    driver = MagicMock()
    fake_iframes = MagicMock()
    fake_iframes.ARVORE = "arvore"
    fake_iframes.return_value.navegar.side_effect = SessaoExpiradaError("caiu")
    selenium.setattr(mod, "IframesSei", fake_iframes)
    with pytest.raises(SessaoExpiradaError):
        ProcessoSei(driver, "19975.120202/2023-82").ir_para_raiz()
