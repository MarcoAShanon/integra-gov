#!/usr/bin/env python3
"""Monta site/index.html a partir das partes em site/parts/.

O nginx serve HTML puro. Este montador e ferramenta LOCAL: existe apenas para
que a proxima alteracao da landing seja por secao, e nao uma cacada dentro de
um arquivo de centenas de linhas.

Uso:
    python site/montar.py              # monta a pagina inteira
    python site/montar.py --so 02-prova  # monta so uma fatia (para revisao)
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


def caminho_saida(so: str | None) -> pathlib.Path:
    """index.html para a pagina inteira; preview-<fatia>.html para uma fatia so.

    Cada fatia grava num arquivo proprio para que varios agentes possam
    trabalhar em paralelo sem sobrescrever a previa um do outro.
    """
    return SAIDA if so is None else RAIZ / f"preview-{so}.html"


def montar(so: str | None = None) -> str:
    """Devolve o HTML completo. `so` limita a uma fatia, para revisao isolada."""
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

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="pt-BR">',
            "<head>",
            _ler("head.html"),
            "<style>",
            "\n".join(css),
            "</style>",
            "</head>",
            "<body>",
            '<a class="skip" href="#conteudo">Pular para o conteúdo</a>',
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
    args = ap.parse_args()
    html = montar(so=args.so)
    destino = caminho_saida(args.so)
    destino.write_text(html, encoding="utf-8", newline="\n")
    print(f"{destino} — {len(html.encode('utf-8')) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
