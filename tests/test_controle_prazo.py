"""Testes de ``integra_gov.sei.controle_prazo`` — parte pura (Selenium mockado).

Cobre a validação do prazo em dias (``1..9999``) e o fluxo de
``definir``/``excluir`` contra um WebDriver falso: as chamadas de
``WebDriverWait``/``expected_conditions`` do módulo só precisam de
``find_element``/``switch_to.alert``, então um fake mínimo basta. A navegação
(``clicar_icone_barra``) é neutralizada — abrir a tela real do SEI fica para a
verificação ao vivo.
"""

from __future__ import annotations

import pytest
from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchElementException,
)

from integra_gov.sei import controle_prazo as cp
from integra_gov.sei.controle_prazo import ControlePrazo
from integra_gov.sei.exceptions import ControlePrazoError, SeiNavegacaoError


# ----- fakes de Selenium -----


class _FakeElemento:
    """Elemento sempre visível e habilitado que registra as interações."""

    def __init__(self):
        self.clicado = False
        self.limpo = False
        self.enviado = None

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def click(self):
        self.clicado = True

    def clear(self):
        self.limpo = True

    def send_keys(self, valor):
        self.enviado = valor


class _FakeAlerta:
    def __init__(self):
        self.aceito = False
        self.text = ""

    def accept(self):
        self.aceito = True


class _FakeSwitchTo:
    def __init__(self, driver):
        self._driver = driver

    @property
    def alert(self):
        if self._driver.alerta is None:
            raise NoAlertPresentException()
        return self._driver.alerta

    def default_content(self):
        pass

    def frame(self, ref):
        pass


class _FakeDriver:
    """Driver mínimo para o fluxo ``WebDriverWait``/``EC`` do módulo.

    ``elementos`` mapeia o *value* do localizador (o XPath) para o elemento
    devolvido por ``find_element``; ausência levanta ``NoSuchElementException``
    — que o ``WebDriverWait`` ignora, esgota o tempo e o módulo converte em
    ``ControlePrazoError``.
    """

    def __init__(self, elementos=None, alerta=None):
        self.elementos = elementos or {}
        self.alerta = alerta
        self.switch_to = _FakeSwitchTo(self)
        self.buscas = []

    def find_element(self, by, value):
        self.buscas.append((by, value))
        try:
            return self.elementos[value]
        except KeyError:
            raise NoSuchElementException(value)

    def find_elements(self, by, value):
        elemento = self.elementos.get(value)
        return [elemento] if elemento is not None else []


def _driver_para_definir():
    """Driver com todos os elementos do fluxo ``definir`` presentes."""
    elementos = {
        ControlePrazo.XPATH_OPCAO_DIAS: _FakeElemento(),
        ControlePrazo.XPATH_CAMPO_DIAS: _FakeElemento(),
        ControlePrazo.XPATH_BTN_CONFIRMAR: _FakeElemento(),
    }
    return _FakeDriver(elementos=elementos)


@pytest.fixture(autouse=True)
def clicar_icone_falso(monkeypatch):
    """Neutraliza ``clicar_icone_barra`` e registra as chamadas (título, timeout)."""
    chamadas = []

    def _falso(driver, titulo, *, timeout=10, estabilizar_apos_no=0.0):
        chamadas.append((titulo, timeout))

    monkeypatch.setattr(cp, "clicar_icone_barra", _falso)
    return chamadas


# ----- definir: validação de dias -----


@pytest.mark.parametrize("dias", [1, 30, 9999])
def test_definir_aceita_dias_validos(dias, clicar_icone_falso):
    driver = _driver_para_definir()

    ControlePrazo(driver, timeout=1).definir(dias)

    # o valor foi digitado em txtDias como string (o campo foi limpo antes)
    campo = driver.elementos[ControlePrazo.XPATH_CAMPO_DIAS]
    assert campo.limpo is True
    assert campo.enviado == str(dias)
    # a opção "dias" e a confirmação foram acionadas
    assert driver.elementos[ControlePrazo.XPATH_OPCAO_DIAS].clicado is True
    assert driver.elementos[ControlePrazo.XPATH_BTN_CONFIRMAR].clicado is True
    # o ícone certo foi acionado com o timeout da instância
    assert clicar_icone_falso == [(ControlePrazo.ICONE, 1)]


@pytest.mark.parametrize("dias", [0, -1, 10000, 100000])
def test_definir_rejeita_dias_fora_da_faixa(dias, clicar_icone_falso):
    driver = _driver_para_definir()

    with pytest.raises(ValueError):
        ControlePrazo(driver).definir(dias)

    # validação vem antes de qualquer navegação/interação com a tela
    assert clicar_icone_falso == []
    assert driver.buscas == []


@pytest.mark.parametrize("dias", [True, False, 1.0, "30", None])
def test_definir_rejeita_tipos_invalidos(dias, clicar_icone_falso):
    with pytest.raises(ValueError):
        ControlePrazo(_FakeDriver()).definir(dias)

    assert clicar_icone_falso == []


# ----- definir: falhas de UI viram ControlePrazoError -----


def test_definir_traduz_erro_de_navegacao(monkeypatch):
    def _raiser(driver, titulo, *, timeout=10, estabilizar_apos_no=0.0):
        raise SeiNavegacaoError("ícone 'Controle de Prazo' não encontrado")

    monkeypatch.setattr(cp, "clicar_icone_barra", _raiser)

    with pytest.raises(ControlePrazoError):
        ControlePrazo(_FakeDriver(), timeout=0).definir(30)


def test_definir_sem_opcao_dias_levanta():
    # nem a opção "dias" aparece → falha em _selecionar_opcao_dias (divOptDias)
    elementos = {
        ControlePrazo.XPATH_CAMPO_DIAS: _FakeElemento(),
        ControlePrazo.XPATH_BTN_CONFIRMAR: _FakeElemento(),
    }
    with pytest.raises(ControlePrazoError, match="divOptDias"):
        ControlePrazo(_FakeDriver(elementos=elementos), timeout=0).definir(30)


def test_definir_sem_campo_dias_levanta():
    # opção "dias" presente, mas o campo txtDias não aparece
    elementos = {ControlePrazo.XPATH_OPCAO_DIAS: _FakeElemento()}
    driver = _FakeDriver(elementos=elementos)

    with pytest.raises(ControlePrazoError, match="txtDias"):
        ControlePrazo(driver, timeout=0).definir(30)


def test_definir_sem_botao_confirmar_levanta():
    # opção e campo presentes, mas o botão de confirmar (sbmDefinirControlePrazo)
    # não aparece → falha em _confirmar
    elementos = {
        ControlePrazo.XPATH_OPCAO_DIAS: _FakeElemento(),
        ControlePrazo.XPATH_CAMPO_DIAS: _FakeElemento(),
    }
    with pytest.raises(ControlePrazoError, match="sbmDefinirControlePrazo"):
        ControlePrazo(_FakeDriver(elementos=elementos), timeout=0).definir(30)


# ----- excluir -----


def test_excluir_aceita_alerta():
    alerta = _FakeAlerta()
    elementos = {ControlePrazo.XPATH_BTN_EXCLUIR: _FakeElemento()}
    driver = _FakeDriver(elementos=elementos, alerta=alerta)

    ControlePrazo(driver, timeout=1).excluir()

    assert elementos[ControlePrazo.XPATH_BTN_EXCLUIR].clicado is True
    assert alerta.aceito is True


def test_excluir_sem_botao_levanta():
    # processo sem prazo: btnExcluir ausente → ControlePrazoError (não Timeout cru)
    driver = _FakeDriver(elementos={}, alerta=None)

    with pytest.raises(ControlePrazoError):
        ControlePrazo(driver, timeout=0).excluir()


def test_excluir_sem_alerta_levanta():
    # btnExcluir existe, mas nenhum alerta de confirmação aparece
    elementos = {ControlePrazo.XPATH_BTN_EXCLUIR: _FakeElemento()}
    driver = _FakeDriver(elementos=elementos, alerta=None)

    with pytest.raises(ControlePrazoError):
        ControlePrazo(driver, timeout=0).excluir()
