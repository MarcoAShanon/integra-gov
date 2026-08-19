"""Leitura de ficha financeira em PDF (SIAPE e e-SIAPE) como dados.

Recebe o PDF de uma ficha financeira — de servidor, aposentado, pensionista ou
instituidor — e devolve os lançamentos estruturados: rubrica, descrição,
competência, valor e natureza (rendimento ou desconto).

A biblioteca **não decide nada de negócio**: ela devolve o que está impresso,
em estruturas neutras, e qualquer script escolhe o que fazer com isso —
filtrar uma rubrica, somar um período, comparar exercícios, exportar planilha.

Um PDF pode conter **mais de uma ficha**: os extratores do próprio pacote
mesclam blocos de até 15 anos e vários órgãos num único arquivo. Por isso a
unidade de retorno é *uma identidade em um exercício*, e a API principal é
plural.

Publicados: o contrato de dados
(:mod:`~integra_gov.ficha_financeira.modelo`), as exceções, a leitura bruta do
PDF (:mod:`~integra_gov.ficha_financeira.leitura`) — inclusive
:func:`tem_camada_de_texto`, o guard que distingue um PDF legível de um
impresso com os glifos convertidos em curva vetorial —, o parser do relatório
do SIAPE mainframe e a conciliação (:func:`conciliar`). Falta o parser da
impressão web do e-SIAPE e a API de conveniência que despacha entre os dois.
"""

from .api import ler_ficha_financeira, ler_fichas_financeiras
from .conciliacao import conciliar
from .exceptions import (
    FichaFinanceiraError,
    FichaInconsistenteError,
    LayoutNaoReconhecidoError,
    LinhaNaoReconhecidaError,
    MultiplasFichasError,
    PdfIlegivelError,
    PdfSemTextoError,
)
from .leitura import (
    PaginaTexto,
    abrir_pdf,
    extrair_paginas,
    tem_camada_de_texto,
)
from .modelo import (
    Aviso,
    BlocoCru,
    CodigoAviso,
    Competencia,
    FichaFinanceira,
    Identificacao,
    Lancamento,
    Layout,
    LinhaCrua,
    Natureza,
    Origem,
    TipoBeneficiario,
    TotaisMes,
)

__all__ = [
    "Aviso",
    "BlocoCru",
    "CodigoAviso",
    "Competencia",
    "FichaFinanceira",
    "FichaFinanceiraError",
    "FichaInconsistenteError",
    "Identificacao",
    "Lancamento",
    "Layout",
    "LayoutNaoReconhecidoError",
    "LinhaCrua",
    "LinhaNaoReconhecidaError",
    "MultiplasFichasError",
    "Natureza",
    "Origem",
    "PaginaTexto",
    "PdfIlegivelError",
    "PdfSemTextoError",
    "TipoBeneficiario",
    "TotaisMes",
    "abrir_pdf",
    "conciliar",
    "ler_ficha_financeira",
    "ler_fichas_financeiras",
    "extrair_paginas",
    "tem_camada_de_texto",
]
