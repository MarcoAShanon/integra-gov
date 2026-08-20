"""Testes do montador e do verificador da landing (site/)."""
from __future__ import annotations

import pathlib
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parents[1] / "site"
sys.path.insert(0, str(SITE))

import montar as m  # noqa: E402
import verificar as v  # noqa: E402


def _partes_completas() -> bool:
    """As fatias chegam uma por vez (Tasks 3 a 8); ate la, montar() nao roda."""
    exigidos = ["head.html", "00-sistema.css", "script.js"]
    exigidos += [f"{fatia}.html" for fatia in m.FATIAS]
    return all((SITE / "parts" / nome).exists() for nome in exigidos)


completo = pytest.mark.skipif(
    not _partes_completas(), reason="site/parts/ ainda incompleto — fatias pendentes"
)


# ---------------------------------------------------------------- montar
@completo
def test_montar_produz_documento_completo():
    html = m.montar()
    assert html.startswith("<!doctype html>")
    assert '<html lang="pt-BR">' in html
    assert html.rstrip().endswith("</html>")


@completo
def test_montar_inclui_todas_as_fatias_na_ordem():
    html = m.montar()
    posicoes = [html.index(f'id="{fatia}"') for fatia in m.IDS_FATIAS]
    assert posicoes == sorted(posicoes), "fatias fora de ordem"


@completo
def test_montar_so_uma_fatia_exclui_as_outras():
    html = m.montar(so="01-hero")
    assert 'id="hero"' in html
    assert 'id="conversao"' not in html


def test_montar_so_rejeita_fatia_inexistente():
    with pytest.raises(ValueError, match="desconhecida"):
        m.montar(so="99-nada")


@completo
def test_caminho_saida_da_pagina_inteira_e_o_index():
    assert m.caminho_saida(None).name == "index.html"


def test_caminho_saida_de_uma_fatia_e_isolado():
    assert m.caminho_saida("02-prova").name == "preview-02-prova.html"


def test_cada_fatia_grava_num_caminho_distinto():
    """Fatias construidas em paralelo nao podem sobrescrever a previa uma da outra."""
    caminhos = {m.caminho_saida(fatia) for fatia in m.FATIAS}
    assert len(caminhos) == len(m.FATIAS)
    assert m.caminho_saida(None) not in caminhos


@completo
def test_montar_css_do_sistema_vem_antes_do_css_das_fatias():
    html = m.montar()
    assert html.index("/* ===== 00-sistema ===== */") < html.index(
        "/* ===== 01-hero ===== */"
    )


# ------------------------------------------------------------- verificar
def test_h1_duplicado_e_achado():
    achados = v.verificar("<h1>a</h1><h1>b</h1>")
    assert any("h1" in a for a in achados)


def test_h1_unico_nao_e_achado():
    assert not any("h1" in a for a in v.verificar("<h1>a</h1><h2>b</h2>"))


def test_titulo_que_pula_degrau_e_achado():
    achados = v.verificar("<h1>a</h1><h3>c</h3>")
    assert any("degrau" in a for a in achados)


def test_link_morto_e_achado():
    achados = v.verificar('<a href="#">x</a>')
    assert any("href" in a for a in achados)


def test_imagem_sem_alt_e_achado():
    achados = v.verificar('<img src="a.png">')
    assert any("alt" in a for a in achados)


def test_imagem_com_alt_vazio_nao_e_achado():
    assert not any("alt" in a for a in v.verificar('<img src="a.png" alt="">'))


def test_recurso_externo_nao_permitido_e_achado():
    achados = v.verificar('<script src="https://cdn.exemplo.com/x.js"></script>')
    assert any("externo" in a for a in achados)


def test_google_fonts_e_permitido():
    html = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=X">'
    assert not any("externo" in a for a in v.verificar(html))


def test_link_de_ancora_para_site_externo_nao_e_recurso():
    html = '<a href="https://github.com/MarcoAShanon/integra-gov">repo</a>'
    assert not any("externo" in a for a in v.verificar(html))


def test_fonte_vetada_como_escolha_e_achado():
    achados = v.verificar(":root{--font-display:Inter,serif}")
    assert any("vetada" in a for a in achados)


def test_fonte_vetada_como_fallback_e_permitida():
    html = ":root{--font-display:Fraunces,Georgia,Arial,sans-serif}"
    assert not any("vetada" in a for a in v.verificar(html))


def test_ausencia_de_skip_link_e_achado():
    achados = v.verificar("<body><h1>a</h1></body>")
    assert any("skip" in a for a in achados)


def test_ausencia_de_movimento_reduzido_e_achado():
    achados = v.verificar("<style>.x{transition:1s}</style>")
    assert any("reduced-motion" in a for a in achados)


def test_cpf_no_html_e_achado():
    achados = v.verificar("<p>123.456.789-00</p>")
    assert any("CPF" in a for a in achados)


def test_palavra_de_conclusao_e_achado():
    achados = v.verificar("<p>O projeto está completo.</p>")
    assert any("incremental" in a for a in achados)


# ------------------------------------------------- verificar_partes
def test_fatia_que_redefine_token_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(":root{--brand:#FF0000}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path)
    assert any("redefine" in a for a in achados)


def test_fatia_com_seletor_sem_prefixo_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(".card{color:red}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path)
    assert any("prefixo" in a for a in achados)


def test_fatia_bem_comportada_nao_gera_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text("#hero .card{color:var(--brand)}", encoding="utf-8")
    assert v.verificar_partes(tmp_path) == []
