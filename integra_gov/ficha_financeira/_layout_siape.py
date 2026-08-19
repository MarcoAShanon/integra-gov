"""Parser do relatório do SIAPE mainframe (``L.A54120.DE``) — formato A.

Transforma as páginas de texto em :class:`~integra_gov.ficha_financeira.
modelo.BlocoCru`: exatamente o que está impresso, **sem interpretar**. O
marcador ``R/D`` em branco continua ``None`` aqui; resolvê-lo é trabalho da
conciliação, que faz a herança de grupo e a confere contra os totais.

O relatório é monoespaçado e a informação está na **posição** do caractere,
não em separadores. Toda a geometria está em :data:`COLUNAS_VALOR` e nas
constantes ao lado, expressas como slices Python (fim exclusivo) — a mesma
convenção para todos os campos, porque misturar intervalo inclusivo com
exclusivo é a origem clássica do off-by-one aqui.

Uma página cobre seis meses; um exercício ocupa duas páginas. Páginas
consecutivas com a mesma identidade e o mesmo exercício viram **um** bloco,
porque um PDF pode trazer vários anos e várias pessoas emendados.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Iterable, Optional, Sequence

from ._comum import limpar_campo, normalizar_rotulo, para_decimal
from .exceptions import LayoutNaoReconhecidoError, LinhaNaoReconhecidaError
from .leitura import PaginaTexto
from .modelo import (
    BlocoCru,
    Competencia,
    Identificacao,
    LinhaCrua,
    TipoBeneficiario,
    TotaisMes,
)


__all__ = ["ASSINATURA", "e_layout_siape", "parsear_paginas"]

# --- Geometria da tabela (slices Python, fim exclusivo) --------------------

RUBRICA = slice(0, 5)
DESCRICAO = slice(6, 32)
#: O marcador fica na coluna 33: o rótulo ``R/D`` do cabeçalho começa em 32,
#: mas o caractere de dado alinha com o **meio** do rótulo. Ler a 32 devolveria
#: branco em toda linha e a herança de grupo atribuiria tudo ao primeiro grupo.
MARCADOR = slice(33, 34)
SEQUENCIA = slice(36, 39)
#: Os seis campos de valor: 15 caracteres cada, alinhados à direita.
COLUNAS_VALOR = (slice(41, 56), slice(56, 71), slice(71, 86),
                 slice(86, 101), slice(101, 116), slice(116, 131))

# --- Reconhecimento de linhas ---------------------------------------------

#: Identificador do relatório, impresso no alto de toda página.
ASSINATURA = "L.A54120.DE"
_CABECALHO_TABELA = "R U B R I C A"
_SEPARADOR = re.compile(r"^-+$")
_RUBRICA = re.compile(r"^\d{5} ")
_TOTAL = re.compile(r"^\*{4}")

_RE_TITULO = re.compile(r"FICHA FINANCEIRA\s+(.+?)\s+REFERENTE A\s+(\d{4})")
_RE_EMITIDO = re.compile(r"EMITIDO EM\s*:\s*(\d{2})([A-Z]{3})(\d{4})")
_RE_ORGAO = re.compile(r"ORGAO\s*:\s*(\S+)\s*-\s*(.+)")
_RE_UPAG = re.compile(r"UNID\.PAGADORA\s*:\s*(\S+)\s*-\s*(.+)")
_RE_BENEF = re.compile(r"BENEF\s*:\s*(\S+)\s*-\s*(.+)")
_RE_INST = re.compile(r"INST\.\s*:\s*(\S+)\s*-\s*(.+)")
_RE_BANCO = re.compile(
    r"BANCO/AGENCIA/C\.CORRENTE\s*:\s*([^/\s]+)/([^/\s]+)/(\S+)")

#: Palavra do título → tipo de beneficiário. O literal do título é preservado
#: em :attr:`Identificacao.situacao`, então nada se perde quando o mapa falha.
_TIPOS = {
    "SERVIDOR": TipoBeneficiario.SERVIDOR,
    "APOSENTADO": TipoBeneficiario.APOSENTADO,
    "PENSIONISTA": TipoBeneficiario.PENSIONISTA,
    "INSTITUIDOR": TipoBeneficiario.INSTITUIDOR,
}

_TOTAIS = {
    "TOTALBRUTO": "bruto",
    "TOTALDESCONTOS": "descontos",
    "TOTALLIQUIDO": "liquido",
}

#: Rótulos que aparecem à direita de outro campo na mesma linha do cabeçalho.
#: São eles que delimitam o fim do campo anterior — o espaçamento não serve,
#: porque o próprio conteúdo dos campos contém blocos de espaço.
_ROTULOS_A_DIREITA = (
    "UNID.PAGADORA:",
    "UNID.CONTROLE:",
    "BANCO/AGENCIA/C.CORRENTE",
    "DEP.IR",
    "MATRICULA:",
    "DATA:",
)

_MESES_EMISSAO = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
                  "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}


def e_layout_siape(pagina: PaginaTexto) -> bool:
    """Diz se a página é do relatório do mainframe.

    Exige a assinatura do relatório **e** o cabeçalho da tabela: só a
    assinatura passaria numa folha de rosto sem lançamento nenhum.
    """
    return ASSINATURA in pagina.texto and _CABECALHO_TABELA in pagina.texto


def parsear_paginas(paginas: Sequence[PaginaTexto]) -> tuple[BlocoCru, ...]:
    """Converte as páginas do formato A em blocos crus.

    Páginas que não são deste layout (ou que falharam na extração) são
    ignoradas — quem escolhe o parser é o despachante, e uma página ilegível
    já carrega o próprio erro em :attr:`PaginaTexto.erro`.

    Args:
        paginas: as páginas devolvidas por
            :func:`~integra_gov.ficha_financeira.leitura.extrair_paginas`.

    Returns:
        Um bloco por identidade+exercício, na ordem em que aparecem.

    Raises:
        LinhaNaoReconhecidaError: alguma linha da tabela não casou com nenhum
            padrão conhecido — perda de dado nunca é silenciosa.
        LayoutNaoReconhecidoError: uma página é deste layout mas lhe falta um
            elemento estrutural (o título, de onde saem tipo e exercício).
    """
    return _agrupar(_parsear_pagina(p) for p in paginas if e_layout_siape(p))


# --------------------------------------------------------------------------
# Uma página
# --------------------------------------------------------------------------

class _PaginaParseada:
    """Resultado intermediário de uma página, antes do agrupamento."""

    __slots__ = ("identificacao", "exercicio", "competencias", "linhas",
                 "totais", "emitido_em", "numero")

    def __init__(self, identificacao, exercicio, competencias, linhas,
                 totais, emitido_em, numero):
        self.identificacao = identificacao
        self.exercicio = exercicio
        self.competencias = competencias
        self.linhas = linhas
        self.totais = totais
        self.emitido_em = emitido_em
        self.numero = numero


def _parsear_pagina(pagina: PaginaTexto) -> _PaginaParseada:
    linhas = pagina.texto.splitlines()

    titulo = _achar(linhas, _RE_TITULO)
    if titulo is None:
        # A página tem assinatura e cabeçalho de tabela — é formato A — mas
        # falta o título. Devolvê-la vazia apagaria as rubricas dela do
        # retorno, e log não é contrato.
        raise LayoutNaoReconhecidoError(
            f"página {pagina.numero} é do relatório do SIAPE mas não traz o "
            f"título 'FICHA FINANCEIRA ... REFERENTE A <ano>', de onde saem o "
            f"tipo de beneficiário e o exercício",
            pagina=pagina.numero)
    rotulo, exercicio = titulo.group(1).strip(), int(titulo.group(2))

    indice_tabela = _indice_cabecalho_tabela(linhas)
    if indice_tabela is None:  # pragma: no cover - e_layout_siape já garante
        raise LayoutNaoReconhecidoError(
            f"página {pagina.numero} não traz o cabeçalho da tabela",
            pagina=pagina.numero)

    por_coluna = _competencias_do_cabecalho(linhas[indice_tabela], exercicio)
    corpo = linhas[indice_tabela + 1:]
    linhas_cruas, totais = _parsear_corpo(corpo, por_coluna, pagina.numero)

    return _PaginaParseada(
        identificacao=_identificacao(linhas, rotulo),
        exercicio=exercicio,
        competencias=tuple(c for c in por_coluna if c is not None),
        linhas=linhas_cruas,
        totais=totais,
        emitido_em=_emitido_em(linhas),
        numero=pagina.numero,
    )


def _indice_cabecalho_tabela(linhas: Sequence[str]) -> Optional[int]:
    for indice, linha in enumerate(linhas):
        if _CABECALHO_TABELA in linha:
            return indice
    return None


def _competencias_do_cabecalho(
    cabecalho: str, exercicio: int
) -> tuple[Optional[Competencia], ...]:
    """Lê os meses do cabeçalho da tabela, nunca do número da página.

    Uma ficha com muitas rubricas pode ocupar mais páginas do que as duas do
    caso comum; derivar o mês da posição da página quebraria em silêncio nesse
    caso, e o cabeçalho está sempre impresso.

    Devolve **uma entrada por coluna**, com ``None`` onde o cabeçalho não traz
    mês. Compactar a lista descartando as vazias faria o pareamento
    mês↔coluna deslizar se alguma coluna não-final viesse vazia — e deslizaria
    igual nas linhas de total, de modo que a conferência fecharia com todos os
    rótulos de mês trocados. É corrupção que a autoverificação não pegaria,
    justamente por ser coerente consigo mesma.
    """
    por_coluna: list[Optional[Competencia]] = []
    for coluna in COLUNAS_VALOR:
        sigla = cabecalho[coluna].strip()
        por_coluna.append(Competencia.de_texto(sigla, exercicio) if sigla else None)
    return tuple(por_coluna)


def _parsear_corpo(
    corpo: Sequence[str],
    por_coluna: Sequence[Optional[Competencia]],
    numero_pagina: int,
) -> tuple[tuple[LinhaCrua, ...], tuple[TotaisMes, ...]]:
    linhas_cruas: list[LinhaCrua] = []
    acumulado: dict[Competencia, dict[str, Optional[Decimal]]] = {}

    for texto in corpo:
        if not texto.strip() or _SEPARADOR.match(texto.strip()):
            continue
        if _RUBRICA.match(texto):
            linhas_cruas.append(_linha_de_rubrica(texto, por_coluna,
                                                  numero_pagina))
        elif _TOTAL.match(texto.lstrip()):
            _acumular_total(texto, por_coluna, acumulado, numero_pagina)
        else:
            raise LinhaNaoReconhecidaError(
                f"linha da tabela não reconhecida na página {numero_pagina}: "
                f"{texto.strip()!r}",
                linha=texto, pagina=numero_pagina)

    totais = tuple(
        TotaisMes(competencia=competencia,
                  bruto=valores.get("bruto"),
                  descontos=valores.get("descontos"),
                  liquido=valores.get("liquido"),
                  # Nível cru: ninguém conferiu ainda. Quem confere é a
                  # conciliação, e ela é que decide este bit.
                  confere=False)
        for competencia, valores in acumulado.items()
    )
    return tuple(linhas_cruas), totais


def _linha_de_rubrica(texto: str,
                      por_coluna: Sequence[Optional[Competencia]],
                      numero_pagina: int) -> LinhaCrua:
    marcador = texto[MARCADOR].strip() or None
    if marcador is not None and marcador not in ("R", "D"):
        raise LinhaNaoReconhecidaError(
            f"marcador R/D inesperado {marcador!r} na página {numero_pagina}",
            linha=texto, pagina=numero_pagina)

    return LinhaCrua(
        rubrica=texto[RUBRICA],
        descricao=texto[DESCRICAO].strip(),
        # Em branco fica em branco: a herança de grupo é da conciliação.
        natureza_declarada=marcador,
        sequencia=_inteiro(texto[SEQUENCIA]),
        valores=_valores(texto, por_coluna, numero_pagina),
        # Uma tabela por página, neste layout.
        tabela=numero_pagina,
    )


def _acumular_total(texto: str,
                    por_coluna: Sequence[Optional[Competencia]],
                    acumulado: dict, numero_pagina: int) -> None:
    rotulo = normalizar_rotulo(texto[:COLUNAS_VALOR[0].start])
    campo = _TOTAIS.get(rotulo)
    if campo is None:
        raise LinhaNaoReconhecidaError(
            f"linha de total não reconhecida na página {numero_pagina}: "
            f"{texto.strip()!r}",
            linha=texto, pagina=numero_pagina)

    for competencia, valor in _valores(texto, por_coluna, numero_pagina):
        acumulado.setdefault(competencia, {})[campo] = valor


def _valores(texto: str, por_coluna: Sequence[Optional[Competencia]],
             numero_pagina: int) -> tuple[tuple[Competencia, Decimal], ...]:
    """Lê as células preenchidas da linha, pareando **por posição de coluna**.

    Célula vazia é omitida — a linha do SIAPE vem cortada no último caractere
    não-branco, então os meses finais sem lançamento simplesmente não existem
    no texto e os slices degradam para ``''``.

    Valor numa coluna cujo cabeçalho não traz mês é dado que não dá para
    rotular: levanta, em vez de atribuí-lo ao mês vizinho.
    """
    lidos = []
    for competencia, coluna in zip(por_coluna, COLUNAS_VALOR):
        bruto = texto[coluna].strip()
        if not bruto:
            continue
        if competencia is None:
            raise LinhaNaoReconhecidaError(
                f"valor {bruto!r} na página {numero_pagina} está numa coluna "
                f"sem mês no cabeçalho da tabela",
                linha=texto, pagina=numero_pagina)
        try:
            lidos.append((competencia, para_decimal(bruto)))
        except ValueError as exc:
            raise LinhaNaoReconhecidaError(
                f"valor ilegível em {competencia} na página {numero_pagina}: "
                f"{bruto!r} ({exc})",
                linha=texto, pagina=numero_pagina) from exc
    return tuple(lidos)




def _inteiro(texto: str) -> Optional[int]:
    limpo = texto.strip()
    return int(limpo) if limpo.isdigit() else None


def _identificacao(linhas: Sequence[str], rotulo: str) -> Identificacao:
    orgao = _achar(linhas, _RE_ORGAO)
    upag = _achar(linhas, _RE_UPAG)
    benef = _achar(linhas, _RE_BENEF)
    inst = _achar(linhas, _RE_INST)
    banco = _achar(linhas, _RE_BANCO)

    return Identificacao(
        tipo=_TIPOS.get(rotulo.upper(), TipoBeneficiario.DESCONHECIDO),
        matricula=benef.group(1) if benef else None,
        nome=_nome(benef.group(2)) if benef else None,
        # O literal do título é a fonte do tipo; preservá-lo evita perder
        # informação quando o rótulo não estiver no mapa.
        situacao=rotulo or None,
        orgao_codigo=orgao.group(1) if orgao else None,
        orgao_nome=_nome(orgao.group(2)) if orgao else None,
        upag_codigo=upag.group(1) if upag else None,
        upag_nome=_nome(upag.group(2)) if upag else None,
        instituidor_matricula=inst.group(1) if inst else None,
        instituidor_nome=_nome(inst.group(2)) if inst else None,
        banco=banco.group(1) if banco else None,
        agencia=banco.group(2) if banco else None,
        conta=banco.group(3) if banco else None,
    )


def _nome(bruto: str) -> Optional[str]:
    """Isola o campo e normaliza o espaçamento interno.

    O relatório emenda dois campos na mesma linha, então o texto capturado à
    direita de um rótulo pode arrastar o rótulo seguinte junto: o corte é feito
    no **próximo rótulo conhecido** (:data:`_ROTULOS_A_DIREITA`).

    Cortar no primeiro bloco de dois espaços — o jeito óbvio — perde dado
    impresso: o SIAPE preenche o nome até a largura do campo e emenda o sufixo
    de UF, de modo que ``"UNIDADE FICTICIA DE TESTE  - DF"`` viraria
    ``"UNIDADE FICTICIA DE TESTE"``, com o ``- DF`` descartado. Por isso
    os espaços internos são **colapsados**, nunca usados como separador.
    """
    texto = bruto
    for rotulo in _ROTULOS_A_DIREITA:
        posicao = texto.find(rotulo)
        if posicao != -1:
            texto = texto[:posicao]
    nome = re.sub(r"\s{2,}", " ", texto).strip()
    return nome or None


def _nome(bruto: str) -> Optional[str]:
    """Isola um campo do cabeçalho deste layout."""
    return limpar_campo(bruto, _ROTULOS_A_DIREITA)


def _emitido_em(linhas: Sequence[str]):
    achado = _achar(linhas, _RE_EMITIDO)
    if achado is None:
        return None
    from datetime import date
    mes = _MESES_EMISSAO.get(achado.group(2))
    if mes is None:
        return None
    return date(int(achado.group(3)), mes, int(achado.group(1)))


def _achar(linhas: Sequence[str], padrao: re.Pattern):
    for linha in linhas:
        achado = padrao.search(linha)
        if achado:
            return achado
    return None


# --------------------------------------------------------------------------
# Agrupamento
# --------------------------------------------------------------------------

def _agrupar(paginas: Iterable[_PaginaParseada]) -> tuple[BlocoCru, ...]:
    """Junta páginas consecutivas da mesma identidade e do mesmo exercício.

    O corte é por ``(chave da identificação, exercício)``: um PDF mesclado
    emenda vários anos e, no caso do extrator multi-órgão, várias matrículas.
    """
    blocos: list[BlocoCru] = []
    atual: Optional[_PaginaParseada] = None
    acumulado: dict = {}

    for pagina in paginas:
        chave = (pagina.identificacao.chave, pagina.exercicio)
        if atual is None or chave != (atual.identificacao.chave,
                                      atual.exercicio):
            if atual is not None:
                blocos.append(_montar_bloco(atual, acumulado))
            atual = pagina
            acumulado = {"competencias": [], "linhas": [], "totais": [],
                         "paginas": []}
        _absorver(acumulado, pagina)

    if atual is not None:
        blocos.append(_montar_bloco(atual, acumulado))
    return tuple(blocos)


def _absorver(acumulado: dict, pagina: _PaginaParseada) -> None:
    for competencia in pagina.competencias:
        if competencia not in acumulado["competencias"]:
            acumulado["competencias"].append(competencia)
    acumulado["linhas"].extend(pagina.linhas)
    acumulado["totais"].extend(pagina.totais)
    acumulado["paginas"].append(pagina.numero)


def _montar_bloco(primeira: _PaginaParseada, acumulado: dict) -> BlocoCru:
    return BlocoCru(
        identificacao=primeira.identificacao,
        exercicio=primeira.exercicio,
        competencias=tuple(sorted(acumulado["competencias"])),
        linhas=tuple(acumulado["linhas"]),
        totais_lidos=tuple(acumulado["totais"]),
        emitido_em=primeira.emitido_em,
        paginas=tuple(acumulado["paginas"]),
    )
