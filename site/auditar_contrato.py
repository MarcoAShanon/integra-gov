#!/usr/bin/env python3
"""Confere que todo numero de contraste do contrato de design tem lastro no CSS.

POR QUE ISTO EXISTE
===================
O `site/parts/contrato.md` e consumido por agentes que constroem uma secao
cada, sem poder perguntar nada a ninguem. Ele afirma dezenas de razoes de
contraste, e essas afirmacoes sao a unica garantia de acessibilidade que as
fatias tem. Um numero errado ali nao e um erro de redacao: e uma promessa de
AA que ninguem cumpriu, propagada para cinco secoes de uma vez.

Este arquivo nao e zelo. E cicatriz. A mesma classe de erro — NUMERO
DECLARADO EM VEZ DE CALCULADO — pegou este contrato tres vezes, e nas tres
quem achou foi uma pessoa lendo com atencao:

1. A esmeralda. O contrato afirmava que o `#10A87E` media "3,3:1 sobre o
   ecru". Ninguem tinha calculado; o valor veio de memoria. O real e
   **2,91:1** — a conclusao (aposentar a esmeralda) continuava certa, mas
   pelo numero errado, na secao que se apresenta como medida.
2. A rampa de dados. O contrato afirmava que as tres cores de grafico se
   distinguiam "por intensidade, nao por matiz". Medidas entre si, davam
   **1,02:1** — mesma luminancia. Em escala de cinza viravam 136/134/132:
   uma massa so para quem tem daltonismo e para impressao em preto e branco.
   A prosa descrevia uma propriedade que a paleta nao tinha.
3. As sete celulas. Ao mudar `--fundo-alt` do tema escuro, sete razoes da
   tabela do § 6.2 ficaram para tras, silenciosamente, apontando para uma
   cor que nao existia mais.

Os tres casos tem a mesma forma: o CSS e a verdade, o contrato e a copia, e
copia envelhece. Este script inverte o fluxo — le os tokens do proprio
`00-sistema.css`, recalcula tudo e cobra do contrato.

REGRA DE USO: mexeu em token de cor, rodou isto. Numero no contrato sem
lastro no CSS e defeito, nao estilo.

O QUE ELE CHECA
===============
1. PISO — todo par texto/fundo da paleta passa AA (4,5:1), e todo par
   objeto-grafico/fundo passa 3:1. Vale nos seis escopos: claro, claro em
   faixa par, escuro, escuro em faixa par, e a faixa de tinta nos dois temas.
2. RAMPA — os extremos da rampa de dados (`--dado` x `--dado-fraco`) se
   separam por >= 3:1 e os vizinhos por >= 1,7:1.
3. COBERTURA — cada razao que o contrato publica nas duas tabelas cheias
   (tema claro e tema escuro) tem que bater com o valor recalculado. E esta
   a checagem que pega a celula esquecida.
4. DERIVADOS — as afirmacoes numericas avulsas do contrato (a esmeralda
   aposentada, o ambar da marca que nao pode ser barra, a faixa do fio de
   cabelo) tambem sao recalculadas, em vez de ficarem de fora so por nao
   estarem numa tabela.

LIMITE HONESTO
==============
A checagem de cobertura pergunta "este numero aparece em algum lugar do
contrato?", nao "aparece na celula certa da tabela certa". Duas razoes
diferentes podem calhar de dar o mesmo valor, e nesse caso uma celula
trocada passaria. Isso e proposital: casar celula com par exigiria um
parser de Markdown e amarraria o auditor ao formato da tabela, que muda.
Ele existe para pegar o numero que ENVELHECEU — que foi o defeito real
das tres vezes —, nao para provar que a diagramacao esta certa.

Uso:
    python site/auditar_contrato.py          # audita; sai 1 se houver achado
    python site/auditar_contrato.py -v       # mostra tambem o que passou
"""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent
PARTS = RAIZ / "parts"

# minimos da WCAG 2: texto normal 4,5:1; objeto grafico e contorno 3:1.
MIN_TEXTO = 4.5
MIN_GRAFICO = 3.0
# separacao interna da rampa de dados (ver contrato, § 6.6). O alvo dos
# extremos e 3:1 — o mesmo da WCAG para objetos adjacentes. O dos vizinhos e
# 1,7:1 porque 3:1 nos tres pares e aritmeticamente impossivel: com o nivel
# mais claro preso em L <= 0,2601, a rampa inteira comporta 6,20:1, ou
# 2,49:1 entre vizinhos em dois degraus, e isso usando preto puro.
MIN_RAMPA_EXTREMOS = 3.0
MIN_RAMPA_VIZINHOS = 1.7

TOKENS_TEXTO = ("--text", "--text-soft", "--acento-ink", "--ok")
TOKENS_GRAFICO = ("--dado", "--dado-neutro", "--dado-fraco")
FUNDOS = ("--bg", "--fundo-alt", "--surface")

_RE_COR = re.compile(r"(--[a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{6})")
_RE_COMENTARIO = re.compile(r"/\*.*?\*/", re.S)


# ------------------------------------------------------------------ cor
def _canal(valor: int) -> float:
    c = valor / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminancia(cor: str) -> float:
    """Luminancia relativa (WCAG 2), de '#RRGGBB'."""
    cor = cor.lstrip("#")
    r, g, b = (int(cor[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _canal(r) + 0.7152 * _canal(g) + 0.0722 * _canal(b)


def razao(a: str, b: str) -> float:
    """Razao de contraste entre duas cores, sempre >= 1."""
    la, lb = luminancia(a), luminancia(b)
    claro, escuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (escuro + 0.05)


def formatar(valor: float) -> str:
    """'5,49:1' — o mesmo formato que o contrato usa, para poder procurar."""
    return f"{valor:.2f}".replace(".", ",") + ":1"


# --------------------------------------------------------------- escopos
def _fim(css: str, inicio: int) -> int:
    """Indice do `}` que fecha o bloco aberto em `inicio`, contando chaves."""
    profundidade = 0
    for i in range(inicio, len(css)):
        if css[i] == "{":
            profundidade += 1
        elif css[i] == "}":
            profundidade -= 1
            if profundidade == 0:
                return i
    return len(css)


def _bloco(css: str, seletor: str, desde: int = 0) -> dict[str, str]:
    """Cores declaradas no bloco `seletor`, contando chaves para achar o fim.

    Contar chaves importa duas vezes. O `@media` escuro contem DOIS blocos
    (`:root` e `.faixa.tinta`), e uma leitura ingenua do media inteiro faria
    o `--surface` da tinta vazar por cima do `--surface` do `:root`. E o
    seletor `.faixa.alt` aparece nos DOIS temas: quem procurar a partir do
    inicio do media escuro acha a versao escura, nao a clara, e passa a
    auditar o tema claro com a superficie do escuro.
    """
    try:
        inicio = css.index(seletor, desde)
    except ValueError:
        return {}
    return dict(_RE_COR.findall(css[inicio : _fim(css, inicio)]))


def paletas(css: str) -> dict[str, dict[str, str]]:
    """Os seis escopos de cor que a pagina pode apresentar."""
    css = _RE_COMENTARIO.sub("", css)
    inicio_escuro = css.index("@media (prefers-color-scheme:dark)")
    fim_escuro = _fim(css, inicio_escuro)

    claro = _bloco(css, ":root{")
    tinta_claro = {**claro, **_bloco(css, ".faixa.tinta{")}
    # a .faixa.alt do tema claro mora entre as primitivas, DEPOIS do fim do
    # @media escuro — procurar a partir do inicio dele acharia a escura.
    alt_claro = {**claro, **_bloco(css, ".faixa.alt{", fim_escuro)}

    escuro = {**claro, **_bloco(css, ":root{", inicio_escuro)}
    alt_escuro = {**escuro, **_bloco(css, ".faixa.alt{", inicio_escuro)}
    tinta_escuro = {
        **escuro,
        **_bloco(css, ".faixa.tinta{"),
        **_bloco(css, ".faixa.tinta{", inicio_escuro),
    }
    # dentro de uma faixa a cor do fundo chama-se --bg: e o que a fatia usa.
    for escopo in (alt_claro, alt_escuro):
        escopo["--bg"] = escopo["--fundo-alt"]
    for escopo in (tinta_claro, tinta_escuro):
        escopo["--bg"] = escopo.get("--fundo-tinta", escopo["--bg"])

    return {
        "claro": claro,
        "claro/faixa par": alt_claro,
        "escuro": escuro,
        "escuro/faixa par": alt_escuro,
        "tinta no tema claro": tinta_claro,
        "tinta no tema escuro": tinta_escuro,
    }


def _pares(paleta: dict[str, str]) -> list[tuple[str, str, float]]:
    """(frente, fundo, minimo) de todo par que a paleta precisa garantir."""
    saida: list[tuple[str, str, float]] = []
    for fundo in FUNDOS:
        if fundo not in paleta:
            continue
        saida += [(t, fundo, MIN_TEXTO) for t in TOKENS_TEXTO if t in paleta]
        saida += [(t, fundo, MIN_GRAFICO) for t in TOKENS_GRAFICO if t in paleta]
    saida += [
        ("--text", "--acento-soft", MIN_TEXTO),
        ("--text-soft", "--acento-soft", MIN_TEXTO),
        ("--acento-ink", "--acento-soft", MIN_TEXTO),
        ("--ok", "--ok-soft", MIN_TEXTO),
        ("--on-acento", "--acento", MIN_TEXTO),
    ]
    return [(f, b, m) for f, b, m in saida if f in paleta and b in paleta]


# ------------------------------------------------------- afirmacoes soltas
# Numeros que o contrato afirma fora das duas tabelas cheias. Ficam aqui
# para serem recalculados tambem — foi um destes (a esmeralda) que abriu
# esta lista.
DERIVADOS = (
    ("a esmeralda aposentada, sobre o ecru", "#10A87E", "--bg", "claro"),
    ("a esmeralda aposentada, sobre o papel", "#10A87E", "--surface", "claro"),
    ("a esmeralda aposentada, sobre a faixa par", "#10A87E", "--fundo-alt", "claro"),
    ("o ambar da marca, que nao pode ser barra", "--acento", "--surface", "claro"),
    ("o fio de cabelo, sobre a faixa par", "--border", "--fundo-alt", "claro"),
    ("o fio de cabelo, sobre o papel", "--border", "--surface", "claro"),
)


def _cor(referencia: str, paleta: dict[str, str]) -> str | None:
    return paleta.get(referencia) if referencia.startswith("--") else referencia


# ------------------------------------------------------------- auditoria
def auditar(css: str, contrato: str, *, verboso: bool = False) -> list[str]:
    """Achados. Lista vazia significa que o contrato tem lastro no CSS."""
    achados: list[str] = []
    passou: list[str] = []
    escopos = paletas(css)

    # 1 e 3 — piso, e cobertura nas duas tabelas cheias
    for nome, paleta in escopos.items():
        publica_tabela = nome in ("claro", "escuro")
        for frente, fundo, minimo in _pares(paleta):
            valor = razao(paleta[frente], paleta[fundo])
            texto = formatar(valor)
            if valor < minimo:
                achados.append(
                    f"piso: [{nome}] {frente} {paleta[frente]} sobre {fundo} "
                    f"{paleta[fundo]} = {texto}, abaixo do minimo de {minimo}"
                )
            elif publica_tabela and texto not in contrato:
                achados.append(
                    f"sem lastro: [{nome}] {frente} sobre {fundo} vale {texto} "
                    f"no CSS e esse numero nao aparece no contrato"
                )
            else:
                passou.append(f"ok {texto:>9}  [{nome}] {frente} sobre {fundo}")

    # 2 — a rampa de dados precisa ser uma rampa
    for nome, paleta in escopos.items():
        if not all(t in paleta for t in TOKENS_GRAFICO):
            continue
        checagens = (
            ("extremos --dado x --dado-fraco", "--dado", "--dado-fraco", MIN_RAMPA_EXTREMOS),
            ("vizinhos --dado x --dado-neutro", "--dado", "--dado-neutro", MIN_RAMPA_VIZINHOS),
            ("vizinhos --dado-neutro x --dado-fraco", "--dado-neutro", "--dado-fraco", MIN_RAMPA_VIZINHOS),

        )
        for rotulo, a, b, minimo in checagens:
            valor = razao(paleta[a], paleta[b])
            if valor < minimo:
                achados.append(
                    f"rampa: [{nome}] {rotulo} = {formatar(valor)}, "
                    f"abaixo do alvo de {minimo}"
                )
            else:
                passou.append(f"ok {formatar(valor):>9}  [{nome}] {rotulo}")

    # 4 — as afirmacoes avulsas
    for rotulo, frente, fundo, escopo in DERIVADOS:
        paleta = escopos[escopo]
        cor_frente, cor_fundo = _cor(frente, paleta), _cor(fundo, paleta)
        if not cor_frente or not cor_fundo:
            achados.append(f"derivado: nao consegui resolver as cores de {rotulo!r}")
            continue
        texto = formatar(razao(cor_frente, cor_fundo))
        if texto not in contrato:
            achados.append(
                f"sem lastro: {rotulo} vale {texto} no CSS e esse numero "
                f"nao aparece no contrato"
            )
        else:
            passou.append(f"ok {texto:>9}  {rotulo}")

    if verboso:
        for linha in passou:
            print(linha)
    print(f"{len(passou) + len(achados)} razoes recalculadas a partir de 00-sistema.css")
    return achados


def main() -> int:
    verboso = "-v" in sys.argv or "--verboso" in sys.argv
    css = (PARTS / "00-sistema.css").read_text(encoding="utf-8")
    contrato = (PARTS / "contrato.md").read_text(encoding="utf-8")
    achados = auditar(css, contrato, verboso=verboso)
    if not achados:
        print("auditar_contrato: sem achados — todo numero do contrato tem lastro")
        return 0
    print(f"auditar_contrato: {len(achados)} achado(s)")
    for achado in achados:
        print(f"  - {achado}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
