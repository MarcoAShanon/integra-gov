"""Testes de ``integra_gov.sei.editar_conteudo`` — parte pura (sem WebDriver).

Cobre o helper :func:`montar_link_documento`, a validação de ``chaves_html`` e a
substituição com **escape por-chave** (texto escapado + link cru na mesma
passada). O ``_substituir`` só conversa com o driver via ``execute_script``, então
um fake basta — abrir/fechar o editor real fica para a verificação ao vivo.
"""

from __future__ import annotations

import json

import pytest

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

    def __init__(self, instancias: dict):
        self._instancias = instancias
        self.escritas: dict[str, str] = {}

    def execute_script(self, script, *args):
        if script == EditarConteudo.JS_LER_INSTANCIAS:
            return json.dumps(self._instancias)
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
