"""Testes de ``integra_gov.sei.enviar_processo`` — lógica pura (Selenium mockado).

Cobre o fluxo de envio (formulário, autocomplete com fallback por TAB, confirmação
em ``selUnidades``, alerta de erro) e as falhas, sem WebDriver real:
``clicar_icone_barra`` e ``switch_to_iframe_visualizacao`` são neutralizados e um
driver falso responde ao mínimo que ``WebDriverWait``/``EC`` consomem. A seleção
do órgão é *best-effort* (o driver não expõe ``selOrgao`` → o passo só avisa).
Abrir a tela real fica para a verificação ao vivo.
"""

from __future__ import annotations

import pytest
from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchElementException,
)
from selenium.webdriver.common.by import By

from integra_gov.sei import enviar_processo as ep
from integra_gov.sei.enviar_processo import EnviarProcesso
from integra_gov.sei.exceptions import EnviarProcessoError, SeiNavegacaoError

UNIDADE = "MGI-SGP-DECIPEX-CGBEN"


# ----- fakes de Selenium -----


class _El:
    def __init__(self, text="", options=None):
        self.text = text
        self.clicado = False
        self.enviado = None
        self._selected = False
        self._options = options or []

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def is_selected(self):
        return self._selected

    def click(self):
        self.clicado = True
        self._selected = True

    def clear(self):
        pass

    def send_keys(self, valor):
        self.enviado = valor

    def find_elements(self, by, value):
        return self._options if value == "option" else []


class _Opt:
    def __init__(self, text):
        self.text = text


class _Alerta:
    def __init__(self, texto):
        self.text = texto
        self.aceito = False

    def accept(self):
        self.aceito = True


class _SwitchTo:
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


class _Driver:
    """``elementos`` mapeia id → elemento (find_element por By.ID); a sugestão do
    autocomplete é devolvida para qualquer XPath com "AutoCompletar"."""

    def __init__(self, *, elementos=None, sugestao=None, alerta=None):
        self.elementos = elementos or {}
        self.sugestao = sugestao
        self.alerta = alerta
        self.switch_to = _SwitchTo(self)

    def find_element(self, by, value):
        if by == By.XPATH and "AutoCompletar" in value:
            if self.sugestao is None:
                raise NoSuchElementException(value)
            return self.sugestao
        try:
            return self.elementos[value]
        except KeyError:
            raise NoSuchElementException(value)

    def execute_script(self, script, *args):
        # emula o clique via JS (checkbox/botão Enviar)
        for a in args:
            if hasattr(a, "click"):
                a.click()
        return None


@pytest.fixture(autouse=True)
def _neutraliza(monkeypatch):
    """Neutraliza clicar_icone_barra e switch_to_iframe_visualizacao."""

    def _clicar(driver, titulo, *, timeout=10, estabilizar_apos_no=0.0):
        pass

    def _switch(driver, timeout=10):
        return "ifrConteudoVisualizacao"

    monkeypatch.setattr(ep, "clicar_icone_barra", _clicar)
    monkeypatch.setattr(ep, "switch_to_iframe_visualizacao", _switch)


def _driver_ok(
    unidade=UNIDADE,
    *,
    sugestao_ok=True,
    na_lista=True,
    alerta=None,
    com_manter=True,
    com_enviar=True,
):
    """Driver do fluxo feliz. Sem ``selOrgao`` → a seleção de órgão só avisa."""
    lista = _El(options=[_Opt(f"{unidade} - Coordenação")] if na_lista else [])
    elementos = {
        EnviarProcesso.ID_UNIDADE: _El(),
        EnviarProcesso.ID_LISTA_UNIDADES: lista,
    }
    if com_manter:
        elementos[EnviarProcesso.ID_MANTER_ABERTO] = _El()
    if com_enviar:
        elementos[EnviarProcesso.ID_ENVIAR] = _El()
    sugestao = _El(text=unidade) if sugestao_ok else None
    return _Driver(elementos=elementos, sugestao=sugestao, alerta=alerta)


# ----- validação e helper puro -----


@pytest.mark.parametrize("valor", ["", "   "])
def test_unidade_destino_obrigatoria(valor):
    with pytest.raises(ValueError):
        EnviarProcesso(_Driver(), valor)


def test_orgao_da_sigla():
    assert EnviarProcesso._orgao_da_sigla("MGI-SGP-DECIPEX-CGBEN") == "MGI"
    assert EnviarProcesso._orgao_da_sigla("CGBEN") is None


# ----- caminhos de falha -----


def test_icone_nao_encontrado_levanta(monkeypatch):
    def _raiser(driver, titulo, *, timeout=10, estabilizar_apos_no=0.0):
        raise SeiNavegacaoError("ícone 'Enviar Processo' não encontrado")

    monkeypatch.setattr(ep, "clicar_icone_barra", _raiser)
    with pytest.raises(EnviarProcessoError):
        EnviarProcesso(_Driver(), UNIDADE, timeout=0).enviar()


def test_formulario_nao_carrega_levanta():
    with pytest.raises(EnviarProcessoError, match="txtUnidade"):
        EnviarProcesso(_Driver(), UNIDADE, timeout=0).enviar()


def test_unidade_nao_entrou_na_lista_levanta():
    driver = _driver_ok(na_lista=False)  # nem clique nem TAB populam selUnidades
    with pytest.raises(EnviarProcessoError, match="não entrou na lista"):
        EnviarProcesso(driver, UNIDADE, timeout=0).enviar()


def test_subunidade_nao_conta_como_a_unidade():
    # selUnidades só com uma SUB-unidade (sigla prefixada pela nossa) → NÃO casa
    # a unidade exata → falha (fix do prefixo pai/filha).
    driver = _driver_ok(na_lista=False)
    driver.elementos[EnviarProcesso.ID_LISTA_UNIDADES]._options = [
        _Opt(f"{UNIDADE}-SUB - Sub-unidade qualquer")
    ]
    with pytest.raises(EnviarProcessoError, match="não entrou na lista"):
        EnviarProcesso(driver, UNIDADE, timeout=0).enviar()


def test_manter_aberto_sem_checkbox_levanta():
    driver = _driver_ok(com_manter=False)
    with pytest.raises(EnviarProcessoError, match="chkSinManterAberto"):
        EnviarProcesso(driver, UNIDADE, manter_aberto=True, timeout=0).enviar()


def test_sem_botao_enviar_levanta():
    driver = _driver_ok(com_enviar=False)
    with pytest.raises(EnviarProcessoError, match="sbmEnviar"):
        EnviarProcesso(driver, UNIDADE, timeout=0).enviar()


def test_alerta_de_erro_apos_enviar_levanta():
    driver = _driver_ok(alerta=_Alerta("Unidade destino inválida."))
    with pytest.raises(EnviarProcessoError, match="recusou o envio"):
        EnviarProcesso(driver, UNIDADE, timeout=1).enviar()
    assert driver.alerta.aceito is True


# ----- caminho feliz e resiliência do autocomplete -----


def test_envio_bem_sucedido():
    driver = _driver_ok()
    assert EnviarProcesso(driver, UNIDADE, timeout=0).enviar() is None
    # digitou a unidade, clicou a sugestão do autocomplete e clicou Enviar
    assert driver.elementos[EnviarProcesso.ID_UNIDADE].enviado == UNIDADE
    assert driver.sugestao.clicado is True
    assert driver.elementos[EnviarProcesso.ID_ENVIAR].clicado is True


def test_sucesso_mesmo_sem_clicar_sugestao():
    # a sugestão não aparece, mas a unidade entra em selUnidades (via TAB/outra
    # via) → o envio é dado por bom pela verificação de selUnidades.
    driver = _driver_ok(sugestao_ok=False, na_lista=True)
    assert EnviarProcesso(driver, UNIDADE, timeout=0).enviar() is None
    assert driver.elementos[EnviarProcesso.ID_ENVIAR].clicado is True


def test_manter_aberto_marca_checkbox():
    driver = _driver_ok()
    EnviarProcesso(driver, UNIDADE, manter_aberto=True, timeout=0).enviar()
    assert driver.elementos[EnviarProcesso.ID_MANTER_ABERTO].clicado is True
