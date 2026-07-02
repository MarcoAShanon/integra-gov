"""Testes de ``integra_gov.siape.lancador`` — sem HOD/pywinauto real.

Substitui ``glob``, ``os.startfile``, ``os.path.getctime`` e
``_dependencias.Application`` por fakes.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from integra_gov.siape import _dependencias as dep
from integra_gov.siape import lancador as mod
from integra_gov.siape.exceptions import LancamentoHodError, PywinautoIndisponivel
from integra_gov.siape.lancador import LancadorHod


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)


@pytest.fixture
def fake_app(monkeypatch):
    """Application() cujo connect() devolve um app indexável por título."""
    dlg = MagicMock()
    app = MagicMock()
    app.__getitem__.return_value = dlg  # app["Painel de controle"] -> dlg
    app.connect.return_value = app
    monkeypatch.setattr(dep, "Application", lambda: app)
    app._dlg = dlg
    return app


def test_localizar_sem_arquivo_levanta(monkeypatch):
    monkeypatch.setattr(mod.glob, "glob", lambda _p: [])
    with pytest.raises(LancamentoHodError):
        LancadorHod("C:/downloads").localizar_modulo()


def test_localizar_pega_mais_recente(monkeypatch):
    monkeypatch.setattr(mod.glob, "glob", lambda _p: ["a.jsp", "b.jsp"])
    monkeypatch.setattr(mod.os.path, "getctime", lambda f: 1 if f == "a.jsp" else 2)
    assert LancadorHod("C:/downloads").localizar_modulo() == "b.jsp"


def test_executar_modulo_chama_startfile(monkeypatch):
    chamados = []
    monkeypatch.setattr(mod.os, "startfile", chamados.append, raising=False)
    LancadorHod("C:/downloads").executar_modulo("C:/downloads/hodcivws1.jsp")
    assert chamados == ["C:/downloads/hodcivws1.jsp"]


def test_executar_modulo_sem_startfile_levanta(monkeypatch):
    # Força o estado deterministicamente (em Linux/CI startfile já é ausente).
    monkeypatch.setattr(mod.os, "startfile", None, raising=False)
    with pytest.raises(LancamentoHodError):
        LancadorHod("C:/downloads").executar_modulo("x.jsp")


def test_executar_modulo_oserror_levanta(monkeypatch):
    def _boom(_caminho):
        raise OSError("falha ao abrir")

    monkeypatch.setattr(mod.os, "startfile", _boom, raising=False)
    with pytest.raises(LancamentoHodError):
        LancadorHod("C:/d").executar_modulo("C:/d/hodcivws1.jsp")


def test_lancar_fluxo_completo(monkeypatch, fake_app):
    monkeypatch.setattr(mod.glob, "glob", lambda _p: ["C:/d/hodcivws9.jsp"])
    monkeypatch.setattr(mod.os.path, "getctime", lambda _f: 1)
    monkeypatch.setattr(mod.os, "startfile", lambda _c: None, raising=False)

    LancadorHod("C:/d").lancar()

    # Conduziu o painel: 5 TABs + ENTER.
    teclas = [c.args[0] for c in fake_app._dlg.type_keys.call_args_list]
    assert teclas.count("{TAB}") == LancadorHod.TABS_PAINEL
    assert teclas[-1] == "{ENTER}"


def test_painel_nao_aparece_levanta(monkeypatch):
    monkeypatch.setattr(mod.glob, "glob", lambda _p: ["C:/d/hodcivws9.jsp"])
    monkeypatch.setattr(mod.os.path, "getctime", lambda _f: 1)
    monkeypatch.setattr(mod.os, "startfile", lambda _c: None, raising=False)

    app = MagicMock()
    app.connect.side_effect = dep.ElementNotFoundError("janela ausente")
    monkeypatch.setattr(dep, "Application", lambda: app)

    lanc = LancadorHod("C:/d")
    lanc.TIMEOUT_PAINEL = 2  # encurta o retry
    with pytest.raises(LancamentoHodError):
        lanc.lancar()


def test_erro_inesperado_no_connect_propaga(monkeypatch, fake_app):
    # Um erro que NÃO seja "janela ausente" não vira timeout silencioso.
    monkeypatch.setattr(mod.glob, "glob", lambda _p: ["C:/d/hodcivws9.jsp"])
    monkeypatch.setattr(mod.os.path, "getctime", lambda _f: 1)
    monkeypatch.setattr(mod.os, "startfile", lambda _c: None, raising=False)
    fake_app.connect.side_effect = TypeError("kwargs errados")
    with pytest.raises(TypeError):
        LancadorHod("C:/d").lancar()


def test_pywinauto_indisponivel_levanta(monkeypatch):
    monkeypatch.setattr(mod.glob, "glob", lambda _p: ["C:/d/hodcivws9.jsp"])
    monkeypatch.setattr(mod.os.path, "getctime", lambda _f: 1)
    monkeypatch.setattr(mod.os, "startfile", lambda _c: None, raising=False)
    monkeypatch.setattr(dep, "Application", None)  # extra não instalado
    with pytest.raises(PywinautoIndisponivel):
        LancadorHod("C:/d").lancar()
