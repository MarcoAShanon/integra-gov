"""Testes do parser da impressão web do e-SIAPE (M4, formato B)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from integra_gov.ficha_financeira import (
    Competencia,
    LayoutNaoReconhecidoError,
    LinhaNaoReconhecidaError,
    TipoBeneficiario,
)
from integra_gov.ficha_financeira._layout_esiape import (
    e_layout_esiape,
    parsear_paginas,
)
from integra_gov.ficha_financeira.leitura import PaginaTexto

FIXTURE = Path(__file__).parent / "fixtures" / "ficha_esiape_instituidor.txt"

CABECALHO = ("Rubrica|              Nome Rubrica              |R/D|Seq."
             "|    JAN     |    FEV     |    MAR     |    ABR     "
             "|    MAI     |    JUN     ")


def _rubrica(codigo="00001", descricao="VENCIMENTO BASICO", marcador=" ",
             seq="0", valores=("    2.629,31",)) -> str:
    celulas = [f" {codigo} ", descricao.ljust(40), f" {marcador} ", f" {seq}  "]
    celulas.extend(valores)
    return "|".join(celulas)


def _total(rotulo="TOTAL BRUTO", valores=("    2.629,31",)) -> str:
    return "|".join([" ***** ", rotulo.ljust(40), "   ", "    ", *valores])


def _bloco(corpo, *, exercicio=2026, semestre=1, situacao="15 - INSTITUIDOR PENSAO",
           matricula="9999999", orgao="99999", cabecalho=CABECALHO) -> list[str]:
    return [
        "Siape - Sistema Integrado de Administracao de Recursos Humanos"
        "                    Emitido em: 19/08/2026",
        f"Ficha Financeira referente a: {exercicio} - {semestre}º Semestre",
        "",
        f"Órgão: {orgao} - ORGAO FICTICIO DE TESTE"
        "     Unid. Pagadora : 000000555 - UPAG FICTICIA - DF",
        f"Reg. Jurídico:EST Situação Servidor:{situacao}"
        "       Unid. Exercício: 000000777 - ORGAO EXERCICIO - DF",
        f"Nome: {matricula} - FULANO DE TAL TESTE",
        "Cargo/Lotação: 000000 X X                 Função/Exerc.:"
        "                Localização:      Dep.IR/SF:      T.serv.: 10",
        "_" * 120,
        "",
        "Dados do responsável pela emissão",
        "Nome: SERVIDOR DE TESTE          Matrícula: 00000-0000000"
        "          Data: 19/08/2026",
        "_" * 120,
        "",
        cabecalho,
        *corpo,
    ]


def _pagina(corpo, numero=1, **kwargs) -> PaginaTexto:
    return PaginaTexto(numero=numero, texto="\n".join(_bloco(corpo, **kwargs)))


# --------------------------------------------------------------------------
# Detecção
# --------------------------------------------------------------------------

def test_reconhece_a_impressao_web():
    assert e_layout_esiape(_pagina([_rubrica()])) is True


def test_nao_reconhece_o_relatorio_do_mainframe():
    outra = PaginaTexto(numero=1, texto="L.A54120.DE\n   R U B R I C A   R/D SEQ")
    assert e_layout_esiape(outra) is False


def test_nao_reconhece_pagina_com_titulo_mas_sem_tabela():
    folha = PaginaTexto(numero=1,
                        texto="Ficha Financeira referente a: 2026 - 1º Semestre")
    assert e_layout_esiape(folha) is False


def test_paginas_de_outro_layout_sao_ignoradas():
    assert parsear_paginas([PaginaTexto(numero=1, texto="L.A54120.DE")]) == ()


# --------------------------------------------------------------------------
# A tabela é por pipes, não por coluna
# --------------------------------------------------------------------------

def test_le_rubrica_descricao_marcador_e_sequencia():
    linha = parsear_paginas([_pagina([
        _rubrica("82701", "GDPGPE - LEI 11.784/2008 AT", "R", "3"),
    ])])[0].linhas[0]

    assert linha.rubrica == "82701"
    assert linha.descricao == "GDPGPE - LEI 11.784/2008 AT"
    assert linha.natureza_declarada == "R"
    assert linha.sequencia == 3


def test_espacamento_irregular_nao_quebra_a_leitura():
    # O corte é por separador, não por posição: é o que sustenta o parser
    # depois do round-trip até PDF, em que a largura da coluna pode mudar.
    apertada = "|".join(["00001", "VENCIMENTO BASICO", "R", "0", "2.629,31"])
    linha = parsear_paginas([_pagina([apertada])])[0].linhas[0]

    assert (linha.rubrica, linha.natureza_declarada) == ("00001", "R")
    assert linha.valores == ((Competencia(2026, 1), Decimal("2629.31")),)


def test_marcador_em_branco_e_preservado():
    # O parser não resolve herança — isso é da conciliação.
    linhas = parsear_paginas([_pagina([
        _rubrica("00001", marcador="R"),
        _rubrica("00013", marcador=" "),
    ])])[0].linhas
    assert [ln.natureza_declarada for ln in linhas] == ["R", None]


def test_valores_por_mes_na_ordem_do_cabecalho():
    linha = parsear_paginas([_pagina([
        _rubrica(valores=("    1.407,00", "", "      262,93")),
    ])])[0].linhas[0]

    assert linha.valores == (
        (Competencia(2026, 1), Decimal("1407.00")),
        (Competencia(2026, 3), Decimal("262.93")),
    )


def test_linha_de_preenchimento_e_ignorada():
    vazia = "|".join(["       ", " " * 40, "   ", "    ", "            "])
    bloco = parsear_paginas([_pagina([_rubrica(), vazia])])[0]
    assert len(bloco.linhas) == 1


def test_sequencia_ausente_vira_none():
    linha = parsear_paginas([_pagina([_rubrica(seq=" ")])])[0].linhas[0]
    assert linha.sequencia is None


# --------------------------------------------------------------------------
# Totais (com acento, ao contrário do mainframe)
# --------------------------------------------------------------------------

def test_le_os_tres_totais():
    bloco = parsear_paginas([_pagina([
        _rubrica(),
        _total("TOTAL BRUTO", ("    8.066,40",)),
        _total("TOTAL DESCONTOS", ("      100,00",)),
        _total("TOTAL LÍQUIDO", ("    7.966,40",)),
    ])])[0]
    janeiro = bloco.totais_lidos[0]

    assert (janeiro.bruto, janeiro.descontos, janeiro.liquido) == (
        Decimal("8066.40"), Decimal("100.00"), Decimal("7966.40"))
    # Nível cru: ninguém conferiu ainda.
    assert janeiro.confere is False


def test_total_desconhecido_levanta():
    with pytest.raises(LinhaNaoReconhecidaError, match="total não reconhecida"):
        parsear_paginas([_pagina([_total("TOTAL INVENTADO")])])


# --------------------------------------------------------------------------
# Ruído da impressão do navegador
# --------------------------------------------------------------------------

@pytest.mark.parametrize("ruido", [
    "https://esiape.sigepe.gov.br/modsiape/servlet/StartCISPage?SESSIONID=SESSAOFICTICIA0",
    "$11/default/titlePrintVersionOutput$",
    "1/1",
    "19/08/2026, 08:33",
])
def test_ruido_da_impressao_e_descartado(ruido):
    # Reconhecido POR PADRÃO e descartado — o que sobra sem casar com nada é
    # que levanta. Os dois requisitos se atropelariam sem essa fronteira.
    bloco = parsear_paginas([_pagina([_rubrica(), ruido])])[0]
    assert len(bloco.linhas) == 1


def test_linha_estranha_na_tabela_levanta_com_payload():
    with pytest.raises(LinhaNaoReconhecidaError) as exc:
        parsear_paginas([_pagina([_rubrica(), "TEXTO QUE NAO DEVERIA ESTAR AQUI"],
                                 numero=4)])

    assert exc.value.pagina == 4
    assert "NAO DEVERIA" in exc.value.linha


def test_marcador_invalido_levanta():
    with pytest.raises(LinhaNaoReconhecidaError, match="marcador"):
        parsear_paginas([_pagina([_rubrica(marcador="X")])])


def test_valor_negativo_levanta():
    with pytest.raises(LinhaNaoReconhecidaError, match="ilegível"):
        parsear_paginas([_pagina([_rubrica(valores=("   -1.000,00",))])])


def test_valor_em_coluna_sem_mes_levanta():
    cabecalho = "|".join(["Rubrica", "Nome Rubrica".ljust(40), "R/D", "Seq.",
                          "    JAN     ", "            ", "    MAR     "])
    with pytest.raises(LinhaNaoReconhecidaError, match="sem mês no cabeçalho"):
        parsear_paginas([_pagina([_rubrica(valores=("  1,00", "  2,00"))],
                                 cabecalho=cabecalho)])


def test_bloco_sem_titulo_levanta():
    # A página é do layout (o 1º bloco tem título), mas o 2º perdeu o dele.
    # Deixá-lo cair fora do retorno apagaria as rubricas daquele semestre.
    segundo = [ln for ln in _bloco([_rubrica()], semestre=2)
               if "Ficha Financeira referente a" not in ln]
    texto = "\n".join([*_bloco([_rubrica()], semestre=1), *segundo])

    with pytest.raises(LayoutNaoReconhecidoError, match="exercício"):
        parsear_paginas([PaginaTexto(numero=2, texto=texto)])


# --------------------------------------------------------------------------
# Identificação
# --------------------------------------------------------------------------

def test_nome_do_titular_nao_e_o_de_quem_emitiu():
    # Os dois blocos usam o rótulo "Nome:"; sem o corte, o servidor que emitiu
    # o relatório entraria como titular da ficha.
    ident = parsear_paginas([_pagina([_rubrica()])])[0].identificacao
    assert ident.nome == "FULANO DE TAL TESTE"
    assert ident.matricula == "9999999"


def test_situacao_preserva_o_literal_e_deriva_o_tipo():
    ident = parsear_paginas([_pagina([_rubrica()])])[0].identificacao
    assert ident.situacao == "15 - INSTITUIDOR PENSAO"
    assert ident.tipo is TipoBeneficiario.INSTITUIDOR


@pytest.mark.parametrize("situacao,esperado", [
    ("02 - APOSENTADO", TipoBeneficiario.APOSENTADO),
    ("15 - INSTITUIDOR PENSAO", TipoBeneficiario.INSTITUIDOR),
    ("01 - ATIVO PERMANENTE", TipoBeneficiario.SERVIDOR),
    ("99 - COISA NOVA", TipoBeneficiario.DESCONHECIDO),
])
def test_tipos_derivados_da_situacao(situacao, esperado):
    ident = parsear_paginas([_pagina([_rubrica()], situacao=situacao)])[0]
    assert ident.identificacao.tipo is esperado


def test_orgao_e_upag():
    ident = parsear_paginas([_pagina([_rubrica()])])[0].identificacao
    assert ident.orgao_codigo == "99999"
    assert ident.orgao_nome == "ORGAO FICTICIO DE TESTE"
    assert ident.upag_codigo == "000000555"
    # O sufixo de UF não pode ser descartado.
    assert ident.upag_nome.endswith("- DF")


def test_emitido_em():
    assert parsear_paginas([_pagina([_rubrica()])])[0].emitido_em == date(2026, 8, 19)


# --------------------------------------------------------------------------
# Dois blocos por página
# --------------------------------------------------------------------------

def test_os_dois_semestres_viram_uma_ficha_so():
    segundo = CABECALHO.replace("JAN", "JUL").replace("FEV", "AGO") \
                       .replace("MAR", "SET").replace("ABR", "OUT") \
                       .replace("MAI", "NOV").replace("JUN", "DEZ")
    texto = "\n".join([
        *_bloco([_rubrica()], semestre=1),
        *_bloco([_rubrica()], semestre=2, cabecalho=segundo),
    ])
    blocos = parsear_paginas([PaginaTexto(numero=1, texto=texto)])

    assert len(blocos) == 1
    assert len(blocos[0].competencias) == 12


def test_cada_bloco_recebe_um_id_de_tabela_distinto():
    segundo = CABECALHO.replace("JAN", "JUL")
    texto = "\n".join([
        *_bloco([_rubrica()], semestre=1),
        *_bloco([_rubrica()], semestre=2, cabecalho=segundo),
    ])
    linhas = parsear_paginas([PaginaTexto(numero=1, texto=texto)])[0].linhas
    assert [ln.tabela for ln in linhas] == [1, 2]


def test_identidades_diferentes_viram_fichas_diferentes():
    texto = "\n".join([
        *_bloco([_rubrica()], matricula="1111111"),
        *_bloco([_rubrica()], matricula="2222222"),
    ])
    blocos = parsear_paginas([PaginaTexto(numero=1, texto=texto)])

    assert [b.identificacao.matricula for b in blocos] == ["1111111", "2222222"]


# --------------------------------------------------------------------------
# A ficha real anonimizada
# --------------------------------------------------------------------------

@pytest.fixture()
def bloco_real():
    texto = FIXTURE.read_text(encoding="utf-8")
    return parsear_paginas([PaginaTexto(numero=1, texto=texto)])[0]


def test_ficha_real_vira_um_bloco_de_doze_meses(bloco_real):
    assert bloco_real.exercicio == 2026
    assert len(bloco_real.competencias) == 12
    assert bloco_real.emitido_em == date(2026, 8, 19)


def test_ficha_real_identificacao(bloco_real):
    ident = bloco_real.identificacao
    assert ident.tipo is TipoBeneficiario.INSTITUIDOR
    assert ident.situacao == "15 - INSTITUIDOR PENSAO"
    assert ident.nome == "FULANO DE TAL TESTE"


def test_ficha_real_marcadores_como_impressos(bloco_real):
    # Só a PRIMEIRA linha do primeiro bloco traz o marcador; todas as outras
    # vêm em branco, inclusive a que abre o 2º semestre.
    assert [ln.natureza_declarada for ln in bloco_real.linhas] == [
        "R", None, None, None, None, None, None, None]


def test_ficha_real_segundo_semestre_abre_sem_marcador(bloco_real):
    do_segundo = [ln for ln in bloco_real.linhas if ln.tabela == 2]
    assert do_segundo, "o 2º semestre deve ter linhas"
    # É este caso que refuta "a tabela reabre o grupo": a primeira linha do
    # bloco novo vem em branco e a aritmética exige que seja rendimento.
    assert do_segundo[0].natureza_declarada is None


def test_ficha_real_totais_de_janeiro(bloco_real):
    janeiro = next(t for t in bloco_real.totais_lidos
                   if t.competencia == Competencia(2026, 1))
    assert janeiro.bruto == Decimal("8066.40")
    # Sem descontos no período: a linha vem vazia, e vazio não é zero.
    assert janeiro.descontos is None


def test_ficha_real_le_o_campo_bancario(bloco_real):
    # Campo que só existe no PDF impresso — a tela do e-SIAPE não o mostra.
    # Apareceu na primeira leitura do arquivo real, e sem tratá-lo ele era
    # arrastado para dentro do nome do titular.
    ident = bloco_real.identificacao
    assert "Banco" not in (ident.nome or "")
    # Sem conta informada a ficha imprime "000/-/-": traço não é dado.
    assert ident.agencia is None
    assert ident.conta is None


def test_ficha_real_ruido_da_impressao_nao_vira_lancamento(bloco_real):
    # O PDF impresso traz cabeçalho com data/hora do navegador e rodapé com a
    # URL contendo o SESSIONID. Nenhum dos dois pode virar rubrica.
    assert all(ln.rubrica.isdigit() for ln in bloco_real.linhas)
    assert len(bloco_real.linhas) == 8
