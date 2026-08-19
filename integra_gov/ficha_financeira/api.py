"""API pública: do arquivo PDF às fichas estruturadas.

Amarra as camadas — leitura, parser de layout e conciliação — e resolve o que
só quem enxerga o **PDF inteiro** consegue resolver: qual página é de qual
layout, e o que fazer com as páginas que não puderam ser extraídas.

Um PDF pode conter **mais de uma ficha**. Os extratores do próprio pacote
mesclam blocos de até 15 anos e vários órgãos num único arquivo, com matrícula
e órgão mudando de uma página para outra. Por isso a função principal é plural;
a singular existe para o caso simples e **recusa** escolher quando há mais de
uma identidade.

Os dois layouts conhecidos são lidos: o relatório do SIAPE mainframe
(monoespaçado, largura fixa) e a impressão web do e-SIAPE (tabela por ``|``).
Cada página é classificada pelo seu próprio detector, e o PDF pode misturar os
dois — um arquivo mesclado não precisa ser homogêneo.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from . import _layout_esiape, _layout_siape
from .conciliacao import conciliar
from .exceptions import LayoutNaoReconhecidoError, MultiplasFichasError
from .leitura import OrigemPdf, PaginaTexto, extrair_paginas
from .modelo import Aviso, CodigoAviso, FichaFinanceira, Layout, Origem

__all__ = ["ler_ficha_financeira", "ler_fichas_financeiras"]

#: Os layouts conhecidos, cada um com seu detector e seu parser.
_PARSERS = (
    (Layout.SIAPE, _layout_siape.e_layout_siape, _layout_siape.parsear_paginas),
    (Layout.ESIAPE, _layout_esiape.e_layout_esiape, _layout_esiape.parsear_paginas),
)


def ler_fichas_financeiras(
    origem: OrigemPdf,
    *,
    strict: bool = False,
) -> tuple[FichaFinanceira, ...]:
    """Lê um PDF de ficha financeira e devolve as fichas que ele contém.

    Args:
        origem: caminho, ``bytes`` ou arquivo binário já aberto.
        strict: quando ``True``, um mês que não fecha contra os totais
            impressos vira exceção em vez de aviso. Perda de dado levanta
            sempre, independente disto.

    Returns:
        Uma ficha por identidade e exercício, na ordem em que aparecem no PDF.

    Raises:
        PdfIlegivelError: o arquivo não abre, ou nenhuma página pôde ser
            extraída.
        PdfSemTextoError: o PDF abriu e não tem camada de texto.
        LayoutNaoReconhecidoError: alguma página tem texto e não corresponde a
            nenhum dos layouts conhecidos.
        LinhaNaoReconhecidaError: alguma linha da tabela não foi reconhecida.
        FichaInconsistenteError: só com ``strict=True``.
    """
    paginas = extrair_paginas(origem)
    ilegiveis = {pagina.numero for pagina in paginas if pagina.erro}

    por_layout = _parsear_por_layout(paginas)
    blocos = [bloco for _, bloco in por_layout]
    atribuidas, orfas = _atribuir_ilegiveis(blocos, ilegiveis)

    fichas = []
    for indice, (layout, bloco) in enumerate(por_layout):
        fichas.append(conciliar(
            bloco,
            strict=strict,
            paginas_ilegiveis=atribuidas.get(indice, ()),
            origem=Origem(layout=layout,
                          arquivo=_nome(origem),
                          paginas=bloco.paginas),
        ))

    return tuple(_anexar_orfas(fichas, blocos, orfas))


def ler_ficha_financeira(origem: OrigemPdf, *,
                         strict: bool = False) -> FichaFinanceira:
    """Lê um PDF que contém **uma** ficha.

    Args:
        origem: caminho, ``bytes`` ou arquivo binário já aberto.
        strict: ver :func:`ler_fichas_financeiras`.

    Returns:
        A única ficha do PDF.

    Raises:
        MultiplasFichasError: o PDF contém mais de uma ficha. Devolver a
            primeira seria escolher em silêncio por quem chamou.
        LayoutNaoReconhecidoError: o PDF não contém ficha nenhuma legível.
        FichaFinanceiraError: as demais causas de
            :func:`ler_fichas_financeiras`.
    """
    fichas = ler_fichas_financeiras(origem, strict=strict)

    if not fichas:
        raise LayoutNaoReconhecidoError(
            "o PDF tem texto, mas nenhuma página é de uma ficha financeira "
            "reconhecida")
    if len(fichas) > 1:
        identidades = ", ".join(
            f"{ficha.identificacao.matricula or '?'}/{ficha.exercicio}"
            for ficha in fichas)
        raise MultiplasFichasError(
            f"o PDF contém {len(fichas)} fichas ({identidades}); use "
            f"ler_fichas_financeiras() — os extratores do pacote mesclam "
            f"vários anos e órgãos num arquivo só",
            quantidade=len(fichas))

    return fichas[0]


# --------------------------------------------------------------------------
# Despacho de layout
# --------------------------------------------------------------------------

def _classificar(pagina: PaginaTexto):
    """Diz de qual layout é a página, ou ``None`` se ela não tem conteúdo.

    Página em branco não é erro: um PDF mesclado pode ter folha vazia no meio.
    """
    if pagina.vazia:
        return None
    for layout, detecta, _ in _PARSERS:
        if detecta(pagina):
            return layout

    if _layout_siape.ASSINATURA in pagina.texto:
        # Falhar alto continua certo — sem amostra, adivinhar o que fazer com
        # ela seria pior. Mas o diagnóstico tem de citar o que foi encontrado:
        # dizer só "não corresponde a layout conhecido" numa página que carrega
        # a assinatura do relatório mandaria o usuário desconfiar do arquivo
        # errado.
        raise LayoutNaoReconhecidoError(
            f"a página {pagina.numero} traz a assinatura do relatório do SIAPE "
            f"({_layout_siape.ASSINATURA}) mas não o cabeçalho da tabela de "
            f"rubricas, sem o qual não há o que ler nela",
            pagina=pagina.numero)
    raise LayoutNaoReconhecidoError(
        f"a página {pagina.numero} tem texto mas não corresponde a nenhum "
        f"layout de ficha financeira conhecido",
        pagina=pagina.numero)


def _parsear_por_layout(paginas):
    """Parseia cada trecho contíguo de mesmo layout com o parser dele.

    Trechos, e não o documento inteiro: assim a **ordem** das fichas continua
    sendo a do PDF mesmo num arquivo que misture os dois formatos, e cada ficha
    sabe de qual layout veio.
    """
    resultado = []
    trecho, layout_corrente = [], None

    def despejar():
        if not trecho:
            return
        parsear = next(p for lay, _, p in _PARSERS if lay is layout_corrente)
        resultado.extend((layout_corrente, bloco) for bloco in parsear(trecho))
        trecho.clear()

    for pagina in paginas:
        layout = _classificar(pagina)
        if layout is None:
            continue
        if layout is not layout_corrente:
            despejar()
            layout_corrente = layout
        trecho.append(pagina)
    despejar()
    return resultado


# --------------------------------------------------------------------------
# Páginas ilegíveis: atribuição às fichas
# --------------------------------------------------------------------------

def _atribuir_ilegiveis(blocos, ilegiveis):
    """Distribui as páginas ilegíveis entre os blocos que as contêm.

    Uma página ilegível nunca aparece em ``bloco.paginas`` — sem texto ela não
    é reconhecida como do layout e o parser nem a vê. O que dá para saber é se
    ela caiu **dentro** do intervalo de algum bloco. As que sobram são órfãs:
    não pertencem a nenhuma ficha identificada e podem ser, elas mesmas, uma
    ficha inteira que desapareceu.
    """
    atribuidas: dict = {}
    orfas = set(ilegiveis)

    for indice, bloco in enumerate(blocos):
        if not bloco.paginas:
            continue
        intervalo = set(range(min(bloco.paginas), max(bloco.paginas) + 1))
        dentro = intervalo & set(ilegiveis)
        if dentro:
            atribuidas[indice] = dentro
            orfas -= dentro

    return atribuidas, sorted(orfas)


def _anexar_orfas(fichas, blocos, orfas):
    """Anexa aviso de página órfã às fichas vizinhas — a de antes e a de depois.

    Conservador de propósito: não dá para saber a que ficha a página pertencia,
    e no layout do e-SIAPE uma página pode ser uma ficha inteira. Marcar as
    duas vizinhas deixa a perda visível de onde quer que o consumidor olhe;
    marcar nenhuma repetiria, um andar acima, o buraco que a decisão de expor
    ``PaginaTexto.erro`` fechou.
    """
    if not orfas or not fichas:
        return fichas

    resultado = list(fichas)
    for numero in orfas:
        aviso = Aviso(
            codigo=CodigoAviso.PAGINA_ILEGIVEL,
            mensagem=(f"a página {numero} não pôde ser extraída e não pertence "
                      f"a nenhuma ficha identificada; ela pode conter uma "
                      f"ficha inteira que não está neste resultado"),
        )
        for vizinha in _vizinhas(blocos, numero):
            resultado[vizinha] = replace(
                resultado[vizinha],
                avisos=resultado[vizinha].avisos + (aviso,))
    return resultado


def _vizinhas(blocos, numero: int) -> set:
    """Índices do bloco imediatamente antes e do imediatamente depois."""
    antes: Optional[int] = None
    depois: Optional[int] = None
    for indice, bloco in enumerate(blocos):
        if not bloco.paginas:
            continue
        if max(bloco.paginas) < numero:
            antes = indice
        elif min(bloco.paginas) > numero and depois is None:
            depois = indice
    return {indice for indice in (antes, depois) if indice is not None}


def _nome(origem: OrigemPdf) -> Optional[str]:
    """O caminho do arquivo, quando a leitura veio de um caminho."""
    if isinstance(origem, (str, bytes)):
        return origem if isinstance(origem, str) else None
    caminho = getattr(origem, "__fspath__", None)
    return str(origem) if caminho is not None else None
