"""Testes do montador e do verificador da landing (site/)."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

SITE = pathlib.Path(__file__).resolve().parents[1] / "site"
sys.path.insert(0, str(SITE))

import auditar_contrato as a  # noqa: E402
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


# ------------------------------------------------ M1: skip link morto
@completo
def test_montar_envolve_corpo_em_main_com_id_conteudo():
    """O skip link aponta para #conteudo; sem <main id="conteudo"> ele e um
    link morto por construcao. O <a class="skip"> fica FORA do <main> — ele
    aponta pra dentro."""
    html = m.montar()
    assert '<main id="conteudo">' in html
    assert html.index('<a class="skip"') < html.index('<main id="conteudo">')
    assert "</main>" in html


@completo
def test_montar_so_uma_fatia_tambem_envolve_em_main():
    html = m.montar(so="01-hero")
    assert '<main id="conteudo">' in html


# ------------------------------------------------ A1: nav vira header proprio
# A navegacao morava DENTRO da fatia 1 (hero), logo dentro do <main>. Isso
# deixava a pagina sem landmark "banner", a nav sem ser landmark de topo, e o
# skip link (href="#conteudo") aterrissando ANTES da navegacao — ou seja, nao
# pulava nada, que e o unico proposito de um skip link. montar() agora emite
# <header> (com o conteudo de nav.html, se existir) ANTES do <main>.
@completo
def test_montar_emite_header_antes_do_main():
    html = m.montar()
    assert "<header>" in html
    assert html.index("<header>") < html.index('<main id="conteudo">')


@completo
def test_montar_alvo_do_skip_link_vem_depois_do_header():
    html = m.montar()
    assert html.index('id="conteudo"') > html.index("</header>")


@completo
def test_montar_so_uma_fatia_tambem_emite_header_antes_do_main():
    html = m.montar(so="01-hero")
    assert html.index("<header>") < html.index('<main id="conteudo">')


# ------------------------------------------------ A3: modo previa (Task 10)
@completo
def test_previa_leva_noindex():
    """A previa fica publica numa URL adivinhavel; buscador nao pode indexa-la."""
    html = m.montar(previa=True)
    assert '<meta name="robots" content="noindex,nofollow">' in html


@completo
def test_pagina_de_producao_nao_leva_noindex():
    assert "noindex" not in m.montar()


@completo
def test_previa_e_producao_diferem_so_pelo_robots():
    previa = m.montar(previa=True).replace(
        '<meta name="robots" content="noindex,nofollow">\n', ""
    )
    assert previa == m.montar()


def test_caminho_saida_da_previa_e_isolado():
    assert m.caminho_saida(None, previa=True).name == "previa.html"


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


# ------------------------------------- V1 (BLOQUEANTE): modo fatia
def test_fatia_com_h2_e_sem_h1_nao_e_achado():
    achados = v.verificar("<h2>a</h2>", fatia=True)
    assert not any(a.startswith("h1") for a in achados)


def test_fatia_com_dois_h1_ainda_e_achado():
    achados = v.verificar("<h1>a</h1><h1>b</h1>", fatia=True)
    assert any(a.startswith("h1") for a in achados)


def test_fatia_com_h2_seguido_de_h4_ainda_e_achado():
    achados = v.verificar("<h2>a</h2><h4>b</h4>", fatia=True)
    assert any("degrau" in a for a in achados)


def test_pagina_inteira_sem_h1_continua_achado():
    achados = v.verificar("<h2>a</h2>")
    assert any(a.startswith("h1") for a in achados)


def test_fatia_nao_exige_skip_link():
    achados = v.verificar("<body><h2>a</h2></body>", fatia=True)
    assert not any("skip" in a for a in achados)


# ------------------------------------- V9: longhand nao pode casar custom property
def test_custom_property_transition_speed_nao_e_falso_positivo_de_reduced_motion():
    achados = v.verificar(":root{--transition-speed:200ms}")
    assert not any("reduced-motion" in a for a in achados)


def test_transition_duration_sem_media_ainda_e_achado():
    achados = v.verificar("<style>.x{transition-duration:1s}</style>")
    assert any("reduced-motion" in a for a in achados)


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


# --------------------------------------- correcoes da revisao cega (Task 1)
# CRITICO: a guarda de at-rule nunca disparava — @media/@keyframes eram
# capturados como "seletor" e acusados de vazar, o que bloquearia a UNICA
# forma correta de obedecer a Restricao Global 7 (movimento so dentro de
# @media prefers-reduced-motion).
def test_media_query_nao_e_seletor_mas_conteudo_interno_e_verificado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(
        "#hero .card{transition:transform .2s}\n"
        "@media (prefers-reduced-motion: reduce){#hero .card{transition:none}}",
        encoding="utf-8",
    )
    achados = v.verificar_partes(tmp_path)
    assert achados == []


def test_seletor_sem_prefixo_dentro_de_media_query_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(
        "@media (prefers-reduced-motion: reduce){.card{transition:none}}",
        encoding="utf-8",
    )
    achados = v.verificar_partes(tmp_path)
    assert any("prefixo" in a for a in achados)


def test_keyframes_nao_e_seletor(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(
        "@keyframes hero-spin{0%{opacity:0}100%{opacity:1}}",
        encoding="utf-8",
    )
    achados = v.verificar_partes(tmp_path)
    assert not any("keyframes" in a for a in achados)


# --------------------------- falso positivo de keyframe percentual (pos-revisao)
# 0% e 100% NAO comecam com "%" (terminam) — a guarda startswith(("@", "from",
# "to", "%")) nunca reconhecia um passo percentual de verdade.
def test_keyframes_percentual_nao_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(
        "@keyframes brilho{0%{opacity:0}100%{opacity:1}}",
        encoding="utf-8",
    )
    assert v.verificar_partes(tmp_path) == []


def test_keyframes_percentual_agrupado_por_virgula_nao_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(
        "@keyframes brilho{0%,100%{opacity:0}50%{opacity:.5}}",
        encoding="utf-8",
    )
    assert v.verificar_partes(tmp_path) == []


def test_keyframes_from_to_nao_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(
        "@keyframes brilho{from{opacity:0}to{opacity:1}}",
        encoding="utf-8",
    )
    assert v.verificar_partes(tmp_path) == []


def test_seletor_com_porcentagem_em_atributo_sem_prefixo_ainda_e_achado(tmp_path):
    """A guarda de keyframe nao pode virar 'qualquer coisa com %' — um seletor
    de verdade com % (ex.: atributo) continua tendo que ser verificado."""
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(
        '.card[data-progresso="50%"]{color:red}',
        encoding="utf-8",
    )
    achados = v.verificar_partes(tmp_path)
    assert any("prefixo" in a for a in achados)


def test_seletor_com_calc_sem_prefixo_ainda_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(
        ".card{width:calc(50% - 4px)}",
        encoding="utf-8",
    )
    achados = v.verificar_partes(tmp_path)
    assert any("prefixo" in a for a in achados)


# IMPORTANTE 1: fonte vetada so era vista na primeira declaracao do token.
def test_fonte_vetada_em_declaracao_subsequente_e_achado():
    html = (
        ":root{--font-display:Fraunces,Georgia,serif}\n"
        "@media print{:root{--font-display:Arial,sans-serif}}"
    )
    achados = v.verificar(html)
    assert any("vetada" in a for a in achados)


# IMPORTANTE 2: protocolo-relativo, @import e url() sao rotas reais para um
# CDN entrar sem o verificador acusar, ja que o CSS final vive inline.
def test_recurso_protocolo_relativo_e_achado():
    achados = v.verificar('<script src="//cdn.jsdelivr.net/npm/x.js"></script>')
    assert any("externo" in a for a in achados)


def test_import_css_externo_e_achado():
    html = '<style>@import url("https://cdn.exemplo.com/f.css");</style>'
    achados = v.verificar(html)
    assert any("externo" in a for a in achados)


def test_url_css_externo_e_achado():
    html = '<style>.x{background:url(https://cdn.exemplo.com/bg.png)}</style>'
    achados = v.verificar(html)
    assert any("externo" in a for a in achados)


def test_google_fonts_via_import_e_permitido():
    html = '<style>@import url("https://fonts.googleapis.com/css2?family=X");</style>'
    assert not any("externo" in a for a in v.verificar(html))


def test_google_fonts_via_url_e_permitido():
    html = "<style>@font-face{src:url(https://fonts.gstatic.com/s/x.woff2)}</style>"
    assert not any("externo" in a for a in v.verificar(html))


# IMPORTANTE 3: animacao por propriedade longhand escapava da guarda de
# movimento reduzido.
def test_animacao_longhand_sem_reduced_motion_e_achado():
    html = "<style>.x{animation-name:spin;animation-duration:1s}</style>"
    achados = v.verificar(html)
    assert any("reduced-motion" in a for a in achados)


# MENOR 1: href com aspas simples tambem deve ser reconhecido como link morto.
def test_link_morto_com_aspas_simples_e_achado():
    achados = v.verificar("<a href='#'>x</a>")
    assert any("href" in a for a in achados)


# MENOR 2: CPF sem pontuacao deve ser reconhecido, sem gerar falso positivo
# em numeros grandes formatados (contagens, valores em reais, datas).
# "11144477735" tem digitos verificadores validos (V10 exige isso agora —
# o exemplo antigo, "12345678900", NAO tem, entao deixou de ser achado; essa
# e exatamente a mudanca de comportamento que V10 pede).
def test_cpf_sem_pontuacao_e_achado():
    achados = v.verificar("<p>11144477735</p>")
    assert any("CPF" in a for a in achados)


def test_numero_grande_formatado_nao_e_falso_positivo_de_cpf():
    html = "<p>15.440 processos concluidos, R$ 12,11 milhões economizados.</p>"
    assert not any("CPF" in a for a in v.verificar(html))


def test_sequencia_de_mais_de_onze_digitos_nao_e_falso_positivo_de_cpf():
    achados = v.verificar("<p>123456789012</p>")
    assert not any("CPF" in a for a in achados)


# --------------------------------- lote consolidado (rodada 2): V2, V3, V4,
# V5, V6, V7, V10. V1, V9 e M1 ja foram tratados no commit anterior; V8 e
# so documentacao, ja anexada ao docstring de verificar().

# V2 — ancora interna quebrada e id duplicado
def test_ancora_interna_sem_id_correspondente_e_achado():
    achados = v.verificar('<a href="#modulos">x</a>')
    assert any("ancora" in a for a in achados)


def test_ancora_interna_com_id_correspondente_nao_e_achado():
    html = '<a href="#modulos">x</a><section id="modulos"></section>'
    assert not any("ancora" in a for a in v.verificar(html))


def test_id_duplicado_e_achado():
    html = '<section id="hero"></section><div id="hero"></div>'
    achados = v.verificar(html)
    assert any(a.startswith("id:") for a in achados)


def test_href_vazio_continua_achado_pela_regra_antiga():
    achados = v.verificar('<a href="#">x</a>')
    assert any("href" in a for a in achados)


def test_fatia_nao_verifica_ancora_quebrada():
    """Uma fatia legitimamente aponta para ancoras de outras fatias."""
    achados = v.verificar('<a href="#outra-fatia">x</a>', fatia=True)
    assert not any("ancora" in a for a in achados)


def test_fatia_ainda_verifica_id_duplicado():
    html = '<section id="x"></section><div id="x"></div>'
    achados = v.verificar(html, fatia=True)
    assert any(a.startswith("id:") for a in achados)


def test_data_id_nao_e_confundido_com_id_de_verdade():
    """data-id e um gancho de JS, nao o atributo id — nao pode contar pra
    deteccao de duplicata nem virar alvo de ancora."""
    html = '<div data-id="123"><section id="123"></section></div>'
    achados = v.verificar(html)
    assert not any(a.startswith("id:") for a in achados)


# V3 — font-family/font crus, e a familia dentro da URL do Google Fonts
def test_font_family_crua_vetada_e_achado():
    achados = v.verificar("<style>#prova{font-family:Inter}</style>")
    assert any("vetada" in a for a in achados)


def test_font_family_crua_permitida_nao_e_achado():
    html = "<style>#prova{font-family:Fraunces,Arial,sans-serif}</style>"
    assert not any("vetada" in a for a in v.verificar(html))


def test_font_shorthand_vetada_e_achado():
    achados = v.verificar("<style>.x{font:600 1rem Inter,serif}</style>")
    assert any("vetada" in a for a in achados)


def test_google_fonts_url_com_familia_vetada_e_achado():
    html = (
        '<link rel="stylesheet" '
        'href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700">'
    )
    achados = v.verificar(html)
    assert any("vetada" in a for a in achados)


def test_google_fonts_url_com_familia_permitida_nao_e_achado():
    html = (
        '<link rel="stylesheet" '
        'href="https://fonts.googleapis.com/css2?family=Fraunces:opsz@9..144">'
    )
    achados = v.verificar(html)
    assert not any("vetada" in a for a in achados)


# V4 — recurso externo fora de src/href
def test_poster_externo_e_achado():
    html = '<video poster="https://cdn.exemplo.com/poster.jpg"></video>'
    assert any("externo" in a for a in v.verificar(html))


def test_srcset_externo_e_achado():
    html = '<img srcset="https://cdn.exemplo.com/a.jpg 1x, /img/b.jpg 2x" src="/img/b.jpg" alt="">'
    assert any("externo" in a for a in v.verificar(html))


def test_srcset_so_local_nao_e_achado():
    html = '<img srcset="/img/a.jpg 1x, /img/b.jpg 2x" src="/img/b.jpg" alt="">'
    assert not any("externo" in a for a in v.verificar(html))


def test_data_video_externo_e_achado():
    html = '<button data-video="https://cdn.exemplo.com/v.mp4">play</button>'
    assert any("externo" in a for a in v.verificar(html))


def test_embed_externo_e_achado():
    assert any("externo" in a for a in v.verificar('<embed src="https://cdn.exemplo.com/x.svg">'))


def test_use_href_externo_e_achado():
    html = '<svg><use href="https://cdn.exemplo.com/sprite.svg#icon"></use></svg>'
    assert any("externo" in a for a in v.verificar(html))


# V5 — token novo criado por uma fatia em :root
def test_fatia_cria_token_novo_em_root_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(":root{--meu-token:#fff}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path)
    assert any(a.startswith("root:") for a in achados)


def test_root_em_00_sistema_nao_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--meu-token:#fff}", encoding="utf-8")
    assert v.verificar_partes(tmp_path) == []


# V6 — o proprio dominio nao e "terceiro"
def test_proprio_dominio_nao_e_achado_de_externo():
    html = '<link rel="canonical" href="https://projeto.govintegra.com.br/">'
    assert not any("externo" in a for a in v.verificar(html))


# V7 — allowlist de frases exatas pro veto de conclusao
def test_frase_permitida_vem_pronto_para_nao_e_achado():
    html = "<p>O que já vem pronto para outro órgão adotar: licença MIT</p>"
    assert not any("incremental" in a for a in v.verificar(html))


def test_projeto_esta_pronto_continua_achado():
    achados = v.verificar("<p>o projeto está pronto</p>")
    assert any("incremental" in a for a in achados)


def test_sistema_completo_continua_achado():
    achados = v.verificar("<p>sistema completo</p>")
    assert any("incremental" in a for a in achados)


def test_fecha_o_ciclo_continua_achado():
    achados = v.verificar("<p>fecha o ciclo</p>")
    assert any("incremental" in a for a in achados)


# V10 — CPF sem pontuacao: validar digito verificador (nao confundir com telefone)
def test_telefone_de_onze_digitos_nao_e_falso_positivo_de_cpf():
    achados = v.verificar("<p>61999998888</p>")
    assert not any("CPF" in a for a in achados)


def test_nup_sei_nao_e_falso_positivo_de_cpf():
    achados = v.verificar("<p>19975.009280/2025-99</p>")
    assert not any("CPF" in a for a in achados)


def test_cpf_pontuado_continua_achado_sem_exigir_digito_verificador():
    """O formato PONTUADO continua achado sem validar o digito verificador —
    quem escreve um CPF pontuado esta escrevendo um CPF, valido ou nao."""
    achados = v.verificar("<p>000.000.000-00</p>")
    assert any("CPF" in a for a in achados)


# ============================================== rodada 3: bypasses confirmados
# BYPASS 1 (V5) — seletor composto (":root, #hero .card") escapava do guard
# de igualdade exata com a string inteira, caindo no laco de prefixo onde
# ":root" e explicitamente isento.
def test_root_composto_com_outro_seletor_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(":root, #hero .card{--novo:red}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path)
    assert any(a.startswith("root:") for a in achados)


def test_root_composto_ordem_invertida_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text("#hero .card, :root{--novo:red}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path)
    assert any(a.startswith("root:") for a in achados)


def test_root_puro_ainda_e_achado(tmp_path):
    """Regressao: :root sozinho (sem composicao) continua achado."""
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(":root{--novo:red}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path)
    assert any(a.startswith("root:") for a in achados)


def test_seletor_prefixado_sem_root_nao_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text("#hero .card{color:red}", encoding="utf-8")
    assert v.verificar_partes(tmp_path) == []


# BYPASS 2 (V7) — a allowlist casava por substring solto ("vem pronto
# para"), entao qualquer frase nova que reaproveitasse esse trecho escapava
# do veto, mesmo sem ser a frase humana-aprovada.
def test_frase_publicada_completa_continua_sem_achado():
    html = "<p>O que já vem pronto para outro órgão adotar: licença MIT</p>"
    assert not any("incremental" in a for a in v.verificar(html))


def test_frase_nova_reaproveitando_vem_pronto_para_e_achado():
    achados = v.verificar("<p>O projeto vem pronto para uso, nada mais a fazer</p>")
    assert any("incremental" in a for a in achados)


def test_frase_permitida_com_espacamento_irregular_e_caixa_diferente_nao_e_achado():
    html = "<p>VEM   PRONTO PARA\noutro   ÓRGÃO  adotar</p>"
    assert not any("incremental" in a for a in v.verificar(html))


# MENOR 1 — id em bloco HTML comentado nao pode contar como duplicata: a
# copia comentada nao esta na pagina renderizada.
def test_id_em_comentario_html_nao_conta_como_duplicata():
    html = '<!-- <section id="hero"></section> --><section id="hero"></section>'
    achados = v.verificar(html)
    assert not any(a.startswith("id:") for a in achados)


def test_ancora_para_id_que_so_existe_em_comentario_ainda_e_achado():
    html = '<!-- <section id="hero"></section> --><a href="#hero">x</a>'
    achados = v.verificar(html)
    assert any("ancora" in a for a in achados)


# MENOR 2 — as dez sequencias de digito repetido passam no modulo 11 mas
# sao notoriamente invalidas; toda biblioteca de referencia as exclui.
def test_cpf_sem_pontuacao_com_digitos_repetidos_nao_e_achado():
    achados = v.verificar("<p>11111111111</p>")
    assert not any("CPF" in a for a in achados)


def test_cpf_sem_pontuacao_todos_zeros_nao_e_achado():
    achados = v.verificar("<p>00000000000</p>")
    assert not any("CPF" in a for a in achados)


# ============================================== rodada 4: bypass de host
# H1 — _checar_host aceitava um host permitido em QUALQUER LUGAR da string
# (substring), nao so como o hostname de verdade. Isso abre caminho pra
# subdominio forjado (fonts.googleapis.com.evil.com), host permitido
# escondido no PATH, ou na QUERY string.
def test_host_permitido_no_path_de_url_maliciosa_e_achado():
    html = '<script src="https://evil.com/fonts.googleapis.com/x.js"></script>'
    achados = v.verificar(html)
    assert any("externo" in a for a in achados)


def test_subdominio_forjado_e_achado():
    html = '<script src="https://fonts.googleapis.com.evil.com/x.js"></script>'
    achados = v.verificar(html)
    assert any("externo" in a for a in achados)


def test_host_permitido_na_query_de_url_maliciosa_e_achado():
    html = '<img src="https://evil.com/a.png?from=fonts.googleapis.com" alt="">'
    achados = v.verificar(html)
    assert any("externo" in a for a in achados)


def test_google_fonts_de_verdade_continua_permitido():
    html = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces">'
    assert not any("externo" in a for a in v.verificar(html))


def test_protocolo_relativo_de_host_permitido_continua_permitido():
    html = '<script src="//fonts.gstatic.com/s/x.woff2"></script>'
    assert not any("externo" in a for a in v.verificar(html))


def test_proprio_dominio_canonical_continua_permitido():
    html = '<link rel="canonical" href="https://projeto.govintegra.com.br/">'
    assert not any("externo" in a for a in v.verificar(html))


def test_host_permitido_em_caixa_alta_continua_permitido():
    html = '<link rel="stylesheet" href="https://FONTS.GOOGLEAPIS.COM/css2?family=X">'
    assert not any("externo" in a for a in v.verificar(html))


# ============================================== rodada 5: escopo do verificador
# A2 — com cinco agentes construindo fatias em paralelo na mesma arvore,
# verificar_partes() varria SEMPRE parts/*.css inteiro. O agente do hero
# rodava a verificacao da sua propria previa e recebia achados de CSS de
# outras fatias ainda pela metade — destrutivo de editar (nao e dele) e
# injusto de reportar como reprovacao da propria fatia.
def test_verificar_partes_modo_fatia_ignora_css_de_outras_fatias(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text("#hero .card{color:var(--brand)}", encoding="utf-8")
    (tmp_path / "03-contexto.css").write_text(".vaza{color:red}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path, somente="01-hero")
    assert achados == []


def test_verificar_partes_pagina_inteira_ainda_acusa_outras_fatias(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text("#hero .card{color:var(--brand)}", encoding="utf-8")
    (tmp_path / "03-contexto.css").write_text(".vaza{color:red}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path)
    assert any("03-contexto.css" in a for a in achados)


def test_verificar_partes_modo_fatia_ainda_le_00_sistema_para_tokens(tmp_path):
    """00-sistema.css continua sendo lido como fonte dos tokens nos dois
    modos — sem ele, nao daria pra saber se a fatia redefine um token."""
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(":root{--brand:#FF0000}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path, somente="01-hero")
    assert any("redefine" in a for a in achados)


def test_verificar_partes_modo_fatia_sem_css_proprio_nao_e_achado(tmp_path):
    """Se a fatia ainda nao tem CSS proprio (so HTML), nao ha nada pra
    verificar nela — nao pode virar achado por ausencia."""
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "03-contexto.css").write_text(".vaza{color:red}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path, somente="01-hero")
    assert achados == []


# ============================================== rodada 6: piloto da fatia 1
# P1 — verificar_partes exigia que TODO seletor de 01-hero.css comecasse
# com #hero, mas a navegacao (nav.html) mora dentro do <header> que o
# montador emite — FORA do #hero. Escolha: "header" vira prefixo valido
# ADICIONAL so para 01-hero.css. Nenhuma outra fatia ganha esse prefixo —
# a protecao contra vazamento entre fatias nao afrouxa em lugar nenhum,
# so ganha uma excecao estrutural exatamente onde o montador de fato
# coloca o conteudo dessa fatia (ver A1, montar.py emite <header> antes
# do <main>, so pra fatia 1 atraves de nav.html).
def test_seletor_com_prefixo_header_em_01_hero_e_aceito(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text("header .nav a{color:var(--brand)}", encoding="utf-8")
    assert v.verificar_partes(tmp_path) == []


def test_seletor_com_prefixo_header_em_outra_fatia_e_achado(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "03-contexto.css").write_text("header .nav a{color:var(--brand)}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path)
    assert any(a.startswith("prefixo:") for a in achados)


def test_seletor_sem_prefixo_nenhum_ainda_e_achado_em_01_hero(tmp_path):
    (tmp_path / "00-sistema.css").write_text(":root{--brand:#E7920D}", encoding="utf-8")
    (tmp_path / "01-hero.css").write_text(".vaza{color:red}", encoding="utf-8")
    achados = v.verificar_partes(tmp_path)
    assert any(a.startswith("prefixo:") for a in achados)


# P2 — comentario HTML contava como marcacao de verdade: um <h1> ou
# href="#" DENTRO de <!-- --> gerava achado falso. Ja resolvido para
# id/ancora com _sem_comentarios_html (rodada 3); estende pra contagem de
# h1, hierarquia de titulos, links mortos, alt de imagem e recursos
# externos (a checagem por tag src/href — as vias embutidas em CSS
# ficam de fora desta rodada, ver nota no codigo).
def test_h1_em_comentario_nao_conta_e_h1_real_continua_contando():
    achados = v.verificar("<!-- <h1>exemplo</h1> --><h1>real</h1>")
    assert not any(a.startswith("h1") for a in achados)


def test_href_morto_em_comentario_nao_e_achado():
    achados = v.verificar('<!-- href="#" -->')
    assert not any("href" in a for a in achados)


def test_imagem_sem_alt_em_comentario_nao_e_achado():
    achados = v.verificar("<!-- <img src=x> -->")
    assert not any("alt" in a for a in achados)


def test_titulo_que_pula_degrau_em_comentario_nao_conta():
    html = "<!-- <h1>a</h1><h3>c</h3> --><h1>a</h1><h2>b</h2>"
    achados = v.verificar(html)
    assert not any("degrau" in a for a in achados)


def test_recurso_externo_em_comentario_nao_e_achado():
    html = '<!-- <script src="https://evil.com/x.js"></script> -->'
    achados = v.verificar(html)
    assert not any("externo" in a for a in achados)


def test_stripper_html_nao_interfere_com_comentario_css_no_style():
    """O gemeo: comentario HTML (<!-- -->) desaparece; comentario CSS
    (/* */) dentro do <style>, que fica FORA de qualquer <!-- -->,
    sobrevive intacto — e o h1 real, depois do <style>, continua sendo
    contado normalmente (nem a mais, nem a menos)."""
    html = (
        "<style>/* nao mexer */ .x{color:red}</style>"
        "<!-- <h1>fantasma</h1> -->"
        "<h1>real</h1>"
    )
    achados = v.verificar(html)
    assert not any(a.startswith("h1") for a in achados)


# ------------------------------------------------- auditor do contrato
# A classe de erro "numero declarado em vez de calculado" pegou o contrato
# de design tres vezes (ver a docstring de site/auditar_contrato.py). Estes
# testes provam que o auditor reprova o que tem de reprovar — senao ele vira
# um carimbo verde que da falsa seguranca, que e pior que nao existir.
CSS_SISTEMA = (SITE / "parts" / "00-sistema.css").read_text(encoding="utf-8")
CONTRATO = (SITE / "parts" / "contrato.md").read_text(encoding="utf-8")


def test_auditor_aprova_o_contrato_real():
    """O estado versionado tem que passar limpo — se este quebrar, ou o CSS
    mudou sem o contrato acompanhar, ou o contrario."""
    assert a.auditar(CSS_SISTEMA, CONTRATO) == []


def test_auditor_recalcula_e_nao_confia_no_texto():
    """Numero afirmado no contrato que o CSS nao produz vira achado.

    E o caso da esmeralda (3,3:1 afirmado, 2,91:1 real) e o das sete celulas
    que ficaram para tras quando --fundo-alt mudou.
    """
    # 16,75:1 e --text sobre --bg no tema claro; trocado, perde o lastro.
    adulterado = CONTRATO.replace("16,75:1", "9,99:1")
    assert adulterado != CONTRATO, "o numero de referencia sumiu do contrato"
    achados = a.auditar(CSS_SISTEMA, adulterado)
    assert any("sem lastro" in achado for achado in achados)
    assert any("--text sobre --bg" in achado for achado in achados)


def test_auditor_acusa_par_abaixo_de_aa():
    """Token de texto que deixa de passar 4,5:1 vira achado, mesmo que o
    contrato continue afirmando o numero antigo."""
    cinza_fraco = CSS_SISTEMA.replace("--text-soft:#6A6055", "--text-soft:#C9C4BC", 1)
    assert cinza_fraco != CSS_SISTEMA
    achados = a.auditar(cinza_fraco, CONTRATO)
    assert any(achado.startswith("piso:") and "--text-soft" in achado for achado in achados)


def test_auditor_acusa_rampa_de_dados_achatada():
    """Regressao do defeito real: as tres cores de grafico separadas por
    matiz, nao por intensidade. Estas SAO as cores antigas — davam 1,02:1
    entre si e viravam uma massa so em escala de cinza."""
    achatado = CSS_SISTEMA
    for token, antigo in (
        ("--dado", "#C0770B"),
        ("--dado-neutro", "#8C8377"),
        ("--dado-fraco", "#9C8256"),
    ):
        achatado = re.sub(
            rf"{token}:#[0-9A-Fa-f]{{6}};", f"{token}:{antigo};", achatado, count=1
        )
    achados = a.auditar(achatado, CONTRATO)
    assert any(achado.startswith("rampa:") for achado in achados)


def test_auditor_le_a_faixa_alt_clara_e_nao_a_escura():
    """O seletor .faixa.alt existe nos dois temas. Ler o do tema errado faz
    o auditor auditar texto claro sobre superficie escura e acusar seis
    falhas que nao existem — foi o primeiro defeito dele."""
    escopos = a.paletas(CSS_SISTEMA)
    assert escopos["claro/faixa par"]["--surface"] == "#F8F6F1"
    assert escopos["escuro/faixa par"]["--surface"] == "#2D2720"


def test_auditor_acusa_vizinhos_indistinguiveis():
    """Contraste contra o FUNDO e contraste entre VIZINHOS sao perguntas
    diferentes. Se o texto secundario encostar no principal, a tabela do
    6.2 continua passando e so a checagem de vizinhanca acusa."""
    colado = CSS_SISTEMA.replace("--text-soft:#6A6055", "--text-soft:#1C1917", 1)
    assert colado != CSS_SISTEMA
    achados = a.auditar(colado, CONTRATO)
    assert any(
        achado.startswith("vizinhanca:") and "abaixo do minimo" in achado
        for achado in achados
    )


def test_auditor_avisa_quando_proibicao_vira_letra_morta():
    """O contrato proibe .link dentro de .lede porque --acento-ink e
    --text-soft nao se separam (1,07:1). Se um dia separarem, a proibicao
    perde a razao de ser — e o auditor tem que dizer isso, senao o contrato
    envelhece para o lado restritivo e ninguem percebe."""
    afastado = CSS_SISTEMA.replace("--text-soft:#6A6055", "--text-soft:#1C1917", 1)
    achados = a.auditar(afastado, CONTRATO)
    assert any("estrito demais" in achado for achado in achados)


def test_auditor_aprova_a_vizinhanca_atual():
    """No estado versionado, os pares proibidos seguem indistinguiveis e os
    exigidos seguem separando — nenhum achado de vizinhanca."""
    achados = a.auditar(CSS_SISTEMA, CONTRATO)
    assert not [achado for achado in achados if achado.startswith("vizinhanca:")]


# ------------------------------------- cascata, glifos e escopo (ciclo 5)
CSS_F4 = "\n".join([
    ":root{--surface:#FFFFFF}",
    "@media (prefers-color-scheme:dark){",
    "  :root{--surface:#241D15}",
    "  .faixa.alt{--surface:#2D2720}",
    "}",
    ".faixa.alt{background:var(--fundo-alt);--surface:#F8F6F1}",
])

CSS_ORDEM_CERTA = "\n".join([
    ":root{--surface:#FFFFFF}",
    ".faixa.alt{--surface:#F8F6F1}",
    "@media (prefers-color-scheme:dark){ .faixa.alt{--surface:#2D2720} }",
])


def test_auditor_acusa_token_declarado_dentro_e_fora_de_media():
    """Regressao do F4: .faixa.alt{--surface} existia no @media escuro E
    fora dele. Mesma especificidade, a de baixo vence NOS DOIS TEMAS, e o
    cartao das faixas pares virava papel branco dentro da faixa escura,
    com o texto do tema escuro por cima."""
    achados = a.auditar_cascata(CSS_F4)
    assert any(achado.startswith("cascata:") for achado in achados)
    assert any(".faixa.alt" in achado and "--surface" in achado for achado in achados)


def test_auditor_aceita_override_de_media_que_vem_depois():
    """O inverso NAO e defeito: condicional depois de incondicional e a
    ordem normal de um tema escuro, e funciona."""
    assert a.auditar_cascata(CSS_ORDEM_CERTA) == []


def test_sistema_nao_tem_token_sombreado():
    assert a.auditar_cascata(CSS_SISTEMA) == []


def test_auditor_acusa_glifo_colado_em_content():
    """content com glifo colado nao sobrevive a round-trip de codificacao —
    foi assim que o visto da .lista-ok virou os bytes C2 B9 33 ("¹3")."""
    colado = '.x::before{content:"' + chr(0x2713) + '"}'
    achados = a.auditar_glifos("teste.css", colado)
    assert any(achado.startswith("glifo:") for achado in achados)


def test_auditor_aceita_escape_css():
    escapado = r'.x::before{content:"\2713"}'
    assert a.auditar_glifos("teste.css", escapado) == []


def test_auditor_acusa_caractere_invisivel():
    invisivel = ".x{color:red}" + chr(0x200B)
    achados = a.auditar_glifos("teste.css", invisivel)
    assert any("invisivel" in achado for achado in achados)


def test_sistema_nao_tem_glifo_nem_invisivel():
    assert a.auditar_glifos("00-sistema.css", CSS_SISTEMA) == []


def test_auditor_resolve_var_entre_tokens():
    """Depois do F4 as superficies de faixa sao var(--surface-alt). Um
    auditor que so lesse hexadecimal deixaria de enxergar o cartao das
    faixas pares — e voltaria a auditar um CSS que nao existe."""
    escopos = a.paletas(CSS_SISTEMA)
    assert escopos["claro/faixa par"]["--surface"] == "#F8F6F1"
    assert escopos["escuro/faixa par"]["--surface"] == "#2D2720"
    assert escopos["tinta no tema claro"]["--surface"] == "#241D15"
    assert escopos["tinta no tema escuro"]["--surface"] == "#352C1F"


def test_auditor_visita_todos_os_escopos():
    """A vizinhanca nao pode escolher onde olhar: foi uma lista de escopos
    embutida numa checagem que deixou a tabela do contrato valendo so no
    tema claro."""
    achados = a.auditar(CSS_SISTEMA, CONTRATO)
    assert not [x for x in achados if x.startswith("escopo:")]

# ----------------------------------------- a imagem de compartilhamento
OG_HTML = (SITE / "parts" / "og.html").read_text(encoding="utf-8")


def test_og_copia_os_tokens_do_sistema_sem_divergir():
    """O og.html e standalone e REPLICA os tokens do tema claro. Copia
    envelhece: se um valor mudar no sistema e nao la, a marca do link passa
    a divergir da marca da pagina devagar, e sem ninguem notar — porque
    ninguem abre o og.html."""
    assert a.auditar_og(CSS_SISTEMA, OG_HTML) == []


def test_og_acusa_cor_que_saiu_da_paleta():
    adulterado = OG_HTML.replace("--acento-ink:#96570A", "--acento-ink:#B4700D", 1)
    assert adulterado != OG_HTML
    achados = a.auditar_og(CSS_SISTEMA, adulterado)
    assert any("--acento-ink" in achado for achado in achados)


def test_og_acusa_fonte_diferente_da_pagina():
    """A dependencia que o plano manda nao deixar implicita: se o contrato
    trocar a fonte de display, a marca do link so acompanha depois de
    alguem rodar gerar_og.py. O auditor avisa que ela ficou para tras."""
    adulterado = OG_HTML.replace('"Bricolage Grotesque","Segoe UI"', '"Archivo","Segoe UI"', 1)
    assert adulterado != OG_HTML
    achados = a.auditar_og(CSS_SISTEMA, adulterado)
    assert any("--font-display" in achado for achado in achados)


def test_og_image_tem_exatamente_1200x630():
    """Qualquer outra dimensao e cortada pelas redes."""
    import gerar_og

    imagem = SITE / "assets" / "og-image.png"
    assert imagem.exists(), "rode: python site/gerar_og.py"
    assert gerar_og.dimensoes_png(imagem) == (1200, 630)

# --------------------------- a rampa, o JS ausente e a subsecao (ciclo 7)
def test_auditor_exige_ordem_de_destaque_invariante_ao_tema():
    """A luminancia dos tres tons de grafico INVERTE entre os temas: no
    claro --dado-fraco e o mais claro, no escuro e o mais escuro. Foi por
    descrever a rampa como "o degrau mais claro" que a legenda da fatia 2
    virou falsa no escuro. O que nao inverte e o destaque contra a faixa,
    e e isso que o auditor cobra."""
    trocado = CSS_SISTEMA.replace("--dado:#EFD7AF", "--dado:#6B5A3C", 1)
    assert trocado != CSS_SISTEMA
    achados = a.auditar(trocado, CONTRATO)
    assert any(
        achado.startswith("rampa:") and "ordem de destaque" in achado
        for achado in achados
    )


def test_ordem_de_destaque_vale_hoje_nos_seis_escopos():
    achados = a.auditar(CSS_SISTEMA, CONTRATO)
    assert not [x for x in achados if x.startswith("rampa:")]


def test_sistema_oferece_a_chave_de_javascript():
    """Nenhuma fatia consegue condicionar CSS a classe js — o verificador
    exige prefixo da fatia e html:not(.js) vaza. Sem estas duas regras no
    sistema, a fatia so tem saidas ruins: controle inerte ou duplicado."""
    assert "html:not(.js) .so-com-js{display:none !important}" in CSS_SISTEMA
    assert ".js .so-sem-js{display:none !important}" in CSS_SISTEMA


def test_sem_js_a_trilha_e_o_botao_de_video_somem():
    """Sem script a .trilha e um retangulo vazio com rotulos descrevendo
    barras que nao existem, e o <button> do video fica desenhado e inerte.
    O sistema resolve os dois sozinho, sem a fatia marcar nada.

    O !important nao e enfeite: sem ele a rede pesa (0,2,0) e (0,3,2), e
    QUALQUER seletor de fatia com id — `#oferta .play`, (1,1,0) — a vence.
    A fatia 4 pagou isso: o botao continuava visivel sem JS, e o CSS estava
    "certo". Ela so descobriu medindo o display computado. Uma rede que perde
    para uma regra normal nao e rede, entao o teste cobra a arma."""
    assert "html:not(.js) .trilha{display:none !important}" in CSS_SISTEMA
    assert (
        "html:not(.js) .proj[data-video] button{display:none !important}"
        in CSS_SISTEMA
    )


def test_o_video_abre_mudo():
    """O contrato diz "nada toca sozinho"; o lightbox chamava play() sem
    muted."""
    js = (SITE / "parts" / "script.js").read_text(encoding="utf-8")
    assert "video.muted = true" in js
    assert js.index("video.muted = true") < js.index("var p = video.play();")


def test_a_subsecao_tem_primitiva_com_as_tres_medidas_fixas():
    """A .abertura fixava o topo da faixa e nada fixava o segundo nivel:
    mediu-se h3->paragrafo a 12, 20 e 32px, e tres medidas de leitura."""
    bloco = CSS_SISTEMA[CSS_SISTEMA.index(".sub{"):]
    bloco = bloco[:bloco.index("}")]
    assert "gap:var(--e-3)" in bloco
    assert "margin-bottom:var(--e-5)" in bloco
    assert "max-width:62ch" in bloco


# ---------------------------------------------------------------- o texto
def _fatia(nome: str) -> str:
    """O HTML de uma fatia SEM os comentarios de projeto — ou seja, o texto
    que o leitor ve.

    Tirar o comentario nao e detalhe: os vetos abaixo cobram o texto
    PUBLICADO, e o comentario de cada fatia precisa poder dizer o que saiu e
    por que ("aqui exigia-se Python; saiu em 26/08"). Sem esta linha, o
    proprio registro da decisao derrubaria o teste que a decisao criou."""
    bruto = (SITE / "parts" / f"{nome}.html").read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", " ", bruto, flags=re.S)


def test_a_porta_do_gestor_nao_exige_programador_nem_maquina():
    """A 01b existe para derrubar "isso e coisa de TI, eu nao tenho equipe" e,
    no mesmo bloco, reintroduzia a objecao como requisito: exigia alguem que
    lesse Python e uma maquina Windows.

    Decisao do usuario em 26/08/2026 (spec 2026-08-26-landing-porta-do-gestor,
    D1 e D2): o degrau de entrada e querer conhecer o projeto, nao ter um
    programador. O Windows sai junto porque dizer "Windows so se for o SIAPE"
    abre a pergunta seguinte, cuja resposta e servidor online pago do proprio
    bolso."""
    texto = _fatia("01b-gestor")
    assert "Python" not in texto
    assert "Windows" not in texto
    assert "3270" not in texto


def test_a_porta_do_gestor_nao_fecha_no_e_mail_nem_termina_ai():
    """D3 e D4: nao limitar o contato ao e-mail, e nao fechar portas. O
    limite continua DITO (quem implanta e a equipe do orgao) — o que sai e a
    porta batendo."""
    texto = _fatia("01b-gestor")
    assert "termina aí" not in texto.lower()
    assert "por e-mail" not in texto
    assert "não há acompanhamento" not in texto


def test_a_porta_do_gestor_diz_o_que_basta_e_quem_faz():
    """O cartao passa a dizer o que basta, e mantem UM item sobre pessoa. Sem
    ele os tres restantes (fluxo, acesso, autorizacao) nao respondem "quem
    faz?" — e o leitor completa a lacuna com "entao e TI mesmo", que e
    exatamente a objecao que a secao existe para derrubar. Cobre tambem a
    frase de D1 ("o degrau de entrada e querer conhecer o projeto, nao ter
    um programador"), que virou texto no paragrafo da objecao e nao tinha
    asserção nenhuma."""
    texto = _fatia("01b-gestor")
    assert "Por onde isso começa" in texto
    assert "Uma pessoa da própria área" in texto
    assert "O que a sua unidade precisa ter" not in texto
    assert "E você não precisa decidir nada agora" in texto


def test_a_comparacao_honesta_nao_transforma_python_em_pre_requisito():
    """A 01b dispensa o requisito tecnico e, no mapa, manda o leitor para o
    #contexto — onde o cartao "Automatizar com o INTEGRA" dizia "Para comecar:
    alguem da equipe le e ajusta Python". O leitor saia pela porta da frente e
    reencontrava a exigencia tres secoes abaixo.

    O CUSTO continua dito: o cartao existe para por os dois precos a vista, e
    "acompanha o roteiro" mantem que a automacao exige alguem por perto. O que
    sai e a linguagem de programacao como condicao de entrada."""
    texto = _fatia("03-contexto")
    assert "Python" not in texto
    assert "Alguém da própria área acompanha o roteiro." in texto


def test_o_convite_nao_exige_programador_nem_maquina():
    """A 05 e o destino do botao da 01b. Ela pedia a versao do SEI, se as
    maquinas eram Windows e se havia alguem que programasse — ou seja, a
    barreira de que a 01b acabara de dispensar o leitor, tres telas abaixo.
    Uma pagina que se desmente no clique que ela mesma pediu. A frase
    "alguém que programe" nao contem nenhuma das tres palavras acima, entao
    o teste passaria intacto com ela de volta — e e a edicao que mais
    diretamente qualifica o leitor, por isso ganha asserção propria."""
    texto = _fatia("05-conversao")
    assert "Python" not in texto
    assert "Windows" not in texto
    assert "3270" not in texto
    assert "alguém que programe" not in texto


def test_o_convite_nao_nega_o_formulario_nem_termina_ai():
    """D3 e D4. "Nao ha formulario nesta pagina, e nao vai haver" e "Termina
    ai" sao as duas portas se fechando; o limite continua dito no positivo
    (quem implanta e a equipe do orgao), e a frase de registro — "nao uma
    central de atendimento" — permanece, porque ela diz o registro da conversa
    sem fechar nada."""
    texto = _fatia("05-conversao")
    assert "não vai haver" not in texto
    assert "termina aí" not in texto.lower()
    assert "não uma central de atendimento" in texto


def test_o_convite_oferece_mais_de_um_caminho():
    """D3: "nao quero limitar no texto que estamos limitados a contato por
    e-mail e nada mais". O e-mail continua e continua sendo o primario; o que
    entra e um segundo caminho, para quem prefere falar a escrever.

    O numero foi conferido contra o portao de privacidade antes de entrar:
    24988493257 nao passa no digito verificador do modulo 11, entao nao e
    falso positivo de CPF (ver test_telefone_de_onze_digitos_...).

    As quatro asserções originais so pegavam o .fecho: ele sozinho ja traz
    tel:, wa.me e o numero formatado, entao a linha do .rodape podia sumir
    sem que nenhuma delas reclamasse. A contagem == 2 e o rotulo do rodape
    amarram os DOIS lugares de publicacao, nao so o primeiro."""
    texto = _fatia("05-conversao")
    assert "mailto:marco.aurelio-silva@gestao.gov.br" in texto
    assert "tel:+5524988493257" in texto
    assert "https://wa.me/5524988493257" in texto
    assert "(24) 98849-3257" in texto
    assert texto.count("(24) 98849-3257") == 2
    assert '<span class="rot">telefone</span>' in texto


def test_a_porta_do_gestor_nao_cobra_preco_na_entrada():
    """O cartao "O que nao da para prometer" saiu em 26/08/2026, por decisao
    do usuario: antipatico, "principalmente por que fala de preco". Falar de
    custo na secao que existe para ABRIR uma porta e receber o visitante com
    uma fatura na mao.

    A comparacao honesta NAO se perdeu — o cartao dos dois precos continua no
    #contexto, que e onde chega quem foi procurar por ela. O que a pagina
    deixou de dizer, e foi apontado ao usuario antes da decisao: que o prazo
    de um piloto e desconhecido.

    Sem este portao o cartao volta numa edicao futura e ninguem percebe."""
    texto = _fatia("01b-gestor")
    assert "O que não dá para prometer" not in texto
    assert "os dois preços à vista" not in texto


def test_a_porta_do_gestor_abre_pela_demanda_que_cresce():
    """A abertura dizia "A equipe encolheu", que e vago, e depois "Parte da
    equipe se aposenta", que enquadrava a secao como PERDA DE GENTE. O critico
    cego mostrou o custo disso: assim enquadrada, o "8 -> 4 tecnicos" da fatia
    02 lia como precedente de corte de pessoal — e a equipe do gestor leria
    igual, sendo justamente quem precisa colaborar no piloto.

    Com o foco na demanda que cresce, o mesmo numero volta a significar gente
    liberada para outra frente. A aposentadoria sem reposicao continua dita,
    na lede.

    Sem exclamacao: a pagina inteira tem ZERO no texto visivel, e os cinco h2
    sao declarativos. Um "!" aqui seria o unico da pagina."""
    texto = _fatia("01b-gestor")
    assert "A demanda aumenta. A força de trabalho, não." in texto
    assert "aposentadoria sem reposição" in texto
    assert "A equipe encolheu" not in texto
    assert "Parte da equipe se aposenta" not in texto
    assert "!" not in texto.split("<h2>")[1].split("</h2>")[0]


def test_a_pagina_nao_vende_uma_solucao():
    """"Solucao" esta na lista de palavras vetadas por implicar transacao
    (§ 0 da spec de 20/08, junto com cliente, atendimento, oferta e proposta
    de valor). Nenhum portao cobrava essa lista — ela se cumpria a olho — e em
    26/08/2026 a palavra quase entrou na .promessa da 01b, sugerida por quem
    tinha acabado de pedir um texto MENOS comercial. E exatamente o risco: em
    texto de trabalho "solucao" passa despercebida.

    So "solucao" entra neste portao. As outras da lista precisam de allowlist
    para nao virarem falso positivo: "cliente" e "atendimento" aparecem em
    texto visivel NEGADOS — "nao ha empresa nem cliente", "nao uma central de
    atendimento" —, que e o oposto de adotar o registro comercial."""
    # RADICAL, nao a palavra: o portao nascido em 26/08 testava "solucao" e
    # deixava passar "Dos blocos as SOLUCOES que ja rodam", um <h3> visivel da
    # fatia 04 — plural nao contem singular. Achado da Revisao, que varreu o
    # texto visivel do index.html montado em vez de confiar no teste.
    for fatia in ("01-hero", "01b-gestor", "02-prova", "03-contexto",
                  "04-oferta", "05-conversao", "nav"):
        assert "soluç" not in _fatia(fatia).casefold(), fatia


def test_a_secao_da_conversa_nao_tem_nome_de_plano_de_servico():
    """A faixa 05 chamava-se "Piloto assistido" na navegacao, no mapa da 01b,
    na pilula e no h2 — e a lede existia para definir o que "assistido" queria
    dizer. Saiu em 26/08/2026 por decisao do usuario: e nome de plano de
    servico, soa a fornecedor descrevendo um pacote, e esse e o registro que o
    § 0 veta. A secao passou a se chamar "Conversa", que e a palavra que a
    propria pagina ja usava em todo lugar."""
    for parte in ("nav", "01b-gestor", "05-conversao"):
        assert "Piloto assistido" not in _fatia(parte), parte
    assert '<a href="#conversao">Conversa</a>' in _fatia("nav")


def test_o_gestor_descobre_o_que_e_MIT_onde_encontra_o_termo():
    """"Licenca MIT" nao diz nada a quem nao e tecnico, e aparece justamente
    no paragrafo que existe para TIRAR o peso da decisao ("nao ha o que
    contratar"). Ate 26/08/2026 a explicacao so chegava na fatia 04, tres
    secoes adiante. A glosa passou a entrar na primeira vez que o gestor
    encontra o termo em prosa."""
    texto = _fatia("01b-gestor")
    assert "sem pagar nada e sem pedir autorização" in texto
    # A condicao da MIT sao DOIS avisos, nao um: o LICENSE exige "The above
    # copyright notice AND THIS PERMISSION NOTICE". A glosa citava so o
    # primeiro, e um orgao que a seguisse ao pe da letra ficava em
    # descumprimento. Achado da Revisao, que foi ler o LICENSE.
    assert "basta manter o aviso de autoria e o texto da licença" in texto


def test_a_porta_do_gestor_convida_sem_repetir_a_faixa_seguinte():
    """A .promessa da 01b repetia o .limite da 05 quase palavra por palavra —
    as duas diferiam por um sinal de pontuacao, e a revisao final da branch
    apontou a duplicacao. Em 26/08/2026 ela passou a convidar a conversar pelo
    meio que o leitor preferir, e o limite ficou so na faixa 05, que e para
    onde o botao daqui leva.

    O h3 mudou junto: "o seu caso PODE SER diferente", e nao "e outro", que
    afirmava do caso alheio uma coisa que ninguem aqui sabe.

    Nenhuma das duas tinha portao. A Revisao provou isso revertendo so o
    paragrafo ao texto anterior e avaliando as 19 assercoes dos outros doze
    testes: passavam todas."""
    texto = _fatia("01b-gestor")
    assert "Podemos conversar pelo meio mais conveniente" in texto
    assert "o seu caso pode ser diferente" in texto
    assert "Quem implanta, configura e opera é a sua equipe" not in texto
    assert "o seu caso é outro" not in texto

