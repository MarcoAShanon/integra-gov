"""Testes de ``integra_gov.sei.concluir_processo`` — lógica pura (Selenium mockado).

Cobre os três caminhos que o SEI apresenta (formulário SEI 4.x, alert de
confirmação legado, e bloqueio por documento restrito) e as falhas técnicas,
sem WebDriver real: ``clicar_icone_barra`` é neutralizado e um driver falso
responde ao mínimo que ``WebDriverWait``/``EC`` consomem (``switch_to.alert``,
``find_element``/``find_elements`` do iframe/botão/crítica). Abrir a tela real
fica para a verificação ao vivo.
"""

from __future__ import annotations

import pytest
from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchElementException,
    UnexpectedAlertPresentException,
)

from integra_gov.sei import concluir_processo as cp
from integra_gov.sei.concluir_processo import ConcluirProcesso
from integra_gov.sei.exceptions import (
    ConcluirProcessoError,
    ProcessoBloqueadoError,
    SeiNavegacaoError,
)


# ----- fakes de Selenium -----


class _FakeElemento:
    def __init__(self, texto=""):
        self.text = texto
        self.clicado = False

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def click(self):
        self.clicado = True


class _FakeAlerta:
    def __init__(self, texto):
        self.text = texto
        self.aceito = False

    def accept(self):
        self.aceito = True


class _FakeSwitchTo:
    def __init__(self, driver):
        self._d = driver

    def default_content(self):
        pass

    def frame(self, ref):
        pass

    @property
    def alert(self):
        if self._d.alerta is None:
            raise NoAlertPresentException()
        return self._d.alerta


class _FakeDriver:
    """``elementos`` mapeia o value do localizador (id) para o elemento de
    ``find_element``; ``divs_erro`` sao as ``div.alert-danger`` do formulario."""

    def __init__(self, *, alerta=None, elementos=None, divs_erro=None):
        self.alerta = alerta
        self.elementos = elementos or {}
        self.divs_erro = divs_erro or []
        self.switch_to = _FakeSwitchTo(self)
        self.scripts = []

    def find_element(self, by, value):
        try:
            return self.elementos[value]
        except KeyError:
            raise NoSuchElementException(value)

    def find_elements(self, by, value):
        if value == ConcluirProcesso.CSS_ALERTA_ERRO:
            return self.divs_erro
        return []

    def execute_script(self, script, *args):
        self.scripts.append((script, args))
        for a in args:
            if hasattr(a, "click"):
                a.click()
        return None


@pytest.fixture(autouse=True)
def clicar_icone_falso(monkeypatch):
    """Neutraliza ``clicar_icone_barra`` (registra as chamadas)."""
    chamadas = []

    def _falso(driver, titulo, *, timeout=10, estabilizar_apos_no=0.0):
        chamadas.append((titulo, timeout, estabilizar_apos_no))

    monkeypatch.setattr(cp, "clicar_icone_barra", _falso)
    return chamadas


def _driver_form(*, com_salvar=True, com_iframe=True, divs_erro=None):
    """Driver do fluxo do formulario SEI 4.x (sem alert imediato)."""
    elementos = {}
    if com_iframe:
        elementos[ConcluirProcesso.ID_IFRAME_FORM] = _FakeElemento()
    if com_salvar:
        elementos[ConcluirProcesso.ID_BOTAO_SALVAR] = _FakeElemento()
    return _FakeDriver(elementos=elementos, divs_erro=divs_erro)


# ----- caminho: acionar o icone -----


def test_icone_nao_encontrado_levanta(monkeypatch):
    def _raiser(driver, titulo, *, timeout=10, estabilizar_apos_no=0.0):
        raise SeiNavegacaoError("ícone 'Concluir Processo' não encontrado")

    monkeypatch.setattr(cp, "clicar_icone_barra", _raiser)
    with pytest.raises(ConcluirProcessoError):
        ConcluirProcesso(_FakeDriver(), timeout=0).concluir()


# ----- caminho: alert imediato (bloqueio / confirmacao legado) -----


def test_bloqueio_por_alert_levanta_bloqueado():
    alerta = _FakeAlerta("Não é possível concluir o processo (documento restrito).")
    driver = _FakeDriver(alerta=alerta)
    with pytest.raises(ProcessoBloqueadoError):
        ConcluirProcesso(driver, timeout=1).concluir()
    assert alerta.aceito is True


def test_bloqueio_por_alert_sem_acento_levanta():
    # a marca de bloqueio sem acento também é reconhecida
    alerta = _FakeAlerta("Nao e possivel concluir o processo.")
    with pytest.raises(ProcessoBloqueadoError):
        ConcluirProcesso(_FakeDriver(alerta=alerta), timeout=1).concluir()


def test_alert_inesperado_no_clique_trata_bloqueio(monkeypatch):
    # um alert que surge JÁ no clique do ícone (UnexpectedAlertPresentException)
    # é lido e classificado — aqui, bloqueio.
    def _raiser(driver, titulo, *, timeout=10, estabilizar_apos_no=0.0):
        raise UnexpectedAlertPresentException("alerta durante o clique")

    monkeypatch.setattr(cp, "clicar_icone_barra", _raiser)
    alerta = _FakeAlerta("Não é possível concluir (documento restrito).")
    with pytest.raises(ProcessoBloqueadoError):
        ConcluirProcesso(_FakeDriver(alerta=alerta), timeout=1).concluir()
    assert alerta.aceito is True


def test_alert_inesperado_no_clique_confirmacao_conclui(monkeypatch):
    # mesmo caso, mas alert de confirmação legado → conclui (não levanta).
    def _raiser(driver, titulo, *, timeout=10, estabilizar_apos_no=0.0):
        raise UnexpectedAlertPresentException("alerta durante o clique")

    monkeypatch.setattr(cp, "clicar_icone_barra", _raiser)
    alerta = _FakeAlerta("Deseja concluir o processo?")
    ConcluirProcesso(_FakeDriver(alerta=alerta), timeout=1).concluir()  # não levanta
    assert alerta.aceito is True


def test_confirmacao_legado_conclui():
    alerta = _FakeAlerta("Deseja concluir o processo?")
    driver = _FakeDriver(alerta=alerta)
    ConcluirProcesso(driver, timeout=1).concluir()  # não levanta
    assert alerta.aceito is True


# ----- caminho: formulario SEI 4.x -----


def test_formulario_conclui_clicando_salvar(clicar_icone_falso):
    driver = _driver_form()
    assert ConcluirProcesso(driver, timeout=0).concluir() is None  # sucesso
    salvar = driver.elementos[ConcluirProcesso.ID_BOTAO_SALVAR]
    assert salvar.clicado is True
    # o execute_script clicou no PRÓPRIO botão Salvar (não em outro elemento)
    assert driver.scripts and driver.scripts[0][1][0] is salvar
    # o ícone certo foi acionado, com a estabilização anti-corrida
    assert clicar_icone_falso == [(ConcluirProcesso.ICONE, 0, cp.SETTLE_APOS_NO)]


def test_formulario_bloqueado_levanta():
    driver = _driver_form(
        com_salvar=False,
        divs_erro=[_FakeElemento("Não é possível concluir: documento restrito.")],
    )
    with pytest.raises(ProcessoBloqueadoError):
        ConcluirProcesso(driver, timeout=0).concluir()


def test_bloqueio_no_formulario_precede_salvar():
    # crítica de bloqueio presente E botão Salvar clicável → o bloqueio vence e
    # o Salvar NÃO é clicado (preserva a distinção bloqueado/concluído).
    driver = _driver_form(
        com_salvar=True,
        divs_erro=[_FakeElemento("Não é possível concluir: documento restrito.")],
    )
    with pytest.raises(ProcessoBloqueadoError):
        ConcluirProcesso(driver, timeout=0).concluir()
    assert driver.elementos[ConcluirProcesso.ID_BOTAO_SALVAR].clicado is False


def test_formulario_sem_salvar_levanta():
    driver = _driver_form(com_salvar=False)  # iframe ok, sem botão nem crítica
    with pytest.raises(ConcluirProcessoError, match="sbmSalvar"):
        ConcluirProcesso(driver, timeout=0).concluir()


def test_formulario_iframe_ausente_levanta():
    driver = _driver_form(com_iframe=False, com_salvar=False)
    with pytest.raises(ConcluirProcessoError, match="ifrConteudoVisualizacao"):
        ConcluirProcesso(driver, timeout=0).concluir()
