"""Testes de ``integra.sei.iniciar_processo`` — sem navegador real.

``WebDriverWait`` vira um fake cujo ``.until(cond)`` chama ``cond(driver)``;
``EC.element_to_be_clickable`` / ``EC.presence_of_element_located`` viram
condições que só fazem ``driver.find_element(*locator)``. Assim, TODA busca de
elemento passa por ``driver.find_element(by, value)`` — e a fixture roteia por
``value`` para devolver um mock distinto por campo (ou levantar ``NoSuchElement``).
"""

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.keys import Keys

from integra.sei import iniciar_processo as mod
from integra.sei.exceptions import IniciarProcessoError, NivelAcessoError
from integra.sei.iniciar_processo import IniciarProcesso


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
    """Driver fake: ``find_element(by, value)`` devolve um mock por ``value``
    (memorizado em ``driver.els``); ``value`` em ``missing`` levanta NoSuchElement."""
    driver = MagicMock()
    driver.title = "SEI - 19975.014466/2026-41"  # NUP do processo criado
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
    # Por padrão, nenhum alerta de validação após "Salvar".
    monkeypatch.setattr(mod.EC, "alert_is_present", lambda: (lambda d: False))
    # O nível de acesso tem testes próprios (test_nivel_acesso); aqui é stub.
    monkeypatch.setattr(mod, "configurar_nivel_acesso", MagicMock())
    return monkeypatch


# ----- validação de argumentos (sem driver) -----


def test_tipo_obrigatorio():
    with pytest.raises(ValueError):
        IniciarProcesso(MagicMock(), "")


def test_nivel_acesso_invalido():
    with pytest.raises(ValueError):
        IniciarProcesso(MagicMock(), "Tipo X", nivel_acesso="secreto")


def test_restrito_exige_hipotese_legal():
    with pytest.raises(ValueError):
        IniciarProcesso(MagicMock(), "Tipo X", nivel_acesso="restrito")


# ----- fluxo -----


def test_iniciar_devolve_o_numero_do_processo(selenium):
    driver = _make_driver(missing=(IniciarProcesso.XPATH_EXIBIR_TODOS,))
    driver.title = "SEI - 00688.003899/2023-35"
    numero = IniciarProcesso(driver, "Tipo X").iniciar()
    assert numero == "00688.003899/2023-35"


def test_numero_ausente_no_titulo_levanta(selenium):
    driver = _make_driver(missing=(IniciarProcesso.XPATH_EXIBIR_TODOS,))
    driver.title = "SEI - Iniciar Processo"  # salvou, mas sem NUP no título
    with pytest.raises(IniciarProcessoError):
        IniciarProcesso(driver, "Tipo X").iniciar()


def test_fluxo_minimo_so_tipo(selenium):
    driver = _make_driver(missing=(IniciarProcesso.XPATH_EXIBIR_TODOS,))
    IniciarProcesso(driver, "Arrecadação: Cobrança").iniciar()

    # Menu acionado e tipo digitado no filtro.
    driver.els[IniciarProcesso.XPATH_MENU_INICIAR].click.assert_called_once()
    driver.els[IniciarProcesso.ID_FILTRO_TIPO].send_keys.assert_any_call(
        "Arrecadação: Cobrança"
    )
    # Confirmou o tipo destacado (ENTER no elemento em foco) e salvou.
    driver.switch_to.active_element.send_keys.assert_called_once_with(Keys.ENTER)
    driver.els[IniciarProcesso.ID_SALVAR].click.assert_called_once()


def test_fluxo_completo_restrito(selenium):
    driver = _make_driver(
        missing=(
            IniciarProcesso.XPATH_EXIBIR_TODOS,
            IniciarProcesso.XPATH_ASSUNTO_PENDENTE,  # sem classificação padrão
        )
    )
    IniciarProcesso(
        driver,
        "Tipo X",
        especificacao="Minha especificação",
        assunto="Pessoal: Férias",
        interessado="Fulano de Tal",
        observacao="uma observação",
        nivel_acesso="restrito",
        hipotese_legal="Informação Pessoal",
    ).iniciar()

    driver.els[IniciarProcesso.ID_ESPECIFICACAO].send_keys.assert_any_call(
        "Minha especificação"
    )
    driver.els[IniciarProcesso.ID_ASSUNTO].send_keys.assert_any_call(
        "Pessoal: Férias"
    )
    driver.els[IniciarProcesso.ID_INTERESSADO].send_keys.assert_any_call(
        "Fulano de Tal"
    )
    driver.els[IniciarProcesso.ID_OBSERVACOES].send_keys.assert_any_call(
        "uma observação"
    )
    # O nível de acesso é delegado ao componente compartilhado.
    mod.configurar_nivel_acesso.assert_called_once_with(
        driver, "restrito", hipotese_legal="Informação Pessoal", timeout=10
    )
    driver.els[IniciarProcesso.ID_SALVAR].click.assert_called_once()


def test_campos_opcionais_nao_sao_tocados_quando_ausentes(selenium):
    driver = _make_driver(missing=(IniciarProcesso.XPATH_EXIBIR_TODOS,))
    IniciarProcesso(driver, "Tipo X").iniciar()
    # Sem especificação/assunto/interessado/observação informados → IDs nunca buscados.
    buscados = {c.args[1] for c in driver.find_element.call_args_list}
    assert IniciarProcesso.ID_ESPECIFICACAO not in buscados
    assert IniciarProcesso.ID_ASSUNTO not in buscados
    assert IniciarProcesso.ID_INTERESSADO not in buscados
    assert IniciarProcesso.ID_OBSERVACOES not in buscados


def test_acesso_delega_ao_componente_compartilhado(selenium):
    driver = _make_driver(missing=(IniciarProcesso.XPATH_EXIBIR_TODOS,))
    IniciarProcesso(driver, "Tipo X").iniciar()  # nível público (padrão)
    mod.configurar_nivel_acesso.assert_called_once_with(
        driver, "publico", hipotese_legal=None, timeout=10
    )


def test_salvar_com_alerta_de_validacao_levanta(selenium):
    driver = _make_driver(missing=(IniciarProcesso.XPATH_EXIBIR_TODOS,))
    driver.switch_to.alert.text = "Informe o nível de acesso."
    # Após "Salvar", um alerta de validação significa que o processo NÃO foi criado.
    selenium.setattr(
        mod.EC, "alert_is_present", lambda: (lambda d: d.switch_to.alert)
    )
    with pytest.raises(IniciarProcessoError):
        IniciarProcesso(driver, "Tipo X").iniciar()


def test_menu_ausente_levanta_erro(selenium):
    driver = _make_driver(missing=(IniciarProcesso.XPATH_MENU_INICIAR,))
    with pytest.raises(IniciarProcessoError):
        IniciarProcesso(driver, "Tipo X").iniciar()


def test_filtro_de_tipo_nao_carrega_levanta_erro(selenium):
    driver = _make_driver(
        missing=(
            IniciarProcesso.XPATH_EXIBIR_TODOS,
            IniciarProcesso.ID_FILTRO_TIPO,
        )
    )
    with pytest.raises(IniciarProcessoError):
        IniciarProcesso(driver, "Tipo X").iniciar()


def test_salvar_ausente_levanta_erro(selenium):
    driver = _make_driver(
        missing=(
            IniciarProcesso.XPATH_EXIBIR_TODOS,
            IniciarProcesso.ID_SALVAR,
        )
    )
    with pytest.raises(IniciarProcessoError):
        IniciarProcesso(driver, "Tipo X").iniciar()


def test_interessado_aceita_alerta(selenium):
    driver = _make_driver(missing=(IniciarProcesso.XPATH_EXIBIR_TODOS,))
    IniciarProcesso(driver, "Tipo X", interessado="Fulano").iniciar()
    driver.switch_to.alert.accept.assert_called_once()


def test_interessado_sem_alerta_nao_quebra(selenium):
    driver = _make_driver(missing=(IniciarProcesso.XPATH_EXIBIR_TODOS,))
    # Acessar `.alert` levanta NoAlertPresentException → ramo "sem alerta".
    type(driver.switch_to).alert = property(
        lambda self: (_ for _ in ()).throw(NoAlertPresentException())
    )
    IniciarProcesso(driver, "Tipo X", interessado="Fulano").iniciar()
    driver.els[IniciarProcesso.ID_SALVAR].click.assert_called_once()


def test_observacao_pedida_mas_ausente_levanta_erro(selenium):
    driver = _make_driver(
        missing=(
            IniciarProcesso.XPATH_EXIBIR_TODOS,
            IniciarProcesso.ID_OBSERVACOES,  # form sem campo de observação
        )
    )
    # Observação foi pedida explicitamente: não pode ser descartada em silêncio.
    with pytest.raises(IniciarProcessoError):
        IniciarProcesso(driver, "Tipo X", observacao="algo").iniciar()


def test_remove_classificacao_padrao_quando_presente(selenium):
    # XPATH_ASSUNTO_PENDENTE e XPATH_REMOVER_ASSUNTOS presentes → remoção real.
    driver = _make_driver(missing=(IniciarProcesso.XPATH_EXIBIR_TODOS,))
    IniciarProcesso(driver, "Tipo X", assunto="Pessoal: Férias").iniciar()
    driver.els[IniciarProcesso.XPATH_ASSUNTO_PENDENTE].click.assert_called_once()
    driver.els[IniciarProcesso.XPATH_REMOVER_ASSUNTOS].click.assert_called_once()


def test_classificacao_padrao_sem_botao_remover_levanta_erro(selenium):
    # Bug corrigido: pendente presente mas botão Remover ausente NÃO é engolido.
    driver = _make_driver(
        missing=(
            IniciarProcesso.XPATH_EXIBIR_TODOS,
            IniciarProcesso.XPATH_REMOVER_ASSUNTOS,  # botão sumiu
        )
    )
    with pytest.raises(IniciarProcessoError):
        IniciarProcesso(driver, "Tipo X", assunto="Pessoal: Férias").iniciar()


def test_erro_de_nivel_acesso_propaga(selenium):
    # Uma falha no componente de nível de acesso aborta a criação do processo.
    driver = _make_driver(missing=(IniciarProcesso.XPATH_EXIBIR_TODOS,))
    mod.configurar_nivel_acesso.side_effect = NivelAcessoError("falhou")
    with pytest.raises(NivelAcessoError):
        IniciarProcesso(driver, "Tipo X").iniciar()
