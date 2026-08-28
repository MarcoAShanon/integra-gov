"""Testes da API pública (M6): despacho de layout e páginas órfãs."""

from __future__ import annotations

from pathlib import Path

import pytest

from integra_gov.ficha_financeira import (
    CodigoAviso,
    Layout,
    LayoutNaoReconhecidoError,
    MultiplasFichasError,
    Natureza,
    PdfSemTextoError,
    TipoBeneficiario,
    ler_ficha_financeira,
    ler_fichas_financeiras,
)
from integra_gov.ficha_financeira._layout_siape import COLUNAS_VALOR

from tests._pdf_sintetico import pdf_bytes

FIXTURE = Path(__file__).parent / "fixtures" / "ficha_siape_pensionista.txt"


def _paginas_da_fixture() -> list[list[str]]:
    """A ficha real anonimizada, como linhas por página."""
    texto = FIXTURE.read_text(encoding="utf-8")
    return [parte.splitlines() for parte in texto.split("\f")]


def _pdf_real() -> bytes:
    return pdf_bytes(_paginas_da_fixture())


def _paginas_esiape() -> list[str]:
    """A ficha do e-SIAPE anonimizada, como linhas de uma página."""
    caminho = Path(__file__).parent / "fixtures" / "ficha_esiape_instituidor.txt"
    return caminho.read_text(encoding="utf-8").splitlines()


def _linha_siape(rubrica, marcador, valor) -> str:
    buffer = [" "] * COLUNAS_VALOR[-1].stop
    buffer[0:5] = list(rubrica)
    buffer[6:32] = list(f"RUBRICA {rubrica}".ljust(26))
    buffer[33] = marcador
    buffer[36:39] = list("0  ")
    largura = COLUNAS_VALOR[0].stop - COLUNAS_VALOR[0].start
    buffer[COLUNAS_VALOR[0]] = list(valor.rjust(largura))
    return "".join(buffer).rstrip()


def _pagina_siape(matricula="99999999", exercicio=2024) -> list[str]:
    cabecalho = [" "] * COLUNAS_VALOR[-1].stop
    cabecalho[3:16] = list("R U B R I C A")
    cabecalho[32:35] = list("R/D")
    cabecalho[36:39] = list("SEQ")
    cabecalho[COLUNAS_VALOR[0].stop - 3:COLUNAS_VALOR[0].stop] = list("JAN")
    return [
        "SIAPE - SISTEMA INTEGRADO DE ADMINISTRACAO DE RECURSOS HUMANOS",
        "L.A54120.DE                          MES PAGAMENTO:   JAN2026",
        f"FICHA FINANCEIRA PENSIONISTA REFERENTE A {exercicio}"
        "          EMITIDO EM   : 02JAN2026",
        "ORGAO : 99999 - ORGAO FICTICIO    UNID.PAGADORA: 000000555 - UPAG - DF",
        f"BENEF: {matricula} - FULANA DE TAL     "
        "BANCO/AGENCIA/C.CORRENTE : 999/00000-0/000000000000-0  DEP.IR :",
        "".join(cabecalho).rstrip(),
        _linha_siape("00005", "R", "100,00"),
        "**** T O T A L   B R U T O          ****" + "100,00".rjust(
            COLUNAS_VALOR[0].stop - 40),
    ]


# --------------------------------------------------------------------------
# Caminho feliz sobre a ficha real
# --------------------------------------------------------------------------

def test_le_a_ficha_real_pela_api_publica():
    ficha = ler_ficha_financeira(_pdf_real())

    assert ficha.identificacao.tipo is TipoBeneficiario.PENSIONISTA
    assert ficha.exercicio == 2024
    assert ficha.consistente is True
    assert len(ficha.lancamentos) == 15


def test_origem_registra_layout_e_paginas():
    ficha = ler_ficha_financeira(_pdf_real())

    assert ficha.origem.layout is Layout.SIAPE
    # Num PDF mesclado é isto que diz de onde cada ficha saiu.
    assert ficha.origem.paginas == (1, 2)


def test_api_aceita_caminho_em_disco(tmp_path):
    caminho = tmp_path / "ficha.pdf"
    caminho.write_bytes(_pdf_real())

    ficha = ler_ficha_financeira(caminho)
    assert ficha.origem.arquivo == str(caminho)


def test_a_natureza_herdada_chega_ate_a_api():
    ficha = ler_ficha_financeira(_pdf_real())
    junho, novembro = ficha.por_rubrica("00599")

    assert (junho.natureza, junho.natureza_inferida) == (
        Natureza.RENDIMENTO, True)
    assert (novembro.natureza, novembro.natureza_inferida) == (
        Natureza.DESCONTO, False)


# --------------------------------------------------------------------------
# Singular × plural
# --------------------------------------------------------------------------

def test_plural_devolve_uma_ficha_por_identidade():
    pdf = pdf_bytes([_pagina_siape(matricula="11111111"),
                     _pagina_siape(matricula="22222222")])
    fichas = ler_fichas_financeiras(pdf)

    assert [f.identificacao.matricula for f in fichas] == ["11111111",
                                                           "22222222"]


def test_plural_separa_exercicios():
    pdf = pdf_bytes([_pagina_siape(exercicio=2023),
                     _pagina_siape(exercicio=2024)])
    assert [f.exercicio for f in ler_fichas_financeiras(pdf)] == [2023, 2024]


def test_singular_recusa_escolher_quando_ha_mais_de_uma_ficha():
    # Devolver a primeira seria escolher em silêncio por quem chamou.
    pdf = pdf_bytes([_pagina_siape(matricula="11111111"),
                     _pagina_siape(matricula="22222222")])

    with pytest.raises(MultiplasFichasError) as exc:
        ler_ficha_financeira(pdf)

    assert exc.value.quantidade == 2
    assert "ler_fichas_financeiras" in str(exc.value)


def test_singular_sem_ficha_nenhuma_levanta():
    pdf = pdf_bytes([["uma folha de rosto qualquer"]])
    with pytest.raises(LayoutNaoReconhecidoError):
        ler_ficha_financeira(pdf)


# --------------------------------------------------------------------------
# Despacho: precisão de nome importa
# --------------------------------------------------------------------------

def test_pagina_do_esiape_e_despachada_para_o_parser_do_formato_b():
    pdf = pdf_bytes([_paginas_esiape()])
    ficha = ler_ficha_financeira(pdf)

    assert ficha.origem.layout is Layout.ESIAPE
    assert ficha.identificacao.tipo is TipoBeneficiario.INSTITUIDOR


def test_um_pdf_pode_misturar_os_dois_layouts():
    # Arquivo mesclado não precisa ser homogêneo; cada ficha registra de qual
    # layout veio, e a ordem do documento é preservada.
    pdf = pdf_bytes([_pagina_siape(matricula="11111111"), _paginas_esiape()])
    fichas = ler_fichas_financeiras(pdf)

    assert [f.origem.layout for f in fichas] == [Layout.SIAPE, Layout.ESIAPE]


def test_pagina_com_texto_estranho_e_layout_nao_reconhecido():
    pdf = pdf_bytes([["isto nao e ficha financeira de coisa nenhuma"]])
    with pytest.raises(LayoutNaoReconhecidoError):
        ler_fichas_financeiras(pdf)


def test_paginas_em_branco_nao_atrapalham_o_despacho():
    pdf = pdf_bytes([None, _pagina_siape(), None])
    assert len(ler_fichas_financeiras(pdf)) == 1


def test_pdf_sem_camada_de_texto_falha_antes_do_despacho():
    with pytest.raises(PdfSemTextoError):
        ler_fichas_financeiras(pdf_bytes([None], com_fonte=False))


# --------------------------------------------------------------------------
# Páginas ilegíveis (P5 e P7)
# --------------------------------------------------------------------------

def _falhar_na_pagina(monkeypatch, alvo: int) -> None:
    """Faz a extração estourar só na n-ésima página."""
    from pypdf import PageObject

    original = PageObject.extract_text
    contador = {"n": 0}

    def talvez_falhe(self, *args, **kwargs):
        contador["n"] += 1
        if contador["n"] == alvo:
            raise RuntimeError("cmap corrompido")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PageObject, "extract_text", talvez_falhe)


def test_pagina_ilegivel_dentro_do_intervalo_da_ficha_vira_aviso(monkeypatch):
    # Ficha de 3 páginas com a do meio quebrada: as páginas 1 e 3 formam o
    # bloco e a 2 cai dentro do intervalo.
    paginas = _paginas_da_fixture()
    pdf = pdf_bytes([paginas[0], paginas[0], paginas[1]])
    _falhar_na_pagina(monkeypatch, 2)

    fichas = ler_fichas_financeiras(pdf)
    codigos = [aviso.codigo for ficha in fichas for aviso in ficha.avisos]
    assert CodigoAviso.PAGINA_ILEGIVEL in codigos


def test_pagina_ilegivel_orfa_marca_as_fichas_vizinhas(monkeypatch):
    # A página do meio não pertence a bloco nenhum: no layout do e-SIAPE ela
    # poderia ser uma ficha inteira que sumiu do resultado.
    pdf = pdf_bytes([_pagina_siape(matricula="11111111"),
                     _pagina_siape(matricula="33333333"),
                     _pagina_siape(matricula="22222222")])
    _falhar_na_pagina(monkeypatch, 2)

    fichas = ler_fichas_financeiras(pdf)

    assert len(fichas) == 2
    for ficha in fichas:
        assert CodigoAviso.PAGINA_ILEGIVEL in [a.codigo for a in ficha.avisos]
        assert ficha.consistente is False


def test_sem_pagina_ilegivel_nao_ha_aviso():
    ficha = ler_ficha_financeira(_pdf_real())
    assert ficha.avisos == ()


# --------------------------------------------------------------------------
# strict
# --------------------------------------------------------------------------

def test_strict_atravessa_a_api_ate_a_conciliacao():
    from integra_gov.ficha_financeira import FichaInconsistenteError

    quebrada = _pagina_siape()
    quebrada[-1] = ("**** T O T A L   B R U T O          ****"
                    + "999,99".rjust(COLUNAS_VALOR[0].stop - 40))

    with pytest.raises(FichaInconsistenteError):
        ler_fichas_financeiras(pdf_bytes([quebrada]), strict=True)


def test_sem_strict_a_divergencia_vira_aviso():
    quebrada = _pagina_siape()
    quebrada[-1] = ("**** T O T A L   B R U T O          ****"
                    + "999,99".rjust(COLUNAS_VALOR[0].stop - 40))

    ficha = ler_ficha_financeira(pdf_bytes([quebrada]))
    assert ficha.consistente is False
    assert CodigoAviso.MES_NAO_CONFERE in [a.codigo for a in ficha.avisos]


def test_pagina_com_assinatura_do_siape_mas_sem_tabela_cita_a_assinatura():
    # Falhar alto está certo, mas o diagnóstico não pode mandar o usuário
    # desconfiar do arquivo: a página CARREGA a assinatura do relatório.
    pdf = pdf_bytes([["L.A54120.DE", "SIAPE - SISTEMA INTEGRADO",
                      "folha de rosto sem tabela de rubricas"]])

    with pytest.raises(LayoutNaoReconhecidoError) as exc:
        ler_fichas_financeiras(pdf)

    assert "L.A54120.DE" in str(exc.value)
    assert "cabeçalho da tabela" in str(exc.value)
    assert exc.value.pagina == 1
