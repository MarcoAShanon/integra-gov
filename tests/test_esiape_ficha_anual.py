"""Testes de ``integra_gov.esiape.ficha_anual`` — DriverFake estendido."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from integra_gov.esiape import navegacao as nav
from integra_gov.esiape.exceptions import (
    EsiapeError,
    ExtracaoFichaEsiapeInterrompida,
    FichaEsiapeIndisponivel,
)
from integra_gov.esiape.ficha_anual import (
    FichaAnualServidor,
    ResultadoFichaEsiape,
)
from tests.test_esiape_navegacao import DriverFake, ElementoFake, FrameFake


def test_excecoes_novas_sao_esiape_error():
    assert issubclass(ExtracaoFichaEsiapeInterrompida, EsiapeError)
    assert issubclass(FichaEsiapeIndisponivel, EsiapeError)


def test_extracao_interrompida_carrega_blocos_e_causa():
    causa = RuntimeError("popup sumiu")
    exc = ExtracaoFichaEsiapeInterrompida([(2008, 2022)], causa)
    assert exc.blocos_processados == [(2008, 2022)]
    assert exc.causa is causa
    assert "2008" in str(exc)


def test_pypdf_disponivel():
    from pypdf import PdfReader, PdfWriter  # noqa: F401


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    from integra_gov.esiape import ficha_anual as fmod

    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(fmod.time, "sleep", lambda *_a, **_k: None)


class DriverFicha(DriverFake):
    """DriverFake + refresh() (a impressão exige refresh pós-popup)."""

    def __init__(self, raiz):
        super().__init__(raiz)
        self.refreshes = 0

    def refresh(self):
        self.refreshes += 1


def pdf_minimo(caminho: Path) -> Path:
    """PDF real de 1 página em branco (pypdf) para testes de mesclagem."""
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    with open(caminho, "wb") as f:
        w.write(f)
    return caminho


def test_dividir_blocos_respeita_limite_de_15():
    assert FichaAnualServidor._dividir_blocos(2008, 2026) == [
        (2008, 2022), (2023, 2026)]
    assert FichaAnualServidor._dividir_blocos(2020, 2026) == [(2020, 2026)]
    assert FichaAnualServidor._dividir_blocos(2010, 2010) == [(2010, 2010)]


def test_construtor_cria_pastas(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()),
                               pasta_saida=tmp_path / "saida")
    assert (tmp_path / "saida").is_dir()
    assert ficha.pasta_download == tmp_path / "saida" / "_download_esiape"
    assert ficha.pasta_download.is_dir()


def test_extrair_valida_parametros(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)
    with pytest.raises(ValueError):
        ficha.extrair("", 2008, 2026)
    with pytest.raises(ValueError):
        ficha.extrair("0000000", 2026, 2008)


def test_resultado_dataclass():
    r = ResultadoFichaEsiape()
    assert r.pdf is None
    assert r.pdfs_blocos == []
    assert r.blocos_com_dados == []
    assert r.blocos_sem_dados == []
    assert r.duracao_s == 0.0


def _arvore_fpemfichaf():
    """Menu com lupa; clicar Ir abre a tela do FPEMFICHAF completa."""
    raiz = FrameFake()
    wa1 = FrameFake("WA1", visivel=True)
    wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    ir = ElementoFake()
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]
    raiz.filhos = [wa1]

    consulta_online = ElementoFake()
    matricula = ElementoFake()
    ano_ini, ano_fim = ElementoFake(), ElementoFake()
    pesquisar_seletores = {
        FichaAnualServidor.SEL_CONSULTA_ONLINE: [consulta_online],
        FichaAnualServidor.SEL_MATRICULA: [matricula],
        FichaAnualServidor.SEL_ANO_INICIO: [ano_ini],
        FichaAnualServidor.SEL_ANO_FIM: [ano_fim],
    }

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos.update(pesquisar_seletores)

    ir.click = ir_click
    return raiz, wa1, matricula


def test_consultar_bloco_com_dados(tmp_path):
    raiz, wa1, matricula = _arvore_fpemfichaf()
    driver = DriverFicha(raiz)
    driver.resultado_script = ""  # texto da tela sem MSG_SEM_DADOS
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)
    # após a consulta, o botão Gerar Relatório aparece = tem dados
    _click_mat = matricula.send_keys

    def mat_keys(*teclas):
        _click_mat(*teclas)
        wa1.elementos[FichaAnualServidor.SEL_GERAR_RELATORIO] = [ElementoFake()]

    matricula.send_keys = mat_keys
    assert ficha._consultar_bloco("0000000", 2008, 2022) is True
    assert "0000000" in matricula.teclas


def test_consultar_bloco_sem_dados_devolve_false(tmp_path):
    from unittest.mock import patch

    raiz, wa1, matricula = _arvore_fpemfichaf()
    driver = DriverFicha(raiz)

    def roteiro(script, *args):
        if "innerText" in script:
            return "mensagem: NAO HOUVE DADOS PARA CRITERIO SOLICITADO"
        return False  # overlay_presente e afins

    driver.resultado_script = roteiro
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)
    with patch.object(FichaAnualServidor, "TIMEOUT_CONSULTA", 0.05):
        assert ficha._consultar_bloco("0000000", 2008, 2022) is False


def test_consultar_bloco_tela_nao_abre_levanta(tmp_path):
    from unittest.mock import patch

    driver = DriverFicha(FrameFake())  # sem lupa, sem nada
    driver.resultado_script = ""
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)
    from integra_gov.esiape.exceptions import TransacaoNaoAbriu

    # garantir_menu tem timeout REAL de 60s (monotonic) — atalha p/ o teste
    with patch.object(nav, "garantir_menu", lambda d, timeout=60: False):
        with pytest.raises(TransacaoNaoAbriu):
            ficha._consultar_bloco("0000000", 2008, 2022)


def test_imprimir_bloco_popup_download_e_renomeio(tmp_path):
    raiz, wa1, _mat = _arvore_fpemfichaf()
    driver = DriverFicha(raiz)
    driver.resultado_script = False
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)

    imprimir = ElementoFake()
    wa1.elementos[FichaAnualServidor.SEL_IMPRIMIR] = [imprimir]
    wa1.elementos[FichaAnualServidor.SEL_GERAR_RELATORIO] = [ElementoFake()]

    _click_imp = imprimir.click

    def imprimir_click():
        _click_imp()
        driver.window_handles = ["principal", "popup_impressao"]
        pdf_minimo(ficha.pasta_download / "fichas_financeiras.pdf")

    imprimir.click = imprimir_click

    caminho = ficha._imprimir_bloco("0000000", 2008, 2022)
    assert caminho == tmp_path / "ficha_0000000_2008_2022.pdf"
    assert caminho.exists()
    assert "popup_impressao" in driver.fechadas       # fechado por Selenium
    assert driver.janela_atual == "principal"
    assert driver.refreshes >= 1                       # refresh pós-popup
    # download não deixou órfão com o nome bruto
    assert not (ficha.pasta_download / "fichas_financeiras.pdf").exists()


def test_limpar_downloads_orfaos_remove_pdfs_antigos(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)
    orfao = pdf_minimo(ficha.pasta_download / "resto_antigo.pdf")
    ficha._limpar_downloads_orfaos()
    assert not orfao.exists()


def test_extrair_blocos_com_e_sem_dados_mescla_e_renomeia(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)

    def consulta(matricula, ano_de, ano_ate):
        return ano_de != 2023  # 2º bloco sem dados

    def imprime(matricula, ano_de, ano_ate):
        return pdf_minimo(
            tmp_path / f"ficha_{matricula}_{ano_de}_{ano_ate}.pdf")

    with patch.object(ficha, "_consultar_bloco", side_effect=consulta), \
         patch.object(ficha, "_imprimir_bloco", side_effect=imprime):
        r = ficha.extrair("0000000", 2008, 2026)

    assert r.blocos_com_dados == [(2008, 2022)]
    assert r.blocos_sem_dados == [(2023, 2026)]
    assert r.pdfs_blocos == [tmp_path / "ficha_0000000_2008_2022.pdf"]
    assert r.pdf == tmp_path / "ficha_0000000_2008_2026.pdf"
    assert r.pdf.exists() and r.duracao_s >= 0


def test_extrair_bloco_unico_fim_a_fim_sem_colisao_de_nome(tmp_path):
    """Faixa que cabe num único bloco: o bloco JÁ nasce com o mesmo nome do
    destino mesclado. Copiar src==dst estourava PermissionError no Windows —
    aqui não deve copiar, só reconhecer o próprio arquivo como resultado."""
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)

    def imprime(matricula, ano_de, ano_ate):
        caminho = tmp_path / f"ficha_{matricula}_{ano_de}_{ano_ate}.pdf"
        return pdf_minimo(caminho)

    with patch.object(ficha, "_consultar_bloco", return_value=True), \
         patch.object(ficha, "_imprimir_bloco", side_effect=imprime):
        r = ficha.extrair("0000000", 2014, 2026)

    esperado = tmp_path / "ficha_0000000_2014_2026.pdf"
    assert r.pdf == esperado
    assert esperado.exists()


def test_extrair_todos_sem_dados_pdf_none(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)
    with patch.object(ficha, "_consultar_bloco", return_value=False):
        r = ficha.extrair("0000000", 2020, 2024)
    assert r.pdf is None
    assert r.blocos_sem_dados == [(2020, 2024)]


def test_extrair_erro_no_bloco_aborta_com_processados(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)

    def consulta(matricula, ano_de, ano_ate):
        if ano_de == 2023:
            raise RuntimeError("Browser window not found")
        return True

    def imprime(matricula, ano_de, ano_ate):
        return pdf_minimo(
            tmp_path / f"ficha_{matricula}_{ano_de}_{ano_ate}.pdf")

    with patch.object(ficha, "_consultar_bloco", side_effect=consulta), \
         patch.object(ficha, "_imprimir_bloco", side_effect=imprime):
        with pytest.raises(ExtracaoFichaEsiapeInterrompida) as exc:
            ficha.extrair("0000000", 2008, 2026)
    assert exc.value.blocos_processados == [(2008, 2022)]
    assert isinstance(exc.value.causa, RuntimeError)
    # parcial fica no disco para diagnóstico
    assert (tmp_path / "ficha_0000000_2008_2022.pdf").exists()


def test_mesclar_ordem_cronologica(tmp_path):
    from pypdf import PdfReader

    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)
    a = pdf_minimo(tmp_path / "a.pdf")
    b = pdf_minimo(tmp_path / "b.pdf")
    destino = ficha._mesclar([a, b], tmp_path / "final.pdf")
    assert PdfReader(destino).get_num_pages() == 2


class DriverPopupTeimoso(DriverFicha):
    """close() não fecha de verdade (popup teimoso do CIS)."""

    def close(self):
        self.fechadas.append(self.janela_atual)  # registra, mas não remove


def test_popup_teimoso_fallback_js_e_fluxo_segue(tmp_path):
    raiz, wa1, _mat = _arvore_fpemfichaf()
    driver = DriverPopupTeimoso(raiz)
    driver.resultado_script = False
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)

    imprimir = ElementoFake()
    wa1.elementos[FichaAnualServidor.SEL_IMPRIMIR] = [imprimir]
    wa1.elementos[FichaAnualServidor.SEL_GERAR_RELATORIO] = [ElementoFake()]

    _click_imp = imprimir.click

    def imprimir_click():
        _click_imp()
        driver.window_handles = ["principal", "popup_teimoso"]
        pdf_minimo(ficha.pasta_download / "fichas_financeiras.pdf")

    imprimir.click = imprimir_click

    caminho = ficha._imprimir_bloco("0000000", 2008, 2022)
    assert caminho.exists()                       # o fluxo NÃO morre
    assert any("window.close" in s for s in driver.scripts)  # fallback JS
    assert "popup_teimoso" in driver.window_handles  # órfã fica p/ a varredura


def test_exports_do_ciclo_e2():
    import integra_gov.esiape as pacote

    for nome in ("FichaAnualServidor", "ResultadoFichaEsiape",
                 "DadosFuncionais", "DadosFuncionaisOrgao",
                 "FichaMultiOrgao", "ResultadoMultiOrgao"):
        assert hasattr(pacote, nome), nome
        assert nome in pacote.__all__
