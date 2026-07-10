"""Testes de ``integra_gov.sei.iframes`` — sem navegador real (Selenium mockado).

Estratégia: ``EC.frame_to_be_available_and_switch_to_it`` é substituído para
devolver a própria tupla locator ``(By, nome)``, e ``WebDriverWait`` por um
fake cujo ``.until()`` considera sucesso apenas para os nomes de iframe
configurados em cada teste. Assim testamos a lógica de fallback/retry sem abrir
um navegador.
"""

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By

from integra_gov.sei import iframes
from integra_gov.sei.iframes import IframesSei


def _fake_wait_factory(frames_disponiveis):
    disponiveis = set(frames_disponiveis)

    class _FakeWait:
        def __init__(self, driver, timeout):
            self.driver = driver

        def until(self, cond):
            nome = cond[1]  # cond é a tupla (By, nome) do EC fake
            if nome in disponiveis:
                return True
            raise TimeoutException(f"{nome} indisponível")

    return _FakeWait


@pytest.fixture
def selenium(monkeypatch):
    """Patcha o EC e expõe um setter para configurar os iframes disponíveis."""
    monkeypatch.setattr(
        iframes.EC, "frame_to_be_available_and_switch_to_it", lambda loc: loc
    )
    monkeypatch.setattr(iframes.time, "sleep", lambda _s: None)

    def _configurar(frames):
        monkeypatch.setattr(iframes, "WebDriverWait", _fake_wait_factory(frames))

    return _configurar


def test_switch_visualizacao_sei4_usa_wrapper(selenium):
    selenium({"ifrConteudoVisualizacao", "ifrVisualizacao"})
    driver = MagicMock()
    assert iframes.switch_to_iframe_visualizacao(driver) == "ifrConteudoVisualizacao"
    driver.switch_to.default_content.assert_called()


def test_switch_visualizacao_sei3_cai_para_ifrvisualizacao(selenium):
    selenium({"ifrVisualizacao"})  # sem o wrapper do SEI 4.0
    driver = MagicMock()
    assert iframes.switch_to_iframe_visualizacao(driver) == "ifrVisualizacao"


def test_switch_visualizacao_sem_nenhum_levanta_timeout(selenium):
    selenium(set())
    driver = MagicMock()
    with pytest.raises(TimeoutException):
        iframes.switch_to_iframe_visualizacao(driver)


def test_navegar_arvore(selenium):
    selenium({"ifrArvore"})
    driver = MagicMock()
    assert IframesSei(driver, IframesSei.ARVORE).navegar() is True


def test_navegar_visualizacao(selenium):
    selenium({"ifrConteudoVisualizacao"})
    driver = MagicMock()
    assert IframesSei(driver, IframesSei.VISUALIZACAO).navegar() is True


def test_navegar_documento_html(selenium):
    selenium({"ifrConteudoVisualizacao", "ifrArvoreHtml"})
    driver = MagicMock()
    assert IframesSei(driver, IframesSei.DOCUMENTO_HTML).navegar() is True


def test_navegar_documento_html_desce_ifrvisualizacao_aninhado(selenium):
    """SEI 4.0: o ``ifrArvoreHtml`` fica no ``ifrVisualizacao`` ANINHADO dentro do
    wrapper; ``DOCUMENTO_HTML`` precisa descer essa camada antes de trocar para o
    ``ifrArvoreHtml`` (senão nunca o encontra)."""
    selenium({"ifrConteudoVisualizacao", "ifrArvoreHtml"})
    driver = MagicMock()
    IframesSei(driver, IframesSei.DOCUMENTO_HTML).navegar()
    driver.find_element.assert_called_with(By.NAME, "ifrVisualizacao")
    driver.switch_to.frame.assert_called_once_with(driver.find_element.return_value)


def test_descer_para_conteudo_noop_sem_ifrvisualizacao_aninhado():
    """SEI < 4.0 (sem wrapper): já estamos no ``ifrVisualizacao`` e não há camada
    aninhada — a descida é um no-op e não troca de frame."""
    driver = MagicMock()
    driver.find_element.side_effect = NoSuchElementException("sem aninhado")
    iframes.descer_para_conteudo_documento(driver)  # não deve levantar
    driver.switch_to.frame.assert_not_called()


def test_navegar_destino_desconhecido_levanta_valueerror(selenium):
    selenium(set())
    driver = MagicMock()
    with pytest.raises(ValueError):
        IframesSei(driver, "destino_invalido").navegar()


def test_navegar_retry_em_falha_transitoria(monkeypatch):
    monkeypatch.setattr(
        iframes.EC, "frame_to_be_available_and_switch_to_it", lambda loc: loc
    )
    monkeypatch.setattr(iframes.time, "sleep", lambda _s: None)
    chamadas = {"n": 0}

    class _FlakyWait:
        def __init__(self, driver, timeout):
            pass

        def until(self, cond):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise StaleElementReferenceException("transitório")
            return True

    monkeypatch.setattr(iframes, "WebDriverWait", _FlakyWait)
    driver = MagicMock()
    assert IframesSei(driver, IframesSei.ARVORE).navegar() is True
    assert chamadas["n"] == 2  # falhou 1x, sucesso na 2ª tentativa
