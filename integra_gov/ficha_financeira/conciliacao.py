"""Conciliação: transforma o que foi lido no que a biblioteca devolve.

Recebe um :class:`~integra_gov.ficha_financeira.modelo.BlocoCru` — o que estava
impresso, sem interpretação — e devolve uma
:class:`~integra_gov.ficha_financeira.modelo.FichaFinanceira`. Função pura: não
lê arquivo, não conhece layout, não guarda estado.

Faz duas coisas, nesta ordem, e a ordem é o desenho:

1. **Herança de grupo.** A ficha só imprime o marcador ``R/D`` na linha em que
   o grupo começa; as seguintes o herdam. A resolução é uma varredura na ordem
   impressa carregando o último marcador — determinística, não busca de
   subconjunto que some ao total. A busca seria ambígua sempre que dois
   lançamentos de mesmo valor tivessem naturezas opostas, que é exatamente o
   caso da rubrica de adiantamento da gratificação natalina.

2. **Conferência contra os totais.** A soma dos rendimentos tem de reproduzir
   o ``TOTAL BRUTO`` do mês, a dos descontos o ``TOTAL DESCONTOS``, e a
   diferença o ``TOTAL LIQUIDO``. Isso é **validação**, não motor de
   inferência: se a herança estiver errada, o mês não fecha e volta marcado,
   em vez de devolver um número silenciosamente trocado.

O princípio que rege os casos difíceis: **nada afirma mais do que se
verificou**. Mês sem totais impressos não é mês conferido — é mês *não
conferível*, e sai com ``confere=False`` e aviso, não com ``True`` por não ter
havido o que comparar.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Collection, Optional

from .exceptions import FichaInconsistenteError
from .modelo import (
    Aviso,
    BlocoCru,
    CodigoAviso,
    Competencia,
    FichaFinanceira,
    Lancamento,
    LinhaCrua,
    Natureza,
    Origem,
    TotaisMes,
)


__all__ = ["conciliar"]

_ZERO = Decimal("0")


def conciliar(
    bloco: BlocoCru,
    *,
    strict: bool = False,
    paginas_ilegiveis: Collection[int] = (),
    origem: Optional[Origem] = None,
) -> FichaFinanceira:
    """Resolve as naturezas e confere o bloco contra os totais impressos.

    Args:
        bloco: o que o parser de layout leu.
        strict: quando ``True``, uma divergência aritmética vira exceção em vez
            de aviso. O padrão é ``False`` porque a divergência já fica
            visível em :attr:`TotaisMes.confere` e em
            :attr:`FichaFinanceira.avisos` — o consumidor é que decide se ela
            o impede de seguir.
        paginas_ilegiveis: páginas do PDF que não puderam ser extraídas. Se
            alguma cair no intervalo deste bloco, a ficha sai com aviso: ela
            pode estar incompleta, e uma ficha faltando não deixa rastro
            nenhum se ninguém disser que faltou.
        origem: rastreabilidade da leitura, quando o chamador a conhece.

    Returns:
        A ficha com os lançamentos resolvidos e os meses conferidos.

    Raises:
        FichaInconsistenteError: só com ``strict=True``, quando algum mês não
            fecha.
    """
    avisos: list[Aviso] = []
    lancamentos = _resolver_naturezas(bloco.linhas, avisos)
    totais = _conferir(bloco, lancamentos, avisos)
    _avisar_paginas_ilegiveis(bloco, paginas_ilegiveis, avisos)

    if strict:
        nao_fecham = [total for total in totais if not total.confere]
        if nao_fecham:
            meses = ", ".join(str(total.competencia) for total in nao_fecham)
            raise FichaInconsistenteError(
                f"a soma dos lançamentos não reproduz os totais impressos em: "
                f"{meses}")

    return FichaFinanceira(
        identificacao=bloco.identificacao,
        exercicio=bloco.exercicio,
        lancamentos=tuple(lancamentos),
        totais=tuple(totais),
        emitido_em=bloco.emitido_em,
        origem=origem,
        avisos=tuple(avisos),
    )


# --------------------------------------------------------------------------
# 1. Herança de grupo
# --------------------------------------------------------------------------

def _resolver_naturezas(linhas: Collection[LinhaCrua],
                        avisos: list[Aviso]) -> list[Lancamento]:
    """Varre as linhas na ordem impressa, carregando o último marcador.

    O grupo **atravessa a quebra de tabela** dentro de uma mesma ficha. Chegamos
    a supor o contrário — o relatório do mainframe reimprime o marcador na
    primeira linha de cada página, o que parecia indicar reabertura de grupo —
    mas a ficha do e-SIAPE refutou: no bloco do 2º semestre a primeira rubrica
    vem **em branco**, e a aritmética dos totais exige que ela seja rendimento
    (``2.825,50 + 282,55 + 1.477,50 = 4.585,55``, o ``TOTAL BRUTO`` de julho).

    A regra que explica os dois formatos é a mesma: o marcador é impresso
    quando o grupo **muda**, não a cada página ou tabela. Reimprimi-lo na
    virada é redundância inofensiva, não reabertura.

    O grupo começa indefinido a cada bloco, e isso basta: a conciliação roda
    uma vez por :class:`BlocoCru`, e cada bloco é uma identidade num exercício.
    Se a herança atravessar um limite onde não devia, os totais não fecham e a
    ficha volta marcada — a rede de segurança continua sendo a conferência.
    """
    lancamentos: list[Lancamento] = []
    grupo: Optional[str] = None

    for linha in linhas:
        if linha.natureza_declarada is not None:
            grupo = linha.natureza_declarada

        if grupo is None:
            natureza = Natureza.INDEFINIDA
            avisos.append(Aviso(
                codigo=CodigoAviso.NATUREZA_INDEFINIDA,
                mensagem=(f"rubrica {linha.rubrica} veio sem marcador R/D e "
                          f"sem nenhum grupo aberto antes dela nesta ficha "
                          f"(tabela {linha.tabela}): a natureza não pôde ser "
                          f"determinada"),
            ))
        else:
            natureza = Natureza(grupo)

        for competencia, valor in linha.valores:
            lancamentos.append(Lancamento(
                rubrica=linha.rubrica,
                descricao=linha.descricao,
                competencia=competencia,
                valor=valor,
                natureza=natureza,
                natureza_declarada=linha.natureza_declarada,
                sequencia=linha.sequencia,
            ))

    return lancamentos


# --------------------------------------------------------------------------
# 2. Conferência
# --------------------------------------------------------------------------

def _conferir(bloco: BlocoCru, lancamentos: Collection[Lancamento],
              avisos: list[Aviso]) -> list[TotaisMes]:
    """Compara a soma dos lançamentos com os totais impressos, mês a mês."""
    lidos = _indexar_totais(bloco.totais_lidos, avisos)
    somados = _somar_por_mes(lancamentos)

    competencias = sorted(set(lidos) | set(somados) | set(bloco.competencias))
    conferidos: list[TotaisMes] = []

    for competencia in competencias:
        impresso = lidos.get(competencia)
        rendimentos, descontos, indefinidos = somados.get(
            competencia, (_ZERO, _ZERO, False))

        if impresso is None:
            # Não há contra o que conferir. Isso NÃO é um mês conferido: é um
            # mês não conferível, e o estado tem de dizer isso.
            if competencia in somados:
                avisos.append(Aviso(
                    codigo=CodigoAviso.TOTAIS_AUSENTES,
                    mensagem=(f"a ficha não imprimiu os totais de "
                              f"{competencia}; os lançamentos do mês não "
                              f"puderam ser conferidos"),
                    competencia=competencia))
                conferidos.append(TotaisMes(competencia, None, None, None,
                                            confere=False))
            continue

        confere = not indefinidos and _bate(impresso, rendimentos, descontos)
        if not confere:
            avisos.append(Aviso(
                codigo=CodigoAviso.MES_NAO_CONFERE,
                mensagem=_explicar(competencia, impresso, rendimentos,
                                   descontos, indefinidos),
                competencia=competencia))
        conferidos.append(TotaisMes(
            competencia=competencia,
            bruto=impresso.bruto,
            descontos=impresso.descontos,
            liquido=impresso.liquido,
            confere=confere,
        ))

    return conferidos


def _indexar_totais(totais: Collection[TotaisMes],
                    avisos: list[Aviso]) -> dict:
    """Um total por competência; divergência entre duplicatas vira aviso."""
    indexados: dict = {}
    for total in totais:
        anterior = indexados.get(total.competencia)
        if anterior is not None and (
                anterior.bruto, anterior.descontos, anterior.liquido) != (
                total.bruto, total.descontos, total.liquido):
            avisos.append(Aviso(
                codigo=CodigoAviso.MES_NAO_CONFERE,
                mensagem=(f"{total.competencia} apareceu com dois conjuntos de "
                          f"totais diferentes na mesma ficha"),
                competencia=total.competencia))
        indexados[total.competencia] = total
    return indexados


def _somar_por_mes(lancamentos: Collection[Lancamento]) -> dict:
    """Soma rendimentos e descontos por mês, sinalizando os indefinidos.

    O terceiro elemento diz se o mês tem algum lançamento de natureza
    indefinida — nesse caso a soma está incompleta dos dois lados e o mês não
    pode ser dado por conferido, ainda que os números batam por coincidência.
    """
    somas: dict = {}
    for lancamento in lancamentos:
        rendimentos, descontos, indefinidos = somas.get(
            lancamento.competencia, (_ZERO, _ZERO, False))
        if lancamento.natureza is Natureza.RENDIMENTO:
            rendimentos += lancamento.valor
        elif lancamento.natureza is Natureza.DESCONTO:
            descontos += lancamento.valor
        else:
            indefinidos = True
        somas[lancamento.competencia] = (rendimentos, descontos, indefinidos)
    return somas


def _bate(impresso: TotaisMes, rendimentos: Decimal,
          descontos: Decimal) -> bool:
    """Confere as três linhas de total.

    Linha em branco na ficha (``None``) é lida como zero **para comparar** —
    um mês sem desconto imprime a linha vazia, não ``0,00``. O campo continua
    ``None`` no resultado: ausência e zero impresso são coisas diferentes, e
    só a comparação as trata igual.
    """
    if _ou_zero(impresso.bruto) != rendimentos:
        return False
    if _ou_zero(impresso.descontos) != descontos:
        return False
    if impresso.liquido is not None:
        return _ou_zero(impresso.liquido) == rendimentos - descontos
    # Sem líquido impresso, as duas outras linhas já foram conferidas.
    return True


def _ou_zero(valor: Optional[Decimal]) -> Decimal:
    return _ZERO if valor is None else valor


def _explicar(competencia: Competencia, impresso: TotaisMes,
              rendimentos: Decimal, descontos: Decimal,
              indefinidos: bool) -> str:
    if indefinidos:
        return (f"{competencia} tem lançamento de natureza indefinida; a soma "
                f"do mês está incompleta e não pode ser conferida")
    return (f"{competencia}: somei rendimentos {rendimentos} e descontos "
            f"{descontos}, mas a ficha imprime bruto {impresso.bruto}, "
            f"descontos {impresso.descontos} e líquido {impresso.liquido}")


def _avisar_paginas_ilegiveis(bloco: BlocoCru,
                              paginas_ilegiveis: Collection[int],
                              avisos: list[Aviso]) -> None:
    """Avisa sobre página ilegível **no intervalo** do bloco.

    A interseção tem de ser com o intervalo, não com as páginas parseadas: uma
    página ilegível nunca está em :attr:`BlocoCru.paginas`, porque sem texto
    ela não é reconhecida como do layout e o parser nem chega a vê-la. Comparar
    com as páginas parseadas daria um conjunto vazio por construção — o guard
    existiria sem nunca disparar.

    O que este intervalo captura é a página quebrada **entre** páginas do mesmo
    bloco (a do meio de uma ficha de três). Páginas ilegíveis fora de qualquer
    intervalo são de outro andar: quem decide o destino delas é o despachante,
    que é o único que enxerga o PDF inteiro.
    """
    if not bloco.paginas:
        return
    intervalo = range(min(bloco.paginas), max(bloco.paginas) + 1)
    atingidas = sorted(set(paginas_ilegiveis) & set(intervalo))
    if atingidas:
        avisos.append(Aviso(
            codigo=CodigoAviso.PAGINA_ILEGIVEL,
            mensagem=(f"páginas {atingidas} desta ficha não puderam ser "
                      f"extraídas; a ficha pode estar incompleta"),
        ))
