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
