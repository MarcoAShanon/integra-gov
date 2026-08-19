"""Testes do contrato de dados da ficha financeira (M1) — estruturas puras."""

from __future__ import annotations

import dataclasses
import json
from datetime import date
from decimal import Decimal

import pytest

from integra_gov.ficha_financeira import (
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


# --------------------------------------------------------------------------
# Competencia
# --------------------------------------------------------------------------

def test_competencia_de_texto_aceita_abreviacao_do_siape():
    assert Competencia.de_texto("JUN", 2024) == Competencia(ano=2024, mes=6)


def test_competencia_de_texto_ignora_caixa_e_espacos():
    assert Competencia.de_texto("  dez ", 2024) == Competencia(ano=2024, mes=12)


def test_competencia_de_texto_recusa_mes_desconhecido():
    with pytest.raises(ValueError, match="mês não reconhecido"):
        Competencia.de_texto("XXX", 2024)


def test_competencia_recusa_mes_fora_do_intervalo():
    with pytest.raises(ValueError, match="fora de 1–12"):
        Competencia(ano=2024, mes=13)


def test_competencia_ordena_cronologicamente_atravessando_o_ano():
    fora_de_ordem = [
        Competencia(2025, 1),
        Competencia(2024, 12),
        Competencia(2024, 2),
    ]
    assert sorted(fora_de_ordem) == [
        Competencia(2024, 2),
        Competencia(2024, 12),
        Competencia(2025, 1),
    ]


def test_competencia_serve_de_chave_de_dicionario():
    assert {Competencia(2024, 6): "ok"}[Competencia(2024, 6)] == "ok"


def test_competencia_texto_e_sigla():
    comp = Competencia(2024, 6)
    assert str(comp) == "2024-06"
    assert comp.sigla == "JUN"


# --------------------------------------------------------------------------
# Lancamento
# --------------------------------------------------------------------------

def _lanc(rubrica="00597", mes=6, valor="1931.56", natureza=Natureza.RENDIMENTO,
          descricao="PENSAO COMPLEMENTAR - CIVI", **kwargs) -> Lancamento:
    return Lancamento(
        rubrica=rubrica,
        descricao=descricao,
        competencia=Competencia(2024, mes),
        valor=Decimal(valor),
        natureza=natureza,
        **kwargs,
    )


def test_lancamento_recusa_valor_negativo():
    # O sinal é a natureza; valor negativo embutiria convenção contábil.
    with pytest.raises(ValueError, match="valor deve ser positivo"):
        _lanc(valor="-1")


def test_lancamento_aceita_valor_zero():
    assert _lanc(valor="0").valor == Decimal("0")


def test_lancamento_atalhos_de_natureza():
    rendimento = _lanc(natureza=Natureza.RENDIMENTO)
    desconto = _lanc(natureza=Natureza.DESCONTO)
    indefinido = _lanc(natureza=Natureza.INDEFINIDA)

    assert (rendimento.e_rendimento, rendimento.e_desconto) == (True, False)
    assert (desconto.e_rendimento, desconto.e_desconto) == (False, True)
    # Indefinida não é rendimento nem desconto — não pode virar um dos dois.
    assert (indefinido.e_rendimento, indefinido.e_desconto) == (False, False)


def test_lancamento_preserva_zeros_a_esquerda_da_rubrica():
    assert _lanc(rubrica="00597").rubrica == "00597"


def test_natureza_inferida_e_falsa_quando_o_marcador_veio_impresso():
    assert _lanc(natureza_declarada="R").natureza_inferida is False


def test_natureza_inferida_e_verdadeira_quando_herdada_do_grupo():
    # Linha sem marcador que herdou o grupo anterior (carry-forward).
    assert _lanc(natureza_declarada=None).natureza_inferida is True


def test_natureza_inferida_e_falsa_quando_nao_deu_para_resolver():
    # Sem marcador E sem grupo: não houve inferência nenhuma.
    lanc = _lanc(natureza=Natureza.INDEFINIDA, natureza_declarada=None)
    assert lanc.natureza_inferida is False


def test_lancamento_to_dict_serializa_decimal_como_texto():
    dados = _lanc(valor="1931.56", sequencia=0, natureza_declarada="R").to_dict()
    assert dados["valor"] == "1931.56"
    assert dados["competencia"] == "2024-06"
    assert dados["natureza"] == "R"
    assert dados["natureza_inferida"] is False
    assert dados["sequencia"] == 0
    json.dumps(dados)  # não levanta


# --------------------------------------------------------------------------
# Aviso
# --------------------------------------------------------------------------

def test_aviso_expoe_codigo_estavel_para_gate_programatico():
    aviso = Aviso(codigo=CodigoAviso.MES_NAO_CONFERE,
                  mensagem="soma dos lançamentos difere do total impresso",
                  competencia=Competencia(2024, 6))
    assert aviso.codigo == "MES_NAO_CONFERE"
    assert aviso.to_dict()["competencia"] == "2024-06"


def test_aviso_sem_competencia_serializa_none():
    aviso = Aviso(codigo=CodigoAviso.TOTAIS_AUSENTES, mensagem="sem totais")
    assert aviso.to_dict()["competencia"] is None


# --------------------------------------------------------------------------
# Nível cru — o que os parsers produzem
# --------------------------------------------------------------------------

def test_linha_crua_guarda_o_marcador_em_branco_sem_interpretar():
    linha = LinhaCrua(
        rubrica="00599",
        descricao="ADIANT.GRAT.NAT.BENEF.PENS",
        natureza_declarada=None,
        sequencia=0,
        valores=((Competencia(2024, 6), Decimal("965.78")),),
    )
    # O parser não resolve natureza — quem resolve é a conciliação.
    assert linha.natureza_declarada is None
    assert linha.valores[0][1] == Decimal("965.78")


def test_bloco_cru_preserva_a_ordem_impressa_das_linhas():
    # A ordem importa: o marcador R/D é herdado da linha anterior.
    linhas = tuple(LinhaCrua(rubrica=r, descricao="") for r in
                   ("00597", "00600", "00599"))
    bloco = BlocoCru(identificacao=Identificacao(), exercicio=2024, linhas=linhas)
    assert [linha.rubrica for linha in bloco.linhas] == ["00597", "00600", "00599"]


def test_bloco_cru_carrega_paginas_e_emissao():
    bloco = BlocoCru(identificacao=Identificacao(), exercicio=2024,
                     emitido_em=date(2026, 1, 2), paginas=(1, 2))
    assert bloco.emitido_em == date(2026, 1, 2)
    assert bloco.paginas == (1, 2)


# --------------------------------------------------------------------------
# Identificacao
# --------------------------------------------------------------------------

def test_identificacao_chave_distingue_matricula_e_orgao():
    # É o que permite segmentar um PDF mesclado por identidade.
    a = Identificacao(tipo=TipoBeneficiario.APOSENTADO, matricula="1", orgao_codigo="99999")
    b = Identificacao(tipo=TipoBeneficiario.APOSENTADO, matricula="1", orgao_codigo="88888")
    c = Identificacao(tipo=TipoBeneficiario.APOSENTADO, matricula="1", orgao_codigo="99999")
    assert a.chave != b.chave
    assert a.chave == c.chave


def test_identificacao_preserva_o_literal_da_situacao():
    ident = Identificacao(tipo=TipoBeneficiario.APOSENTADO,
                          situacao="02 - APOSENTADO")
    assert ident.to_dict()["situacao"] == "02 - APOSENTADO"


# --------------------------------------------------------------------------
# Ficha completa — espelha fichas/pensionista.pdf, com dados fictícios
# --------------------------------------------------------------------------

@pytest.fixture()
def ficha() -> FichaFinanceira:
    """Recorte de uma ficha de pensão: 00597 mensal, 00599 crédito em JUN.

    Reproduz o padrão real (adiantamento pago em junho e descontado em
    novembro) com valores fictícios.
    """
    lancamentos = (
        _lanc(mes=6, natureza_declarada="R"),
        _lanc(mes=11, natureza_declarada="R"),
        _lanc(rubrica="00599", descricao="ADIANT.GRAT.NAT.BENEF.PENS",
              mes=6, valor="965.78", natureza=Natureza.RENDIMENTO,
              natureza_declarada=None),
        _lanc(rubrica="00599", descricao="ADIANT.GRAT.NAT.BENEF.PENS",
              mes=11, valor="965.78", natureza=Natureza.DESCONTO,
              natureza_declarada="D"),
    )
    totais = (
        TotaisMes(Competencia(2024, 6), bruto=Decimal("2897.34"),
                  descontos=None, liquido=Decimal("2897.34"), confere=True),
        TotaisMes(Competencia(2024, 11), bruto=Decimal("1931.56"),
                  descontos=Decimal("965.78"), liquido=Decimal("965.78"),
                  confere=True),
    )
    return FichaFinanceira(
        identificacao=Identificacao(
            tipo=TipoBeneficiario.PENSIONISTA,
            matricula="00000000",
            nome="FULANA DE TAL",
            instituidor_matricula="1111111",
            instituidor_nome="BELTRANO DE TAL",
        ),
        exercicio=2024,
        lancamentos=lancamentos,
        totais=totais,
        emitido_em=date(2026, 1, 2),
        origem=Origem(layout=Layout.SIAPE, arquivo="ficha.pdf", paginas=(1, 2)),
    )


def test_rubricas_sao_distintas_e_ordenadas(ficha):
    assert ficha.rubricas() == ("00597", "00599")


def test_competencias_sao_distintas_e_cronologicas(ficha):
    assert ficha.competencias() == (Competencia(2024, 6), Competencia(2024, 11))


def test_por_rubrica_devolve_em_ordem_cronologica(ficha):
    meses = [lanc.competencia.mes for lanc in ficha.por_rubrica("00599")]
    assert meses == [6, 11]


def test_por_rubrica_normaliza_zeros_a_esquerda(ficha):
    assert ficha.por_rubrica("597") == ficha.por_rubrica("00597")


def test_por_rubrica_inexistente_devolve_vazio(ficha):
    assert ficha.por_rubrica("99999") == ()


def test_por_competencia_filtra_o_mes(ficha):
    rubricas = {lanc.rubrica for lanc in ficha.por_competencia(2024, 6)}
    assert rubricas == {"00597", "00599"}


def test_por_competencia_de_mes_ausente_devolve_vazio(ficha):
    assert ficha.por_competencia(2024, 1) == ()


def test_por_natureza_separa_a_mesma_rubrica_nos_dois_sentidos(ficha):
    # 00599 é crédito em junho e débito em novembro — o mesmo código, naturezas
    # opostas. Este é o comportamento real da gratificação natalina, e é por
    # isso que a natureza é do lançamento, não da rubrica.
    descontos = ficha.por_natureza(Natureza.DESCONTO)
    assert len(descontos) == 1
    assert (descontos[0].rubrica, descontos[0].competencia.mes) == ("00599", 11)


def test_totais_de_mes_presente_e_ausente(ficha):
    assert ficha.totais_de(2024, 6).bruto == Decimal("2897.34")
    assert ficha.totais_de(2024, 1) is None


def test_totais_distinguem_ausencia_de_zero(ficha):
    # Junho não teve desconto: a ficha imprime a linha em branco, e isso é
    # None — não Decimal("0").
    assert ficha.totais_de(2024, 6).descontos is None


def test_total_por_rubrica_soma_com_precisao_decimal(ficha):
    assert ficha.total_por_rubrica() == {
        "00597": Decimal("3863.12"),
        "00599": Decimal("1931.56"),
    }


def test_consistente_verdadeiro_sem_avisos(ficha):
    assert ficha.consistente is True


def test_consistente_falso_quando_um_mes_nao_confere(ficha):
    quebrada = FichaFinanceira(
        identificacao=ficha.identificacao,
        exercicio=ficha.exercicio,
        lancamentos=ficha.lancamentos,
        totais=(TotaisMes(Competencia(2024, 6), bruto=None, descontos=None,
                          liquido=None, confere=False),),
    )
    assert quebrada.consistente is False


def test_consistente_falso_quando_ha_aviso(ficha):
    com_aviso = FichaFinanceira(
        identificacao=ficha.identificacao,
        exercicio=ficha.exercicio,
        lancamentos=ficha.lancamentos,
        totais=ficha.totais,
        avisos=(Aviso(CodigoAviso.NATUREZA_INDEFINIDA, "sem grupo anterior"),),
    )
    assert com_aviso.consistente is False


def test_to_dict_da_ficha_e_serializavel_em_json(ficha):
    dados = ficha.to_dict()
    texto = json.dumps(dados, ensure_ascii=False)

    reidratado = json.loads(texto)
    assert reidratado["exercicio"] == 2024
    assert reidratado["identificacao"]["tipo"] == "PENSIONISTA"
    assert reidratado["origem"]["layout"] == "SIAPE"
    assert reidratado["origem"]["paginas"] == [1, 2]
    assert reidratado["emitido_em"] == "2026-01-02"
    assert len(reidratado["lancamentos"]) == 4
    assert reidratado["consistente"] is True


def test_ficha_e_imutavel(ficha):
    with pytest.raises(dataclasses.FrozenInstanceError):
        ficha.exercicio = 2025  # type: ignore[misc]


def test_ficha_minima_so_com_identificacao_e_exercicio():
    vazia = FichaFinanceira(identificacao=Identificacao(), exercicio=2024)
    assert vazia.lancamentos == ()
    assert vazia.rubricas() == ()
    assert vazia.total_por_rubrica() == {}
    assert vazia.origem is None
    assert vazia.emitido_em is None


# --------------------------------------------------------------------------
# Invariantes de contrato — estados que a spec define como impossíveis
# --------------------------------------------------------------------------

def test_lancamento_recusa_natureza_que_contradiz_o_marcador_impresso():
    # Marcador impresso é definitivo (§ 3 da spec): se a ficha diz "D", a
    # natureza efetiva não pode ser rendimento. Sem esta guarda, um erro do
    # carry-forward viraria um valor com o sinal trocado, em silêncio.
    with pytest.raises(ValueError, match="contradiz o marcador"):
        _lanc(natureza=Natureza.RENDIMENTO, natureza_declarada="D")


def test_lancamento_recusa_indefinida_com_marcador_impresso():
    # INDEFINIDA existe só para linha SEM marcador — com marcador, não há o
    # que ficar indefinido.
    with pytest.raises(ValueError, match="contradiz o marcador"):
        _lanc(natureza=Natureza.INDEFINIDA, natureza_declarada="R")


def test_lancamento_recusa_marcador_fora_do_dominio():
    with pytest.raises(ValueError, match="marcador R/D inválido"):
        _lanc(natureza_declarada="X")


def test_lancamento_aceita_marcador_coerente():
    assert _lanc(natureza=Natureza.DESCONTO, natureza_declarada="D").e_desconto


def test_competencia_recusa_ano_de_dois_digitos():
    # ano=26 ordenaria antes de qualquer ficha real, corrompendo a comparação
    # entre exercícios sem dar sinal nenhum.
    with pytest.raises(ValueError, match="quatro dígitos"):
        Competencia(ano=26, mes=6)


def test_totais_mes_exige_posicionamento_explicito_sobre_confere():
    # Sem default: o estado não-validado não pode nascer parecendo validado.
    with pytest.raises(TypeError):
        TotaisMes(Competencia(2024, 6))  # type: ignore[call-arg]


def test_por_rubrica_com_entrada_vazia_devolve_vazio(ficha):
    # "" e "0" normalizam para o mesmo lugar se a normalização for ingênua;
    # entrada vazia não pode casar com rubrica nenhuma.
    assert ficha.por_rubrica("") == ()
    assert ficha.por_rubrica("   ") == ()


def test_por_rubrica_nao_confunde_vazio_com_rubrica_toda_de_zeros():
    zerada = FichaFinanceira(
        identificacao=Identificacao(),
        exercicio=2024,
        lancamentos=(_lanc(rubrica="00000"),),
    )
    assert len(zerada.por_rubrica("00000")) == 1
    assert len(zerada.por_rubrica("0")) == 1
    assert zerada.por_rubrica("") == ()
