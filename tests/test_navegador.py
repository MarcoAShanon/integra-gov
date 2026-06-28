"""Testes de ``integra.sei.navegador`` — sem Chrome real.

``subprocess.run`` e ``webdriver.Chrome`` são trocados por fakes; a plataforma
(``sys.platform``) é forçada para exercitar tanto Windows quanto POSIX.
"""

from __future__ import annotations

import pytest
from selenium.common.exceptions import SessionNotCreatedException

from integra.sei import navegador as mod
from integra.sei.exceptions import NavegadorError
from integra.sei.navegador import (
    criar_driver_chrome,
    encerrar_chrome,
    encerrar_chromedriver_orfaos,
)


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    """Neutraliza o backoff entre tentativas e conta as esperas."""
    esperas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", esperas.append)
    return esperas


@pytest.fixture
def comandos(monkeypatch):
    """Captura cada lista de argumentos passada a ``subprocess.run``."""
    chamadas: list[list[str]] = []

    def _fake_run(cmd, **_kwargs):
        chamadas.append(cmd)
        return None

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    return chamadas


@pytest.fixture
def driver_falso(monkeypatch):
    """Substitui ``webdriver.Chrome`` por um fake que registra as ``options``."""
    capturado = {}

    class _ChromeFake:
        def __init__(self, *, options):
            capturado["options"] = options
            capturado["args"] = list(options.arguments)

    monkeypatch.setattr(mod.webdriver, "Chrome", _ChromeFake)
    return capturado


def _forcar_windows(monkeypatch):
    monkeypatch.setattr(mod.sys, "platform", "win32")


def _forcar_posix(monkeypatch):
    monkeypatch.setattr(mod.sys, "platform", "linux")


def test_orfaos_no_windows_usa_taskkill(monkeypatch, comandos):
    _forcar_windows(monkeypatch)
    encerrar_chromedriver_orfaos()
    assert comandos == [["taskkill", "/F", "/IM", "chromedriver.exe"]]


def test_orfaos_no_posix_usa_pkill(monkeypatch, comandos):
    _forcar_posix(monkeypatch)
    encerrar_chromedriver_orfaos()
    assert comandos == [["pkill", "-x", "chromedriver"]]


def test_encerrar_chrome_mata_driver_e_navegador(monkeypatch, comandos):
    _forcar_windows(monkeypatch)
    encerrar_chrome()
    assert comandos == [
        ["taskkill", "/F", "/IM", "chromedriver.exe"],
        ["taskkill", "/F", "/IM", "chrome.exe"],
    ]


def test_matar_processos_tolera_comando_ausente(monkeypatch):
    def _explode(*_a, **_k):
        raise FileNotFoundError

    monkeypatch.setattr(mod.subprocess, "run", _explode)
    # Não deve levantar — apenas registra em debug e segue.
    encerrar_chromedriver_orfaos()


def test_criar_driver_aplica_args_gov_e_limpa_orfaos(
    monkeypatch, comandos, driver_falso
):
    _forcar_windows(monkeypatch)
    driver = criar_driver_chrome()
    assert driver is not None
    # Limpou os órfãos por padrão (não tocou no chrome.exe).
    assert comandos == [["taskkill", "/F", "/IM", "chromedriver.exe"]]
    assert "--no-sandbox" in driver_falso["args"]
    assert "--disable-dev-shm-usage" in driver_falso["args"]
    assert "--headless=new" not in driver_falso["args"]


def test_criar_driver_headless_adiciona_flag(monkeypatch, comandos, driver_falso):
    _forcar_posix(monkeypatch)
    criar_driver_chrome(headless=True)
    assert "--headless=new" in driver_falso["args"]


def test_criar_driver_sem_limpeza_nao_mata_nada(
    monkeypatch, comandos, driver_falso
):
    _forcar_windows(monkeypatch)
    criar_driver_chrome(limpar_chromedriver=False)
    assert comandos == []


def test_criar_driver_encerrar_todo_chrome(monkeypatch, comandos, driver_falso):
    _forcar_windows(monkeypatch)
    criar_driver_chrome(encerrar_todo_chrome=True)
    # Marreta: mata chromedriver E chrome; não repete a limpeza leve.
    assert comandos == [
        ["taskkill", "/F", "/IM", "chromedriver.exe"],
        ["taskkill", "/F", "/IM", "chrome.exe"],
    ]


def test_criar_driver_args_extra_e_options_proprias(
    monkeypatch, comandos, driver_falso
):
    _forcar_posix(monkeypatch)
    opts = mod.ChromeOptions()
    opts.add_argument("--lang=pt-BR")
    criar_driver_chrome(
        options=opts, args_extra=("--user-data-dir=/tmp/sei",)
    )
    args = driver_falso["args"]
    assert "--lang=pt-BR" in args  # reaproveitou as options passadas
    assert "--user-data-dir=/tmp/sei" in args
    assert "--no-sandbox" in args
    assert driver_falso["options"] is opts


def _chrome_que_falha(monkeypatch, falhas: int):
    """Faz ``webdriver.Chrome`` falhar ``falhas`` vezes e então abrir.

    Retorna um dict com a contagem de tentativas observadas.
    """
    estado = {"chamadas": 0}

    class _ChromeFlaky:
        def __init__(self, *, options):
            estado["chamadas"] += 1
            if estado["chamadas"] <= falhas:
                raise SessionNotCreatedException("Chrome instance exited")

    monkeypatch.setattr(mod.webdriver, "Chrome", _ChromeFlaky)
    return estado


def test_retry_abre_apos_falhas_transitorias(monkeypatch, comandos, _sem_espera):
    _forcar_windows(monkeypatch)
    estado = _chrome_que_falha(monkeypatch, falhas=2)
    driver = criar_driver_chrome(tentativas=3)
    assert driver is not None
    assert estado["chamadas"] == 3  # 2 falhas + 1 sucesso
    # Limpeza de órfãos roda ANTES de cada tentativa (a falha deixa zumbi).
    assert comandos == [["taskkill", "/F", "/IM", "chromedriver.exe"]] * 3
    assert len(_sem_espera) == 2  # backoff entre as 3 tentativas


def test_esgota_tentativas_levanta_navegador_error(
    monkeypatch, comandos, _sem_espera
):
    _forcar_posix(monkeypatch)
    _chrome_que_falha(monkeypatch, falhas=99)
    with pytest.raises(NavegadorError) as exc:
        criar_driver_chrome(tentativas=2)
    # Encadeia a causa original (selenium) para diagnóstico.
    assert isinstance(exc.value.__cause__, SessionNotCreatedException)
    assert len(_sem_espera) == 1  # espera entre as 2 tentativas, não após a última
