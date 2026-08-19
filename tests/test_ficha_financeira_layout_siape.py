"""Testes do parser do relatório do SIAPE mainframe (M3, formato A)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from integra_gov.ficha_financeira import (
    Competencia,
    LayoutNaoReconhecidoError,
    LinhaNaoReconhecidaError,
)
from integra_gov.ficha_financeira._layout_siape import (
    COLUNAS_VALOR,
    e_layout_siape,
    parsear_paginas,
)
from integra_gov.ficha_financeira.leitura import PaginaTexto
from integra_gov.ficha_financeira.modelo import TipoBeneficiario

FIXTURE = Path(__file__).parent / "fixtures" / "ficha_siape_pensionista.txt"


# --------------------------------------------------------------------------
# Montagem de páginas com a geometria exata do relatório
# --------------------------------------------------------------------------

def _linha(rubrica="00597", descricao="PENSAO COMPLEMENTAR - CIVI",
           marcador=" ", seq="0", valores=()) -> str:
    """Monta uma linha de rubrica nas colunas reais do relatório.

    Termina com ``rstrip``, como o SIAPE faz: a linha vem cortada no último
    caractere não-branco, e é isso que produz as linhas curtas.
    """
    buffer = [" "] * (COLUNAS_VALOR[-1].stop)
    buffer[0:5] = list(rubrica.ljust(5))
    buffer[6:32] = list(descricao.ljust(26)[:26])
    buffer[33] = marcador
    buffer[36:39] = list(seq.ljust(3))
    for texto, coluna in zip(valores, COLUNAS_VALOR):
        if texto:
            largura = coluna.stop - coluna.start
            buffer[coluna] = list(texto.rjust(largura))
    return "".join(buffer).rstrip()


def _total(rotulo: str, valores=()) -> str:
    buffer = [" "] * (COLUNAS_VALOR[-1].stop)
    marcado = f"**** {rotulo} ****"
    buffer[0:len(marcado)] = list(marcado)
    for texto, coluna in zip(valores, COLUNAS_VALOR):
        if texto:
            largura = coluna.stop - coluna.start
            buffer[coluna] = list(texto.rjust(largura))
    return "".join(buffer).rstrip()


def _cabecalho_tabela(meses=("JAN", "FEV", "MAR", "ABR", "MAI", "JUN")) -> str:
    buffer = [" "] * (COLUNAS_VALOR[-1].stop)
    buffer[3:16] = list("R U B R I C A")
    buffer[32:35] = list("R/D")
    buffer[36:39] = list("SEQ")
    for mes, coluna in zip(meses, COLUNAS_VALOR):
        if mes:  # None deixa a coluna sem mês, para testar o buraco
            buffer[coluna.stop - 3:coluna.stop] = list(mes)
    return "".join(buffer).rstrip()


def _pagina(corpo, *, numero=1, tipo="PENSIONISTA", exercicio=2024,
            orgao="99999", matricula="99999999",
            meses=("JAN", "FEV", "MAR", "ABR", "MAI", "JUN")) -> PaginaTexto:
    linhas = [
        "SIAPE - SISTEMA INTEGRADO DE ADMINISTRACAO DE RECURSOS HUMANOS",
        "L.A54120.DE                                    MES PAGAMENTO:   JAN2026",
        f"FICHA FINANCEIRA {tipo} REFERENTE A {exercicio}"
        "                          EMITIDO EM   : 02JAN2026",
        f"ORGAO : {orgao} - ORGAO FICTICIO DE TESTE    "
        "UNID.PAGADORA: 000000555 - UPAG FICTICIA  - DF",
        f"BENEF: {matricula} - MARIA DA SILVA TESTE     "
        "BANCO/AGENCIA/C.CORRENTE : 999/00000-0/000000000000-0  DEP.IR :",
        "-" * 84,
        _cabecalho_tabela(meses),
        "-" * 84,
    ]
    linhas.extend(corpo)
    return PaginaTexto(numero=numero, texto="\n".join(linhas))


# --------------------------------------------------------------------------
# Detecção de layout
# --------------------------------------------------------------------------

def test_reconhece_o_layout_do_mainframe():
    assert e_layout_siape(_pagina([])) is True


def test_nao_reconhece_pagina_de_outro_layout():
    outra = PaginaTexto(numero=1, texto="Ficha Financeira referente a 2026")
    assert e_layout_siape(outra) is False


def test_nao_reconhece_folha_com_assinatura_mas_sem_tabela():
    # Só a assinatura passaria numa folha de rosto sem lançamento nenhum.
    folha = PaginaTexto(numero=1, texto="L.A54120.DE\nSIAPE - SISTEMA")
    assert e_layout_siape(folha) is False


def test_paginas_de_outro_layout_sao_ignoradas():
    outra = PaginaTexto(numero=9, texto="tabela|com|pipes")
    blocos = parsear_paginas([outra])
    assert blocos == ()


# --------------------------------------------------------------------------
# O caso decisivo: marcador em branco INTERCALADO entre os grupos
# --------------------------------------------------------------------------

def test_marcador_em_branco_intercalado_e_preservado_na_ordem_impressa():
    # É o caso que separa "herança até o próximo marcador" de "grupo
    # contíguo". O parser NÃO resolve a herança — ele preserva o branco e a
    # ordem, que é o que a conciliação precisa para resolvê-la.
    corpo = [
        _linha("00005", "PROVENTO BASICO", "R", "0", ("1.536,79",)),
        _linha("00182", "ADIANT.GRATIF.NATALINA - AP", " ", "1", ("1.868,80",)),
        _linha("34113", "EMPREST BCO OFICIAL - CEF", "D", "1", ("1.260,12",)),
        _linha("34334", "MENSALIDADE SINDICAL", " ", "1", ("30,60",)),
    ]
    bloco = parsear_paginas([_pagina(corpo)])[0]

    assert [linha.rubrica for linha in bloco.linhas] == [
        "00005", "00182", "34113", "34334"]
    assert [linha.natureza_declarada for linha in bloco.linhas] == [
        "R", None, "D", None]


# --------------------------------------------------------------------------
# Geometria
# --------------------------------------------------------------------------

def test_le_rubrica_descricao_marcador_e_sequencia():
    corpo = [_linha("00597", "PENSAO COMPLEMENTAR - CIVIL", "R", "7",
                    ("1.931,56",))]
    linha = parsear_paginas([_pagina(corpo)])[0].linhas[0]

    assert linha.rubrica == "00597"
    # 26 caracteres: o SIAPE trunca e a biblioteca não completa.
    assert linha.descricao == "PENSAO COMPLEMENTAR - CIVI"
    assert linha.natureza_declarada == "R"
    assert linha.sequencia == 7


def test_valores_sao_decimal_no_formato_pt_br():
    corpo = [_linha(valores=("1.931,56", "", "12.345,67"))]
    valores = parsear_paginas([_pagina(corpo)])[0].linhas[0].valores

    assert valores == (
        (Competencia(2024, 1), Decimal("1931.56")),
        (Competencia(2024, 3), Decimal("12345.67")),
    )


def test_celulas_vazias_sao_omitidas_e_nao_viram_zero():
    corpo = [_linha(valores=("", "", "", "", "", "965,78"))]
    valores = parsear_paginas([_pagina(corpo)])[0].linhas[0].valores
    assert valores == ((Competencia(2024, 6), Decimal("965.78")),)


def test_linha_curta_nao_quebra_a_leitura():
    # O SIAPE corta a linha no último não-branco: uma rubrica só com valor em
    # janeiro produz uma linha bem mais curta que a largura da tabela.
    corpo = [_linha(valores=("1.931,56",))]
    linha = parsear_paginas([_pagina(corpo)])[0].linhas[0]
    assert len(linha.valores) == 1


def test_sequencia_ausente_vira_none():
    corpo = [_linha(seq=" ", valores=("1,00",))]
    assert parsear_paginas([_pagina(corpo)])[0].linhas[0].sequencia is None


# --------------------------------------------------------------------------
# Meses vêm do cabeçalho, nunca do número da página (P1)
# --------------------------------------------------------------------------

def test_meses_saem_do_cabecalho_da_tabela():
    corpo = [_linha(valores=("1.931,56",))]
    pagina = _pagina(corpo, numero=1,
                     meses=("JUL", "AGO", "SET", "OUT", "NOV", "DEZ"))
    bloco = parsear_paginas([pagina])[0]

    # Página 1 com cabeçalho do 2º semestre: se o mês viesse do índice da
    # página, isto viraria janeiro.
    assert bloco.linhas[0].valores[0][0] == Competencia(2024, 7)


def test_cabecalho_com_menos_de_seis_meses():
    corpo = [_linha(valores=("1,00", "2,00"))]
    pagina = _pagina(corpo, meses=("NOV", "DEZ"))
    bloco = parsear_paginas([pagina])[0]
    assert bloco.competencias == (Competencia(2024, 11), Competencia(2024, 12))


# --------------------------------------------------------------------------
# Totais
# --------------------------------------------------------------------------

def test_totais_sao_lidos_por_mes():
    corpo = [
        _linha(valores=("1.931,56",)),
        _total("T O T A L   B R U T O", ("2.897,34",)),
        _total("T O T A L   D E S C O N T O S", ("965,78",)),
        _total("T O T A L   L I Q U I D O", ("1.931,56",)),
    ]
    totais = parsear_paginas([_pagina(corpo)])[0].totais_lidos
    janeiro = next(t for t in totais if t.competencia == Competencia(2024, 1))

    assert (janeiro.bruto, janeiro.descontos, janeiro.liquido) == (
        Decimal("2897.34"), Decimal("965.78"), Decimal("1931.56"))


def test_totais_chegam_sempre_com_confere_falso():
    # Nível cru: ninguém conferiu ainda. Quem confere é a conciliação.
    corpo = [_total("T O T A L   B R U T O", ("1,00",))]
    totais = parsear_paginas([_pagina(corpo)])[0].totais_lidos
    assert all(total.confere is False for total in totais)


def test_linha_de_descontos_sem_nenhum_valor_nao_gera_total():
    # No PDF real a linha 'TOTAL DESCONTOS' de um semestre sem desconto vem
    # com 40 caracteres e nenhum valor.
    corpo = [
        _total("T O T A L   B R U T O", ("1.931,56",)),
        _total("T O T A L   D E S C O N T O S"),
    ]
    totais = parsear_paginas([_pagina(corpo)])[0].totais_lidos
    janeiro = next(t for t in totais if t.competencia == Competencia(2024, 1))
    # Ausência não é zero.
    assert janeiro.bruto == Decimal("1931.56")
    assert janeiro.descontos is None


# --------------------------------------------------------------------------
# Perda de dado nunca é silenciosa
# --------------------------------------------------------------------------

def test_linha_estranha_na_tabela_levanta_com_payload():
    corpo = [_linha(valores=("1,00",)), "LINHA QUE NAO DEVERIA ESTAR AQUI"]

    with pytest.raises(LinhaNaoReconhecidaError) as exc:
        parsear_paginas([_pagina(corpo, numero=7)])

    # A exceção carrega o suficiente para achar o ponto no PDF.
    assert exc.value.pagina == 7
    assert "NAO DEVERIA" in exc.value.linha


def test_total_desconhecido_levanta():
    corpo = [_total("T O T A L   I N V E N T A D O", ("1,00",))]
    with pytest.raises(LinhaNaoReconhecidaError, match="total não reconhecida"):
        parsear_paginas([_pagina(corpo)])


def test_marcador_invalido_levanta():
    corpo = [_linha(marcador="X", valores=("1,00",))]
    with pytest.raises(LinhaNaoReconhecidaError, match="marcador"):
        parsear_paginas([_pagina(corpo)])


def test_valor_ilegivel_levanta_em_vez_de_virar_zero():
    corpo = [_linha(valores=("ABC,DE",))]
    with pytest.raises(LinhaNaoReconhecidaError, match="ilegível"):
        parsear_paginas([_pagina(corpo)])


def test_valor_negativo_levanta_em_vez_de_perder_o_sinal():
    # O sinal nesta ficha é a coluna R/D; um menos impresso é semântica que o
    # parser não conhece — adivinhar trocaria um valor.
    corpo = [_linha(valores=("-1.931,56",))]
    with pytest.raises(LinhaNaoReconhecidaError, match="ilegível"):
        parsear_paginas([_pagina(corpo)])


def test_separadores_e_linhas_em_branco_sao_ignorados():
    corpo = ["-" * 84, "", "   ", _linha(valores=("1,00",)), ""]
    assert len(parsear_paginas([_pagina(corpo)])[0].linhas) == 1


# --------------------------------------------------------------------------
# Agrupamento por identidade e exercício (G4)
# --------------------------------------------------------------------------

def test_duas_paginas_do_mesmo_exercicio_viram_um_bloco():
    p1 = _pagina([_linha(valores=("1,00",))], numero=1)
    p2 = _pagina([_linha(valores=("2,00",))], numero=2,
                 meses=("JUL", "AGO", "SET", "OUT", "NOV", "DEZ"))
    blocos = parsear_paginas([p1, p2])

    assert len(blocos) == 1
    assert blocos[0].paginas == (1, 2)
    assert len(blocos[0].competencias) == 12


def test_exercicios_diferentes_viram_blocos_diferentes():
    p1 = _pagina([_linha(valores=("1,00",))], numero=1, exercicio=2023)
    p2 = _pagina([_linha(valores=("2,00",))], numero=2, exercicio=2024)
    blocos = parsear_paginas([p1, p2])

    assert [bloco.exercicio for bloco in blocos] == [2023, 2024]


def test_matriculas_diferentes_viram_blocos_diferentes():
    # É o PDF do extrator multi-órgão: matrícula muda entre páginas.
    p1 = _pagina([_linha(valores=("1,00",))], numero=1, matricula="11111111")
    p2 = _pagina([_linha(valores=("2,00",))], numero=2, matricula="22222222")
    blocos = parsear_paginas([p1, p2])

    assert len(blocos) == 2
    assert [b.identificacao.matricula for b in blocos] == ["11111111",
                                                           "22222222"]


def test_orgaos_diferentes_viram_blocos_diferentes():
    p1 = _pagina([_linha(valores=("1,00",))], numero=1, orgao="11111")
    p2 = _pagina([_linha(valores=("2,00",))], numero=2, orgao="22222")
    assert len(parsear_paginas([p1, p2])) == 2


# --------------------------------------------------------------------------
# Fixture por scrub geométrico do PDF real (P3)
# --------------------------------------------------------------------------

@pytest.fixture()
def paginas_reais() -> tuple[PaginaTexto, ...]:
    """A ficha real anonimizada: nome/matrícula/órgão trocados por strings de
    MESMO comprimento, valores e colunas intactos."""
    texto = FIXTURE.read_text(encoding="utf-8")
    return tuple(PaginaTexto(numero=indice, texto=parte)
                 for indice, parte in enumerate(texto.split("\f"), start=1))


def test_ficha_real_vira_um_unico_bloco_de_doze_meses(paginas_reais):
    blocos = parsear_paginas(paginas_reais)
    assert len(blocos) == 1
    assert blocos[0].paginas == (1, 2)
    assert len(blocos[0].competencias) == 12


def test_ficha_real_identificacao(paginas_reais):
    ident = parsear_paginas(paginas_reais)[0].identificacao
    assert ident.tipo is TipoBeneficiario.PENSIONISTA
    assert ident.matricula == "99999999"
    assert ident.nome == "MARIA DA SILVA TESTE"
    # Ficha de pensão traz o instituidor além do beneficiário.
    assert ident.instituidor_nome == "JOAO PEREIRA TESTADO"
    assert (ident.banco, ident.agencia) == ("999", "00000-0")


def test_ficha_real_emitido_em(paginas_reais):
    bloco = parsear_paginas(paginas_reais)[0]
    assert bloco.emitido_em.isoformat() == "2026-01-02"


def test_ficha_real_preserva_os_marcadores_como_impressos(paginas_reais):
    bloco = parsear_paginas(paginas_reais)[0]
    assert [(linha.rubrica, linha.natureza_declarada)
            for linha in bloco.linhas] == [
        ("00597", "R"),
        ("00599", None),   # junho: em branco, herda o grupo anterior
        ("00597", "R"),
        ("00600", None),   # novembro: em branco, ainda no grupo de rendimentos
        ("00599", "D"),    # novembro: abre o grupo de descontos
    ]


def test_ficha_real_totais_dos_meses_criticos(paginas_reais):
    totais = {str(t.competencia): t
              for t in parsear_paginas(paginas_reais)[0].totais_lidos}

    junho = totais["2024-06"]
    assert (junho.bruto, junho.descontos) == (Decimal("2897.34"), None)

    novembro = totais["2024-11"]
    assert (novembro.bruto, novembro.descontos, novembro.liquido) == (
        Decimal("3863.12"), Decimal("965.78"), Decimal("2897.34"))


def test_ficha_real_a_mesma_rubrica_aparece_nas_duas_naturezas(paginas_reais):
    bloco = parsear_paginas(paginas_reais)[0]
    marcadores = {linha.natureza_declarada
                  for linha in bloco.linhas if linha.rubrica == "00599"}
    # 00599 é crédito em junho e débito em novembro — a natureza é do
    # lançamento, não da rubrica.
    assert marcadores == {None, "D"}


# --------------------------------------------------------------------------
# Campos do cabeçalho: separação por rótulo, não por espaçamento
# --------------------------------------------------------------------------

def test_nome_da_unidade_preserva_o_sufixo_de_uf(paginas_reais):
    # O SIAPE preenche o nome até a largura do campo e emenda " - DF". Cortar
    # no primeiro bloco de dois espaços descartaria a UF em silêncio.
    ident = parsear_paginas(paginas_reais)[0].identificacao
    assert ident.upag_nome.endswith("- DF")


def test_campo_nao_arrasta_o_rotulo_seguinte(paginas_reais):
    ident = parsear_paginas(paginas_reais)[0].identificacao
    # A linha do ORGAO emenda "UNID.PAGADORA:" à direita.
    assert "UNID.PAGADORA" not in ident.orgao_nome
    # A do BENEF emenda "BANCO/AGENCIA/C.CORRENTE".
    assert "BANCO" not in ident.nome


def test_espacos_internos_do_campo_sao_colapsados(paginas_reais):
    ident = parsear_paginas(paginas_reais)[0].identificacao
    assert "  " not in ident.upag_nome


# --------------------------------------------------------------------------
# Pareamento mês↔coluna não pode deslizar
# --------------------------------------------------------------------------

def test_coluna_vazia_no_meio_do_cabecalho_nao_desloca_os_meses():
    # Cabeçalho com buraco: se as competências fossem compactadas, o valor da
    # 3ª coluna seria rotulado com o mês da 1ª — e os totais deslizariam
    # junto, fazendo a conferência FECHAR com os meses todos trocados.
    corpo = [_linha(valores=("", "", "1.000,00"))]
    pagina = _pagina(corpo, meses=("JAN", None, "MAR", "ABR", "MAI", "JUN"))
    linha = parsear_paginas([pagina])[0].linhas[0]

    assert linha.valores == ((Competencia(2024, 3), Decimal("1000.00")),)


def test_valor_em_coluna_sem_mes_levanta_em_vez_de_ser_atribuido_ao_vizinho():
    corpo = [_linha(valores=("", "999,99"))]
    pagina = _pagina(corpo, meses=("JAN", None, "MAR", "ABR", "MAI", "JUN"))

    with pytest.raises(LinhaNaoReconhecidaError, match="sem mês no cabeçalho"):
        parsear_paginas([pagina])


def test_competencias_do_bloco_ignoram_as_colunas_sem_mes():
    corpo = [_linha(valores=("1,00",))]
    pagina = _pagina(corpo, meses=("JAN", None, "MAR", None, None, None))
    bloco = parsear_paginas([pagina])[0]
    assert bloco.competencias == (Competencia(2024, 1), Competencia(2024, 3))


# --------------------------------------------------------------------------
# Página do layout com elemento estrutural faltando
# --------------------------------------------------------------------------

def test_pagina_do_layout_sem_titulo_levanta_em_vez_de_sumir():
    # A página tem assinatura e cabeçalho de tabela — e_layout_siape diz que é
    # formato A. Descartá-la apagaria as rubricas dela do retorno.
    pagina = _pagina([_linha(valores=("1,00",))], numero=4)
    sem_titulo = PaginaTexto(
        numero=4,
        texto="\n".join(ln for ln in pagina.texto.splitlines()
                        if "FICHA FINANCEIRA" not in ln),
    )

    with pytest.raises(LayoutNaoReconhecidoError) as exc:
        parsear_paginas([sem_titulo])

    assert exc.value.pagina == 4
    assert "título" in str(exc.value)
