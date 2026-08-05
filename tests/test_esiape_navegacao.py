"""Testes de ``integra_gov.esiape`` — navegação CIS com DriverFake."""

from __future__ import annotations

import pytest

from integra_gov.esiape import navegacao as nav
from integra_gov.esiape.exceptions import (
    AutenticacaoNaoConfirmada,
    EsiapeError,
    HabilitacaoNaoEncontrada,
    MenuInacessivel,
    TransacaoNaoAbriu,
)


def test_excecoes_sao_esiape_error():
    for exc in (MenuInacessivel, AutenticacaoNaoConfirmada,
                TransacaoNaoAbriu, HabilitacaoNaoEncontrada):
        assert issubclass(exc, EsiapeError)


def test_transacao_nao_abriu_carrega_contexto():
    exc = TransacaoNaoAbriu("TROCAHAB", '[data-testtoolid="x"]')
    assert exc.transacao == "TROCAHAB"
    assert exc.seletor_confirmacao == '[data-testtoolid="x"]'
    assert "TROCAHAB" in str(exc)


def test_habilitacao_nao_encontrada_lista_codigos():
    exc = HabilitacaoNaoEncontrada("00000", ["11111", "22222"])
    assert exc.orgao == "00000"
    assert exc.codigos_visiveis == ["11111", "22222"]
    assert "11111" in str(exc)


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)


class ElementoFake:
    """Elemento DOM roteirizado (visibilidade, atributos, texto, cliques)."""

    def __init__(self, visivel=True, atributos=None, texto=""):
        self.visivel = visivel
        self.atributos = atributos or {}
        self.text = texto
        self.cliques = 0
        self.teclas = []

    def is_displayed(self):
        return self.visivel

    def get_attribute(self, nome):
        return self.atributos.get(nome)

    def click(self):
        self.cliques += 1

    def clear(self):
        pass

    def send_keys(self, *teclas):
        self.teclas.extend(teclas)


class FrameFake:
    """Nó da árvore de frames: filhos (iframes) + elementos por seletor."""

    def __init__(self, nome="", visivel=True):
        self.nome = nome
        self.visivel = visivel
        self.filhos: list[FrameFake] = []
        self.elementos: dict[str, list[ElementoFake]] = {}


class _SwitchToFake:
    def __init__(self, driver):
        self._d = driver

    def default_content(self):
        self._d._caminho = []

    def parent_frame(self):
        if self._d._caminho:
            self._d._caminho.pop()

    def frame(self, ref):
        atual = self._d._frame_atual()
        if isinstance(ref, ElementoFake):
            self._d._caminho.append(self._d._indice_do_iframe[id(ref)])
            return
        for i, filho in enumerate(atual.filhos):
            if ref in (filho.nome, i):
                self._d._caminho.append(i)
                return
        raise Exception(f"no such frame: {ref}")

    def window(self, handle):
        self._d.janela_atual = handle


class DriverFake:
    """Driver Selenium roteirizado sobre uma árvore de FrameFake."""

    def __init__(self, raiz: FrameFake):
        self.raiz = raiz
        self._caminho: list[int] = []
        self._indice_do_iframe: dict[int, int] = {}
        self.switch_to = _SwitchToFake(self)
        self.window_handles = ["principal"]
        self.janela_atual = "principal"
        self.fechadas: list[str] = []
        self.scripts: list[str] = []
        self.resultado_script = None  # valor fixo OU callable(script, *args)
        self.url = ""

    # -- infraestrutura --
    def _frame_atual(self) -> FrameFake:
        frame = self.raiz
        for i in self._caminho:
            frame = frame.filhos[i]
        return frame

    # -- API Selenium usada pela navegação --
    def find_elements(self, by, valor):
        atual = self._frame_atual()
        if valor == "iframe":
            saida = []
            for i, filho in enumerate(atual.filhos):
                el = ElementoFake(visivel=filho.visivel,
                                  atributos={"name": filho.nome, "id": filho.nome})
                self._indice_do_iframe[id(el)] = i
                saida.append(el)
            return saida
        return atual.elementos.get(valor, [])

    def find_element(self, by, valor):
        els = self.find_elements(by, valor)
        if not els:
            raise Exception(f"no such element: {valor}")
        return els[0]

    def execute_script(self, script, *args):
        self.scripts.append(script)
        if callable(self.resultado_script):
            return self.resultado_script(script, *args)
        return self.resultado_script

    @property
    def current_window_handle(self):
        return self.janela_atual

    def close(self):
        self.fechadas.append(self.janela_atual)
        self.window_handles = [h for h in self.window_handles
                               if h != self.janela_atual]

    def get(self, url):
        self.url = url


def _arvore_menu(com_lupa=True):
    """Raiz com WA0 oculto (tela velha COM lupa) e WA1 visível."""
    raiz = FrameFake()
    wa0 = FrameFake("WA0", visivel=False)
    wa0.elementos[nav.SELETOR_LUPA] = [ElementoFake()]  # tela morta!
    wa1 = FrameFake("WA1", visivel=True)
    if com_lupa:
        wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]
    raiz.filhos = [wa0, wa1]
    return raiz


def test_procurar_ignora_frame_oculto_com_o_seletor():
    driver = DriverFake(_arvore_menu(com_lupa=True))
    caminho = nav.procurar_em_frames(driver, nav.SELETOR_LUPA)
    assert caminho == ("WA1",)  # achou no visível, NUNCA no WA0 oculto


def test_procurar_devolve_none_sem_seletor_visivel():
    driver = DriverFake(_arvore_menu(com_lupa=False))
    assert nav.procurar_em_frames(driver, nav.SELETOR_LUPA) is None


def test_esperar_seletor_timeout_devolve_none():
    driver = DriverFake(_arvore_menu(com_lupa=False))
    assert nav.esperar_seletor(driver, nav.SELETOR_LUPA, timeout=0.05) is None


def test_limpar_overlay_esconde_cortina_presa():
    driver = DriverFake(FrameFake())
    # 1ª consulta: cortina presente; após o JS de esconder: ausente
    respostas = iter([True, True, 0, False])  # presente, presente, esconde, sumiu

    def roteiro(script, *args):
        return next(respostas)

    driver.resultado_script = roteiro
    assert nav.limpar_overlay(driver, timeout=0.05) is True


def test_limpar_overlay_sem_cortina_retorna_imediato():
    driver = DriverFake(FrameFake())
    driver.resultado_script = False  # overlay_presente() -> False
    assert nav.limpar_overlay(driver, timeout=0.05) is True
    assert len(driver.scripts) == 1  # não tentou esconder


def test_fechar_janelas_extras_fecha_e_volta_ao_principal():
    driver = DriverFake(FrameFake())
    driver.window_handles = ["principal", "popup1", "popup2"]
    principal = nav.fechar_janelas_extras(driver, "principal")
    assert principal == "principal"
    assert driver.fechadas == ["popup1", "popup2"]
    assert driver.janela_atual == "principal"


def test_fechar_popups_cis_clica_o_x_do_topo():
    raiz = FrameFake()
    x = ElementoFake(atributos={"id": "TITLEBAR0_2CLOSE"})
    raiz.elementos[nav.SELETOR_POPUP_FECHAR] = [x]
    driver = DriverFake(raiz)
    assert nav.fechar_popups_cis(driver) == 1
    assert x.cliques == 1


def test_fechar_popups_cis_ignora_x_invisivel():
    raiz = FrameFake()
    raiz.elementos[nav.SELETOR_POPUP_FECHAR] = [ElementoFake(visivel=False)]
    driver = DriverFake(raiz)
    assert nav.fechar_popups_cis(driver) == 0
