"""Testes da conciliação (M5): herança de grupo + conferência contra os totais."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from integra_gov.ficha_financeira import (
    BlocoCru,
    CodigoAviso,
    Competencia,
    FichaInconsistenteError,
    Identificacao,
    LinhaCrua,
    Natureza,
    TotaisMes,
)
from integra_gov.ficha_financeira._layout_siape import parsear_paginas
from integra_gov.ficha_financeira.conciliacao import conciliar
from integra_gov.ficha_financeira.leitura import PaginaTexto

FIXTURE = Path(__file__).parent / "fixtures" / "ficha_siape_pensionista.txt"

JAN = Competencia(2024, 1)
FEV = Competencia(2024, 2)


def _linha(rubrica, marcador, valor, competencia=JAN, tabela=1) -> LinhaCrua:
    return LinhaCrua(
        rubrica=rubrica,
        descricao=f"RUBRICA {rubrica}",
        natureza_declarada=marcador,
        sequencia=0,
        valores=((competencia, Decimal(valor)),),
        tabela=tabela,
    )


def _bloco(linhas, totais=()) -> BlocoCru:
    return BlocoCru(
        identificacao=Identificacao(),
        exercicio=2024,
        competencias=(JAN,),
        linhas=tuple(linhas),
        totais_lidos=tuple(totais),
        paginas=(1,),
    )


def _totais(competencia=JAN, bruto=None, descontos=None, liquido=None):
    return TotaisMes(competencia, bruto=bruto, descontos=descontos,
                     liquido=liquido, confere=False)


def _codigos(ficha):
    return [aviso.codigo for aviso in ficha.avisos]


# --------------------------------------------------------------------------
# Herança de grupo
# --------------------------------------------------------------------------

def test_linha_em_branco_herda_o_marcador_anterior():
    bloco = _bloco([_linha("00005", "R", "100.00"),
                    _linha("10289", None, "50.00")])
    ficha = conciliar(bloco)

    assert [lanc.natureza for lanc in ficha.lancamentos] == [
        Natureza.RENDIMENTO, Natureza.RENDIMENTO]
    # A segunda herdou: a natureza não veio impressa nela.
    assert ficha.lancamentos[1].natureza_inferida is True


def test_linha_em_branco_herda_desconto_e_nao_vira_rendimento():
    # É o caso que separa "herança de grupo" de "branco significa R".
    bloco = _bloco([_linha("34113", "D", "100.00"),
                    _linha("34334", None, "30.00")])
    ficha = conciliar(bloco)
    assert [lanc.natureza for lanc in ficha.lancamentos] == [
        Natureza.DESCONTO, Natureza.DESCONTO]


def test_marcador_atravessa_linha_intercalada_em_vez_de_resetar():
    # O caso mais difícil do relatório real: uma linha em branco entre o grupo
    # de rendimentos e o de descontos pertence ao grupo ANTERIOR. Um parser
    # que resetasse no branco trocaria o sinal dela.
    bloco = _bloco([
        _linha("00005", "R", "1536.79"),
        _linha("00182", None, "1868.80"),   # intercalada: ainda rendimento
        _linha("34113", "D", "1260.12"),
        _linha("34334", None, "30.60"),
    ])
    ficha = conciliar(bloco)

    assert [lanc.natureza.value for lanc in ficha.lancamentos] == [
        "R", "R", "D", "D"]


def test_marcador_explicito_sempre_vence_a_heranca():
    bloco = _bloco([_linha("00005", "R", "100.00"),
                    _linha("34113", "D", "40.00"),
                    _linha("00006", "R", "10.00")])
    ficha = conciliar(bloco)
    assert [lanc.natureza.value for lanc in ficha.lancamentos] == ["R", "D", "R"]


def test_linha_sem_marcador_e_sem_grupo_anterior_fica_indefinida():
    bloco = _bloco([_linha("00005", None, "100.00")])
    ficha = conciliar(bloco)

    assert ficha.lancamentos[0].natureza is Natureza.INDEFINIDA
    # Não houve inferência nenhuma — não é o mesmo que herdar.
    assert ficha.lancamentos[0].natureza_inferida is False
    assert CodigoAviso.NATUREZA_INDEFINIDA in _codigos(ficha)


def test_o_grupo_atravessa_a_quebra_de_tabela():
    # Chegamos a supor que a tabela reabria o grupo, porque o mainframe
    # reimprime o marcador na primeira linha de cada página. A ficha do
    # e-SIAPE refutou: o bloco do 2º semestre abre com rubrica EM BRANCO que
    # a aritmética dos totais exige ser rendimento. O marcador é impresso
    # quando o grupo MUDA — reimprimi-lo na virada é redundância, não
    # reabertura.
    bloco = BlocoCru(
        identificacao=Identificacao(),
        exercicio=2024,
        competencias=(JAN,),
        linhas=(_linha("00005", "R", "100.00", tabela=1),
                _linha("10289", None, "50.00", tabela=2)),
        paginas=(1, 2),
    )
    ficha = conciliar(bloco)

    assert ficha.lancamentos[0].natureza is Natureza.RENDIMENTO
    assert ficha.lancamentos[1].natureza is Natureza.RENDIMENTO
    assert ficha.lancamentos[1].natureza_inferida is True


def test_sem_nenhum_grupo_aberto_na_ficha_a_natureza_fica_indefinida():
    # O grupo começa indefinido a cada ficha: atravessar tabela é uma coisa,
    # adivinhar sem nenhum marcador anterior é outra.
    bloco = BlocoCru(
        identificacao=Identificacao(),
        exercicio=2024,
        competencias=(JAN,),
        linhas=(_linha("00005", None, "100.00", tabela=1),
                _linha("10289", None, "50.00", tabela=2)),
        paginas=(1, 2),
    )
    ficha = conciliar(bloco)

    assert all(lanc.natureza is Natureza.INDEFINIDA
               for lanc in ficha.lancamentos)


# --------------------------------------------------------------------------
# Conferência contra os totais
# --------------------------------------------------------------------------

def test_mes_que_fecha_sai_conferido_e_sem_aviso():
    bloco = _bloco(
        [_linha("00005", "R", "100.00"), _linha("34113", "D", "30.00")],
        [_totais(bruto=Decimal("100.00"), descontos=Decimal("30.00"),
                 liquido=Decimal("70.00"))],
    )
    ficha = conciliar(bloco)

    assert ficha.totais[0].confere is True
    assert ficha.avisos == ()
    assert ficha.consistente is True


def test_mes_que_nao_fecha_sai_marcado_com_aviso():
    bloco = _bloco(
        [_linha("00005", "R", "100.00")],
        [_totais(bruto=Decimal("999.99"), liquido=Decimal("999.99"))],
    )
    ficha = conciliar(bloco)

    assert ficha.totais[0].confere is False
    assert CodigoAviso.MES_NAO_CONFERE in _codigos(ficha)
    assert ficha.consistente is False
    # A mensagem mostra os dois lados da divergência.
    assert "100.00" in ficha.avisos[0].mensagem
    assert "999.99" in ficha.avisos[0].mensagem


def test_desconto_em_branco_e_lido_como_zero_para_comparar():
    # Mês sem desconto imprime a linha vazia, não "0,00".
    bloco = _bloco(
        [_linha("00005", "R", "100.00")],
        [_totais(bruto=Decimal("100.00"), descontos=None,
                 liquido=Decimal("100.00"))],
    )
    ficha = conciliar(bloco)

    assert ficha.totais[0].confere is True
    # Mas o campo continua None: ausência e zero impresso são diferentes.
    assert ficha.totais[0].descontos is None


def test_liquido_ausente_nao_impede_a_conferencia():
    bloco = _bloco(
        [_linha("00005", "R", "100.00")],
        [_totais(bruto=Decimal("100.00"))],
    )
    assert conciliar(bloco).totais[0].confere is True


def test_liquido_impresso_inconsistente_reprova_o_mes():
    bloco = _bloco(
        [_linha("00005", "R", "100.00"), _linha("34113", "D", "30.00")],
        [_totais(bruto=Decimal("100.00"), descontos=Decimal("30.00"),
                 liquido=Decimal("999.00"))],
    )
    assert conciliar(bloco).totais[0].confere is False


# --------------------------------------------------------------------------
# Nada afirma mais do que se verificou
# --------------------------------------------------------------------------

def test_mes_sem_totais_impressos_nao_e_mes_conferido():
    # A tentação aqui é marcar confere=True porque "não houve divergência".
    # Não houve CONFERÊNCIA: o mês é não-conferível, e o estado tem de dizer.
    bloco = _bloco([_linha("00005", "R", "100.00")], totais=())
    ficha = conciliar(bloco)

    assert ficha.totais[0].confere is False
    assert CodigoAviso.TOTAIS_AUSENTES in _codigos(ficha)
    assert ficha.consistente is False


def test_mes_com_indefinida_nao_confere_mesmo_com_numeros_batendo():
    # Os números podem coincidir por acaso; com um lançamento fora das duas
    # somas, a conferência não prova nada.
    bloco = _bloco(
        [_linha("00005", None, "100.00")],
        [_totais(bruto=Decimal("100.00"), liquido=Decimal("100.00"))],
    )
    ficha = conciliar(bloco)

    assert ficha.totais[0].confere is False
    assert CodigoAviso.NATUREZA_INDEFINIDA in _codigos(ficha)


def test_totais_divergentes_para_a_mesma_competencia_viram_aviso():
    bloco = _bloco(
        [_linha("00005", "R", "100.00")],
        [_totais(bruto=Decimal("100.00")), _totais(bruto=Decimal("200.00"))],
    )
    assert CodigoAviso.MES_NAO_CONFERE in _codigos(conciliar(bloco))


def test_pagina_ilegivel_entre_paginas_do_bloco_vira_aviso():
    # Estado POSSÍVEL: a página quebrada não aparece em bloco.paginas — sem
    # texto ela nem é reconhecida como do layout. Ela some do meio, e o que
    # sobra são as páginas 1 e 3 com um buraco entre elas.
    bloco = BlocoCru(
        identificacao=Identificacao(), exercicio=2024, competencias=(JAN,),
        linhas=(_linha("00005", "R", "100.00"),),
        totais_lidos=(_totais(bruto=Decimal("100.00")),),
        paginas=(1, 3),
    )
    ficha = conciliar(bloco, paginas_ilegiveis={2})

    assert CodigoAviso.PAGINA_ILEGIVEL in _codigos(ficha)
    assert ficha.consistente is False


def test_pagina_ilegivel_fora_do_intervalo_nao_afeta_a_ficha():
    bloco = _bloco([_linha("00005", "R", "100.00")],
                   [_totais(bruto=Decimal("100.00"))])
    ficha = conciliar(bloco, paginas_ilegiveis={7})

    assert ficha.avisos == ()
    assert ficha.consistente is True


# --------------------------------------------------------------------------
# Modo estrito
# --------------------------------------------------------------------------

def test_strict_transforma_divergencia_aritmetica_em_excecao():
    bloco = _bloco([_linha("00005", "R", "100.00")],
                   [_totais(bruto=Decimal("999.99"))])

    with pytest.raises(FichaInconsistenteError, match="2024-01"):
        conciliar(bloco, strict=True)


def test_strict_nao_reclama_de_ficha_que_fecha():
    bloco = _bloco([_linha("00005", "R", "100.00")],
                   [_totais(bruto=Decimal("100.00"))])
    assert conciliar(bloco, strict=True).consistente is True


# --------------------------------------------------------------------------
# O que a conciliação preserva
# --------------------------------------------------------------------------

def test_o_marcador_impresso_viaja_junto_com_o_lancamento():
    bloco = _bloco([_linha("00005", "R", "100.00"),
                    _linha("10289", None, "50.00")])
    ficha = conciliar(bloco)

    assert ficha.lancamentos[0].natureza_declarada == "R"
    assert ficha.lancamentos[1].natureza_declarada is None


def test_identificacao_e_exercicio_atravessam_intactos():
    bloco = BlocoCru(
        identificacao=Identificacao(matricula="123", nome="FULANO"),
        exercicio=2019, competencias=(JAN,),
        linhas=(_linha("00005", "R", "1.00"),),
        totais_lidos=(_totais(bruto=Decimal("1.00")),),
        paginas=(1,),
    )
    ficha = conciliar(bloco)

    assert ficha.exercicio == 2019
    assert ficha.identificacao.nome == "FULANO"


def test_uma_linha_com_varios_meses_vira_varios_lancamentos():
    linha = LinhaCrua(rubrica="00005", descricao="X", natureza_declarada="R",
                      valores=((JAN, Decimal("10.00")), (FEV, Decimal("20.00"))),
                      tabela=1)
    ficha = conciliar(_bloco([linha]))

    assert [str(lanc.competencia) for lanc in ficha.lancamentos] == [
        "2024-01", "2024-02"]


def test_bloco_sem_linhas_devolve_ficha_vazia_e_consistente():
    ficha = conciliar(_bloco([], totais=()))
    assert ficha.lancamentos == ()
    assert ficha.consistente is True


# --------------------------------------------------------------------------
# Fim a fim, sobre a ficha real anonimizada
# --------------------------------------------------------------------------

@pytest.fixture()
def ficha_real():
    texto = FIXTURE.read_text(encoding="utf-8")
    paginas = tuple(PaginaTexto(numero=indice, texto=parte)
                    for indice, parte in enumerate(texto.split("\f"), start=1))
    return conciliar(parsear_paginas(paginas)[0])


def test_ficha_real_fecha_os_doze_meses(ficha_real):
    # A prova mais forte da herança de grupo: ela não é afirmada, é validada
    # pela aritmética dos totais impressos ao longo do ano inteiro.
    assert len(ficha_real.totais) == 12
    assert all(total.confere for total in ficha_real.totais)
    assert ficha_real.avisos == ()
    assert ficha_real.consistente is True


def test_ficha_real_adiantamento_e_credito_em_junho_e_debito_em_novembro(
        ficha_real):
    lancamentos = {lanc.competencia.mes: lanc
                   for lanc in ficha_real.por_rubrica("00599")}

    # Mesma rubrica, naturezas opostas — e junho veio POR HERANÇA.
    assert lancamentos[6].natureza is Natureza.RENDIMENTO
    assert lancamentos[6].natureza_inferida is True
    assert lancamentos[11].natureza is Natureza.DESCONTO
    assert lancamentos[11].natureza_inferida is False


def test_ficha_real_gratificacao_natalina_herda_rendimento(ficha_real):
    natalina = ficha_real.por_rubrica("00600")[0]
    assert natalina.natureza is Natureza.RENDIMENTO
    assert natalina.natureza_inferida is True


def test_ficha_real_soma_por_natureza_reproduz_os_totais_de_novembro(
        ficha_real):
    de_novembro = ficha_real.por_competencia(2024, 11)
    rendimentos = sum(lanc.valor for lanc in de_novembro if lanc.e_rendimento)
    descontos = sum(lanc.valor for lanc in de_novembro if lanc.e_desconto)
    impresso = ficha_real.totais_de(2024, 11)

    assert rendimentos == impresso.bruto == Decimal("3863.12")
    assert descontos == impresso.descontos == Decimal("965.78")
    assert rendimentos - descontos == impresso.liquido == Decimal("2897.34")


def test_ficha_real_serializa_para_json(ficha_real):
    import json
    dados = json.loads(json.dumps(ficha_real.to_dict(), ensure_ascii=False))
    assert dados["consistente"] is True
    assert len(dados["lancamentos"]) == 15
    assert dados["avisos"] == []


# --------------------------------------------------------------------------
# Ficha de aposentado: o único caso com DESCONTO HERDADO
# --------------------------------------------------------------------------

FIXTURE_APOSENTADO = (Path(__file__).parent / "fixtures"
                      / "ficha_esiape_aposentado.txt")


@pytest.fixture()
def ficha_aposentado():
    """Anonimizada do PDF real impresso pelo Chrome.

    É a única amostra que exercita **desconto herdado** — linha com o marcador
    em branco dentro de um grupo ``D``. As outras fichas só têm desconto com
    ``D`` impresso (pensionista) ou desconto nenhum (instituidor, que é
    ficha de pessoa falecida e por construção não tem).
    """
    from integra_gov.ficha_financeira._layout_esiape import (
        parsear_paginas as parsear_esiape,
    )
    texto = FIXTURE_APOSENTADO.read_text(encoding="utf-8")
    return conciliar(parsear_esiape([PaginaTexto(numero=1, texto=texto)])[0])


def test_aposentado_fecha_todos_os_meses(ficha_aposentado):
    assert ficha_aposentado.consistente is True
    assert ficha_aposentado.avisos == ()
    assert all(total.confere for total in ficha_aposentado.totais)


def test_aposentado_tem_desconto_herdado(ficha_aposentado):
    # O caminho de maior risco do módulo: um erro aqui inverteria o sinal de
    # um valor em dinheiro, transformando desconto em provento.
    herdados = [lanc for lanc in ficha_aposentado.por_natureza(Natureza.DESCONTO)
                if lanc.natureza_inferida]
    assert len(herdados) >= 10
    assert all(lanc.natureza_declarada is None for lanc in herdados)


def test_aposentado_marcador_reaparece_quando_o_grupo_muda(ficha_aposentado):
    # O 1º semestre TERMINA em desconto e o 2º ABRE em rendimento: a ficha
    # imprime o marcador exatamente na virada. É a predição afirmativa da
    # regra "o marcador aparece quando o grupo muda" — se aquela linha viesse
    # em branco, a regra quebraria neste arquivo.
    julho = ficha_aposentado.por_competencia(2026, 7)
    assert julho[0].natureza is Natureza.RENDIMENTO
    assert julho[0].natureza_declarada == "R"


def test_aposentado_julho_reproduz_os_totais_impressos(ficha_aposentado):
    julho = ficha_aposentado.por_competencia(2026, 7)
    rendimentos = sum(lanc.valor for lanc in julho if lanc.e_rendimento)
    descontos = sum(lanc.valor for lanc in julho if lanc.e_desconto)
    impresso = ficha_aposentado.totais_de(2026, 7)

    # Julho tem rendimento E desconto, os dois com linhas herdadas: é a
    # conferência mais completa que o módulo tem contra ficha real.
    assert rendimentos == impresso.bruto
    assert descontos == impresso.descontos
    assert rendimentos - descontos == impresso.liquido
