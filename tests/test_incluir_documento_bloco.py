"""Testes de ``integra_gov.sei.incluir_documento_bloco`` — lógica pura (Selenium
mockado).

Cobre a seleção do bloco (por value e por texto, placeholder filtrado, erro
listando as opções), a marcação dos protocolos (ausente → erro SEM confirmar;
já marcado → não re-clica; checkbox que não marca → erro), a navegação de
iframes (formulário no wrapper, no aninhado e no default) e a **confirmação pela
ausência de recusa** (verificada ao vivo no SEI 4.1.5: a tela do bloco NÃO muda
no sucesso — sem formulário sumindo, sem mensagem). O submit recarrega o iframe
(âncora fica *stale*); recusa = alerta imediato, alerta tardio, ou erro inline.
``clicar_icone_barra`` e as funções de iframe são neutralizados.
"""

from __future__ import annotations

import pytest
from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    UnexpectedAlertPresentException,
)
from selenium.webdriver.common.by import By

from integra_gov.sei import incluir_documento_bloco as idb
from integra_gov.sei.exceptions import BlocoAssinaturaError, SeiNavegacaoError
from integra_gov.sei.incluir_documento_bloco import IncluirDocumentoBloco

BLOCO = "123"
PROTOCOLOS = ["35551895", "37534896"]


# ----- fakes de Selenium -----


class _El:
    def __init__(self, text="", value="", options=None, selected=False):
        self.text = text
        self._value = value
        self._options = options or []
        self._selected = selected
        self.clicado = False

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def is_selected(self):
        return self._selected

    def click(self):
        # toggle: comportamento real de checkbox (duplo clique desmarcaria)
        self.clicado = True
        self._selected = not self._selected

    def get_attribute(self, name):
        return self._value if name == "value" else None

    def find_elements(self, by, value):
        return self._options if value == "option" else []


class _ElTeimoso(_El):
    """Checkbox cujo clique NÃO muda o estado (o SEI 'não pegou' o clique)."""

    def click(self):
        self.clicado = True  # clicou, mas _selected não muda


class _ElBloco(_El):
    """O ``selBloco`` — serve de âncora do *staleness*. Depois que o botão
    Incluir é clicado, ``is_enabled()`` reflete o que o SEI fez com o submit."""

    def __init__(self, driver, **kw):
        super().__init__(**kw)
        self._driver = driver

    def is_enabled(self):
        if not self._driver._incluir_clicado:
            return True
        if self._driver.alerta_tardio is not None:
            raise UnexpectedAlertPresentException(alert_text=self._driver.alerta_tardio)
        if self._driver.reload:
            raise StaleElementReferenceException("iframe recarregou (submit)")
        return True  # submit sem reload detectável → staleness expira (fallback)


class _ElBotaoIncluir(_El):
    def __init__(self, driver, **kw):
        super().__init__(**kw)
        self._driver = driver

    def click(self):
        super().click()
        self._driver._incluir_clicado = True


class _Alerta:
    def __init__(self, texto):
        self.text = texto
        self.aceito = False
        self.dispensado = False

    def accept(self):
        self.aceito = True

    def dismiss(self):
        self.dispensado = True


class _SwitchTo:
    def __init__(self, driver):
        self._d = driver

    def default_content(self):
        self._d.contexto = "default"

    def frame(self, ref):
        pass

    @property
    def alert(self):
        if self._d.alerta is None:
            raise NoAlertPresentException()
        return self._d.alerta


class _Driver:
    """``form_contexto`` restringe onde o ``selBloco`` existe ("wrapper",
    "aninhado", "default"; ``None`` = qualquer). ``reload`` diz se o submit
    recarrega o iframe (âncora fica stale). ``erro_inline`` = texto de um erro de
    validação inline (recusa sem alerta). ``alerta`` = diálogo imediato;
    ``alerta_tardio`` = diálogo que só aparece na espera do processamento."""

    def __init__(
        self,
        *,
        elementos=None,
        checkboxes=None,
        alerta=None,
        alerta_tardio=None,
        reload=True,
        erro_inline=None,
        form_contexto=None,
    ):
        self.elementos = elementos or {}
        self.checkboxes = checkboxes or {}
        self.alerta = alerta
        self.alerta_tardio = alerta_tardio
        self.reload = reload
        self.erro_inline = erro_inline
        self.form_contexto = form_contexto
        self.contexto = "default"
        self._incluir_clicado = False
        self.switch_to = _SwitchTo(self)

    def _contexto_ok(self):
        return self.form_contexto is None or self.contexto == self.form_contexto

    def find_element(self, by, value):
        if by == By.XPATH and 'type="checkbox"' in value:
            for protocolo, cb in self.checkboxes.items():
                if f'@title="{protocolo}"' in value:
                    return cb
            raise NoSuchElementException(value)
        if value == IncluirDocumentoBloco.ID_BLOCO and not self._contexto_ok():
            raise NoSuchElementException(value)
        try:
            return self.elementos[value]
        except KeyError:
            raise NoSuchElementException(value)

    def find_elements(self, by, value):
        if by == By.CSS_SELECTOR and self.erro_inline is not None:
            if value in IncluirDocumentoBloco.SELETORES_ERRO:
                return [_El(text=self.erro_inline)]
            return []
        if value == IncluirDocumentoBloco.ID_BLOCO:
            if not self._contexto_ok():
                return []
            return [self.elementos[value]] if value in self.elementos else []
        if by == By.XPATH and "checkbox" in value and "@title" in value:
            return list(self.checkboxes.values())
        return []

    def execute_script(self, script, *args):
        for a in args:
            if hasattr(a, "click"):
                a.click()
        return None


@pytest.fixture(autouse=True)
def _neutraliza(monkeypatch):
    """Neutraliza barra de ícones e iframes; os fakes de iframe mudam o
    ``driver.contexto`` para os testes de navegação. Zera a estabilização."""

    def _clicar(driver, titulo, *, timeout=10, estabilizar_apos_no=0.0):
        pass

    def _switch(driver, timeout=10):
        driver.contexto = "wrapper"
        return "ifrConteudoVisualizacao"

    def _descer(driver, timeout=10):
        driver.contexto = "aninhado"

    monkeypatch.setattr(idb, "clicar_icone_barra", _clicar)
    monkeypatch.setattr(idb, "switch_to_iframe_visualizacao", _switch)
    monkeypatch.setattr(idb, "descer_para_conteudo_documento", _descer)
    monkeypatch.setattr(idb, "ESTABILIZACAO_POS_BLOCO", 0)


def _driver_ok(
    *,
    protocolos=PROTOCOLOS,
    ja_marcados=(),
    teimosos=(),
    alerta=None,
    alerta_tardio=None,
    reload=True,
    erro_inline=None,
    com_incluir=True,
    form_contexto=None,
    opcoes=None,
):
    driver = _Driver(
        alerta=alerta,
        alerta_tardio=alerta_tardio,
        reload=reload,
        erro_inline=erro_inline,
        form_contexto=form_contexto,
    )
    opcoes = opcoes or [
        _El(text="Bloco Exante", value=BLOCO),
        _El(text="Outro bloco", value="999"),
    ]
    driver.elementos[IncluirDocumentoBloco.ID_BLOCO] = _ElBloco(driver, options=opcoes)
    if com_incluir:
        driver.elementos[IncluirDocumentoBloco.ID_INCLUIR] = _ElBotaoIncluir(driver)
    checkboxes = {}
    for p in protocolos:
        classe = _ElTeimoso if p in teimosos else _El
        checkboxes[p] = classe(selected=(p in ja_marcados))
    driver.checkboxes = checkboxes
    return driver


# ----- validação -----


@pytest.mark.parametrize("valor", ["", "   "])
def test_bloco_obrigatorio(valor):
    with pytest.raises(ValueError):
        IncluirDocumentoBloco(_Driver(), valor, PROTOCOLOS)


@pytest.mark.parametrize("protocolos", [[], ["", "  "]])
def test_protocolos_obrigatorios(protocolos):
    with pytest.raises(ValueError):
        IncluirDocumentoBloco(_Driver(), BLOCO, protocolos)


@pytest.mark.parametrize("protocolo", ["14022.014588/2024-11", 'abc"', "3555 1895"])
def test_protocolo_nao_numerico_levanta_valueerror(protocolo):
    with pytest.raises(ValueError, match="número do documento"):
        IncluirDocumentoBloco(_Driver(), BLOCO, [protocolo])


# ----- caminhos de falha -----


def test_icone_nao_encontrado_levanta(monkeypatch):
    def _raiser(driver, titulo, *, timeout=10, estabilizar_apos_no=0.0):
        raise SeiNavegacaoError("ícone não encontrado")

    monkeypatch.setattr(idb, "clicar_icone_barra", _raiser)
    with pytest.raises(BlocoAssinaturaError):
        IncluirDocumentoBloco(_Driver(), BLOCO, PROTOCOLOS, timeout=0).incluir()


def test_formulario_nao_carrega_levanta():
    with pytest.raises(BlocoAssinaturaError, match="selBloco"):
        IncluirDocumentoBloco(_Driver(), BLOCO, PROTOCOLOS, timeout=0).incluir()


def test_bloco_inexistente_levanta_listando_opcoes():
    driver = _driver_ok()
    with pytest.raises(BlocoAssinaturaError, match="Bloco Exante"):
        IncluirDocumentoBloco(driver, "777", PROTOCOLOS, timeout=0).incluir()


def test_placeholder_nao_aparece_na_listagem():
    opcoes = [
        _El(text="selecione", value="null"),
        _El(text="Bloco Exante", value=BLOCO),
    ]
    driver = _driver_ok(opcoes=opcoes)
    with pytest.raises(BlocoAssinaturaError) as excinfo:
        IncluirDocumentoBloco(driver, "777", PROTOCOLOS, timeout=0).incluir()
    assert "Bloco Exante" in str(excinfo.value)
    assert "null" not in str(excinfo.value)


def test_dropdown_so_com_placeholder_diz_nenhum():
    opcoes = [_El(text="selecione", value="null")]
    driver = _driver_ok(opcoes=opcoes)
    with pytest.raises(BlocoAssinaturaError, match="nenhum"):
        IncluirDocumentoBloco(driver, "777", PROTOCOLOS, timeout=0).incluir()


def test_protocolo_ausente_levanta_sem_confirmar_nem_marcar():
    driver = _driver_ok(protocolos=[PROTOCOLOS[0]])  # só o 1º tem checkbox
    with pytest.raises(BlocoAssinaturaError, match=PROTOCOLOS[1]):
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir()
    assert driver.elementos[IncluirDocumentoBloco.ID_INCLUIR].clicado is False
    assert driver.checkboxes[PROTOCOLOS[0]].clicado is False
    assert driver.contexto == "default"


def test_dois_protocolos_ausentes_listados_juntos():
    driver = _driver_ok(protocolos=[])  # nenhum checkbox na tela
    with pytest.raises(BlocoAssinaturaError) as excinfo:
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir()
    assert PROTOCOLOS[0] in str(excinfo.value)
    assert PROTOCOLOS[1] in str(excinfo.value)


def test_checkbox_que_nao_marca_levanta():
    driver = _driver_ok(teimosos=(PROTOCOLOS[0],))
    with pytest.raises(BlocoAssinaturaError, match="não foi possível marcar"):
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir()
    assert driver.elementos[IncluirDocumentoBloco.ID_INCLUIR].clicado is False


def test_sem_botao_incluir_levanta():
    driver = _driver_ok(com_incluir=False)
    with pytest.raises(BlocoAssinaturaError, match="sbmIncluir"):
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir()


def test_webdriverexception_crua_vira_erro_tipado():
    driver = _driver_ok()

    def _explode(script, *args):
        raise StaleElementReferenceException("stale")

    driver.execute_script = _explode
    with pytest.raises(BlocoAssinaturaError, match="falha inesperada") as excinfo:
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir()
    assert isinstance(excinfo.value.__cause__, StaleElementReferenceException)
    assert driver.contexto == "default"


# ----- confirmação: recusas -----


def test_alerta_imediato_e_dispensado_como_recusa():
    # dismiss (cancela) é o seguro: se for um confirm() de prosseguimento,
    # accept() CONFIRMARIA a inclusão junto com um erro falso.
    driver = _driver_ok(alerta=_Alerta("Documento já pertence a um bloco."))
    with pytest.raises(BlocoAssinaturaError, match="recusa"):
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=1).incluir()
    assert driver.alerta.dispensado is True
    assert driver.alerta.aceito is False


def test_alerta_tardio_vira_recusa():
    # diálogo que só aparece na espera do processamento (fora da janela do
    # _checar_alerta_erro) — é recusa, nunca sucesso.
    driver = _driver_ok(alerta_tardio="Documento já pertence a um bloco.")
    with pytest.raises(BlocoAssinaturaError, match="tardio"):
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=1).incluir()


def test_erro_inline_vira_recusa_com_texto():
    driver = _driver_ok(erro_inline="Bloco de assinatura já disponibilizado.")
    with pytest.raises(BlocoAssinaturaError, match="disponibilizado"):
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir()


# ----- confirmação: sucesso (a tela NÃO muda) -----


def test_inclusao_bem_sucedida():
    driver = _driver_ok()  # reload=True, sem erro
    resultado = IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir()
    assert resultado is None
    opcao = driver.elementos[IncluirDocumentoBloco.ID_BLOCO]._options[0]
    assert opcao.clicado is True  # bloco selecionado por value
    for p in PROTOCOLOS:
        assert driver.checkboxes[p].is_selected() is True
    assert driver.elementos[IncluirDocumentoBloco.ID_INCLUIR].clicado is True
    assert driver.contexto == "default"  # terminou fora do iframe


def test_sucesso_sem_reload_detectavel():
    # o submit não deixa a âncora stale de forma detectável; sem alerta e sem
    # erro inline → mesmo assim é sucesso (o SEI não expõe sinal positivo).
    driver = _driver_ok(reload=False)
    assert (
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir() is None
    )


def test_seleciona_bloco_por_texto():
    driver = _driver_ok()
    IncluirDocumentoBloco(driver, "Bloco Exante", PROTOCOLOS, timeout=0).incluir()
    assert driver.elementos[IncluirDocumentoBloco.ID_BLOCO]._options[0].clicado is True


def test_protocolo_ja_marcado_nao_reclica():
    driver = _driver_ok(ja_marcados=(PROTOCOLOS[0],))
    IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir()
    assert driver.checkboxes[PROTOCOLOS[0]].clicado is False  # já estava marcado
    assert driver.checkboxes[PROTOCOLOS[1]].clicado is True
    assert driver.elementos[IncluirDocumentoBloco.ID_INCLUIR].clicado is True


def test_botao_incluir_via_fallback_generico():
    # sem sbmIncluir; o botão só existe pelo XPath genérico.
    driver = _driver_ok(com_incluir=False)
    driver.elementos[IncluirDocumentoBloco.XPATH_INCLUIR_GENERICO] = _ElBotaoIncluir(
        driver
    )
    assert (
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir() is None
    )
    assert driver.elementos[IncluirDocumentoBloco.XPATH_INCLUIR_GENERICO].clicado


# ----- navegação de iframes (formulário em contextos diferentes) -----


def test_formulario_so_no_ifrvisualizacao_aninhado():
    driver = _driver_ok(form_contexto="aninhado")
    assert (
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir() is None
    )


def test_formulario_no_default_quando_iframes_falham(monkeypatch):
    def _switch_falha(driver, timeout=10):
        raise TimeoutException("sem iframe de visualização")

    monkeypatch.setattr(idb, "switch_to_iframe_visualizacao", _switch_falha)
    driver = _driver_ok(form_contexto="default")
    assert (
        IncluirDocumentoBloco(driver, BLOCO, PROTOCOLOS, timeout=0).incluir() is None
    )
