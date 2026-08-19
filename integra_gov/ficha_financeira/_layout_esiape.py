"""Parser da impressão web do e-SIAPE — formato B.

Transforma as páginas de texto em :class:`~integra_gov.ficha_financeira.
modelo.BlocoCru`, exatamente como o parser do mainframe: o que está impresso,
**sem interpretar**. O marcador ``R/D`` em branco continua ``None``; quem
resolve a herança é a conciliação.

A diferença estrutural em relação ao formato A é dupla:

* **A tabela é delimitada por ``|``**, não por posição de caractere. O corte é
  por separador, de propósito: aqui o texto passa por um round-trip até virar
  PDF, e a largura das colunas não sobrevive necessariamente à extração — os
  pipes sobrevivem.
* **Uma página traz dois blocos**, um por semestre, cada um com o cabeçalho de
  identificação repetido por inteiro. Por isso o identificador de tabela é um
  contador de blocos, e não o número da página: herdar o grupo ``R/D`` de um
  semestre para o outro trocaria o sinal de um valor.

O layout foi levantado da tela do e-SIAPE com o texto real (a página é HTML);
falta confirmá-lo contra um PDF com camada de texto, que é o que o
:mod:`~integra_gov.ficha_financeira.leitura` receberá na prática.
"""

from __future__ import annotations

import re
from datetime import date
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

__all__ = ["e_layout_esiape", "parsear_paginas"]

#: Campos fixos antes das colunas de mês: rubrica, descrição, R/D e sequência.
_CAMPOS_FIXOS = 4

#: Primeira linha de cada bloco — vem ANTES do título, então é ela que
#: delimita o bloco. Cortar pelo título deixaria o cabeçalho do bloco
#: seguinte cair dentro da região de tabela do anterior.
_INICIO_BLOCO = "Siape - Sistema Integrado"
_TITULO = "Ficha Financeira referente a"
_CABECALHO_TABELA = "Nome Rubrica"
#: Separa o cabeçalho do beneficiário do bloco de quem emitiu o relatório.
#: Os dois usam o rótulo ``Nome:``, então sem este corte o parser leria o nome
#: do servidor que emitiu como se fosse o do titular da ficha.
_RESPONSAVEL = "Dados do responsável"

_RE_TITULO = re.compile(r"Ficha Financeira referente a:\s*(\d{4})")
_RE_EMITIDO = re.compile(r"Emitido em:\s*(\d{2})/(\d{2})/(\d{4})")
_RE_ORGAO = re.compile(r"Órgão:\s*(\S+)\s*-\s*(.+)")
_RE_UPAG = re.compile(r"Unid\. Pagadora\s*:\s*(\S+)\s*-\s*(.+)")
_RE_NOME = re.compile(r"Nome:\s*(\S+)\s*-\s*(.+)")
_RE_SITUACAO = re.compile(r"Situação Servidor:\s*(.+)")
#: Só aparece no PDF impresso — a tela do e-SIAPE não mostra este campo.
_RE_BANCO = re.compile(
    r"Banco/Agência/C\. Corrente:\s*([^/\s]*)/([^/\s]*)/(\S*)")

#: Rótulos que aparecem à direita de outro campo na mesma linha.
_ROTULOS_A_DIREITA = (
    "Banco/Agência",
    "Unid. Pagadora",
    "Unid. Exercício",
    "Situação Servidor:",
    "Função/Exerc.",
    "Localização:",
    "Dep.IR/SF:",
    "T.serv.:",
    "Matrícula:",
    "Data:",
    "Emitido em:",
)

#: Palavra da situação → tipo. ``INSTITUIDOR`` vem antes de ``PENSAO`` porque
#: a situação "INSTITUIDOR PENSAO" contém as duas.
_TIPOS = (
    ("INSTITUIDOR", TipoBeneficiario.INSTITUIDOR),
    ("PENSIONISTA", TipoBeneficiario.PENSIONISTA),
    ("APOSENTADO", TipoBeneficiario.APOSENTADO),
    ("ATIVO", TipoBeneficiario.SERVIDOR),
)

_TOTAIS = {
    "TOTALBRUTO": "bruto",
    "TOTALDESCONTOS": "descontos",
    "TOTALLIQUIDO": "liquido",
}

#: Ruído da impressão do navegador, previsto e descartado. A fronteira com
#: :class:`LinhaNaoReconhecidaError` é deliberada: o que casa aqui é ruído
#: **conhecido**; o que sobra sem casar com nada é perda de dado e levanta.
_RUIDO = (
    re.compile(r"https?://|sigepe\.gov\.br", re.I),   # rodapé com a URL/SESSIONID
    re.compile(r"^\s*\$.*\$\s*$"),                     # título não resolvido
    re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),              # contador de página
    re.compile(r"^\s*\d{2}/\d{2}/\d{4},?\s*\d{2}:\d{2}"),  # data/hora do navegador
    re.compile(r"^\s*_+\s*$"),                         # régua separadora
)

_RE_RUBRICA = re.compile(r"^\s*\d{4,6}\s*$")
_RE_TOTAL = re.compile(r"^\s*\*+\s*$")


def e_layout_esiape(pagina: PaginaTexto) -> bool:
    """Diz se a página é da impressão web do e-SIAPE.

    Exige o título **e** o cabeçalho da tabela: só o título passaria numa
    página de continuação sem lançamento nenhum.
    """
    return _TITULO in pagina.texto and _CABECALHO_TABELA in pagina.texto


def parsear_paginas(paginas: Sequence[PaginaTexto]) -> tuple[BlocoCru, ...]:
    """Converte as páginas do formato B em blocos crus.

    Páginas que não são deste layout são ignoradas — quem escolhe o parser é o
    despachante.

    Returns:
        Um bloco por identidade e exercício. Os dois semestres de um mesmo ano
        são **um** bloco, porque são a mesma ficha impressa em duas partes.

    Raises:
        LinhaNaoReconhecidaError: linha da tabela que não é rubrica, total,
            vazia nem ruído conhecido.
        LayoutNaoReconhecidoError: bloco sem o título de onde saem o exercício
            e o semestre.
    """
    parseados = []
    contador = 0
    for pagina in paginas:
        if not e_layout_esiape(pagina):
            continue
        for linhas in _dividir_blocos(pagina.texto):
            contador += 1
            parseados.append(_parsear_bloco(linhas, pagina.numero, contador))
    return _agrupar(parseados)


# --------------------------------------------------------------------------
# Divisão em blocos (um por semestre)
# --------------------------------------------------------------------------

def _dividir_blocos(texto: str) -> list[list[str]]:
    """Quebra a página nos blocos de semestre.

    O corte é na linha de abertura do relatório, não no título: o título vem
    logo **depois** dela, e cortar ali deixaria a abertura do bloco seguinte
    dentro da região de tabela do anterior — onde ela seria lida como linha
    não reconhecida.
    """
    blocos: list[list[str]] = []
    atual: list[str] = []
    for linha in texto.splitlines():
        if _INICIO_BLOCO in linha and atual:
            blocos.append(atual)
            atual = []
        atual.append(linha)
    if atual:
        blocos.append(atual)
    return [bloco for bloco in blocos if _CABECALHO_TABELA in "\n".join(bloco)]


# --------------------------------------------------------------------------
# Um bloco
# --------------------------------------------------------------------------

class _BlocoParseado:
    __slots__ = ("identificacao", "exercicio", "competencias", "linhas",
                 "totais", "emitido_em", "pagina")

    def __init__(self, identificacao, exercicio, competencias, linhas, totais,
                 emitido_em, pagina):
        self.identificacao = identificacao
        self.exercicio = exercicio
        self.competencias = competencias
        self.linhas = linhas
        self.totais = totais
        self.emitido_em = emitido_em
        self.pagina = pagina


def _parsear_bloco(linhas: Sequence[str], numero_pagina: int,
                   tabela: int) -> _BlocoParseado:
    titulo = _achar(linhas, _RE_TITULO)
    if titulo is None:
        raise LayoutNaoReconhecidoError(
            f"a página {numero_pagina} é da impressão web do e-SIAPE mas um "
            f"dos blocos não traz 'Ficha Financeira referente a: <ano>', de "
            f"onde sai o exercício",
            pagina=numero_pagina)
    exercicio = int(titulo.group(1))

    indice = _indice_cabecalho(linhas)
    por_coluna = _competencias_do_cabecalho(linhas[indice], exercicio)
    linhas_cruas, totais = _parsear_corpo(
        linhas[indice + 1:], por_coluna, numero_pagina, tabela)

    return _BlocoParseado(
        identificacao=_identificacao(linhas[:indice]),
        exercicio=exercicio,
        competencias=tuple(c for c in por_coluna if c is not None),
        linhas=linhas_cruas,
        totais=totais,
        emitido_em=_emitido_em(linhas),
        pagina=numero_pagina,
    )


def _indice_cabecalho(linhas: Sequence[str]) -> int:
    for indice, linha in enumerate(linhas):
        if _CABECALHO_TABELA in linha:
            return indice
    raise LayoutNaoReconhecidoError(  # pragma: no cover - _dividir_blocos filtra
        "bloco do e-SIAPE sem o cabeçalho da tabela de rubricas")


def _competencias_do_cabecalho(
    cabecalho: str, exercicio: int
) -> tuple[Optional[Competencia], ...]:
    """Lê os meses do cabeçalho do bloco, nunca do semestre declarado no título.

    Uma entrada por coluna, com ``None`` onde não há mês: compactar faria o
    pareamento mês↔coluna deslizar se uma coluna não-final viesse vazia, e os
    totais deslizariam junto — a conferência fecharia com os rótulos trocados.
    """
    celulas = _celulas(cabecalho)[_CAMPOS_FIXOS:]
    return tuple(
        # `celula.strip()`, não `celula`: uma célula só de espaços é *truthy*,
        # e sem isto a coluna vazia iria parar em Competencia.de_texto.
        Competencia.de_texto(sigla, exercicio) if (sigla := celula.strip())
        else None
        for celula in celulas
    )


def _parsear_corpo(
    corpo: Sequence[str],
    por_coluna: Sequence[Optional[Competencia]],
    numero_pagina: int,
    tabela: int,
) -> tuple[tuple[LinhaCrua, ...], tuple[TotaisMes, ...]]:
    linhas_cruas: list[LinhaCrua] = []
    acumulado: dict = {}

    for texto in corpo:
        if not texto.strip() or _e_ruido(texto):
            continue
        celulas = _celulas(texto)
        if len(celulas) <= _CAMPOS_FIXOS:
            raise LinhaNaoReconhecidaError(
                f"linha da tabela sem as colunas esperadas na página "
                f"{numero_pagina}: {texto.strip()!r}",
                linha=texto, pagina=numero_pagina)

        rotulo = celulas[0]
        if _RE_RUBRICA.match(rotulo):
            linhas_cruas.append(_linha_de_rubrica(
                texto, celulas, por_coluna, numero_pagina, tabela))
        elif _RE_TOTAL.match(rotulo):
            _acumular_total(texto, celulas, por_coluna, acumulado,
                            numero_pagina)
        elif not rotulo.strip() and not any(c.strip() for c in celulas):
            continue  # linha de preenchimento da tabela
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
                  # Nível cru: ninguém conferiu ainda.
                  confere=False)
        for competencia, valores in acumulado.items()
    )
    return tuple(linhas_cruas), totais


def _linha_de_rubrica(texto: str, celulas: Sequence[str],
                      por_coluna: Sequence[Optional[Competencia]],
                      numero_pagina: int, tabela: int) -> LinhaCrua:
    marcador = celulas[2].strip() or None
    if marcador is not None and marcador not in ("R", "D"):
        raise LinhaNaoReconhecidaError(
            f"marcador R/D inesperado {marcador!r} na página {numero_pagina}",
            linha=texto, pagina=numero_pagina)

    return LinhaCrua(
        rubrica=celulas[0].strip(),
        descricao=celulas[1].strip(),
        # Em branco fica em branco: a herança de grupo é da conciliação.
        natureza_declarada=marcador,
        sequencia=_inteiro(celulas[3]),
        valores=_valores(texto, celulas, por_coluna, numero_pagina),
        tabela=tabela,
    )


def _acumular_total(texto: str, celulas: Sequence[str],
                    por_coluna: Sequence[Optional[Competencia]],
                    acumulado: dict, numero_pagina: int) -> None:
    campo = _TOTAIS.get(normalizar_rotulo(celulas[1]))
    if campo is None:
        raise LinhaNaoReconhecidaError(
            f"linha de total não reconhecida na página {numero_pagina}: "
            f"{celulas[1].strip()!r}",
            linha=texto, pagina=numero_pagina)

    for competencia, valor in _valores(texto, celulas, por_coluna,
                                       numero_pagina):
        acumulado.setdefault(competencia, {})[campo] = valor


def _valores(texto: str, celulas: Sequence[str],
             por_coluna: Sequence[Optional[Competencia]],
             numero_pagina: int) -> tuple[tuple[Competencia, Decimal], ...]:
    """Lê as células preenchidas, pareando por posição de coluna."""
    lidos = []
    for competencia, celula in zip(por_coluna, celulas[_CAMPOS_FIXOS:]):
        bruto = celula.strip()
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


# --------------------------------------------------------------------------
# Cabeçalho de identificação
# --------------------------------------------------------------------------

def _identificacao(cabecalho: Sequence[str]) -> Identificacao:
    """Lê a identificação, parando antes do bloco de quem emitiu.

    Os dois blocos usam o rótulo ``Nome:``; sem esse corte, o nome do servidor
    que emitiu o relatório entraria como o do titular da ficha.
    """
    do_titular = []
    for linha in cabecalho:
        if _RESPONSAVEL in linha:
            break
        do_titular.append(linha)

    orgao = _achar(do_titular, _RE_ORGAO)
    upag = _achar(do_titular, _RE_UPAG)
    nome = _achar(do_titular, _RE_NOME)
    banco = _achar(do_titular, _RE_BANCO)
    situacao_bruta = _achar(do_titular, _RE_SITUACAO)
    situacao = (limpar_campo(situacao_bruta.group(1), _ROTULOS_A_DIREITA)
                if situacao_bruta else None)

    return Identificacao(
        tipo=_tipo(situacao),
        matricula=nome.group(1) if nome else None,
        nome=_campo(nome.group(2)) if nome else None,
        # O literal fica preservado: é a fonte de que o tipo foi derivado.
        situacao=situacao,
        orgao_codigo=orgao.group(1) if orgao else None,
        orgao_nome=_campo(orgao.group(2)) if orgao else None,
        upag_codigo=upag.group(1) if upag else None,
        upag_nome=_campo(upag.group(2)) if upag else None,
        banco=_ou_none(banco.group(1)) if banco else None,
        agencia=_ou_none(banco.group(2)) if banco else None,
        conta=_ou_none(banco.group(3)) if banco else None,
    )


def _ou_none(texto: str) -> Optional[str]:
    """Campo bancário vem como ``000/-/-`` quando não há conta informada."""
    limpo = texto.strip()
    return limpo if limpo and limpo != "-" else None


def _tipo(situacao: Optional[str]) -> TipoBeneficiario:
    if situacao:
        normalizada = normalizar_rotulo(situacao)
        for palavra, tipo in _TIPOS:
            if palavra in normalizada:
                return tipo
    return TipoBeneficiario.DESCONHECIDO


def _emitido_em(linhas: Sequence[str]) -> Optional[date]:
    achado = _achar(linhas, _RE_EMITIDO)
    if achado is None:
        return None
    return date(int(achado.group(3)), int(achado.group(2)),
                int(achado.group(1)))


# --------------------------------------------------------------------------
# Auxiliares
# --------------------------------------------------------------------------

def _celulas(linha: str) -> list[str]:
    return linha.split("|")


def _e_ruido(linha: str) -> bool:
    """Ruído da impressão do navegador — reconhecido e descartado.

    Só o que casa aqui é descartado; qualquer outra linha não vazia na região
    da tabela levanta. Ignorar por omissão é que perderia dado calado.
    """
    return any(padrao.search(linha) for padrao in _RUIDO)


def _campo(bruto: str) -> Optional[str]:
    return limpar_campo(bruto, _ROTULOS_A_DIREITA)


def _inteiro(texto: str) -> Optional[int]:
    limpo = texto.strip()
    return int(limpo) if limpo.isdigit() else None


def _achar(linhas: Sequence[str], padrao: re.Pattern):
    for linha in linhas:
        achado = padrao.search(linha)
        if achado:
            return achado
    return None


def _agrupar(blocos: Iterable[_BlocoParseado]) -> tuple[BlocoCru, ...]:
    """Junta os blocos da mesma identidade e do mesmo exercício.

    Os dois semestres de um ano são a mesma ficha impressa em duas partes;
    identidades diferentes (o PDF multi-órgão) viram fichas diferentes.
    """
    resultado: list[BlocoCru] = []
    atual: Optional[_BlocoParseado] = None
    acumulado: dict = {}

    for bloco in blocos:
        chave = (bloco.identificacao.chave, bloco.exercicio)
        if atual is None or chave != (atual.identificacao.chave,
                                      atual.exercicio):
            if atual is not None:
                resultado.append(_montar(atual, acumulado))
            atual = bloco
            acumulado = {"competencias": [], "linhas": [], "totais": [],
                         "paginas": []}
        for competencia in bloco.competencias:
            if competencia not in acumulado["competencias"]:
                acumulado["competencias"].append(competencia)
        acumulado["linhas"].extend(bloco.linhas)
        acumulado["totais"].extend(bloco.totais)
        if bloco.pagina not in acumulado["paginas"]:
            acumulado["paginas"].append(bloco.pagina)

    if atual is not None:
        resultado.append(_montar(atual, acumulado))
    return tuple(resultado)


def _montar(primeiro: _BlocoParseado, acumulado: dict) -> BlocoCru:
    return BlocoCru(
        identificacao=primeiro.identificacao,
        exercicio=primeiro.exercicio,
        competencias=tuple(sorted(acumulado["competencias"])),
        linhas=tuple(acumulado["linhas"]),
        totais_lidos=tuple(acumulado["totais"]),
        emitido_em=primeiro.emitido_em,
        paginas=tuple(acumulado["paginas"]),
    )
