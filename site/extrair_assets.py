#!/usr/bin/env python3
"""Extrai para arquivos as imagens que a landing antiga embutia em base64.

Uso unico, versionado como registro do que foi feito:
    python site/extrair_assets.py <html-de-origem>

Gera site/assets/<nome>.<ext>, site/assets/MAPA.md e
site/original/index-slim.html (o HTML com cada base64 trocado pelo caminho do
arquivo — a referencia de TEXTO para as fatias).
"""
from __future__ import annotations

import base64
import hashlib
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent
ASSETS = RAIZ / "assets"
ORIGINAL = RAIZ / "original"

_RE_DATA = re.compile(r"data:image/(png|jpeg|jpg|webp|gif);base64,([A-Za-z0-9+/=]+)")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    origem = pathlib.Path(sys.argv[1])
    html = origem.read_text(encoding="utf-8", errors="replace")

    ASSETS.mkdir(parents=True, exist_ok=True)
    ORIGINAL.mkdir(parents=True, exist_ok=True)

    linhas_mapa = ["# Mapa dos assets extraidos", "", "| arquivo | KB | origem |", "|---|---|---|"]
    vistos: dict[str, str] = {}

    def troca(m: re.Match[str]) -> str:
        fmt, b64 = m.group(1), m.group(2)
        dados = base64.b64decode(b64)
        digest = hashlib.sha256(dados).hexdigest()[:8]
        if digest in vistos:
            return vistos[digest]
        ext = "jpg" if fmt in ("jpeg", "jpg") else fmt
        nome = f"img-{len(vistos) + 1:02d}-{digest}.{ext}"
        (ASSETS / nome).write_bytes(dados)
        linhas_mapa.append(f"| `{nome}` | {len(dados) / 1024:.1f} | base64 embutido no index.html de 18/07/2026 |")
        caminho = f"assets/{nome}"
        vistos[digest] = caminho
        return caminho

    slim = _RE_DATA.sub(troca, html)
    (ORIGINAL / "index-slim.html").write_text(slim, encoding="utf-8", newline="\n")
    (ASSETS / "MAPA.md").write_text("\n".join(linhas_mapa) + "\n", encoding="utf-8", newline="\n")

    print(f"{len(vistos)} imagens extraidas para {ASSETS}")
    print(f"original enxuto: {ORIGINAL / 'index-slim.html'} "
          f"({len((ORIGINAL / 'index-slim.html').read_bytes()) / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
