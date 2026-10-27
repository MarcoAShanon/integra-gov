"""Testes de ``integra_gov.sei.barra_icones`` — sem navegador real.

``IframesSei`` é neutralizado (a navegação de frame tem testes próprios em
``test_iframes``) e ``WebDriverWait``/``EC`` viram fakes: ``until(cond)`` chama
``cond(driver)`` e as condições resolvem via ``driver.find_element``. O que
interessa aqui é a TIPIFICAÇÃO da falha: nó ou ícone ausente com a página de
login na tela é sessão caída, não erro de navegação.
"""

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from integra_gov.sei import barra_icones as bi
from integra_gov.sei import recarga
from integra_gov.sei.barra_icones import clicar_icone_barra
from integra_gov.sei.exceptions import SeiNavegacaoError, SessaoExpiradaError

IDS_LOGIN = ("txtUsuario", "pwdSenha")
XPATH_ICONE = '//img[@title="Enviar Processo"]'


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


def _driver(*, ausentes=(), na_pagina_de_login=False):
    """Driver fake.

    ``ausentes`` = seletores cuja busca levanta ``NoSuchElement``;
    ``na_pagina_de_login`` faz ``find_elements`` devolver os campos do SIP.

    O ``find_elements`` explícito é OBRIGATÓRIO: sem ele o MagicMock devolveria
    um objeto verdadeiro e ``sessao_expirada()`` leria QUALQUER driver como
    página de login.
    """
    driver = MagicMock()
    els: dict[str, MagicMock] = {}

    def _find(by, value):
        if value in ausentes:
            raise NoSuchElementException(value)
        if value not in els:
            els[value] = MagicMock(name=value)
        return els[value]

    driver.find_element.side_effect = _find
    driver.find_elements.side_effect = lambda by, value: (
        ["el"] if na_pagina_de_login and value in IDS_LOGIN else []
    )
    driver.els = els
    return driver


@pytest.fixture
def selenium(monkeypatch):
    monkeypatch.setattr(bi, "WebDriverWait", _FakeWait)
    monkeypatch.setattr(recarga, "WebDriverWait", _FakeWait)
    monkeypatch.setattr(bi, "IframesSei", MagicMock())
    monkeypatch.setattr(bi.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        bi.EC,
        "element_to_be_clickable",
        lambda locator: (lambda d: d.find_element(*locator)),
    )
    # O frame aninhado é fallback defensivo; aqui nunca está disponível.
    monkeypatch.setattr(
        bi.EC,
        "frame_to_be_available_and_switch_to_it",
        lambda locator: (lambda d: False),
    )
    return monkeypatch


def test_caminho_feliz_clica_o_icone(selenium):
    driver = _driver()
    clicar_icone_barra(driver, "Enviar Processo")
    assert driver.els[XPATH_ICONE].click.called


def test_no_selecionado_e_clicado_via_javascript(selenium):
    """Nó fora da área visível da árvore: o clique nativo dá "element click
    intercepted" no SEI 5.0.4 -- rola até ele e clica via JavaScript."""
    driver = _driver()
    clicar_icone_barra(driver, "Enviar Processo")
    no = driver.els[bi.CSS_NO_SELECIONADO]
    assert not no.click.called
    cliques_js = [c.args for c in driver.execute_script.call_args_list
                  if "scrollIntoView" in c.args[0]]
    assert len(cliques_js) == 1
    script, alvo = cliques_js[0]
    assert "arguments[0].click()" in script
    assert alvo is no


class _FakeWaitLaco:
    """Reavalia a condição até satisfazer (como o WebDriverWait real, sem esperar)."""

    def __init__(self, driver, timeout):
        self.driver = driver

    def until(self, cond):
        for _ in range(20):
            try:
                res = cond(self.driver)
            except NoSuchElementException:
                res = False
            if res:
                return res
        raise TimeoutException("condição não satisfeita")


def _scripts_da_visualizacao(eventos, recarrega_na_consulta):
    """``execute_script`` fake: caminho do frame, marca e "página nova?".
    A página nova aparece na consulta nº ``recarrega_na_consulta`` (0 = nunca)."""
    consultas = {"n": 0}

    def execute_script(script, *args):
        if "frameElement" in script:
            return ["ifrConteudoVisualizacao"]
        if "!window." in script:
            consultas["n"] += 1
            if recarrega_na_consulta and consultas["n"] >= recarrega_na_consulta:
                if "visualização recarregou" not in eventos:
                    eventos.append("visualização recarregou")
                return True
            return False
        return None

    return execute_script


def test_no_reclicado_espera_a_visualizacao_recarregar(selenium):
    """Re-clicar o nó selecionado SEMPRE recarrega a visualização (0,8–1,5s no
    SEI 5.0.4, conferido ao vivo). A pausa fixa de 1,2s perdia a corrida: o
    clique caía no ícone da página velha (e se perdia) ou, vindo de uma tela
    sem a barra, a busca descia para o frame aninhado errado. Agora espera a
    página da visualização ser trocada antes de procurar o ícone."""
    selenium.setattr(recarga, "WebDriverWait", _FakeWaitLaco)
    eventos = []
    driver = _driver()
    driver.execute_script.side_effect = _scripts_da_visualizacao(eventos, 3)
    icone = MagicMock(name="ícone")
    icone.click.side_effect = lambda: eventos.append("clicou o ícone")
    driver.els[XPATH_ICONE] = icone

    clicar_icone_barra(driver, "Enviar Processo")

    assert eventos == ["visualização recarregou", "clicou o ícone"]


def test_visualizacao_que_nao_recarrega_nao_trava(selenium):
    """Se a página não for trocada (SEI que não recarrega), segue em frente."""
    driver = _driver()
    driver.execute_script.side_effect = _scripts_da_visualizacao([], 0)
    clicar_icone_barra(driver, "Enviar Processo")
    assert driver.els[XPATH_ICONE].click.called


def test_no_ausente_com_sessao_viva_e_erro_de_navegacao(selenium):
    driver = _driver(ausentes={bi.CSS_NO_SELECIONADO})
    with pytest.raises(SeiNavegacaoError, match="nenhum nó selecionado"):
        clicar_icone_barra(driver, "Enviar Processo")


def test_no_ausente_na_pagina_de_login_e_sessao_expirada(selenium):
    driver = _driver(ausentes={bi.CSS_NO_SELECIONADO}, na_pagina_de_login=True)
    with pytest.raises(SessaoExpiradaError):
        clicar_icone_barra(driver, "Enviar Processo")


def test_icone_ausente_com_sessao_viva_e_erro_de_navegacao(selenium):
    driver = _driver(ausentes={XPATH_ICONE})
    with pytest.raises(SeiNavegacaoError, match="não encontrado ou não clicável"):
        clicar_icone_barra(driver, "Enviar Processo")


def test_icone_ausente_na_pagina_de_login_e_sessao_expirada(selenium):
    driver = _driver(ausentes={XPATH_ICONE}, na_pagina_de_login=True)
    with pytest.raises(SessaoExpiradaError):
        clicar_icone_barra(driver, "Enviar Processo")


def test_a_causa_original_e_encadeada(selenium):
    driver = _driver(ausentes={XPATH_ICONE}, na_pagina_de_login=True)
    with pytest.raises(SessaoExpiradaError) as excinfo:
        clicar_icone_barra(driver, "Enviar Processo")
    assert isinstance(excinfo.value.__cause__, TimeoutException)
