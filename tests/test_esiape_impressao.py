"""``integra_gov.esiape.impressao`` — a mecânica de imprimir via popup, movida
de ``ficha_anual`` sem mudar comportamento."""

from __future__ import annotations

from pathlib import Path

import pytest

from integra_gov.esiape import impressao as mod
from integra_gov.esiape.impressao import (
    aguardar_pdf_estavel,
    aguardar_popup,
    fechar_popup,
    imprimir_via_popup,
    limpar_downloads_orfaos,
    retornar_apos_impressao,
)


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)


class _SwitchTo:
    def __init__(self, d):
        self._d = d

    def window(self, handle):
        self._d.janela_atual = handle

    def default_content(self):
        self._d.default_content_chamado += 1


class DriverImpressao:
    """Só o que a impressão usa: handles, close, refresh, execute_script."""

    def __init__(self):
        self.window_handles = ["principal"]
        self.janela_atual = "principal"
        self.current_window_handle = "principal"
        self.fechadas: list[str] = []
        self.refreshes = 0
        self.scripts: list[str] = []
        self.default_content_chamado = 0
        self.switch_to = _SwitchTo(self)
        self.close_falha = 0  # nº de vezes que close() deve falhar

    def close(self):
        if self.close_falha > 0:
            self.close_falha -= 1
            raise RuntimeError("close recusado")
        self.fechadas.append(self.janela_atual)
        self.window_handles = [h for h in self.window_handles if h != self.janela_atual]

    def refresh(self):
        self.refreshes += 1

    def execute_script(self, script, *args):
        self.scripts.append(script)
        if script == "window.close();":
            self.window_handles = [h for h in self.window_handles if h != self.janela_atual]


def _pdf(caminho: Path, tamanho: int = 10) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"%PDF-" + b"x" * tamanho)
    return caminho


# ------------------------------------------------------------ popup
def test_aguardar_popup_devolve_o_handle_novo():
    d = DriverImpressao()
    d.window_handles = ["principal", "popup"]
    assert aguardar_popup(d, ["principal"], timeout=0.05) == "popup"


def test_aguardar_popup_sem_popup_devolve_none_no_timeout():
    d = DriverImpressao()
    assert aguardar_popup(d, ["principal"], timeout=0.01) is None


# -------------------------------------------------------------- pdf
def test_aguardar_pdf_estavel_devolve_o_mais_recente_estavel(tmp_path):
    _pdf(tmp_path / "a.pdf")
    assert aguardar_pdf_estavel(tmp_path, timeout=1, intervalo=0) == tmp_path / "a.pdf"


def test_aguardar_pdf_estavel_ignora_arquivo_vazio_ate_ter_conteudo(tmp_path, monkeypatch):
    caminho = tmp_path / "a.pdf"
    caminho.write_bytes(b"")
    leituras = {"n": 0}
    original = Path.stat

    def _stat(self, *a, **k):
        if self == caminho:
            leituras["n"] += 1
            if leituras["n"] >= 3:
                caminho.write_bytes(b"%PDF-xxxx")
        return original(self, *a, **k)

    monkeypatch.setattr(Path, "stat", _stat)
    assert aguardar_pdf_estavel(tmp_path, timeout=2, intervalo=0) == caminho


def test_aguardar_pdf_estavel_timeout_honesto_cita_a_pasta(tmp_path):
    with pytest.raises(TimeoutError, match=str(tmp_path).replace("\\", "\\\\")):
        aguardar_pdf_estavel(tmp_path, timeout=0.01, intervalo=0)


# ------------------------------------------------------------ fechar
def test_fechar_popup_por_selenium():
    d = DriverImpressao()
    d.window_handles = ["principal", "popup"]
    fechar_popup(d, "popup")
    assert d.fechadas == ["popup"] and "popup" not in d.window_handles


def test_fechar_popup_cai_para_js_quando_close_resiste():
    d = DriverImpressao()
    d.window_handles = ["principal", "popup"]
    d.close_falha = 2
    fechar_popup(d, "popup")
    assert "window.close();" in d.scripts and "popup" not in d.window_handles


def test_fechar_popup_inexistente_e_inofensivo():
    d = DriverImpressao()
    fechar_popup(d, "sumiu")
    assert d.fechadas == [] and d.scripts == []


# ------------------------------------------------------------ voltar
def test_retornar_volta_a_principal_com_refresh_e_raiz():
    d = DriverImpressao()
    d.window_handles = ["principal"]
    d.janela_atual = "outra"
    retornar_apos_impressao(d, "principal")
    assert d.janela_atual == "principal" and d.refreshes == 1
    assert d.default_content_chamado == 1


def test_retornar_usa_a_primeira_janela_se_a_principal_sumiu():
    d = DriverImpressao()
    d.window_handles = ["sobrevivente"]
    retornar_apos_impressao(d, "principal")
    assert d.janela_atual == "sobrevivente"


# ------------------------------------------------------------ órfãos
def test_limpar_downloads_orfaos_remove_pdfs(tmp_path):
    a = _pdf(tmp_path / "a.pdf")
    (tmp_path / "nao_pdf.txt").write_text("x")
    limpar_downloads_orfaos(tmp_path)
    assert not a.exists() and (tmp_path / "nao_pdf.txt").exists()


# -------------------------------------------------------- composição
def test_imprimir_via_popup_faz_a_sequencia_inteira(tmp_path):
    d = DriverImpressao()
    _pdf(tmp_path / "resto_antigo.pdf")  # órfão: deve sumir antes do clique

    def clicar():
        d.window_handles = ["principal", "popup"]
        _pdf(tmp_path / "StartDynamicContent.pdf")

    pdf = imprimir_via_popup(d, clicar, tmp_path, timeout_popup=0.5, timeout_download=1)
    assert pdf == tmp_path / "StartDynamicContent.pdf"
    assert not (tmp_path / "resto_antigo.pdf").exists()
    assert d.fechadas == ["popup"]
    assert d.janela_atual == "principal" and d.refreshes == 1


def test_imprimir_via_popup_sem_popup_ainda_devolve_o_pdf(tmp_path):
    """O download pode disparar sem janela nova; quem decide é o PDF no disco."""
    d = DriverImpressao()

    def clicar():
        _pdf(tmp_path / "StartDynamicContent.pdf")

    pdf = imprimir_via_popup(d, clicar, tmp_path, timeout_popup=0.01, timeout_download=1)
    assert pdf.exists() and d.fechadas == [] and d.refreshes == 1
