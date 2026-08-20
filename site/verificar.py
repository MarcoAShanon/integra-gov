#!/usr/bin/env python3
"""Checagens estaticas da landing montada e das partes que a compoem.

Nao altera nada. Devolve uma lista de achados; lista vazia significa integro.
Roda antes de qualquer revisao humana, para que o revisor gaste atencao com o
que so um humano ve.

Uso:
    python site/verificar.py                            # a pagina inteira
    python site/verificar.py site/preview-01-hero.html  # a previa de uma fatia

O modo (pagina inteira x fatia isolada) e inferido pelo NOME do arquivo: um
alvo cujo nome comeca com "preview-" e verificado em modo fatia (ver
verificar()) — casa com o preview-<fatia>.html que montar.py --so gera. Sem
flag pra um agente esquecer de passar.
"""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent

FONTES_VETADAS = {
    "inter", "roboto", "arial", "system-ui", "-apple-system",
    "blinkmacsystemfont", "segoe ui", "helvetica neue", "space grotesk",
}
HOSTS_PERMITIDOS = ("fonts.googleapis.com", "fonts.gstatic.com")
TAGS_DE_RECURSO = ("link", "script", "img", "source", "iframe", "video", "audio")
PALAVRAS_DE_CONCLUSAO = ("completo", "pronto", "finalizado", "fecha o ciclo")

_RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
# CPF sem pontuacao: 11 digitos isolados — nem colados a outros digitos, nem
# a "." ou "," (o que indicaria parte de um numero maior ou de um valor
# formatado, tipo "15.440" ou "12,11").
_RE_CPF_SEM_PONTUACAO = re.compile(r"(?<![\d.,])\d{11}(?![\d.,])")
_RE_TITULO = re.compile(r"<h([1-6])\b", re.I)
_RE_IMG = re.compile(r"<img\b[^>]*>", re.I)
_RE_HREF_MORTO = re.compile(r"""href\s*=\s*(["'])(#)?\1""", re.I)
_RE_TOKEN = re.compile(r"(--[a-z0-9-]+)\s*:", re.I)
# recurso externo via CSS: @import (com ou sem url()) ou url() de propriedade
# (background, src de @font-face etc). So conta se o alvo for absoluto
# (http(s):// ou protocolo-relativo //) — url(/img/x.svg), url(#id) e
# url(data:...) sao locais e nao contam.
_RE_CSS_RECURSO = re.compile(
    r"""(?:@import\s+(?:url\(\s*)?|url\(\s*)['"]?((?:https?:)?//[^'"\)\s]+)""",
    re.I,
)
# um passo de keyframe e "from", "to" ou um percentual (0%, 50%, 50.5%) —
# note que e ancorado nas duas pontas (^...$), nao um startswith: "0%"
# TERMINA em "%", nao comeca, e um seletor de verdade tambem pode conter "%"
# (atributo, calc()) sem ser um passo de keyframe.
_RE_PASSO_KEYFRAMES = re.compile(r"^(?:from|to|\d+(?:\.\d+)?%)$", re.I)


def _sem_comentarios(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _titulos(html: str) -> list[int]:
    return [int(m.group(1)) for m in _RE_TITULO.finditer(html)]


def _e_passo_keyframes(seletores: str) -> bool:
    """True se TODA parte separada por virgula for um passo de keyframe
    (from/to/percentual). Uma parte so que nao seja passo devolve False, e o
    bloco volta a ser verificado como seletor normal."""
    partes = [p.strip() for p in seletores.split(",")]
    return bool(partes) and all(_RE_PASSO_KEYFRAMES.match(p) for p in partes)


def verificar(html: str, *, fatia: bool = False) -> list[str]:
    """Achados no HTML montado.

    `fatia=True` verifica a previa de UMA fatia isolada (ex.:
    `preview-02-prova.html`), nao a pagina inteira. O CLI infere o modo pelo
    nome do arquivo: um alvo cujo nome comeca com "preview-" e tratado como
    fatia automaticamente. Nesse modo:
    - o <h1> pode faltar (pertence ao hero, fatia 1); zero e o caso normal.
      Mais de um <h1> continua sendo achado.
    - a hierarquia de titulos pode comecar num nivel != h1 sem ser "pular
      degrau"; dentro da fatia, o degrau continua valendo.
    - nao se exige skip link nem <main id="conteudo"> — quem emite os dois
      e o montador, na pagina inteira, nao a fatia isolada.
    """
    achados: list[str] = []
    niveis = _titulos(html)

    # --- hierarquia de titulos
    qtd_h1 = niveis.count(1)
    if fatia:
        if qtd_h1 > 1:
            achados.append(f"h1: a fatia tem {qtd_h1} elementos <h1>; no maximo 1 (o h1 e do hero)")
    elif qtd_h1 != 1:
        achados.append(f"h1: a pagina tem {qtd_h1} elementos <h1>; deve ter exatamente 1")
    anterior = None
    for n in niveis:
        if anterior is not None and n > anterior + 1:
            achados.append(f"titulos: h{anterior} seguido de h{n} pula degrau da hierarquia")
            break
        anterior = n

    # --- links mortos
    if _RE_HREF_MORTO.search(html):
        achados.append('links: existe href="#" ou href="" — link que nao leva a lugar nenhum')

    # --- imagens sem alt
    for tag in _RE_IMG.findall(html):
        if not re.search(r"\balt\s*=", tag, re.I):
            achados.append(f"alt: <img> sem atributo alt — {tag[:80]}")

    # --- recursos externos (ancoras <a> nao contam: sao navegacao, nao recurso)
    # aceita tambem protocolo-relativo (//cdn...), que e tao externo quanto
    # https:// mas escapava do "https?://" literal.
    padrao = re.compile(
        r"<(" + "|".join(TAGS_DE_RECURSO) + r")\b[^>]*?\b(?:src|href)\s*=\s*\"((?:https?:)?//[^\"]+)\"",
        re.I,
    )
    for _tag, url in padrao.findall(html):
        if not any(h in url for h in HOSTS_PERMITIDOS):
            achados.append(f"externo: recurso de terceiro nao permitido — {url[:90]}")

    # o CSS final vive inline dentro de <style>: @import e url() sao rotas
    # tao reais quanto <link>/<script> para um CDN entrar sem passar pela
    # checagem acima.
    for url in _RE_CSS_RECURSO.findall(html):
        if not any(h in url for h in HOSTS_PERMITIDOS):
            achados.append(f"externo: recurso de terceiro nao permitido — {url[:90]}")

    # --- fontes vetadas como ESCOLHA (primeira familia), nao como fallback
    # verifica TODAS as declaracoes do token, nao so a primeira — uma fatia
    # pode redeclarar a fonte dentro de um @media e escapar da guarda.
    for prop in ("--font-display", "--font-corpo", "--font-mono"):
        for m in re.finditer(re.escape(prop) + r"\s*:\s*([^;}]+)", html, re.I):
            primeira = m.group(1).split(",")[0].strip().strip("'\"").lower()
            if primeira in FONTES_VETADAS:
                achados.append(f"fonte vetada: {prop} escolhe {primeira!r} como primeira familia")

    # --- skip link (so na pagina inteira — quem emite e o montador, nao a fatia)
    if not fatia:
        if "<body" in html.lower() or "<h1" in html.lower():
            if 'class="skip"' not in html:
                achados.append("skip: falta o skip link para o conteudo principal")

    # --- movimento reduzido (shorthand transition/animation E as longhand:
    # animation-name, animation-duration, transition-property etc). O
    # "(?<!-)" exclui a declaracao de uma CUSTOM PROPERTY: sem ele,
    # "--transition-speed:200ms" batia no regex por causa do "\b" logo apos
    # o segundo hifen, e um token de tempo (exatamente o tipo de coisa que
    # 00-sistema.css declara) acusava reduced-motion sem existir movimento
    # nenhum na pagina.
    #
    # LIMITE HONESTO: isto e uma checagem de "a string existe em algum lugar
    # do documento" — nao prova que TODO trecho com movimento esta dentro de
    # um @media (prefers-reduced-motion). Quem prova isso de verdade e a
    # bateria de navegador do plano (secao 8); nao confie neste verificador
    # alem do que ele consegue enxergar aqui.
    if (
        re.search(r"(?<!-)\b(?:transition|animation)(?:-[a-z]+)?\s*:", html, re.I)
        and "reduced-motion" not in html
    ):
        achados.append("reduced-motion: ha movimento sem @media (prefers-reduced-motion)")

    # --- privacidade
    for cpf in _RE_CPF.findall(html):
        achados.append(f"CPF: padrao de CPF encontrado no HTML — {cpf}")
    for cpf in _RE_CPF_SEM_PONTUACAO.findall(html):
        achados.append(f"CPF: padrao de CPF sem pontuacao encontrado no HTML — {cpf}")

    # --- enquadramento incremental
    texto = re.sub(r"<[^>]+>", " ", html).lower()
    for palavra in PALAVRAS_DE_CONCLUSAO:
        if re.search(r"\b" + re.escape(palavra) + r"\b", texto):
            achados.append(
                f"incremental: a palavra {palavra!r} aparece no texto visivel; "
                "o projeto e publicado modulo a modulo"
            )

    return achados


def verificar_partes(parts: pathlib.Path) -> list[str]:
    """Achados nos CSS das fatias: redefinicao de token e vazamento de seletor."""
    achados: list[str] = []
    sistema = parts / "00-sistema.css"
    if not sistema.exists():
        return [f"partes: {sistema} nao existe"]

    tokens = set(_RE_TOKEN.findall(_sem_comentarios(sistema.read_text(encoding="utf-8"))))

    for arquivo in sorted(parts.glob("*.css")):
        if arquivo.name == "00-sistema.css":
            continue
        css = _sem_comentarios(arquivo.read_text(encoding="utf-8"))
        ident = "#" + arquivo.stem.split("-", 1)[1]

        for token in _RE_TOKEN.findall(css):
            if token in tokens:
                achados.append(f"redefine: {arquivo.name} redefine o token {token} do contrato")

        # nao exclui "@" da classe de caracteres: e o que faz o texto de uma
        # at-rule (@media (...), @keyframes nome) chegar intacto ao
        # startswith("@") abaixo e ser pulado. Excluir "@" aqui e o que
        # fazia a guarda nunca disparar — o "@" nunca sobrevivia para ser
        # comparado. Selecionadores ANINHADOS dentro do bloco da at-rule
        # continuam sendo capturados normalmente pelas iteracoes seguintes
        # do finditer, entao a checagem de prefixo continua valendo la
        # dentro — e la que alguem poderia esconder um seletor vazando.
        for bloco in re.finditer(r"([^{}]+)\{", css):
            seletores = bloco.group(1).strip()
            if not seletores or seletores.startswith("@") or _e_passo_keyframes(seletores):
                continue
            for seletor in seletores.split(","):
                seletor = seletor.strip()
                if seletor and not seletor.startswith(ident) and not seletor.startswith(":root"):
                    achados.append(
                        f"prefixo: {arquivo.name} tem seletor {seletor!r} sem o prefixo {ident} — vaza"
                    )
    return achados


def main() -> int:
    achados: list[str] = []
    alvo = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "index.html"
    fatia = alvo.name.startswith("preview-")
    if alvo.exists():
        achados += verificar(alvo.read_text(encoding="utf-8"), fatia=fatia)
    else:
        achados.append(f"{alvo} nao existe — rode montar.py antes")
    achados += verificar_partes(RAIZ / "parts")

    if not achados:
        print(f"verificar: sem achados ({alvo.name})")
        return 0
    print(f"verificar: {len(achados)} achado(s)")
    for a in achados:
        print(f"  - {a}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
