#!/usr/bin/env python3
"""Recorta o cubo do lockup oficial, descartando o wordmark embutido.

Por que existe: o lockup oficial (cubo + "Projeto INTEGRA / I.A. & AUTOMACAO")
traz o wordmark em luminancia ~242/255 — praticamente branco, feito so para
fundo escuro. A landing tem fundo ecru claro, entao o wordmark embutido
sumiria. A decisao (usuario, 20/08/2026) foi usar o CUBO como imagem e compor o
wordmark em TEXTO, na fonte de display do contrato: funciona nos dois temas,
fica nitido em qualquer tela e herda a tipografia do redesign.

O cubo pelado que a pagina usava tinha 148x140 — pouco para tela retina. Este
recorte tira o cubo do lockup de 283x393, entregando cerca de 283x275.

Pillow nao esta no venv; o PNG e decodificado e reescrito com zlib e struct da
biblioteca padrao. So RGBA/RGB de 8 bits, sem entrelacamento — que e o formato
dos assets deste projeto.

Uso:
    python site/recortar_cubo.py
"""
from __future__ import annotations

import pathlib
import struct
import zlib

RAIZ = pathlib.Path(__file__).resolve().parent
ORIGEM = RAIZ / "assets" / "logo-integra-claro.png"
DESTINO = RAIZ / "assets" / "cubo-integra.png"

# Uma linha so e considerada "vazia" se nenhum pixel dela passa deste alfa.
ALFA_MINIMO = 24


def _decodificar(caminho: pathlib.Path) -> tuple[int, int, int, list[bytearray]]:
    """Devolve (largura, altura, canais, linhas) de um PNG RGB/RGBA de 8 bits."""
    dados_arquivo = caminho.read_bytes()
    if dados_arquivo[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{caminho} nao e PNG")

    idat = b""
    largura = altura = profundidade = tipo_cor = 0
    i = 8
    while i < len(dados_arquivo):
        (tamanho,) = struct.unpack(">I", dados_arquivo[i : i + 4])
        tipo = dados_arquivo[i + 4 : i + 8]
        corpo = dados_arquivo[i + 8 : i + 8 + tamanho]
        if tipo == b"IHDR":
            largura, altura, profundidade, tipo_cor = struct.unpack(">IIBB", corpo[:10])
        elif tipo == b"IDAT":
            idat += corpo
        elif tipo == b"IEND":
            break
        i += 12 + tamanho

    if profundidade != 8 or tipo_cor not in (2, 6):
        raise ValueError(f"{caminho}: so RGB/RGBA de 8 bits (achei cor={tipo_cor} prof={profundidade})")

    canais = 3 if tipo_cor == 2 else 4
    bruto = zlib.decompress(idat)
    passo = largura * canais

    linhas: list[bytearray] = []
    anterior = bytearray(passo)
    pos = 0
    for _ in range(altura):
        filtro = bruto[pos]
        linha = bytearray(bruto[pos + 1 : pos + 1 + passo])
        pos += 1 + passo
        for x in range(passo):
            a = linha[x - canais] if x >= canais else 0
            b = anterior[x]
            c = anterior[x - canais] if x >= canais else 0
            if filtro == 1:
                linha[x] = (linha[x] + a) & 0xFF
            elif filtro == 2:
                linha[x] = (linha[x] + b) & 0xFF
            elif filtro == 3:
                linha[x] = (linha[x] + (a + b) // 2) & 0xFF
            elif filtro == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                linha[x] = (linha[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        linhas.append(linha)
        anterior = linha

    return largura, altura, canais, linhas


def _codificar(caminho: pathlib.Path, largura: int, canais: int, linhas: list[bytearray]) -> None:
    """Grava um PNG sem filtro (tipo 0 por linha) — simples e reprodutivel."""
    tipo_cor = 2 if canais == 3 else 6

    def bloco(tipo: bytes, corpo: bytes) -> bytes:
        return struct.pack(">I", len(corpo)) + tipo + corpo + struct.pack(">I", zlib.crc32(tipo + corpo) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", largura, len(linhas), 8, tipo_cor, 0, 0, 0)
    corpo = b"".join(b"\x00" + bytes(linha) for linha in linhas)
    caminho.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + bloco(b"IHDR", ihdr)
        + bloco(b"IDAT", zlib.compress(corpo, 9))
        + bloco(b"IEND", b"")
    )


def _linha_vazia(linha: bytearray, largura: int, canais: int) -> bool:
    if canais == 3:
        return False  # sem alfa, nada e "vazio"
    return all(linha[x * canais + 3] < ALFA_MINIMO for x in range(largura))


def main() -> None:
    largura, altura, canais, linhas = _decodificar(ORIGEM)

    # O lockup e cubo em cima, wordmark embaixo, separados por uma faixa
    # transparente. Procuramos essa faixa na metade inferior e cortamos nela.
    corte = None
    for y in range(altura // 2, altura):
        if _linha_vazia(linhas[y], largura, canais):
            corte = y
            break

    if corte is None:
        raise SystemExit(
            "nao achei faixa transparente entre cubo e wordmark — "
            "o recorte automatico nao serve para este arquivo, confira a mao"
        )

    _codificar(DESTINO, largura, canais, linhas[:corte])
    print(f"{ORIGEM.name}: {largura}x{altura}")
    print(f"{DESTINO.name}: {largura}x{corte} — {DESTINO.stat().st_size / 1024:.1f} KB")
    print("wordmark descartado: ele e composto em TEXTO pelo contrato de design")


if __name__ == "__main__":
    main()
