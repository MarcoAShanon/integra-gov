"""Testes de ``integra_gov.sei.editar_conteudo`` — parte pura (sem WebDriver).

Cobre o helper :func:`montar_link_documento`, a validação de ``chaves_html`` e a
substituição com **escape por-chave** (texto escapado + link cru na mesma
passada). O ``_substituir`` só conversa com o driver via ``execute_script``, então
um fake basta — abrir/fechar o editor real fica para a verificação ao vivo.
"""

from __future__ import annotations

import functools
import json

import pytest
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.support.ui import WebDriverWait

from integra_gov.sei import editar_conteudo as ec_mod
from integra_gov.sei.editar_conteudo import EditarConteudo, montar_link_documento
from integra_gov.sei.exceptions import EditarConteudoError


# ----- montar_link_documento -----


def test_montar_link_documento_markup():
    assert montar_link_documento("68242793", "62050889") == (
        '<span contenteditable="false" style="text-indent:0;">'
        '<a class="ancora_sei" id="lnkSei68242793" style="text-indent:0;">'
        "62050889</a></span>"
    )


def test_montar_link_documento_escapa_protocolo():
    # Defensivo: o texto visível é escapado (não deve injetar HTML pelo protocolo).
    link = montar_link_documento("123", "a<b>&")
    assert "a&lt;b&gt;&amp;" in link
    assert "<b>" not in link.replace("<b>&", "")  # o '<b>' do valor foi escapado


@pytest.mark.parametrize("id_doc, proto", [("abc", "1"), ("", "1"), ("123", "")])
def test_montar_link_documento_valida(id_doc, proto):
    with pytest.raises(ValueError):
        montar_link_documento(id_doc, proto)


# ----- EditarConteudo: validação -----


def test_chaves_html_desconhecida_levanta():
    with pytest.raises(ValueError):
        EditarConteudo(None, {"{{A}}": "x"}, chaves_html={"{{NAO_EXISTE}}"})


def test_substituicoes_vazio_levanta():
    with pytest.raises(ValueError):
        EditarConteudo(None, {})


# ----- EditarConteudo._substituir: escape por-chave -----


class _FakeDriver:
    """Driver mínimo: responde ao ``getData`` (JS_LER_INSTANCIAS) e registra as
    escritas (JS_ESCREVER_INSTANCIA)."""

    def __init__(self, instancias: dict, *, escrita_pega: bool = True):
        self._instancias = instancias
        self.escrita_pega = escrita_pega
        self.escritas: dict[str, str] = {}

    def execute_script(self, script, *args):
        if script == EditarConteudo.JS_LER_INSTANCIAS:
            atual = {
                nome: dict(dados, conteudo=self.escritas.get(nome, dados["conteudo"])
                           if self.escrita_pega else dados["conteudo"])
                for nome, dados in self._instancias.items()
            }
            return json.dumps(atual)
        if script == EditarConteudo.JS_ESCREVER_INSTANCIA:
            nome, conteudo = args
            self.escritas[nome] = conteudo
        return None


def test_substituir_texto_escapado_link_cru():
    link = montar_link_documento("68242793", "62050889")
    inst = {"corpo": {"conteudo": "<p>{{NOME}} — {{LINK}}</p>", "somenteLeitura": False}}
    drv = _FakeDriver(inst)
    ec = EditarConteudo(
        drv,
        {"{{NOME}}": "A & B <x>", "{{LINK}}": link},
        chaves_html={"{{LINK}}"},
    )

    contagens = ec._substituir()

    escrito = drv.escritas["corpo"]
    assert "A &amp; B &lt;x&gt;" in escrito  # texto: escapado
    assert 'class="ancora_sei" id="lnkSei68242793"' in escrito  # link: cru
    assert contagens == {"{{NOME}}": 1, "{{LINK}}": 1}


def test_substituir_ignora_somente_leitura():
    inst = {
        "cabecalho": {"conteudo": "<p>{{NOME}}</p>", "somenteLeitura": True},
        "corpo": {"conteudo": "<p>{{NOME}}</p>", "somenteLeitura": False},
    }
    drv = _FakeDriver(inst)
    ec = EditarConteudo(drv, {"{{NOME}}": "Maria"})

    ec._substituir()

    assert "cabecalho" not in drv.escritas  # read-only não é tocada
    assert "Maria" in drv.escritas["corpo"]


def test_substituir_exige_todas_por_padrao():
    inst = {"corpo": {"conteudo": "<p>{{NOME}}</p>", "somenteLeitura": False}}
    ec = EditarConteudo(_FakeDriver(inst), {"{{NOME}}": "x", "{{FALTANTE}}": "y"})
    with pytest.raises(EditarConteudoError):
        ec._substituir()


# ----- EditarConteudo._entrar_no_editor: janela do editor carregando -----
#
# Primeira Nota Técnica no SEI 5.0.4 (execução EXANTE de 28/10/2026): a espera
# pelo editor rodou com a janela ainda carregando e o Object.keys de
# CKEDITOR.instances deu "javascript error: Cannot convert undefined or null to
# object". O erro escapou da espera (que só tratava timeout) e deixou o driver
# PRESO na janela do editor — observações e volta à lista falharam em cascata.

ERRO_CARREGANDO = "javascript error: Cannot convert undefined or null to object"


class _Janelas:
    """Driver fake com janelas: SEI (principal), e-SIAPE e o editor recém-aberto.
    A janela principal NÃO é a primeira da lista (como no EXANTE)."""

    def __init__(self, *, erros_js: int, fica_pronto: bool = True):
        self.window_handles = ["esiape", "sei", "editor"]
        self.atual = "sei"
        self.erros_js = erros_js
        self.fica_pronto = fica_pronto
        self.fechadas: list[str] = []
        drv = self

        class _SwitchTo:
            def window(self, h):
                assert h in drv.window_handles, h
                drv.atual = h

            def default_content(self):
                pass

        self.switch_to = _SwitchTo()

    @property
    def current_window_handle(self):
        return self.atual

    def close(self):
        self.fechadas.append(self.atual)
        self.window_handles.remove(self.atual)

    def execute_script(self, script, *args):
        if script == EditarConteudo.JS_EDITORES_PRONTOS:
            assert self.atual == "editor"
            if self.erros_js > 0:
                self.erros_js -= 1
                raise JavascriptException(ERRO_CARREGANDO)
            return self.fica_pronto
        return None


@pytest.fixture
def espera_rapida(monkeypatch):
    monkeypatch.setattr(
        ec_mod, "WebDriverWait", functools.partial(WebDriverWait, poll_frequency=0.01)
    )
    monkeypatch.setattr(EditarConteudo, "TIMEOUT_EDITOR", 0.3)


def test_erro_de_javascript_com_o_editor_carregando_e_so_espera(espera_rapida):
    drv = _Janelas(erros_js=3)
    EditarConteudo(drv, {"{{A}}": "x"})._entrar_no_editor({"esiape", "sei"}, "sei")
    assert drv.atual == "editor" and not drv.fechadas


def test_editor_que_nao_fica_pronto_fecha_e_volta_a_janela_principal(espera_rapida):
    drv = _Janelas(erros_js=10**6)
    with pytest.raises(EditarConteudoError, match="não ficaram prontas"):
        EditarConteudo(drv, {"{{A}}": "x"})._entrar_no_editor({"esiape", "sei"}, "sei")
    assert drv.fechadas == ["editor"]
    assert drv.atual == "sei"  # não a 1ª da lista (e-SIAPE)


def test_scripts_so_usam_ckeditor_instances_no_editor_antigo():
    """SEI 5.0.4: CKEditor 5 multi-raiz, sem CKEDITOR.instances. Todo
    Object.keys(CKEDITOR.instances) fica atrás da checagem do CKEditor 4, e o
    caminho do CKEditor 5 usa o editor preso nas divs (.ckeditorInstance)."""
    assert "!!CKEDITOR.instances" in EditarConteudo._JS_CK5
    for js in (EditarConteudo.JS_EDITORES_PRONTOS, EditarConteudo.JS_LER_INSTANCIAS):
        assert js.index("if (ck4)") < js.index("Object.keys(CKEDITOR.instances)")
        assert "ckeditorInstance" in js
    assert "getData({rootName: nome})" in EditarConteudo.JS_LER_INSTANCIAS
    assert "_ck5().setData(dados)" in EditarConteudo.JS_ESCREVER_INSTANCIA


def test_escrita_que_nao_pegou_no_editor_aborta_sem_salvar():
    inst = {"corpo": {"conteudo": "<p>{{NOME}}</p>", "somenteLeitura": False}}
    ec = EditarConteudo(_FakeDriver(inst, escrita_pega=False), {"{{NOME}}": "Maria"})
    with pytest.raises(EditarConteudoError, match="não ficou no editor"):
        ec._substituir()


@pytest.mark.parametrize("classes, desabilitado", [
    ("cke_button cke_button__save cke_button_disabled", True),       # SEI 4.x
    ("cke_button cke_button__save cke_button_off", False),
    ("ck ck-button ck-disabled ck-off salvar__buttonview", True),     # SEI 5.0.4
    ("ck ck-button ck-off salvar__buttonview salvar__pisca", False),
])
def test_botao_salvar_dos_dois_editores(classes, desabilitado):
    assert EditarConteudo(None, {"{{A}}": "x"})._botao_desabilitado(classes) is desabilitado
    assert "salvar__buttonview" in EditarConteudo.XPATH_BOTAO_SALVAR
