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
flag pra um agente esquecer de passar. No mesmo modo, verificar_partes()
tambem restringe a varredura de CSS a SO a fatia daquele preview (+
00-sistema.css) — com cinco agentes construindo fatias em paralelo na
mesma arvore, o agente de uma fatia nao pode ser acusado pelo CSS de
outro agente ainda pela metade.
"""
from __future__ import annotations

import pathlib
import re
import sys
from urllib.parse import urlsplit

RAIZ = pathlib.Path(__file__).resolve().parent

FONTES_VETADAS = {
    "inter", "roboto", "arial", "system-ui", "-apple-system",
    "blinkmacsystemfont", "segoe ui", "helvetica neue", "space grotesk",
}
HOSTS_PERMITIDOS = ("fonts.googleapis.com", "fonts.gstatic.com", "projeto.govintegra.com.br")
TAGS_DE_RECURSO = ("link", "script", "img", "source", "iframe", "video", "audio", "embed", "use")
PALAVRAS_DE_CONCLUSAO = ("completo", "pronto", "finalizado", "fecha o ciclo")
# Frases EXATAS em que uma palavra de conclusao tem outro sentido no contexto
# ja publicado da pagina ("vem pronto para" = *incluido*, nao "o projeto
# acabou"). Cada frase aqui foi revisada e aprovada por humano — e a valvula
# de escape do veto para O TRECHO ESPECIFICO que esta publicado, NAO um
# passe livre pra "vem pronto para" reaparecer em qualquer frase nova. Por
# isso a frase e o trecho MAIOR e mais especifico que de fato esta no ar
# ("vem pronto para outro orgao adotar"), nao so as tres primeiras palavras
# — "O projeto vem pronto para uso" nao bate nisso e continua achado. Toda
# adicao a esta tupla exige decisao humana; nao e espaco pra um agente
# futuro engordar a lista sozinho ate o portao passar.
FRASES_PERMITIDAS = (
    "vem pronto para outro órgão adotar",
)

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
# ids e ancoras internas: pega href="#x" quebrado (sem id="x" correspondente)
# e id duplicado. href="#" puro/vazio fica pra _RE_HREF_MORTO (regra antiga).
# "(?<=\s)" em vez de "\b": com \b, "data-id=" tambem batia (boundary logo
# apos o hifen), tratando um atributo de gancho de JS como se fosse o id de
# verdade. Exigir espaco imediatamente antes garante que e um atributo
# proprio, nao o sufixo de outro.
_RE_ID = re.compile(r'(?<=\s)id\s*=\s*"([^"]+)"', re.I)
_RE_HREF_ANCORA = re.compile(r'href\s*=\s*"#([^"#]+)"', re.I)
# font-family/font: crus em qualquer regra do CSS — nao so nos 3 tokens do
# sistema. "(?<!-)" e "(?!-)" evitam colidir com "--font-family-x" (custom
# property hipotetica) e com font-size/font-weight/font-style/etc.
_RE_FONT_FAMILY = re.compile(r"(?<!-)\bfont-family\s*:\s*([^;}\"']+)", re.I)
_RE_FONT_SHORTHAND = re.compile(r"\bfont(?!-)\s*:\s*([^;}\"']+)", re.I)
# a familia importada por uma URL do Google Fonts pode ser vetada mesmo com
# o HOST permitido — precisa olhar o parametro family= por dentro.
_RE_GOOGLE_FONTS_LINK = re.compile(r'href\s*=\s*"([^"]*fonts\.googleapis\.com[^"]*)"', re.I)
_RE_GOOGLE_FONTS_FAMILY = re.compile(r"family=([^&\"]+)", re.I)
# poster (video) e data-video (o lightbox transforma em src) nao ficam presos
# a TAGS_DE_RECURSO — podem aparecer em qualquer tag.
_RE_ATRIBUTO_RECURSO_LIVRE = re.compile(r'\b(?:poster|data-video)\s*=\s*"((?:https?:)?//[^"]+)"', re.I)
# srcset e uma lista separada por virgula de "url descritor" (1x, 480w...).
_RE_SRCSET = re.compile(r'\bsrcset\s*=\s*"([^"]+)"', re.I)


def _sem_comentarios(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _sem_comentarios_html(html: str) -> str:
    """Despe <!-- ... --> antes de escanear id/ancora: uma copia comentada
    de um elemento nao esta na pagina renderizada, entao nao pode contar
    pra deteccao de id duplicado nem servir de alvo valido de ancora."""
    return re.sub(r"<!--.*?-->", "", html, flags=re.S)


def _titulos(html: str) -> list[int]:
    return [int(m.group(1)) for m in _RE_TITULO.finditer(html)]


def _e_passo_keyframes(seletores: str) -> bool:
    """True se TODA parte separada por virgula for um passo de keyframe
    (from/to/percentual). Uma parte so que nao seja passo devolve False, e o
    bloco volta a ser verificado como seletor normal."""
    partes = [p.strip() for p in seletores.split(",")]
    return bool(partes) and all(_RE_PASSO_KEYFRAMES.match(p) for p in partes)


def _primeira_familia(valor: str) -> str:
    """Primeira familia de uma lista `font-family` separada por virgula."""
    return valor.split(",")[0].strip().strip("'\"").lower()


def _familia_do_shorthand(valor: str) -> str | None:
    """Extrai a lista de familias de um `font:` shorthand: tudo apos o
    ULTIMO token que contem digito (tamanho, weight numerico, line-height).
    Heuristica suficiente pro CSS desta pagina — nao e um parser CSS
    completo, mas cobre `font:600 1rem Inter,serif`."""
    tokens = valor.split()
    idx_ultimo_numerico = None
    for i, tok in enumerate(tokens):
        if re.search(r"\d", tok):
            idx_ultimo_numerico = i
    if idx_ultimo_numerico is None:
        return None
    resto = " ".join(tokens[idx_ultimo_numerico + 1 :]).strip()
    return resto or None


def _checar_host(url: str, achados: list[str]) -> None:
    """Registra achado de 'externo' se o HOSTNAME de `url` nao estiver na
    allowlist, por IGUALDADE EXATA. Um so lugar pra decidir a regra de
    host — chamado dos quatro pontos que descobrem uma URL de recurso (tag
    src/href, @import/url() em CSS, atributo livre poster/data-video, e
    cada entrada de srcset). O dia em que a regra de host mudar, so mexe
    aqui.

    NAO faz "host permitido in url" (substring): isso deixava passar
    "https://evil.com/fonts.googleapis.com/x.js" (host permitido no PATH),
    "https://fonts.googleapis.com.evil.com/x.js" (subdominio forjado — um
    dominio de outra pessoa) e "https://evil.com/a.png?from=fonts.
    googleapis.com" (host permitido na QUERY). Nenhum subdominio e
    legitimo aqui — os tres hosts da allowlist sao fechados, por isso a
    comparacao e igualdade exata do hostname, nao "termina com" nem
    "contem"."""
    alvo = url
    if alvo.startswith("//"):
        # protocol-relative: urlsplit devolve hostname vazio sem esquema.
        alvo = "https:" + alvo
    hostname = (urlsplit(alvo).hostname or "").lower()
    if hostname not in HOSTS_PERMITIDOS:
        achados.append(f"externo: recurso de terceiro nao permitido — {url[:90]}")


def _cpf_valido(digitos: str) -> bool:
    """Valida os dois digitos verificadores de um CPF de 11 digitos (modulo
    11). Um CPF real tem o 10o e o 11o digito calculaveis a partir dos 9
    primeiros; um telefone ou outro numero de 11 digitos quase nunca
    satisfaz isso — e mais honesto que uma heuristica de formato.

    As dez sequencias de digito repetido (00000000000...99999999999)
    passam no modulo 11 por construcao, mas sao notoriamente invalidas —
    toda biblioteca de referencia as exclui explicitamente, e aqui tambem."""
    if digitos == digitos[0] * len(digitos):
        return False
    nums = [int(c) for c in digitos]

    def _dv(fatia: list[int], peso_inicial: int) -> int:
        soma = sum(d * peso for d, peso in zip(fatia, range(peso_inicial, 1, -1)))
        resto = (soma * 10) % 11
        return resto if resto < 10 else 0

    dv1 = _dv(nums[:9], 10)
    dv2 = _dv(nums[:9] + [dv1], 11)
    return dv1 == nums[9] and dv2 == nums[10]


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
    # despe comentarios HTML (<!-- -->) UMA vez, no topo, e reusa nas
    # checagens que leem marcacao de verdade -- sem isso, um <h1> ou um
    # href="#" so CITADO dentro de um comentario explicativo virava achado
    # falso (o exemplo real: um agente escreveu "<!-- <h1>assim</h1> -->"
    # pra documentar uma decisao, e o verificador contou como um segundo
    # <h1> de verdade). Isto e SO o comentario de HTML: nao mexe em
    # comentario CSS (/* */) dentro de um <style> -- esse e um universo
    # separado, tratado por _sem_comentarios() dentro de verificar_partes,
    # nunca aqui. As checagens embutidas em CSS abaixo (font-family cru,
    # @import/url(), poster/data-video/srcset) continuam lendo o html
    # ORIGINAL, sem essa despida: elas vivem dentro de <style>/atributos, um
    # universo de comentario diferente do de marcacao HTML, e misturar os
    # dois e exatamente o risco que se quer evitar.
    html_sem_comentarios = _sem_comentarios_html(html)
    niveis = _titulos(html_sem_comentarios)

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
    if _RE_HREF_MORTO.search(html_sem_comentarios):
        achados.append('links: existe href="#" ou href="" — link que nao leva a lugar nenhum')

    # --- ids duplicados (roda nos DOIS modos) e ancora interna quebrada (so
    # na pagina inteira -- uma fatia isolada legitimamente aponta pra ancoras
    # de outras fatias que ainda nao existem na previa dela). Uma copia
    # comentada de um id nao esta na pagina renderizada e nao pode contar
    # como duplicata, nem servir de alvo valido de ancora.
    ids = _RE_ID.findall(html_sem_comentarios)
    for id_dup in sorted({i for i in ids if ids.count(i) > 1}):
        achados.append(f"id: {id_dup!r} aparece mais de uma vez no documento")

    if not fatia:
        id_set = set(ids)
        for alvo_ancora in _RE_HREF_ANCORA.findall(html_sem_comentarios):
            if alvo_ancora not in id_set:
                achados.append(
                    f'ancora: href="#{alvo_ancora}" nao tem id="{alvo_ancora}" correspondente'
                )

    # --- imagens sem alt
    for tag in _RE_IMG.findall(html_sem_comentarios):
        if not re.search(r"\balt\s*=", tag, re.I):
            achados.append(f"alt: <img> sem atributo alt — {tag[:80]}")

    # --- recursos externos (ancoras <a> nao contam: sao navegacao, nao recurso)
    # aceita tambem protocolo-relativo (//cdn...), que e tao externo quanto
    # https:// mas escapava do "https?://" literal.
    padrao = re.compile(
        r"<(" + "|".join(TAGS_DE_RECURSO) + r")\b[^>]*?\b(?:src|href)\s*=\s*\"((?:https?:)?//[^\"]+)\"",
        re.I,
    )
    for _tag, url in padrao.findall(html_sem_comentarios):
        _checar_host(url, achados)

    # o CSS final vive inline dentro de <style>: @import e url() sao rotas
    # tao reais quanto <link>/<script> para um CDN entrar sem passar pela
    # checagem acima.
    for url in _RE_CSS_RECURSO.findall(html):
        _checar_host(url, achados)

    # poster (<video>) e data-video (o lightbox transforma em src) nao ficam
    # presos a TAGS_DE_RECURSO — podem estar em qualquer tag.
    for url in _RE_ATRIBUTO_RECURSO_LIVRE.findall(html):
        _checar_host(url, achados)

    # srcset e uma lista "url descritor, url descritor" — cada URL precisa
    # passar pela mesma checagem de host.
    for valor_srcset in _RE_SRCSET.findall(html):
        for entrada in valor_srcset.split(","):
            partes_srcset = entrada.strip().split()
            if not partes_srcset:
                continue
            url = partes_srcset[0]
            if url.startswith(("http://", "https://", "//")):
                _checar_host(url, achados)

    # --- fontes vetadas como ESCOLHA (primeira familia), nao como fallback
    # verifica TODAS as declaracoes do token, nao so a primeira — uma fatia
    # pode redeclarar a fonte dentro de um @media e escapar da guarda.
    for prop in ("--font-display", "--font-corpo", "--font-mono"):
        for m in re.finditer(re.escape(prop) + r"\s*:\s*([^;}]+)", html, re.I):
            primeira = _primeira_familia(m.group(1))
            if primeira in FONTES_VETADAS:
                achados.append(f"fonte vetada: {prop} escolhe {primeira!r} como primeira familia")

    # a checagem acima so olha os 3 tokens do sistema — varre tambem toda
    # declaracao font-family:/font: crua em qualquer regra do CSS (ex.:
    # #prova{font-family:Inter}, que passava limpo antes).
    for m in _RE_FONT_FAMILY.finditer(html):
        primeira = _primeira_familia(m.group(1))
        if primeira in FONTES_VETADAS:
            achados.append(f"fonte vetada: font-family escolhe {primeira!r} como primeira familia")

    for m in _RE_FONT_SHORTHAND.finditer(html):
        familias = _familia_do_shorthand(m.group(1))
        if familias:
            primeira = _primeira_familia(familias)
            if primeira in FONTES_VETADAS:
                achados.append(f"fonte vetada: font (shorthand) escolhe {primeira!r} como primeira familia")

    # o HOST do Google Fonts e permitido, mas a FAMILIA importada dentro da
    # URL (?family=Inter:wght@400) pode ser vetada mesmo assim.
    for url_link in _RE_GOOGLE_FONTS_LINK.findall(html):
        for fam_param in _RE_GOOGLE_FONTS_FAMILY.findall(url_link):
            for familia in fam_param.split("|"):
                nome = familia.split(":")[0].replace("+", " ").strip().lower()
                if nome in FONTES_VETADAS:
                    achados.append(
                        f"fonte vetada: Google Fonts importa {nome!r} (family={familia})"
                    )

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
    # formato PONTUADO: nao exige digito verificador — quem escreve um CPF
    # pontuado esta escrevendo um CPF, valido ou nao, e e isso que a
    # restricao de privacidade quer pegar.
    for cpf in _RE_CPF.findall(html):
        achados.append(f"CPF: padrao de CPF encontrado no HTML — {cpf}")
    # SEM pontuacao: 11 digitos corridos tambem casam com telefone (DDD + 9 +
    # 8 digitos) e outros numeros de 11 digitos. Exigir digito verificador
    # valido elimina praticamente todo falso positivo sem enfraquecer a
    # checagem — e mais honesto que uma heuristica de formato.
    for cpf in _RE_CPF_SEM_PONTUACAO.findall(html):
        if _cpf_valido(cpf):
            achados.append(f"CPF: padrao de CPF sem pontuacao encontrado no HTML — {cpf}")

    # --- enquadramento incremental
    texto = re.sub(r"<[^>]+>", " ", html).lower()
    # normaliza espacos multiplos/quebra de linha antes de comparar com a
    # allowlist — sem isso, um espacamento irregular no texto publicado
    # (ex.: quebra de linha entre palavras) escaparia da frase permitida e
    # geraria falso achado.
    texto = re.sub(r"\s+", " ", texto)
    for frase in FRASES_PERMITIDAS:
        texto = texto.replace(frase.lower(), "")
    for palavra in PALAVRAS_DE_CONCLUSAO:
        if re.search(r"\b" + re.escape(palavra) + r"\b", texto):
            achados.append(
                f"incremental: a palavra {palavra!r} aparece no texto visivel; "
                "o projeto e publicado modulo a modulo"
            )

    return achados


def verificar_partes(parts: pathlib.Path, *, somente: str | None = None) -> list[str]:
    """Achados nos CSS das fatias: redefinicao de token e vazamento de seletor.

    `somente=<fatia>` restringe a varredura ao CSS dessa fatia + 00-sistema.css
    (que ela consome, e por isso continua sendo lido nos dois modos). Sem
    isso, com cinco agentes construindo fatias em paralelo na mesma arvore,
    o agente da fatia X rodando a verificacao da PROPRIA previa receberia
    achados do CSS ainda pela metade de outro agente, misturados com os
    proprios — ou ele edita arquivo alheio (destrutivo, e nao tem como
    perguntar a ninguem), ou reporta a propria fatia como reprovada por
    culpa alheia. Na pagina inteira (somente=None), continua varrendo tudo.
    """
    achados: list[str] = []
    sistema = parts / "00-sistema.css"
    if not sistema.exists():
        return [f"partes: {sistema} nao existe"]

    tokens = set(_RE_TOKEN.findall(_sem_comentarios(sistema.read_text(encoding="utf-8"))))

    if somente is not None:
        candidato = parts / f"{somente}.css"
        arquivos = [candidato] if candidato.exists() else []
    else:
        arquivos = sorted(parts.glob("*.css"))

    for arquivo in arquivos:
        if arquivo.name == "00-sistema.css":
            continue
        css = _sem_comentarios(arquivo.read_text(encoding="utf-8"))
        ident = "#" + arquivo.stem.split("-", 1)[1]
        # so a fatia 1 tem direito ao prefixo "header": a navegacao
        # (nav.html) mora dentro do <header> que o montador emite ANTES do
        # <main> (ver A1) — fora do #hero. Nenhuma outra fatia tem header
        # nenhum pra estilizar, entao nenhuma outra ganha esse prefixo: a
        # protecao contra vazamento entre fatias nao afrouxa em lugar
        # nenhum, so ganha uma excecao estrutural onde o montador de fato
        # coloca o conteudo desta fatia.
        prefixos_validos = [ident, ":root"]
        if arquivo.stem == "01-hero":
            prefixos_validos.append("header")

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
            # a fatia CONSOME os tokens do contrato; nao cria nem redefine em
            # :root. A checagem de prefixo (abaixo) sempre permitiu ":root"
            # explicitamente — o que deixava uma fatia criar um token NOVO
            # (nao so redefinir um existente, que ja e pego por "redefine"
            # acima) passar limpo. Qualquer bloco :root numa fatia e achado,
            # ponto — 00-sistema.css e o unico lugar onde :root e legitimo, e
            # ja foi excluido do loop acima.
            #
            # ":root" precisa ser comparado por PARTE separada por virgula,
            # nao pela string inteira — ":root, #hero .card" falha na
            # igualdade com a string toda, cai direto no laco de prefixo
            # abaixo, onde ":root" e isento explicitamente, e o token novo
            # entra sem achado nenhum. Mesma classe do bug do keyframe
            # percentual: quem compõe um seletor escapa de uma checagem por
            # igualdade da string inteira.
            partes_seletor = [p.strip() for p in seletores.split(",")]
            if ":root" in partes_seletor:
                achados.append(
                    f"root: {arquivo.name} declara um bloco :root — a fatia so consome "
                    "tokens do contrato, nao cria nem redefine em :root"
                )
                continue
            for seletor in seletores.split(","):
                seletor = seletor.strip()
                if seletor and not any(seletor.startswith(p) for p in prefixos_validos):
                    achados.append(
                        f"prefixo: {arquivo.name} tem seletor {seletor!r} sem o prefixo {ident} — vaza"
                    )
    return achados


def main() -> int:
    achados: list[str] = []
    alvo = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "index.html"
    fatia = alvo.name.startswith("preview-")
    # com o alvo preview-<fatia>.html, verificar_partes olha SO o CSS dessa
    # fatia (+ 00-sistema.css) — nao o de outro agente ainda escrevendo em
    # paralelo. alvo.stem de "preview-01-hero.html" e "preview-01-hero";
    # tira o prefixo "preview-" e sobra "01-hero".
    somente = alvo.stem[len("preview-"):] if fatia else None
    if alvo.exists():
        achados += verificar(alvo.read_text(encoding="utf-8"), fatia=fatia)
    else:
        achados.append(f"{alvo} nao existe — rode montar.py antes")
    achados += verificar_partes(RAIZ / "parts", somente=somente)

    if not achados:
        print(f"verificar: sem achados ({alvo.name})")
        return 0
    print(f"verificar: {len(achados)} achado(s)")
    for a in achados:
        print(f"  - {a}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
