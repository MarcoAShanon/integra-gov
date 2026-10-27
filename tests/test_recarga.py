"""Testes de ``integra_gov.sei.recarga`` e do seu uso em ``gerar_documento`` —
sem navegador real.

O driver fake tem um único frame (``ifrConteudoVisualizacao``) cuja página é
trocada algumas consultas depois do clique, e pode "cair para o topo" como o
ChromeDriver faz no SEI 5.0.4 quando a página nova chega durante um comando.
"""

import functools
from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait

from integra_gov.sei import gerar_documento as gd
from integra_gov.sei import recarga
from integra_gov.sei.exceptions import SeiNavegacaoError

FRAME = "ifrConteudoVisualizacao"


class _Navegador:
    def __init__(self, *, troca_em=None, cai_para_o_topo=False):
        self.troca_em = troca_em  # consultas até a página nova (None = não troca)
        self.cai_para_o_topo = cai_para_o_topo
        self.no_topo = False
        self.pagina = {"marcada": False, "n": 1}
        self.consultas = 0
        self.navegando = False
        nav = self

        class _SwitchTo:
            def default_content(self):
                nav.no_topo = True

            def frame(self, nome):
                assert nome == FRAME, nome
                nav.no_topo = False

        self.switch_to = _SwitchTo()

    def clicar(self):
        """Clique que troca a página do frame."""
        self.navegando = True
        if self.cai_para_o_topo:
            self.no_topo = True

    def execute_script(self, script, *args):
        if self.navegando and self.troca_em is not None:
            self.consultas += 1
            if self.consultas >= self.troca_em:
                self.navegando = False
                self.pagina = {"marcada": False, "n": self.pagina["n"] + 1}
        if self.no_topo:
            return [] if "frameElement" in script else None
        if "frameElement" in script:
            return [FRAME]
        if "= true" in script:
            self.pagina["marcada"] = True
            return None
        if "!window." in script:
            return not self.pagina["marcada"] and not self.navegando
        return None


@pytest.fixture(autouse=True)
def polling_rapido(monkeypatch):
    monkeypatch.setattr(
        recarga, "WebDriverWait", functools.partial(WebDriverWait, poll_frequency=0.01)
    )


def _marcar_e_clicar(nav):
    caminho = recarga.caminho_do_frame(nav)
    recarga.marcar_pagina(nav)
    nav.clicar()
    return caminho


def test_detecta_a_pagina_nova():
    nav = _Navegador(troca_em=3)
    caminho = _marcar_e_clicar(nav)
    assert recarga.aguardar_pagina_nova(nav, caminho, 1) is True
    assert nav.pagina["n"] == 2 and not nav.no_topo


def test_volta_ao_frame_quando_o_driver_cai_para_o_topo():
    nav = _Navegador(troca_em=3, cai_para_o_topo=True)
    caminho = _marcar_e_clicar(nav)
    assert caminho == [FRAME]
    assert recarga.aguardar_pagina_nova(nav, caminho, 1) is True
    assert not nav.no_topo


def test_sem_troca_devolve_false_e_fica_no_frame():
    nav = _Navegador(troca_em=None)
    caminho = _marcar_e_clicar(nav)
    nav.no_topo = True
    assert recarga.aguardar_pagina_nova(nav, caminho, 0.1) is False
    assert not nav.no_topo


# ----- gerar_documento._selecionar_tipo -----


class _NavegadorTipos(_Navegador):
    """Tela "Escolha o Tipo": o link do tipo troca a página pelo formulário."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.link = MagicMock(name="link do tipo")
        self.link.click.side_effect = self.clicar

    def find_element(self, by, valor):
        if self.no_topo:
            raise NoSuchElementException(valor)
        return self.link


@pytest.fixture
def tela_tipos(monkeypatch):
    monkeypatch.setattr(gd.time, "sleep", lambda *_a: None)
    monkeypatch.setattr(gd, "TIMEOUT_FORM", 0.2)
    monkeypatch.setattr(
        gd.EC, "element_to_be_clickable", lambda loc: (lambda d: d.find_element(*loc))
    )


def test_tipo_espera_o_formulario_e_devolve_o_frame(tela_tipos):
    """Inclusão 9 de 27/10/2026: depois do clique em "Externo" o driver caiu
    para o topo e o formulário nunca foi achado."""
    nav = _NavegadorTipos(troca_em=3, cai_para_o_topo=True)
    caminho = gd._selecionar_tipo(nav, MagicMock(name="filtro"), "Externo", 1)
    assert caminho == [FRAME]
    assert nav.pagina["n"] == 2 and not nav.no_topo


def test_tipo_sem_formulario_novo_e_erro_de_navegacao(tela_tipos):
    nav = _NavegadorTipos(troca_em=None)
    with pytest.raises(SeiNavegacaoError, match="não carregou"):
        gd._selecionar_tipo(nav, MagicMock(name="filtro"), "Externo", 1)
