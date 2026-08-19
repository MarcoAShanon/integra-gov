"""Utilidades compartilhadas pelos parsers de layout.

Os dois formatos imprimem a mesma informação de formas diferentes, mas duas
coisas eles fazem igual: o número em pt-BR e o hábito de emendar dois campos na
mesma linha, separados só por espaçamento. Manter uma cópia de cada regra por
parser faria as duas divergirem no primeiro ajuste.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Optional, Sequence

__all__ = ["limpar_campo", "normalizar_rotulo", "para_decimal"]


def para_decimal(texto: str) -> Decimal:
    """Converte o valor no formato pt-BR (``"1.931,56"``) para ``Decimal``.

    Ponto é separador de milhar e vírgula é decimal. Valor negativo não é
    aceito: o sinal na ficha é a coluna ``R/D``, e um menos impresso seria uma
    semântica que os parsers não conhecem — melhor levantar do que adivinhar.

    Raises:
        ValueError: se o texto não for um número pt-BR, ou vier negativo.
    """
    limpo = texto.replace(".", "").replace(",", ".")
    if limpo.startswith("-") or limpo.endswith("-"):
        raise ValueError("valor negativo não é esperado nesta ficha "
                         "(o sinal é a coluna R/D)")
    try:
        return Decimal(limpo)
    except InvalidOperation:
        raise ValueError("não é um número no formato pt-BR") from None


def limpar_campo(bruto: str, rotulos: Sequence[str]) -> Optional[str]:
    """Isola um campo do cabeçalho e normaliza o espaçamento interno.

    A ficha emenda dois campos na mesma linha, então o texto capturado à
    direita de um rótulo pode arrastar o rótulo seguinte junto: o corte é feito
    no **próximo rótulo conhecido**.

    Cortar no primeiro bloco de dois espaços — o jeito óbvio — perde dado
    impresso: o nome é preenchido até a largura do campo e o sufixo de UF vem
    emendado, de modo que ``"UNIDADE FICTICIA DE TESTE  - DF"`` viraria
    ``"UNIDADE FICTICIA DE TESTE"``, com o ``- DF`` descartado. Por isso
    os espaços internos são **colapsados**, nunca usados como separador.

    Args:
        bruto: o texto capturado à direita do rótulo.
        rotulos: literais que podem aparecer à direita, delimitando o campo.

    Returns:
        O campo limpo, ou ``None`` se nada sobrar.
    """
    texto = bruto
    for rotulo in rotulos:
        posicao = texto.find(rotulo)
        if posicao != -1:
            texto = texto[:posicao]
    limpo = re.sub(r"\s{2,}", " ", texto).strip()
    return limpo or None


def normalizar_rotulo(texto: str) -> str:
    """Reduz um rótulo a letras maiúsculas sem acento nem espaço.

    ``"T O T A L   L I Q U I D O"`` (mainframe) e ``"TOTAL LÍQUIDO"`` (web) são
    o mesmo rótulo impresso de dois jeitos; esta forma canônica deixa a tabela
    de rótulos servir aos dois parsers.
    """
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^A-Z]", "", sem_acento.upper())
