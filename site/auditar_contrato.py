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
   separam por >= 3:1 e os vizinhos por >= 1,7:1. E a ORDEM DE DESTAQUE
   contra a faixa e invariante ao tema: --dado sempre se destaca mais que
   --dado-neutro, e este mais que --dado-fraco. A luminancia dos tres
   inverte entre os temas; o contraste contra o fundo, nao — e e por isso
   que a legenda do grafico so pode ser escrita em cima dele.
3. COBERTURA — cada razao que o contrato publica nas duas tabelas cheias
   (tema claro e tema escuro) tem que bater com o valor recalculado. E esta
   a checagem que pega a celula esquecida.
4. DERIVADOS — as afirmacoes numericas avulsas do contrato (a esmeralda
   aposentada, o ambar da marca que nao pode ser barra, a faixa do fio de
   cabelo) tambem sao recalculadas, em vez de ficarem de fora so por nao
   estarem numa tabela.
5-c. REDE — toda regra `html:not(.js)` leva `!important`. Elas existem
   para a fatia nao precisar lembrar de nada, e sem o !important perdem
   para qualquer seletor com id — que e como toda regra de fatia comeca.

5-b. ESCOPO — TODA checagem roda em TODOS os escopos, e o auditor prova
   que rodou: ao final ele confere que a lista de escopos visitados e a
   lista de escopos que existem. Nenhuma checagem pode trazer a sua
   propria lista de escopos.

   Isto tambem e cicatriz, e da MESMA forma de erro das outras tres, um
   nivel acima: pergunta certa, medida certa, ESCOPO errado. A tabela de
   vizinhanca do contrato nasceu medida so no :root e publicada como se
   fosse universal — mas .faixa.tinta reescopa 15 tokens, e la dentro
   --acento-ink x --text cai de 3,05:1 para 1,68:1. As PROIBICOES
   sobreviviam (sao conservadoras); as PERMISSOES, nao. Uma checagem que
   escolhe onde olhar acaba olhando onde o defeito nao esta.

5. VIZINHANCA — contraste CONTRA O FUNDO e contraste ENTRE VIZINHOS sao
   perguntas diferentes, e a segunda ja nos pegou duas vezes: a rampa de
   dados (tres cores a 1,02:1 entre si, todas passando contra o fundo) e
   o par --acento-ink x --text-soft (1,07:1, os dois passando contra o
   fundo). Por isso ha duas listas aqui. PARES_VIZINHOS sao os que
   PRECISAM se separar. NAO_SEPARAM sao os que o contrato declara
   indistinguiveis — e sobre os quais ele constroi proibicoes, como
   ".link nao vive dentro de .lede". Se um deles passar a se separar, o
   auditor avisa: a proibicao virou letra morta e o contrato ficou
   estrito demais. Contrato que envelhece para o lado permissivo e
   perigoso; para o lado restritivo, e so burrice acumulada.

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
import unicodedata

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

# um token pode valer um hexadecimal OU um var() para outro token. Ler so
# hexadecimal fazia o auditor enxergar um CSS que nao existe mais.
_RE_COR = re.compile(r"(--[a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{6}|var\(\s*--[a-z0-9-]+\s*\))")
_RE_VAR = re.compile(r"var\(\s*(--[a-z0-9-]+)\s*\)")
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


def _resolver(escopo: dict[str, str]) -> dict[str, str]:
    """Troca cada valor `var(--x)` pelo valor de `--x` no mesmo escopo.

    E o minimo de "resolver a cascata em vez de ler declaracoes": depois
    do F4, as superficies de faixa sao `--surface:var(--surface-alt)`, e
    um auditor que so lesse hexadecimal simplesmente nao veria mais o
    valor do cartao das faixas pares.
    """
    resolvido = dict(escopo)
    for _ in range(8):  # profundidade de sobra; corta ciclo por construcao
        pendentes = {k: v for k, v in resolvido.items() if v.startswith("var(")}
        if not pendentes:
            break
        for token, valor in pendentes.items():
            alvo = _RE_VAR.match(valor).group(1)
            if alvo in resolvido and resolvido[alvo] != valor:
                resolvido[token] = resolvido[alvo]
    return {k: v for k, v in resolvido.items() if v.startswith("#")}


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
        nome: _resolver(escopo)
        for nome, escopo in (
            ("claro", claro),
            ("claro/faixa par", alt_claro),
            ("escuro", escuro),
            ("escuro/faixa par", alt_escuro),
            ("tinta no tema claro", tinta_claro),
            ("tinta no tema escuro", tinta_escuro),
        )
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
    # o link dentro de texto de corpo: e o que justifica onde .link pode viver
    ("o link dentro de texto de corpo", "--acento-ink", "--text", "claro"),
    ("o link dentro de texto secundario", "--acento-ink", "--text-soft", "claro"),
)


def _cor(referencia: str, paleta: dict[str, str]) -> str | None:
    return paleta.get(referencia) if referencia.startswith("--") else referencia


# Pares que aparecem LADO A LADO e precisam se distinguir um do outro.
# (rotulo, token A, token B, minimo, escopos)
# (A rampa de dados tem checagem propria, mais acima.)
# NENHUMA destas listas traz escopo: todas rodam em todos os escopos. Ver
# o item 5-b da docstring — foi uma lista de escopos embutida numa
# checagem que deixou a tabela do contrato valendo so no tema claro.
PARES_VIZINHOS = (
    ("o texto secundario ao lado do principal", "--text-soft", "--text", 1.8),
)

# Pares vizinhos cujos numeros o contrato PUBLICA (secao 6.2-b). Cada um e
# recalculado em cada escopo, e cada valor tem que aparecer no contrato —
# e o que obriga a tabela de la a ter uma coluna por escopo.
VIZINHOS_PUBLICADOS = (
    ("--acento-ink", "--text"),
    ("--ok", "--text"),
    ("--acento-ink", "--text-soft"),
    ("--ok", "--text-soft"),
)

# Pares que o contrato declara INDISTINGUIVEIS, e sobre os quais monta
# proibicoes. O auditor cobra que continuem indistinguiveis: se separarem,
# a proibicao virou letra morta e o texto precisa ser revisto.
NAO_SEPARAM = (
    ("--acento-ink", "--text-soft", "8.3-c proibe .link dentro de .lede", 1.5),
    ("--ok", "--text-soft", "8.3-h proibe .lista-ok com texto em --text-soft", 1.5),
)


# ------------------------------------------------------- cascata e glifos
_RE_REGRA = re.compile(r"([^{}]+)\{([^{}]*)\}")


def auditar_cascata(css: str) -> list[str]:
    """Token declarado pelo MESMO seletor em dois lugares de igual peso.

    O defeito F4 em uma frase: `.faixa.alt{--surface:...}` existia dentro
    do @media escuro E fora dele. Mesma especificidade, e a de baixo vence
    NOS DOIS TEMAS — entao o cartao das faixas pares ficava com a
    superficie clara dentro da faixa escura, com o texto do tema escuro
    por cima. Ilegivel, e invisivel para quem le declaracao por
    declaracao.

    A regra: uma declaracao INCONDICIONAL de (seletor, token) nao pode vir
    depois de uma declaracao do mesmo par dentro de um @media. Se vier,
    ela apaga a condicional em todos os temas.
    """
    achados: list[str] = []
    limpo = _RE_COMENTARIO.sub("", css)
    condicionais: dict[tuple[str, str], int] = {}
    incondicionais: dict[tuple[str, str], int] = {}

    # marca as faixas de texto cobertas por @media
    faixas_media: list[tuple[int, int]] = []
    for m in re.finditer(r"@media[^{]*\{", limpo):
        faixas_media.append((m.start(), _fim(limpo, m.end() - 1)))

    def dentro_de_media(pos: int) -> bool:
        return any(ini <= pos <= fim for ini, fim in faixas_media)

    for regra in _RE_REGRA.finditer(limpo):
        seletor = " ".join(regra.group(1).split())
        if seletor.startswith("@") or not seletor:
            continue
        for token, _valor in _RE_COR.findall(regra.group(2)):
            chave = (seletor, token)
            if dentro_de_media(regra.start()):
                condicionais.setdefault(chave, regra.start())
            else:
                incondicionais.setdefault(chave, regra.start())

    for chave, pos_incond in incondicionais.items():
        pos_cond = condicionais.get(chave)
        if pos_cond is not None and pos_incond > pos_cond:
            seletor, token = chave
            achados.append(
                f"cascata: {seletor!r} declara {token} dentro de um @media e "
                f"DE NOVO fora dele, mais abaixo — a de fora vence nos dois "
                f"temas e apaga a condicional (foi o defeito F4)"
            )
    return achados


def auditar_rede_js(css: str) -> list[str]:
    """Rede de ausencia de JavaScript sem !important nao e rede.

    Toda regra `html:not(.js) ...` do sistema existe para esconder um
    elemento que, sem script, seria uma casca inerte: a .trilha vazia, o
    botao de video que nao abre nada. Elas precisam ganhar de QUALQUER
    coisa que uma fatia escreva, e o que uma fatia escreve comeca sempre
    por um id — `#oferta .play` pesa (1,1,0), enquanto
    `html:not(.js) .proj[data-video] button` pesa (0,3,2) e
    `html:not(.js) .trilha` pesa (0,2,0). As duas perdiam.

    E perdiam EM SILENCIO: o CSS continuava valido, o verificador
    continuava passando, e a degradacao simplesmente nao acontecia. So
    apareceu porque alguem mediu o `display` computado em vez de confiar
    na regra — a mesma familia do cartao branco no tema escuro, em que a
    conta estava certa sobre um CSS que nao fazia o que a conta supunha.

    Havia ainda uma assimetria dentro do proprio sistema: as duas
    primitivas que a fatia marca a mao (.so-com-js/.so-sem-js) levavam
    !important, e as duas redes automaticas — as que existem justamente
    para a fatia nao precisar lembrar de nada — nao levavam.
    """
    achados: list[str] = []
    limpo = _RE_COMENTARIO.sub("", css)
    for regra in _RE_REGRA.finditer(limpo):
        seletor = " ".join(regra.group(1).split())
        if "html:not(.js)" not in seletor:
            continue
        for declaracao in regra.group(2).split(";"):
            if not declaracao.strip():
                continue
            if "!important" not in declaracao:
                achados.append(
                    f"rede: {seletor!r} declara {declaracao.strip()!r} sem "
                    f"!important — qualquer seletor de fatia com id vence esta "
                    f"regra, e a degradacao sem JavaScript deixa de acontecer "
                    f"em silencio"
                )
    return achados


def auditar_glifos(nome: str, css: str) -> list[str]:
    """`content:` com byte nao-ASCII, e caractere invisivel em qualquer lugar.

    O `content` da .lista-ok ficou com os bytes C2 B9 33 — "u00b93" — em vez
    do visto: o `\\2713` perdeu a barra invertida num round-trip e o `271`
    virou escape OCTAL. Passou por cinco portoes porque nenhuma fatia tinha
    usado a primitiva ainda. Escape sobrevive a round-trip de codificacao;
    glifo colado nao — entao a regra e escape, e nao "glifo, com cuidado".
    """
    achados: list[str] = []
    for m in re.finditer(r"content\s*:\s*(['\"])(.*?)\1", css, re.S):
        valor = m.group(2)
        fora = [c for c in valor if ord(c) > 127]
        if fora:
            pontos = ", ".join(hex(ord(c)) for c in fora)
            achados.append(
                f"glifo: {nome} tem content com byte nao-ASCII ({pontos}) — "
                f"use escape CSS (\\2713), que sobrevive a round-trip de codificacao"
            )
    for i, ch in enumerate(css):
        if ord(ch) > 127 and unicodedata.category(ch) in ("Cc", "Cf", "Co", "Cn"):
            linha = css.count(chr(10), 0, i) + 1
            achados.append(
                f"glifo: {nome} linha {linha} tem caractere invisivel "
                f"{hex(ord(ch))} ({unicodedata.category(ch)})"
            )
    return achados


def _pilha(texto: str, nome: str) -> str | None:
    """Valor de uma custom property de FONTE, normalizado por espacos."""
    achado = re.search(re.escape(nome) + r"\s*:\s*([^;}]+)", texto)
    return " ".join(achado.group(1).split()) if achado else None


def auditar_og(css_sistema: str, og: str) -> list[str]:
    """O og.html copia tokens do sistema. Copia envelhece — entao se confere.

    A imagem de compartilhamento e uma pagina AUTONOMA: ela nao passa pelo
    montador e nao pode importar o 00-sistema.css, entao replica os tokens
    do tema claro num <style> proprio. Isso e uma duplicacao consciente, e
    duplicacao consciente sem checagem e so duplicacao. Se um valor mudar
    no sistema e nao aqui, a marca do link passa a divergir da marca da
    pagina — devagar, e sem ninguem notar, porque ninguem abre o og.html.
    """
    achados: list[str] = []
    sistema = _bloco(_RE_COMENTARIO.sub("", css_sistema), ":root{")
    copia = _bloco(_RE_COMENTARIO.sub("", og), ":root{")
    for token, valor in copia.items():
        if not valor.startswith("#"):
            continue
        oficial = sistema.get(token)
        if oficial is None:
            achados.append(f"og: {token} nao existe no 00-sistema.css")
        elif oficial.upper() != valor.upper():
            achados.append(
                f"og: {token} vale {valor} no og.html e {oficial} no sistema — "
                f"a imagem de compartilhamento saiu da paleta da pagina"
            )
    # a pilha de fontes e texto, nao cor: compara literal, sem espacos
    for familia in ("--font-display", "--font-mono"):
        oficial = _pilha(css_sistema, familia)
        aqui = _pilha(og, familia)
        if oficial and aqui and oficial != aqui:
            achados.append(
                f"og: {familia} difere do sistema — a marca do link ficaria "
                f"com outra tipografia que a marca da pagina"
            )
    return achados


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

        # 2-b — a ORDEM da rampa contra o fundo tem de ser invariante ao tema.
        # A luminancia dos tres INVERTE entre claro e escuro: no claro
        # --dado-fraco e o mais claro, no escuro e o mais escuro. Descrever a
        # codificacao por "mais clara" faz a legenda ficar falsa em metade das
        # entregas — foi o defeito A1, e a fatia 2 so transcreveu o que o
        # contrato dizia. O que NAO inverte e o contraste contra a faixa:
        # --dado sempre se destaca mais, --dado-fraco sempre menos. E essa
        # propriedade que o contrato agora descreve, entao e essa que se cobra.
        for fundo in ("--bg", "--surface"):
            if fundo not in paleta:
                continue
            cheia, meio, parcial = (
                razao(paleta[t], paleta[fundo]) for t in TOKENS_GRAFICO
            )
            if not cheia > meio > parcial:
                achados.append(
                    f"rampa: [{nome}] contra {fundo} a ordem de destaque e "
                    f"{formatar(cheia)} / {formatar(meio)} / {formatar(parcial)} — "
                    f"--dado precisa se destacar MAIS que --dado-neutro, e este "
                    f"mais que --dado-fraco, em todo tema; senao a legenda do "
                    f"grafico deixa de ser verdadeira num deles"
                )
            else:
                passou.append(
                    f"ok  ordem   [{nome}] destaque contra {fundo}: "
                    f"dado > neutro > fraco"
                )

    # 5 — vizinhanca, em TODOS os escopos (ver 5-b da docstring)
    visitados: set[str] = set()
    for nome, paleta in escopos.items():
        for rotulo, a_tok, b_tok, minimo in PARES_VIZINHOS:
            if a_tok not in paleta or b_tok not in paleta:
                continue
            visitados.add(nome)
            valor = razao(paleta[a_tok], paleta[b_tok])
            if valor < minimo:
                achados.append(
                    f"vizinhanca: [{nome}] {rotulo} — {a_tok} x {b_tok} = "
                    f"{formatar(valor)}, abaixo do minimo de {minimo}"
                )
            else:
                passou.append(f"ok {formatar(valor):>9}  [{nome}] {a_tok} x {b_tok}")

        for a_tok, b_tok, motivo, teto in NAO_SEPARAM:
            if a_tok not in paleta or b_tok not in paleta:
                continue
            visitados.add(nome)
            valor = razao(paleta[a_tok], paleta[b_tok])
            if valor >= teto:
                achados.append(
                    f"vizinhanca: [{nome}] {a_tok} x {b_tok} = {formatar(valor)}, "
                    f"acima de {teto} — eles agora SE SEPARAM, entao {motivo} "
                    f"ficou estrito demais e precisa ser revisto"
                )
            else:
                passou.append(
                    f"ok {formatar(valor):>9}  [{nome}] {a_tok} x {b_tok} segue indistinguivel"
                )

        # numeros que o contrato publica por escopo: a tabela do 6.2-b
        for a_tok, b_tok in VIZINHOS_PUBLICADOS:
            if a_tok not in paleta or b_tok not in paleta:
                continue
            visitados.add(nome)
            texto = formatar(razao(paleta[a_tok], paleta[b_tok]))
            if texto not in contrato:
                achados.append(
                    f"sem lastro: [{nome}] {a_tok} x {b_tok} vale {texto} e esse "
                    f"numero nao aparece no contrato — a tabela de vizinhanca "
                    f"precisa de uma coluna para este escopo"
                )
            else:
                passou.append(f"ok {texto:>9}  [{nome}] {a_tok} x {b_tok} (publicado)")

    # a prova de que nenhuma checagem escolheu onde olhar
    if visitados != set(escopos):
        achados.append(
            f"escopo: a vizinhanca visitou {sorted(visitados)} mas existem "
            f"{sorted(escopos)} — alguma checagem esta escolhendo onde olhar"
        )

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
    achados += auditar_cascata(css)
    achados += auditar_rede_js(css)
    # glifo se checa em TODO CSS de parts, nao so no sistema: qualquer
    # fatia pode colar um caractere e o defeito e o mesmo.
    for arquivo in sorted(PARTS.glob("*.css")):
        achados += auditar_glifos(arquivo.name, arquivo.read_text(encoding="utf-8"))
    og = PARTS / "og.html"
    if og.exists():
        achados += auditar_og(css, og.read_text(encoding="utf-8"))
    if not achados:
        print("auditar_contrato: sem achados — todo numero do contrato tem lastro")
        return 0
    print(f"auditar_contrato: {len(achados)} achado(s)")
    for achado in achados:
        print(f"  - {achado}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
