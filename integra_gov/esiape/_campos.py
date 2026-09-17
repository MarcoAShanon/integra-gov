"""Normalização e máscara de campos cadastrais do e-SIAPE.

Compartilhado pelos módulos que devolvem dados pessoais — CDCOINDPES
(:mod:`~integra_gov.esiape.dados_pessoais`) e CDCOPSBENE
(:mod:`~integra_gov.esiape.dados_pensionista`): uma implementação por regra,
dois usos.

Máscara: a matrícula e qualquer número longo só aparecem pelos 2 últimos
dígitos, em log, mensagem de exceção ou ``repr``.

Nada pessoal neste arquivo.
"""

from __future__ import annotations

import re

__all__ = ["MESES_SIAPE", "data_siape", "mascarar_digitos",
           "mascarar_matricula"]

#: Meses como o SIAPE os escreve em datas ``DDMMMAAAA``.
MESES_SIAPE = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
               "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}


def mascarar_matricula(matricula: str) -> str:
    """``matricula`` reduzida aos 2 últimos dígitos; nunca expõe tudo, mesmo
    para uma matrícula mais curta que 2 caracteres."""
    return f"*****{matricula[-2:].rjust(2, '*')}"


def mascarar_digitos(texto: str) -> str:
    """Todo grupo de 4+ dígitos vira ``*****`` + os 2 últimos dígitos do
    grupo — cobre tanto uma sequência corrida (``1234567``) quanto uma
    pontuada por ``.``, ``-``, ``/`` ou um único espaço entre dígitos
    (matrícula ``000.000-0``, CPF ``123.456.789-00``). O piso é 4, não 3:
    nada que identifica alguém tem 3 dígitos (matrícula tem 7 ou 8, CPF 11,
    CEP 8) — mas um número de 3 dígitos aparece o tempo todo em mensagem
    honesta, como um timeout (``em 120s``), e mascará-lo sem necessidade
    torna a mensagem ilegível. Um grupo de 1 ou 2 dígitos (ex.: ``UF: 12``)
    já não era tocado e continua não sendo."""
    return re.sub(
        r"\d(?:[.\-/ ]?\d){3,}",
        lambda m: "*****" + re.sub(r"\D", "", m.group(0))[-2:],
        texto,
    )


def data_siape(bruto: str | None) -> str | None:
    """``15AGO1960`` → ``15/08/1960``; qualquer outra forma → ``None``."""
    m = re.fullmatch(r"(\d{2})([A-Z]{3})(\d{4})", (bruto or "").strip().upper())
    if not m or m.group(2) not in MESES_SIAPE:
        return None
    return f"{m.group(1)}/{MESES_SIAPE[m.group(2)]:02d}/{m.group(3)}"
