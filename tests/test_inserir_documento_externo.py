"""Testes de ``integra_gov.sei.inserir_documento_externo`` — sem navegador real.

Foco: a troca de série no formulário "Externo". No SEI 5.0.4 o ``selSerie`` tem
``onchange="trocarSerie()"``, que faz ``submit()`` do formulário: a página é
SUBSTITUÍDA cerca de 1s depois (conferido ao vivo). O que se preenche antes da
troca se perde — na execução EXANTE de 27/10/2026 o clique em "Restrito" caiu
na página velha e a nova chegou com a hipótese legal vazia.

O driver fake modela essa troca ASSÍNCRONA: depois da série, a página velha
continua "viva" por algumas interações e só então é trocada por uma nova (sem
os campos preenchidos). Elementos da página velha passam a dar
``StaleElementReferenceException``, como no Selenium.
"""

import functools

import pytest
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.support.ui import WebDriverWait

from integra_gov.sei import inserir_documento_externo as ide
from integra_gov.sei import recarga
from integra_gov.sei.exceptions import DocumentoExternoError
from integra_gov.sei.inserir_documento_externo import InserirDocumentoExterno


class _Pagina:
    def __init__(self, serie=""):
        self.viva = True
        self.serie = serie
        self.valores = {}
        self.cliques = []


class _Elemento:
    def __init__(self, driver, pagina, id_):
        self.driver = driver
        self.pagina = pagina
        self.id = id_

    def _checar(self):
        self.driver._passar_tempo()
        if not self.pagina.viva:
            raise StaleElementReferenceException(self.id)

    def is_enabled(self):
        self._checar()
        return True

    def clear(self):
        self._checar()
        self.pagina.valores[self.id] = ""

    def send_keys(self, *valores):
        self._checar()
        self.pagina.valores[self.id] = self.pagina.valores.get(self.id, "") + "".join(
            str(v) for v in valores
        )

    def click(self):
        self._checar()
        self.pagina.cliques.append(self.id)


class _FormularioSei:
    """Driver fake do formulário "Externo".

    ``recarrega``: trocar a série reenvia o formulário (SEI 5.0.4).
    ``atraso``: quantas interações a página velha ainda vive depois da série.
    ``serie_apos_recarga``: série que a página nova mostra (padrão: a escolhida).
    ``carregando``: interações em que a página ainda está em readyState 'loading'.
    ``cai_para_o_topo``: o ChromeDriver perde o frame no meio do clique que
        dispara o reenvio e passa a responder pelo documento de cima — e o
        campo velho nem sempre fica "stale" (inclusões 5–7 de 27/10/2026).

    O formulário mora no frame ``ifrConteudoVisualizacao``; o driver começa nele.
    """

    FRAME = "ifrConteudoVisualizacao"

    def __init__(self, *, recarrega=True, atraso=3, serie_apos_recarga=None,
                 carregando=0, cai_para_o_topo=False):
        self.recarrega = recarrega
        self.atraso = atraso
        self.serie_apos_recarga = serie_apos_recarga
        self.pagina = _Pagina()
        self.recargas = 0
        self._pendente = None
        self.carregando = carregando
        self.congelada = False
        self.cai_para_o_topo = cai_para_o_topo
        self.no_topo = False
        driver = self

        class _SwitchTo:
            def default_content(self):
                driver.no_topo = True

            def frame(self, nome):
                assert nome == driver.FRAME, nome
                driver.no_topo = False

        self.switch_to = _SwitchTo()

    # "tempo" do navegador: cada interação aproxima a recarga pendente
    def _passar_tempo(self):
        if self.carregando > 0 and not self.congelada:
            self.carregando -= 1
        if self._pendente is None:
            return
        self._pendente -= 1
        if self._pendente <= 0:
            self._pendente = None
            serie = self.pagina.serie
            self.pagina.viva = False
            self.pagina = _Pagina(self.serie_apos_recarga or serie)
            self.recargas += 1

    def trocar_serie(self, elemento, texto):
        elemento._checar()
        elemento.pagina.serie = texto
        if self.carregando > 0:
            # Execução de 27/10/2026 (inclusão 3 no processo de teste): série
            # escolhida com o formulário ainda carregando -- o reenvio não
            # completou e a página ficou parada sem os campos de baixo.
            self.congelada = True
            return
        if self.recarrega:
            self._pendente = self.atraso
            if self.cai_para_o_topo:
                self.no_topo = True

    def find_element(self, by, valor):
        self._passar_tempo()
        if self.no_topo or (self.congelada and valor != "selSerie"):
            raise NoSuchElementException(valor)
        return _Elemento(self, self.pagina, valor)

    def find_elements(self, by, valor):
        try:
            return [self.find_element(by, valor)]
        except NoSuchElementException:
            return []

    def execute_script(self, script, *args):
        self._passar_tempo()
        if self.no_topo:  # documento de cima: sem formulário, sem marca, carregado
            if "frameElement" in script:
                return []
            return "complete" if "readyState" in script and "return document" in script else None
        pronta = not (self.carregando > 0 or self.congelada)
        if "frameElement" in script:
            return [self.FRAME]
        if "= true" in script:  # marca a página atual
            self.pagina.marcada = True
            return None
        if "!window." in script:  # página sem a marca e carregada?
            return pronta and not getattr(self.pagina, "marcada", False)
        if "readyState" in script:
            return "complete" if pronta else "loading"
        return None


class _SelectFalso:
    """Substitui o ``Select`` do Selenium: escolher a série dispara o onchange."""

    def __init__(self, elemento):
        self.elemento = elemento

    def select_by_visible_text(self, texto):
        self.elemento.driver.trocar_serie(self.elemento, texto)

    @property
    def first_selected_option(self):
        self.elemento._checar()
        pagina = self.elemento.pagina

        class _Opcao:
            text = pagina.serie

            def get_attribute(self, nome):
                return pagina.serie if nome == "textContent" else None

        return _Opcao()


@pytest.fixture
def selenium(monkeypatch, tmp_path):
    monkeypatch.setattr(ide, "Select", _SelectFalso)
    # WebDriverWait real (com as condições reais do Selenium), só com polling curto.
    for modulo in (ide, recarga):
        monkeypatch.setattr(
            modulo, "WebDriverWait", functools.partial(WebDriverWait, poll_frequency=0.01)
        )
    monkeypatch.setattr(InserirDocumentoExterno, "TIMEOUT_RECARGA_SERIE", 0.3)
    arquivo = tmp_path / "doc.pdf"
    arquivo.write_bytes(b"%PDF-1.4\n%%EOF\n")
    return str(arquivo)


def _doc(driver, arquivo):
    return InserirDocumentoExterno(
        driver,
        "Anexo",
        " - Documento de teste",
        arquivo,
        data_elaboracao="27/10/2026",
        timeout=1,
    )


def test_serie_espera_o_formulario_recarregar(selenium):
    driver = _FormularioSei(atraso=3)
    inicial = driver.pagina
    _doc(driver, selenium)._selecionar_serie()
    assert driver.recargas == 1
    assert not inicial.viva and driver.pagina.viva
    assert driver.pagina.serie == "Anexo"


def test_campos_seguintes_vao_para_a_pagina_nova(selenium):
    """Execução EXANTE de 27/10/2026: o que era preenchido logo após a série
    caía na página velha e sumia com o submit do trocarSerie()."""
    driver = _FormularioSei(atraso=3)
    doc = _doc(driver, selenium)
    doc._selecionar_serie()
    doc._preencher_data()
    doc._preencher_nome_arvore()
    final = driver.pagina
    assert final.valores.get(doc.ID_DATA) == "27/10/2026"
    assert final.valores.get(doc.ID_NOME_ARVORE) == " - Documento de teste"


def test_serie_so_e_escolhida_com_o_formulario_carregado(selenium):
    """O clique em "Externo" volta logo; o formulário ainda está carregando
    quando o selSerie já existe. Escolher a série nesse momento deixava a
    página parada, sem a data (inclusão 3 de 27/10/2026, processo de teste)."""
    driver = _FormularioSei(atraso=3, carregando=4)
    doc = _doc(driver, selenium)
    doc._selecionar_serie()
    doc._preencher_data()
    assert driver.recargas == 1
    assert driver.pagina.valores.get(doc.ID_DATA) == "27/10/2026"


def test_driver_que_cai_para_o_topo_volta_ao_frame_do_formulario(selenium):
    """Inclusões 5–7 de 27/10/2026: depois da série o ChromeDriver respondia
    pelo documento de cima — a recarga não era vista e a data "não existia"."""
    driver = _FormularioSei(atraso=3, cai_para_o_topo=True)
    doc = _doc(driver, selenium)
    doc._selecionar_serie()
    doc._preencher_data()
    assert driver.recargas == 1 and not driver.no_topo
    assert driver.pagina.valores.get(doc.ID_DATA) == "27/10/2026"


def test_serie_errada_apos_a_recarga_e_erro(selenium):
    driver = _FormularioSei(atraso=2, serie_apos_recarga="Ofício")
    with pytest.raises(DocumentoExternoError, match="Anexo"):
        _doc(driver, selenium)._selecionar_serie()


def test_sei_que_nao_recarrega_segue_na_mesma_pagina(selenium):
    driver = _FormularioSei(recarrega=False)
    inicial = driver.pagina
    _doc(driver, selenium)._selecionar_serie()
    assert driver.recargas == 0
    assert driver.pagina is inicial and inicial.serie == "Anexo"
