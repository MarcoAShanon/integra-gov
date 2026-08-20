#!/usr/bin/env python3
"""Monta site/index.html a partir das partes em site/parts/.

O nginx serve HTML puro. Este montador e ferramenta LOCAL: existe apenas para
que a proxima alteracao da landing seja por secao, e nao uma cacada dentro de
um arquivo de centenas de linhas.

Uso:
    python site/montar.py              # monta a pagina inteira
    python site/montar.py --so 02-prova  # monta so uma fatia (para revisao)

A navegacao (site/parts/nav.html) vira o conteudo de um <header> proprio,
ANTES do main da pagina (id="conteudo") — nao mora dentro de nenhuma
fatia. Isso da a pagina um landmark "banner" de verdade, com a nav como
landmark de topo, e faz o skip link (que aponta pra #conteudo) pular a
navegacao de fato — pular a nav e o unico proposito de um skip link. Se
nav.html ainda nao existir (as fatias chegam uma por vez), o <header>
sai vazio: montar() nao quebra por causa de uma parte que ainda nao
chegou.
"""
from __future__ import annotations

import argparse
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parent
PARTS = RAIZ / "parts"
SAIDA = RAIZ / "index.html"

FATIAS = ["01-hero", "02-prova", "03-contexto", "04-oferta", "05-conversao"]
IDS_FATIAS = ["hero", "prova", "contexto", "oferta", "conversao"]


def _ler(nome: str) -> str:
    return (PARTS / nome).read_text(encoding="utf-8").strip()


def _ler_opcional(nome: str) -> str:
    """Como _ler(), mas devolve "" se a parte ainda nao existir — pra partes
    que nao bloqueiam a montagem (hoje, so nav.html: ele e escrito pelo
    agente da fatia 1, que chega depois de head.html/00-sistema.css/
    script.js, e montar() nao pode quebrar so porque ele ainda nao chegou)."""
    caminho = PARTS / nome
    return caminho.read_text(encoding="utf-8").strip() if caminho.exists() else ""


def caminho_saida(so: str | None, *, previa: bool = False) -> pathlib.Path:
    """index.html para a pagina inteira; preview-<fatia>.html para uma fatia so;
    previa.html quando previa=True (ignora `so`).

    Cada fatia grava num arquivo proprio para que varios agentes possam
    trabalhar em paralelo sem sobrescrever a previa um do outro.
    """
    if previa:
        return RAIZ / "previa.html"
    return SAIDA if so is None else RAIZ / f"preview-{so}.html"


def montar(so: str | None = None, *, previa: bool = False) -> str:
    """Devolve o HTML completo. `so` limita a uma fatia, para revisao isolada.

    `previa=True` injeta um <meta name="robots" content="noindex,nofollow">
    logo depois do <meta charset> — a previa fica publica numa URL
    adivinhavel, e sem isso um buscador pode indexa-la. Nada mais muda: a
    previa tem que ser byte a byte igual a producao fora essa linha; o
    rel="canonical" continua apontando pra producao, que e a pagina real.
    """
    if so is not None and so not in FATIAS:
        raise ValueError(f"fatia desconhecida: {so!r} (conhecidas: {FATIAS})")

    fatias = [so] if so else FATIAS

    css = ["/* ===== 00-sistema ===== */\n" + _ler("00-sistema.css")]
    corpo = []
    for nome in fatias:
        corpo.append(_ler(f"{nome}.html"))
        arquivo_css = PARTS / f"{nome}.css"
        if arquivo_css.exists():
            css.append(f"/* ===== {nome} ===== */\n" + arquivo_css.read_text(encoding="utf-8").strip())

    head = _ler("head.html")
    if previa:
        # logo depois do <meta charset>: o charset vem primeiro por
        # convencao e precisa estar nos primeiros 1024 bytes do documento.
        head = head.replace(
            '<meta charset="utf-8">',
            '<meta charset="utf-8">\n<meta name="robots" content="noindex,nofollow">',
            1,
        )

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="pt-BR">',
            "<head>",
            head,
            "<style>",
            "\n".join(css),
            "</style>",
            "</head>",
            "<body>",
            '<a class="skip" href="#conteudo">Pular para o conteúdo</a>',
            "<header>",
            _ler_opcional("nav.html"),
            "</header>",
            '<main id="conteudo">',
            "\n".join(corpo),
            "</main>",
            "<script>",
            _ler("script.js"),
            "</script>",
            "</body>",
            "</html>",
            "",
        ]
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--so", metavar="FATIA", help=f"monta so uma fatia: {', '.join(FATIAS)}")
    ap.add_argument(
        "--previa",
        action="store_true",
        help="injeta noindex,nofollow e grava site/previa.html (para publicar em /previa/)",
    )
    args = ap.parse_args()
    html = montar(so=args.so, previa=args.previa)
    destino = caminho_saida(args.so, previa=args.previa)
    destino.write_text(html, encoding="utf-8", newline="\n")
    print(f"{destino} — {len(html.encode('utf-8')) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
