"""Testes da leitura bruta do PDF (M2)."""

from __future__ import annotations

import io

import pytest

from integra_gov.ficha_financeira import PdfIlegivelError, PdfSemTextoError
from integra_gov.ficha_financeira.leitura import (
    abrir_pdf,
    extrair_paginas,
    tem_camada_de_texto,
)

from _pdf_sintetico import pdf_bytes

LINHAS = ["00597 PENSAO COMPLEMENTAR - CIVI R  0", "**** T O T A L ****"]


@pytest.fixture()
def com_texto() -> bytes:
    return pdf_bytes([LINHAS])


@pytest.fixture()
def sem_texto() -> bytes:
    """Reproduz o PDF da impressora do Windows: desenho, nenhuma fonte."""
    return pdf_bytes([None, None], com_fonte=False)


# --------------------------------------------------------------------------
# abrir_pdf
# --------------------------------------------------------------------------

def test_abrir_aceita_bytes(com_texto):
    assert len(abrir_pdf(com_texto).pages) == 1


def test_abrir_aceita_caminho(tmp_path, com_texto):
    caminho = tmp_path / "ficha.pdf"
    caminho.write_bytes(com_texto)
    assert len(abrir_pdf(caminho).pages) == 1
    assert len(abrir_pdf(str(caminho)).pages) == 1


def test_abrir_aceita_arquivo_aberto(com_texto):
    assert len(abrir_pdf(io.BytesIO(com_texto)).pages) == 1


def test_abrir_arquivo_inexistente_levanta_ilegivel(tmp_path):
    with pytest.raises(PdfIlegivelError, match="não encontrado"):
        abrir_pdf(tmp_path / "nao_existe.pdf")


def test_abrir_conteudo_que_nao_e_pdf_levanta_ilegivel():
    with pytest.raises(PdfIlegivelError):
        abrir_pdf(b"isto nao e um PDF")


# --------------------------------------------------------------------------
# tem_camada_de_texto — o guard reusável
# --------------------------------------------------------------------------

def test_tem_camada_de_texto_verdadeiro(com_texto):
    assert tem_camada_de_texto(com_texto) is True


def test_tem_camada_de_texto_falso_no_pdf_vetorizado(sem_texto):
    # É este o caso que passava em silêncio: o PDF abre, tem páginas, tem
    # desenho — e nenhum caractere legível por máquina.
    assert tem_camada_de_texto(sem_texto) is False


def test_tem_camada_de_texto_verdadeiro_com_texto_so_na_ultima_pagina():
    # Não pode olhar só a primeira página: num PDF mesclado a capa pode ser
    # uma folha em branco.
    assert tem_camada_de_texto(pdf_bytes([None, None, LINHAS])) is True


def test_tem_camada_de_texto_nao_confunde_ilegivel_com_sem_texto():
    # Arquivo que nem abre é outro problema, com outra solução — não devolve
    # False, levanta.
    with pytest.raises(PdfIlegivelError):
        tem_camada_de_texto(b"isto nao e um PDF")


# --------------------------------------------------------------------------
# extrair_paginas
# --------------------------------------------------------------------------

def test_extrair_devolve_uma_entrada_por_pagina(com_texto):
    paginas = extrair_paginas(com_texto)
    assert len(paginas) == 1
    assert paginas[0].numero == 1
    assert "00597 PENSAO COMPLEMENTAR - CIVI R" in paginas[0].texto


def test_extrair_numera_a_partir_de_um_e_mantem_paginas_vazias():
    # A numeração tem de bater com o PDF que o usuário vê, senão a
    # rastreabilidade de qual ficha veio de qual página se perde.
    paginas = extrair_paginas(pdf_bytes([None, LINHAS, None]))
    assert [p.numero for p in paginas] == [1, 2, 3]
    assert [p.vazia for p in paginas] == [True, False, True]


def test_extrair_preserva_o_alinhamento_das_colunas():
    # O modo layout é o que sustenta o parser do SIAPE: a coluna 33 é que diz
    # se o lançamento é rendimento ou desconto.
    linha = "00597 PENSAO COMPLEMENTAR - CIVI R  0"
    texto = extrair_paginas(pdf_bytes([[linha]]))[0].texto
    extraida = next(ln for ln in texto.splitlines() if ln.strip())
    assert extraida[33] == "R"
    assert extraida[0:5] == "00597"


def test_extrair_pdf_sem_texto_levanta_com_orientacao(sem_texto):
    with pytest.raises(PdfSemTextoError) as exc:
        extrair_paginas(sem_texto)

    mensagem = str(exc.value)
    # A mensagem tem de dizer o que fazer, não só o que houve — e sem
    # prescrever uma ferramenta: qualquer PDF com camada de texto serve.
    assert "camada de texto" in mensagem
    assert "download direto" in mensagem
    assert "Microsoft Print to PDF" in mensagem


def test_extrair_uma_pagina_com_texto_basta(sem_texto):
    # Só levanta se NENHUMA página tem texto; ficha mesclada pode ter folha em
    # branco no meio sem que isso invalide o documento.
    paginas = extrair_paginas(pdf_bytes([None, LINHAS]))
    assert len(paginas) == 2


def test_extrair_de_arquivo_em_disco(tmp_path, com_texto):
    caminho = tmp_path / "ficha.pdf"
    caminho.write_bytes(com_texto)
    assert extrair_paginas(caminho)[0].numero == 1


# --------------------------------------------------------------------------
# Página que falha na extração — a falha viaja no dado, não só no log
# --------------------------------------------------------------------------

def test_pagina_que_estoura_carrega_o_erro_e_nao_derruba_o_documento(monkeypatch):
    # No layout do e-SIAPE uma ficha inteira cabe numa página: se ela sumisse
    # em silêncio, o retorno traria uma ficha a menos sem nada que denunciasse.
    # O que está sob teste é o NOSSO tratamento da falha, então provocá-la por
    # monkeypatch é legítimo.
    from pypdf import PageObject

    original = PageObject.extract_text
    chamadas = {"n": 0}

    def falha_na_primeira(self, *args, **kwargs):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise RuntimeError("fonte corrompida")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PageObject, "extract_text", falha_na_primeira)

    paginas = extrair_paginas(pdf_bytes([LINHAS, LINHAS]))

    assert len(paginas) == 2
    assert paginas[0].erro == "fonte corrompida"
    assert paginas[0].legivel is False
    assert paginas[0].texto == ""
    # A página seguinte sai intacta — a tolerância continua existindo.
    assert paginas[1].legivel is True
    assert "00597" in paginas[1].texto


def test_pagina_normal_nao_tem_erro(com_texto):
    pagina = extrair_paginas(com_texto)[0]
    assert pagina.erro is None
    assert pagina.legivel is True


def test_pagina_em_branco_legitima_e_vazia_mas_legivel():
    # Vazia e ilegível são coisas diferentes: a folha em branco é vazia e
    # legível; a que estourou é vazia e ilegível.
    pagina = extrair_paginas(pdf_bytes([None, LINHAS]))[0]
    assert pagina.vazia is True
    assert pagina.legivel is True


def test_todas_as_paginas_estourando_nao_vira_diagnostico_de_pdf_sem_texto(
        monkeypatch):
    # "Tudo vazio" tem duas causas com conselhos opostos. Aqui o PDF pode ter
    # camada de texto — quem falhou foi a extração —, então mandar reemitir
    # pelo Chrome seria afirmar uma causa que os próprios erros desmentem.
    from pypdf import PageObject

    def sempre_falha(self, *args, **kwargs):
        raise RuntimeError("cmap corrompido")

    monkeypatch.setattr(PageObject, "extract_text", sempre_falha)

    with pytest.raises(PdfIlegivelError) as exc:
        extrair_paginas(pdf_bytes([LINHAS, LINHAS]))

    mensagem = str(exc.value)
    # As mensagens das falhas viajam na exceção, com a página de cada uma.
    assert "p1: cmap corrompido" in mensagem
    assert "p2: cmap corrompido" in mensagem
    # E a orientação da OUTRA causa não aparece.
    assert "Microsoft Print to PDF" not in mensagem


def test_pdf_realmente_sem_texto_continua_com_o_diagnostico_certo(sem_texto):
    # Sem nenhuma falha de extração, "abriu, extraiu, não havia texto" é o
    # diagnóstico correto — e é o que orienta a reexportação.
    with pytest.raises(PdfSemTextoError, match="Microsoft Print to PDF"):
        extrair_paginas(sem_texto)
