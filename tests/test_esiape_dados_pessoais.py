"""Testes de ``integra_gov.esiape.dados_pessoais`` (CDCOINDPES)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from selenium.webdriver.common.keys import Keys

from integra_gov.esiape import dados_pessoais as dmod
from integra_gov.esiape.exceptions import (
    DadosPessoaisIndisponiveis,
    EsiapeError,
    PdfImpressoIlegivel,
    TransacaoNaoAbriu,
)
from integra_gov.ficha_financeira import PdfIlegivelError
from tests._pdf_sintetico import pdf_bytes

# Rótulos reais da tela CDCOINDPES; valores fictícios.
LINHAS_PDF = [
    "DADOS INDIVIDUAIS PESSOAIS",
    "MATRICULA: 0000000     NOME: FULANO DE TAL",
    "SIT.SER.: 02 APOSENTADO     NUMERO DO CPF: 000.000.000-00",
    "DATA NASCIMENTO: 15AGO1960     E-MAIL PESSOAL: FULANO@EXEMPLO.GOV.BR",
    "MUNICIPIO: CIDADE EXEMPLO     UF: XX",
    "ORGAO SOLICITADO: 00000 - ORGAO/TESTE",
]
TEXTO = "\n".join(LINHAS_PDF)


def pdf_cadastral(caminho: Path, linhas=LINHAS_PDF) -> Path:
    caminho.write_bytes(pdf_bytes([linhas]))
    return caminho


def test_excecao_nova_e_esiape_error():
    exc = DadosPessoaisIndisponiveis("0000000", "botão Imprimir não apareceu")
    assert isinstance(exc, EsiapeError)
    assert exc.matricula == "0000000"
    assert exc.motivo == "botão Imprimir não apareceu"
    assert "*****00" in str(exc) and "0000000" not in str(exc)
    assert "Imprimir" in str(exc)


# ----------------------------------------------------------------- parsing
def test_extrair_campos_le_os_9_rotulos():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos(TEXTO)
    assert c == {
        "matricula": "0000000",
        "nome": "FULANO DE TAL",
        "situacao": "APOSENTADO",
        "cpf": "000.000.000-00",
        "data_nascimento": "15/08/1960",
        "email": "fulano@exemplo.gov.br",
        "municipio": "Cidade Exemplo",
        "uf": "XX",
        "orgao": "ORGAO/TESTE",
    }


def test_extrair_campos_rotulo_ausente_vira_none():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos("MATRICULA: 0000000\nNOME: FULANO DE TAL")
    assert c["matricula"] == "0000000"
    assert c["nome"] == "FULANO DE TAL"
    for k in ("situacao", "cpf", "data_nascimento", "email", "municipio", "uf", "orgao"):
        assert c[k] is None


def test_extrair_campos_corta_no_proximo_rotulo_da_mesma_linha():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos("NOME: FULANO DE TAL  SIT.SER.: 01 ATIVO PERMANENTE")
    assert c["nome"] == "FULANO DE TAL"
    assert c["situacao"] == "ATIVO PERMANENTE"


def test_extrair_campos_matricula_so_digitos():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    assert extrair_campos("MATRICULA: 00.000-00")["matricula"] == "0000000"


def test_extrair_campos_valor_com_dois_espacos_nao_trunca():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos(
        "NOME: FULANO  DE TAL     SIT.SER.: 01 ATIVO PERMANENTE")
    assert c["nome"] == "FULANO  DE TAL"
    assert c["situacao"] == "ATIVO PERMANENTE"


def test_extrair_campos_colunas_com_um_espaco_nao_engole_o_rotulo():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos("MUNICIPIO: CIDADE EXEMPLO UF: XX")
    assert c["municipio"] == "Cidade Exemplo"
    assert c["uf"] == "XX"


def test_extrair_campos_rotulo_nao_mapeado_corta_com_dois_espacos():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos(
        "E-MAIL PESSOAL: A@B.COM     E-MAIL INSTITUCIONAL: C@D.GOV.BR")
    assert c["email"] == "a@b.com"


def test_extrair_campos_rotulo_nao_mapeado_sexo_corta_o_nome():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos("NOME: FULANO DE TAL     SEXO: M")
    assert c["nome"] == "FULANO DE TAL"


def test_extrair_campos_nome_contendo_palavra_uf_nao_confunde_o_rotulo():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos("NOME: MARIA UF DA SILVA     UF: XX")
    assert c["nome"] == "MARIA UF DA SILVA"
    assert c["uf"] == "XX"


def test_extrair_campos_rotulo_precedido_de_barra_nao_confunde():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos("ORGAO/UF: 00000/XX")
    assert c["uf"] is None
    assert c["orgao"] is None


def test_extrair_campos_texto_irreconhecivel_tudo_none():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    assert all(v is None for v in extrair_campos("tela irreconhecivel").values())


@pytest.mark.parametrize("bruto, esperado", [
    ("15AGO1960", "15/08/1960"),
    ("01JAN2001", "01/01/2001"),
    ("15XYZ1960", None),
    ("1960-08-15", None),
    ("", None),
])
def test_data_siape(bruto, esperado):
    from integra_gov.esiape.dados_pessoais import _data_siape

    assert _data_siape(bruto) == esperado


@pytest.mark.parametrize("bruto, esperado", [
    ("02 APOSENTADO", "APOSENTADO"),
    ("APOSENTADO", "APOSENTADO"),
    ("1 - ATIVO", "ATIVO"),
    ("", None),
])
def test_situacao(bruto, esperado):
    from integra_gov.esiape.dados_pessoais import _situacao

    assert _situacao(bruto) == esperado


@pytest.mark.parametrize("bruto, esperado", [
    ("00000 - ORGAO/TESTE", "ORGAO/TESTE"),
    ("ORGAO/TESTE", "ORGAO/TESTE"),
    ("", None),
])
def test_orgao(bruto, esperado):
    from integra_gov.esiape.dados_pessoais import _orgao

    assert _orgao(bruto) == esperado


# ------------------------------------------------------ ler_dados_pessoais
def test_ler_dados_pessoais_devolve_dataclass_com_pdf_e_texto(tmp_path):
    from integra_gov.esiape.dados_pessoais import DadosPessoais, ler_dados_pessoais

    pdf = pdf_cadastral(tmp_path / "x.pdf")
    d = ler_dados_pessoais(pdf)
    assert isinstance(d, DadosPessoais)
    assert d.pdf == pdf
    assert d.matricula == "0000000"
    assert d.nome == "FULANO DE TAL"
    assert d.email == "fulano@exemplo.gov.br"
    assert "NUMERO DO CPF" in d.texto


def test_ler_dados_pessoais_pdf_sem_texto_levanta(tmp_path):
    from integra_gov.esiape.dados_pessoais import ler_dados_pessoais

    pdf = tmp_path / "vetor.pdf"
    pdf.write_bytes(pdf_bytes([None], com_fonte=False))
    with pytest.raises(PdfIlegivelError):
        ler_dados_pessoais(pdf)


def test_ler_dados_pessoais_arquivo_que_nao_abre_levanta(tmp_path):
    from integra_gov.esiape.dados_pessoais import ler_dados_pessoais

    pdf = tmp_path / "lixo.pdf"
    pdf.write_bytes(b"isto nao e um PDF")
    with pytest.raises(PdfIlegivelError):
        ler_dados_pessoais(pdf)


def test_ler_dados_pessoais_le_todas_as_paginas(tmp_path):
    from integra_gov.esiape.dados_pessoais import ler_dados_pessoais

    pdf = tmp_path / "duas.pdf"
    pdf.write_bytes(pdf_bytes([LINHAS_PDF[:3], LINHAS_PDF[3:]]))
    d = ler_dados_pessoais(pdf)
    assert d.uf == "XX" and d.orgao == "ORGAO/TESTE"


def test_repr_nao_expoe_dados_pessoais(tmp_path):
    from integra_gov.esiape.dados_pessoais import ler_dados_pessoais

    pdf = pdf_cadastral(tmp_path / "dados_pessoais_0000000.pdf")
    d = ler_dados_pessoais(pdf)
    r = repr(d)
    assert "FULANO" not in r
    assert "000.000.000-00" not in r
    assert "NUMERO DO CPF" not in r
    assert "*****00" in r
    assert "0000000" not in r


def test_mascarar_matricula_curta_nao_expoe_tudo():
    from integra_gov.esiape.dados_pessoais import _mascarar

    assert _mascarar("5") == "******5"


@pytest.mark.parametrize("bruto, esperado", [
    ("MATRICULA 1234567 NAO CADASTRADA", "MATRICULA *****67 NAO CADASTRADA"),
    ("000.000-0", "*****00"),
    ("123.456.789-00", "*****00"),
    ("1234", "*****34"),
    ("UF 12", "UF 12"),
    ("ORGAO 40806 - X", "ORGAO *****06 - X"),
])
def test_mascarar_digitos(bruto, esperado):
    from integra_gov.esiape.dados_pessoais import _mascarar_digitos

    assert _mascarar_digitos(bruto) == esperado


# ------------------------------------------------- DadosPessoaisServidor
class _Elemento:
    def __init__(self, seletor, ordem):
        self.seletor = seletor
        self.ordem = ordem
        self.cliques = 0
        self.teclas = []

    def click(self):
        self.cliques += 1
        self.ordem.append(self.seletor)

    def clear(self):
        pass

    def send_keys(self, *t):
        self.teclas.extend(t)


class _Popup:
    """Popup CIS fake (``[id^='IPO_']``) para ``_texto_popup_cis``."""

    def __init__(self, texto, visivel=True):
        self.text = texto
        self.visivel = visivel

    def is_displayed(self):
        return self.visivel


class _SwitchToFake:
    def default_content(self):
        pass


class _Driver:
    """Driver mínimo: elementos por seletor CSS, relogin como atributo.

    ``ordem`` é compartilhada por todos os ``_Elemento``: cada ``click()``
    grava o próprio seletor nela, na ordem real dos cliques.
    """

    def __init__(self, seletores, popups=None):
        self.ordem: list[str] = []
        self.el = {s: _Elemento(s, self.ordem) for s in seletores}
        self._esiape_relogin_pendente = False
        self.popups = list(popups) if popups else []
        self.switch_to = _SwitchToFake()

    def find_element(self, by, valor):
        if valor not in self.el:
            raise Exception(f"no such element: {valor}")
        return self.el[valor]

    def find_elements(self, by, valor):
        if valor == "[id^='IPO_']":
            return self.popups
        return []


S = dmod.DadosPessoaisServidor
TODOS = (S.SEL_MATRICULA, S.SEL_CONSULTAR, S.SEL_IMPRIMIR, S.SEL_GERAR_PDF, S.SEL_SAIR)


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """Navegação e impressão substituídas; devolve (driver, servidor, chamadas)."""
    monkeypatch.setattr(dmod.time, "sleep", lambda *_a, **_k: None)
    driver = _Driver(TODOS)
    chamadas = {"navegar": [], "limpar_flag": 0, "imprimir": 0,
                "fechar_janelas_extras": 0, "limpar_overlay": 0,
                "fechar_popups": 0}

    def navegar(d, transacao, seletor, timeout=30):
        chamadas["navegar"].append(transacao)
        return True

    def imprimir(d, clicar, pasta_download, **kw):
        chamadas["imprimir"] += 1
        clicar()
        bruto = Path(pasta_download) / "cis_bruto.pdf"
        pdf_cadastral(bruto)
        return bruto

    def fechar_janelas_extras(d, *a, **k):
        chamadas["fechar_janelas_extras"] += 1

    def limpar_overlay(d, *a, **k):
        chamadas["limpar_overlay"] += 1
        return True

    def fechar_popups(d, *a, **k):
        chamadas["fechar_popups"] += 1
        return 0

    monkeypatch.setattr(dmod, "navegar_para_transacao", navegar)
    monkeypatch.setattr(dmod, "esperar_seletor", lambda d, s, timeout=20: (0,) if s in d.el else None)
    monkeypatch.setattr(dmod, "procurar_em_frames", lambda d, s: (0,) if s in d.el else None)
    monkeypatch.setattr(dmod, "fechar_janelas_extras", fechar_janelas_extras)
    monkeypatch.setattr(dmod, "limpar_overlay", limpar_overlay)
    monkeypatch.setattr(dmod, "fechar_popups_cis", fechar_popups)
    monkeypatch.setattr(dmod, "limpar_flag_relogin",
                        lambda d: chamadas.__setitem__("limpar_flag", chamadas["limpar_flag"] + 1))
    monkeypatch.setattr(dmod, "imprimir_via_popup", imprimir)
    servidor = S(driver, pasta_saida=tmp_path / "saida")
    return driver, servidor, chamadas


def test_pastas_default_como_ficha_anual(tmp_path):
    s = S(object(), pasta_saida=tmp_path / "s")
    assert s.pasta_saida == tmp_path / "s"
    assert s.pasta_download == tmp_path / "s" / "_download_esiape"
    assert s.pasta_saida.is_dir() and s.pasta_download.is_dir()


def test_matricula_vazia_levanta_value_error(ambiente):
    _, servidor, _ = ambiente
    with pytest.raises(ValueError):
        servidor.consultar("   ")


def test_matricula_so_pontuacao_levanta_value_error(ambiente):
    _, servidor, _ = ambiente
    with pytest.raises(ValueError):
        servidor.consultar("...-")


def test_consultar_normaliza_matricula_a_digitos(ambiente):
    _, servidor, _ = ambiente
    d = servidor.consultar("000.000-0")
    assert d.pdf == servidor.pasta_saida / "dados_pessoais_0000000.pdf"
    assert d.pdf.exists()


def test_consultar_caminho_feliz(ambiente):
    driver, servidor, chamadas = ambiente
    d = servidor.consultar(" 0000000 ")
    assert chamadas["navegar"] == ["CDCOINDPES"]
    assert driver.el[S.SEL_MATRICULA].teclas == ["0000000", Keys.ENTER]
    for sel in (S.SEL_CONSULTAR, S.SEL_IMPRIMIR, S.SEL_GERAR_PDF, S.SEL_SAIR):
        assert driver.el[sel].cliques == 1, sel
    assert driver.ordem == [S.SEL_CONSULTAR, S.SEL_IMPRIMIR, S.SEL_GERAR_PDF, S.SEL_SAIR]
    assert chamadas["fechar_janelas_extras"] == 1
    assert chamadas["fechar_popups"] == 1
    assert chamadas["limpar_overlay"] == 1
    assert chamadas["imprimir"] == 1
    assert d.pdf == servidor.pasta_saida / "dados_pessoais_0000000.pdf"
    assert d.pdf.exists()
    assert not (servidor.pasta_download / "cis_bruto.pdf").exists()
    assert d.nome == "FULANO DE TAL" and d.matricula == "0000000"


def test_consultar_sobrescreve_pdf_anterior(ambiente):
    _, servidor, _ = ambiente
    destino = servidor.pasta_saida / "dados_pessoais_0000000.pdf"
    destino.write_bytes(b"velho")
    d = servidor.consultar("0000000")
    assert d.pdf == destino and destino.read_bytes() != b"velho"


def test_relogin_atravessado_repete_uma_vez(ambiente):
    driver, servidor, chamadas = ambiente
    tentativas = []

    def navegar(d, transacao, seletor, timeout=30):
        tentativas.append(1)
        if len(tentativas) == 1:
            d._esiape_relogin_pendente = True
            return False
        return True

    with patch.object(dmod, "navegar_para_transacao", navegar):
        d = servidor.consultar("0000000")
    assert len(tentativas) == 2
    assert chamadas["limpar_flag"] == 1
    assert d.matricula == "0000000"


def test_falha_sem_relogin_nao_repete(ambiente):
    driver, servidor, chamadas = ambiente
    with patch.object(dmod, "navegar_para_transacao", lambda *a, **k: False):
        with pytest.raises(TransacaoNaoAbriu):
            servidor.consultar("0000000")
    assert chamadas["limpar_flag"] == 0


def test_relogin_persistente_levanta_apos_segunda_falha(ambiente):
    driver, servidor, chamadas = ambiente

    def navegar(d, transacao, seletor, timeout=30):
        d._esiape_relogin_pendente = True
        return False

    with patch.object(dmod, "navegar_para_transacao", navegar):
        with pytest.raises(TransacaoNaoAbriu):
            servidor.consultar("0000000")
    assert chamadas["limpar_flag"] == 1


def test_botao_imprimir_ausente_levanta_indisponiveis(ambiente):
    driver, servidor, _ = ambiente
    del driver.el[S.SEL_IMPRIMIR]
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("0000000")
    assert "Imprimir" in str(exc.value) or S.SEL_IMPRIMIR in str(exc.value)
    assert "a tela mostrou" not in str(exc.value)


def test_botao_consultar_ausente_recupera_a_tela(ambiente):
    """Sem o Consultar: recuperação roda (fechar popups de novo, Sair
    clicado, cortina limpa de novo) e a exceção original propaga."""
    driver, servidor, chamadas = ambiente
    del driver.el[S.SEL_CONSULTAR]
    with pytest.raises(DadosPessoaisIndisponiveis):
        servidor.consultar("0000000")
    assert chamadas["fechar_popups"] == 2  # início + recuperação
    assert chamadas["limpar_overlay"] == 2  # início + recuperação
    assert driver.el[S.SEL_SAIR].cliques == 1


def test_impressao_sem_pdf_levanta_indisponiveis(ambiente):
    _, servidor, _ = ambiente

    def imprimir(*a, **k):
        raise TimeoutError("nenhum PDF apareceu")

    with patch.object(dmod, "imprimir_via_popup", imprimir):
        with pytest.raises(DadosPessoaisIndisponiveis) as exc:
            servidor.consultar("0000000")
    assert "nenhum PDF apareceu" in str(exc.value)


def test_matricula_divergente_no_pdf_levanta(ambiente):
    _, servidor, chamadas = ambiente
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("1111111")
    assert "*****00" in str(exc.value) and "*****11" in str(exc.value)
    assert not (servidor.pasta_saida / "dados_pessoais_1111111.pdf").exists()
    # PDF divergente também recupera a tela antes de propagar.
    assert chamadas["fechar_popups"] == 2


def test_matricula_divergente_nao_apaga_pdf_anterior_bom(ambiente):
    _, servidor, _ = ambiente
    destino = servidor.pasta_saida / "dados_pessoais_1111111.pdf"
    destino.write_bytes(b"bom, de verdade")
    with pytest.raises(DadosPessoaisIndisponiveis):
        servidor.consultar("1111111")
    assert destino.read_bytes() == b"bom, de verdade"


def test_pdf_sem_texto_levanta_ilegivel_e_mantem_arquivo(ambiente):
    _, servidor, chamadas = ambiente

    def imprimir(d, clicar, pasta_download, **kw):
        bruto = Path(pasta_download) / "cis_bruto.pdf"
        bruto.write_bytes(pdf_bytes([None], com_fonte=False))
        return bruto

    with patch.object(dmod, "imprimir_via_popup", imprimir):
        with pytest.raises(PdfImpressoIlegivel) as exc:
            servidor.consultar("0000000")
    assert Path(exc.value.caminho).exists()
    assert chamadas["fechar_popups"] == 2  # início + recuperação (PdfImpressoIlegivel também recupera a tela)


def test_sair_falhando_nao_derruba(ambiente, caplog):
    driver, servidor, _ = ambiente
    driver.el[S.SEL_SAIR].click = lambda: (_ for _ in ()).throw(RuntimeError("stale"))
    d = servidor.consultar("0000000")
    assert d.matricula == "0000000"
    assert any("Sair" in r.message for r in caplog.records)


def test_sair_falhando_na_recuperacao_nao_mascara_a_excecao_original(ambiente):
    """Mesmo se o Sair da recuperação falhar, a exceção original (botão
    ausente) tem de propagar intacta — a recuperação nunca a mascara."""
    driver, servidor, _ = ambiente
    del driver.el[S.SEL_CONSULTAR]
    driver.el[S.SEL_SAIR].click = lambda: (_ for _ in ()).throw(RuntimeError("stale"))
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("0000000")
    assert "Consultar" in str(exc.value) or S.SEL_CONSULTAR in str(exc.value)


def test_recuperacao_falhando_nao_mascara_a_excecao_original(ambiente, caplog):
    """Mesmo se uma etapa DENTRO de ``_recuperar_tela`` (limpar_overlay)
    explodir com algo que não a própria falha esperada, o try/except externo
    da recuperação segura o estrago: a exceção original (Consultar ausente)
    continua propagando, e o log registra a falha da recuperação."""
    driver, servidor, _ = ambiente
    del driver.el[S.SEL_CONSULTAR]
    chamadas_overlay = []

    def limpar_overlay_com_erro(d, *a, **k):
        chamadas_overlay.append(1)
        if len(chamadas_overlay) == 1:
            return True  # chamada inicial em consultar(), antes da falha
        raise RuntimeError("overlay travado")  # chamada dentro da recuperação

    with patch.object(dmod, "limpar_overlay", limpar_overlay_com_erro):
        with pytest.raises(DadosPessoaisIndisponiveis) as exc:
            servidor.consultar("0000000")
    assert "Consultar" in str(exc.value) or S.SEL_CONSULTAR in str(exc.value)
    assert any("recuperação" in r.message for r in caplog.records)


def test_texto_popup_cis_mascarado_entra_no_motivo(ambiente):
    driver, servidor, _ = ambiente
    driver.popups.append(_Popup("MATRICULA 1234567 NAO CADASTRADA"))
    del driver.el[S.SEL_CONSULTAR]
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("0000000")
    assert "a tela mostrou: MATRICULA *****67 NAO CADASTRADA" in str(exc.value)
    assert "1234567" not in str(exc.value)


def test_texto_popup_cis_mascara_antes_de_truncar(ambiente):
    """Uma matrícula que cai perto do corte de 200 caracteres não pode
    escapar mascarada pela metade: a máscara roda no texto inteiro, o corte
    vem depois."""
    import re as _re

    driver, servidor, _ = ambiente
    driver.popups.append(_Popup("A" * 197 + "1234567 FIM"))
    del driver.el[S.SEL_CONSULTAR]
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("0000000")
    msg = str(exc.value)
    assert "1234567" not in msg
    assert _re.search(r"\d{3,}", msg) is None


def test_texto_popup_cis_invisivel_e_ignorado(ambiente):
    driver, servidor, _ = ambiente
    driver.popups.append(_Popup("MATRICULA 1234567 NAO CADASTRADA", visivel=False))
    del driver.el[S.SEL_CONSULTAR]
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("0000000")
    assert "a tela mostrou" not in str(exc.value)


def test_log_nao_expoe_matricula_inteira(ambiente, caplog):
    import logging

    _, servidor, _ = ambiente
    with caplog.at_level(logging.INFO, logger="integra_gov.esiape.dados_pessoais"):
        with pytest.raises(DadosPessoaisIndisponiveis):   # PDF traz 0000000
            servidor.consultar("1234567")
    texto = "\n".join(r.getMessage() for r in caplog.records)
    assert "1234567" not in texto and "*****67" in texto


def test_pdf_impresso_ilegivel_sem_bloco_tem_mensagem_sem_bloco(tmp_path):
    exc = PdfImpressoIlegivel(tmp_path / "x.pdf", None, "motivo")
    assert "bloco" not in str(exc) and "ilegível" in str(exc)


def test_exportado_no_subpacote():
    import integra_gov.esiape as pkg

    for nome in ("DadosPessoais", "DadosPessoaisServidor",
                 "DadosPessoaisIndisponiveis", "ler_dados_pessoais"):
        assert hasattr(pkg, nome), nome
        assert nome in pkg.__all__, nome
