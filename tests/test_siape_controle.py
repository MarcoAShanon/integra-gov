"""Testes de ``integra_gov.siape.controle`` — sem pywinauto/terminal real.

O ``pywinauto`` não está instalado na CI (Linux). Os testes substituem
``_dependencias.Application`` e ``_dependencias.clipboard`` por fakes, então o
módulo roda em qualquer plataforma.
"""

from __future__ import annotations

import pytest

from integra_gov.siape import _dependencias as dep
from integra_gov.siape import controle as mod
from integra_gov.siape.controle import ControleTerminal3270
from integra_gov.siape.exceptions import (
    PywinautoIndisponivel,
    SessaoSiapePerdida,
    TerminalError,
    TerminalNaoEncontrado,
)


class _FakeDlg:
    def __init__(self, titulo="Terminal 3270 - A - 00000001"):
        self._titulo = titulo
        self.teclas: list[str] = []

    def window_text(self):
        return self._titulo

    def set_focus(self):
        pass

    def type_keys(self, comando):
        self.teclas.append(comando)


class _FakeApp:
    def __init__(self, dlg, erro_connect=None):
        self._dlg = dlg
        self._erro_connect = erro_connect

    def connect(self, **_kw):
        if self._erro_connect is not None:
            raise self._erro_connect
        return self

    def window(self, **_kw):
        return self._dlg


class _FakeClipboard:
    def __init__(self, data=""):
        self.data = data

    def GetData(self):  # noqa: N802 (nome da API do pywinauto)
        return self.data


@pytest.fixture
def terminal(monkeypatch):
    """Configura um terminal fake e devolve (controle, dlg, clipboard)."""
    dlg = _FakeDlg()
    clip = _FakeClipboard()
    monkeypatch.setattr(dep, "Application", lambda: _FakeApp(dlg))
    monkeypatch.setattr(dep, "clipboard", clip)
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)
    return ControleTerminal3270(), dlg, clip


def test_pywinauto_indisponivel_levanta(monkeypatch):
    monkeypatch.setattr(dep, "Application", None)  # extra não instalado
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)
    with pytest.raises(PywinautoIndisponivel):
        ControleTerminal3270().copiar_tela()


def test_terminal_nao_encontrado_levanta(monkeypatch):
    dlg = _FakeDlg()
    erro = dep.ElementNotFoundError("sem janela")
    monkeypatch.setattr(dep, "Application", lambda: _FakeApp(dlg, erro_connect=erro))
    monkeypatch.setattr(dep, "clipboard", _FakeClipboard())
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)
    with pytest.raises(TerminalNaoEncontrado):
        ControleTerminal3270().copiar_tela()


def test_copiar_tela_retorna_texto_e_usa_ctrl_a_ctrl_c(terminal):
    controle, dlg, clip = terminal
    clip.data = "conteudo da tela"
    assert controle.copiar_tela() == "conteudo da tela"
    assert "^a" in dlg.teclas  # selecionou tudo
    assert "^c" in dlg.teclas  # copiou


def test_copiar_tela_clipboard_sempre_vazio_levanta(terminal):
    controle, _dlg, clip = terminal
    clip.data = ""  # nunca retorna conteúdo
    with pytest.raises(TerminalError):
        controle.copiar_tela(max_tentativas=3)


def test_extrair_texto_por_coordenadas(terminal):
    controle, _dlg, _clip = terminal
    # Duas linhas de 82 caracteres; "ALVO" começa na coluna 1 da linha 2.
    linha1 = "a" * ControleTerminal3270.CARACTERES_POR_LINHA
    linha2 = "ALVO".ljust(ControleTerminal3270.CARACTERES_POR_LINHA, "b")
    tela = linha1 + linha2
    assert controle.extrair_texto(tela, 2, 1, 2, 4) == "ALVO"


def test_extrair_texto_tela_vazia_levanta(terminal):
    controle, _dlg, _clip = terminal
    with pytest.raises(ValueError):
        controle.extrair_texto("", 1, 1, 1, 4)


def test_buscar_texto_encontrado_e_ausente(terminal):
    controle, _dlg, clip = terminal
    largura = ControleTerminal3270.CARACTERES_POR_LINHA
    clip.data = ("x" * largura) + ("UORG".rjust(10))  # na linha 2
    pos = controle.buscar_texto("UORG")
    assert pos is not None
    assert pos[0] == 2  # linha
    clip.data = "nada aqui"
    assert controle.buscar_texto("UORG") is None


def test_mover_cursor_envia_comando_coordenada(terminal):
    controle, dlg, _clip = terminal
    controle.mover_cursor(22, 2)
    assert "22,2" in dlg.teclas


def test_escrever_texto_move_e_digita(terminal):
    controle, dlg, _clip = terminal
    controle.escrever_texto("TROCAHAB", 22, 2)
    assert "22,2" in dlg.teclas  # moveu o cursor
    assert "TROCAHAB" in dlg.teclas  # digitou


def test_verificar_texto_presente(terminal):
    controle, _dlg, clip = terminal
    largura = ControleTerminal3270.CARACTERES_POR_LINHA
    # "COD. SEGURANCA" na linha 1, colunas 1..14.
    clip.data = "COD. SEGURANCA".ljust(largura)
    assert controle.verificar_texto_presente("COD. SEGURANCA", 1, 1, 14) is True
    assert controle.verificar_texto_presente("AUSENTE", 1, 1, 14) is False


class _FakeDlgFalha:
    """Dlg cujo ``type_keys`` falha as primeiras ``falhas`` vezes."""

    def __init__(self, falhas):
        self.falhas = falhas
        self.tentativas = 0
        self.teclas: list[str] = []

    def window_text(self):
        return "Terminal 3270 - A - 00000001"

    def set_focus(self):
        pass

    def type_keys(self, comando):
        self.tentativas += 1
        if self.tentativas <= self.falhas:
            raise RuntimeError("type_keys falhou")
        self.teclas.append(comando)


def test_copiar_tela_retry_clipboard_intermitente(monkeypatch):
    dlg = _FakeDlg()
    estado = {"n": 0}

    class _ClipFlaky:
        def GetData(self):  # noqa: N802
            estado["n"] += 1
            if estado["n"] == 1:
                raise OSError("clipboard ocupado")
            if estado["n"] == 2:
                return ""  # vazio: tenta de novo
            return "TELA OK"

    monkeypatch.setattr(dep, "Application", lambda: _FakeApp(dlg))
    monkeypatch.setattr(dep, "clipboard", _ClipFlaky())
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)
    assert ControleTerminal3270().copiar_tela() == "TELA OK"
    assert estado["n"] >= 3  # houve retry


def test_enviar_teclas_reconecta_apos_falha(monkeypatch):
    dlg = _FakeDlgFalha(falhas=1)  # falha 1x, depois envia
    monkeypatch.setattr(dep, "Application", lambda: _FakeApp(dlg))
    monkeypatch.setattr(dep, "clipboard", _FakeClipboard())
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)
    ControleTerminal3270().enviar_teclas("{F2}")  # não deve levantar
    assert dlg.teclas == ["{F2}"]
    assert dlg.tentativas == 2  # 1 falha + 1 sucesso


def test_enviar_teclas_falha_total_levanta_sessao_perdida(monkeypatch):
    dlg = _FakeDlgFalha(falhas=99)
    monkeypatch.setattr(dep, "Application", lambda: _FakeApp(dlg))
    monkeypatch.setattr(dep, "clipboard", _FakeClipboard())
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)
    with pytest.raises(SessaoSiapePerdida):
        ControleTerminal3270().enviar_teclas("{F2}")


def test_extrair_texto_coordenadas_invalidas(terminal):
    controle, _dlg, _clip = terminal
    tela = "x" * (ControleTerminal3270.CARACTERES_POR_LINHA * 3)
    with pytest.raises(ValueError):
        controle.extrair_texto(tela, 0, 1, 0, 4)  # linha < 1
    with pytest.raises(ValueError):
        controle.extrair_texto(tela, 1, 10, 1, 5)  # coluna_final < coluna_inicial
