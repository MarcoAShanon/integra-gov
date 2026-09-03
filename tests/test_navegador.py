"""Testes de ``integra_gov.sei.navegador`` — sem Chrome real.

``subprocess.run`` e ``webdriver.Chrome`` são trocados por fakes; a plataforma
(``sys.platform``) é forçada para exercitar tanto Windows quanto POSIX.
"""

from __future__ import annotations

import pytest
from selenium.common.exceptions import SessionNotCreatedException

from integra_gov.sei import navegador as mod
from integra_gov.sei.exceptions import NavegadorError
from integra_gov.sei.navegador import (
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
    # Sem Chrome real: a varredura de PIDs não tem o que listar.
    monkeypatch.setattr(mod, "_listar_pids_chrome", lambda: set())
    monkeypatch.setattr(mod, "_listar_processos_chrome", dict)
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
    monkeypatch.setattr(mod, "_listar_pids_chrome", lambda: set())
    monkeypatch.setattr(mod, "_listar_processos_chrome", dict)
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
    monkeypatch.setattr(mod, "_listar_pids_chrome", lambda: set())
    monkeypatch.setattr(mod, "_listar_processos_chrome", dict)
    _chrome_que_falha(monkeypatch, falhas=99)
    with pytest.raises(NavegadorError) as exc:
        criar_driver_chrome(tentativas=2)
    # Encadeia a causa original (selenium) para diagnóstico.
    assert isinstance(exc.value.__cause__, SessionNotCreatedException)
    assert len(_sem_espera) == 1  # espera entre as 2 tentativas, não após a última


# Linhas de comando REAIS, medidas nesta maquina (Chrome 152 + chromedriver).
# Encurtadas, mas os marcadores sao os que o processo traz de verdade.
CMD_AUTOMACAO = (
    '"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --no-sandbox '
    "--enable-automation --headless=new --remote-debugging-port=0 "
    '--test-type=webdriver --user-data-dir="C:\\Temp\\scoped_dir13412_145"'
)
CMD_PESSOAL = '"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" '
CMD_RENDERER_PESSOAL = (
    '"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --type=renderer '
    "--lang=pt-BR --num-raster-threads=2 --renderer-client-id=7"
)


def test_e_da_automacao_separa_pessoal_de_webdriver():
    assert mod._e_da_automacao(CMD_AUTOMACAO)
    assert not mod._e_da_automacao(CMD_PESSOAL)
    # O renderer pessoal e o caso perigoso: nasce DURANTE a tentativa que falha.
    assert not mod._e_da_automacao(CMD_RENDERER_PESSOAL)


def test_orfao_da_tentativa_falha_e_encerrado(monkeypatch, _sem_espera):
    _forcar_windows(monkeypatch)
    # Antes da tentativa havia so o Chrome pessoal "100".
    monkeypatch.setattr(mod, "_listar_pids_chrome", lambda: {"100"})
    # Depois da falha, sobrou o orfao "200" (com marcadores de WebDriver).
    monkeypatch.setattr(
        mod, "_listar_processos_chrome",
        lambda: {"100": CMD_PESSOAL, "200": CMD_AUTOMACAO},
    )
    mortos: list[set[str]] = []
    monkeypatch.setattr(mod, "_matar_pids", lambda pids: mortos.append(set(pids)))
    monkeypatch.setattr(mod, "encerrar_chromedriver_orfaos", lambda: None)
    _chrome_que_falha(monkeypatch, falhas=1)

    assert criar_driver_chrome(tentativas=2) is not None
    # Matou SO o orfao "200" - nunca o Chrome pessoal "100".
    assert mortos == [{"200"}]


def test_aba_pessoal_aberta_durante_a_falha_sobrevive(monkeypatch, _sem_espera):
    """O defeito que este filtro corrige.

    Numa maquina com EDR a tentativa pode levar dezenas de segundos. Se o
    usuario abrir uma aba nessa janela, nasce um ``chrome.exe`` novo - que a
    regra antiga (so "PID novo") encerrava junto com o orfao.
    """
    _forcar_windows(monkeypatch)
    monkeypatch.setattr(mod, "_listar_pids_chrome", lambda: {"100"})
    monkeypatch.setattr(
        mod, "_listar_processos_chrome",
        lambda: {
            "100": CMD_PESSOAL,
            "200": CMD_AUTOMACAO,           # orfao da automacao: deve morrer
            "300": CMD_RENDERER_PESSOAL,    # aba que o usuario abriu: deve viver
        },
    )
    mortos: list[set[str]] = []
    monkeypatch.setattr(mod, "_matar_pids", lambda pids: mortos.append(set(pids)))
    monkeypatch.setattr(mod, "encerrar_chromedriver_orfaos", lambda: None)
    _chrome_que_falha(monkeypatch, falhas=1)

    assert criar_driver_chrome(tentativas=2) is not None
    assert mortos == [{"200"}]


def test_automacao_ja_em_curso_nao_e_encerrada(monkeypatch, _sem_espera):
    """Outro Selenium ja rodando (ex.: um lote do orquestrador) esta protegido
    pela primeira condicao: o PID ja existia antes da tentativa."""
    _forcar_windows(monkeypatch)
    monkeypatch.setattr(mod, "_listar_pids_chrome", lambda: {"100", "150"})
    monkeypatch.setattr(
        mod, "_listar_processos_chrome",
        lambda: {"100": CMD_PESSOAL, "150": CMD_AUTOMACAO, "200": CMD_AUTOMACAO},
    )
    mortos: list[set[str]] = []
    monkeypatch.setattr(mod, "_matar_pids", lambda pids: mortos.append(set(pids)))
    monkeypatch.setattr(mod, "encerrar_chromedriver_orfaos", lambda: None)
    _chrome_que_falha(monkeypatch, falhas=1)

    assert criar_driver_chrome(tentativas=2) is not None
    assert mortos == [{"200"}]


def test_sem_listagem_de_processos_nao_mata_ninguem(monkeypatch, _sem_espera):
    """Se a varredura falhar, nao se sabe o que e de quem - entao nao mata."""
    _forcar_windows(monkeypatch)
    monkeypatch.setattr(mod, "_listar_pids_chrome", lambda: {"100"})
    monkeypatch.setattr(mod, "_listar_processos_chrome", dict)
    mortos: list[set[str]] = []
    monkeypatch.setattr(mod, "_matar_pids", lambda pids: mortos.append(set(pids)))
    monkeypatch.setattr(mod, "encerrar_chromedriver_orfaos", lambda: None)
    _chrome_que_falha(monkeypatch, falhas=1)

    assert criar_driver_chrome(tentativas=2) is not None
    assert mortos == []


def test_sucesso_na_primeira_nao_mata_chrome(monkeypatch, driver_falso):
    _forcar_windows(monkeypatch)
    mortos: list[set[str]] = []
    monkeypatch.setattr(mod, "_matar_pids", lambda pids: mortos.append(set(pids)))
    monkeypatch.setattr(mod, "encerrar_chromedriver_orfaos", lambda: None)
    criar_driver_chrome()
    assert mortos == []  # caminho de sucesso não encerra nenhum Chrome


def test_listar_pids_chrome_windows_parseia_csv(monkeypatch):
    _forcar_windows(monkeypatch)
    saida = '"chrome.exe","100","Console","1","50 K"\n"chrome.exe","200","Console","1","60 K"\n'
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *_a, **_k: type("R", (), {"stdout": saida})()
    )
    assert mod._listar_pids_chrome() == {"100", "200"}


def test_listar_pids_chrome_sem_processos(monkeypatch):
    _forcar_windows(monkeypatch)
    saida = "INFO: No tasks are running which match the specified criteria.\n"
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *_a, **_k: type("R", (), {"stdout": saida})()
    )
    assert mod._listar_pids_chrome() == set()


def test_listar_pids_chrome_posix(monkeypatch):
    _forcar_posix(monkeypatch)
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *_a, **_k: type("R", (), {"stdout": "100\n200\n"})()
    )
    assert mod._listar_pids_chrome() == {"100", "200"}


def test_listar_processos_chrome_windows_parseia_json(monkeypatch):
    _forcar_windows(monkeypatch)
    saida = (
        '[{"ProcessId":100,"CommandLine":"chrome.exe"},'
        '{"ProcessId":200,"CommandLine":"chrome.exe --test-type=webdriver"}]'
    )
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *_a, **_k: type("R", (), {"stdout": saida})()
    )
    assert mod._listar_processos_chrome() == {
        "100": "chrome.exe",
        "200": "chrome.exe --test-type=webdriver",
    }


def test_listar_processos_chrome_um_so_vem_como_objeto(monkeypatch):
    """Com UM processo, ConvertTo-Json devolve objeto, nao lista."""
    _forcar_windows(monkeypatch)
    saida = '{"ProcessId":100,"CommandLine":"chrome.exe --enable-automation"}'
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *_a, **_k: type("R", (), {"stdout": saida})()
    )
    assert mod._listar_processos_chrome() == {
        "100": "chrome.exe --enable-automation"
    }


def test_listar_processos_chrome_commandline_nula(monkeypatch):
    """Processo protegido devolve CommandLine null: vira string vazia, e string
    vazia nunca casa com marcador - fica de fora do encerramento."""
    _forcar_windows(monkeypatch)
    saida = '[{"ProcessId":100,"CommandLine":null}]'
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *_a, **_k: type("R", (), {"stdout": saida})()
    )
    processos = mod._listar_processos_chrome()
    assert processos == {"100": ""}
    assert not mod._e_da_automacao(processos["100"])


def test_listar_processos_chrome_json_invalido(monkeypatch):
    _forcar_windows(monkeypatch)
    monkeypatch.setattr(
        mod.subprocess, "run",
        lambda *_a, **_k: type("R", (), {"stdout": "isto nao e json"})(),
    )
    assert mod._listar_processos_chrome() == {}


def test_listar_processos_chrome_posix(monkeypatch):
    _forcar_posix(monkeypatch)
    saida = (
        "  100 /usr/bin/chrome --enable-automation\n"
        "  200 /usr/bin/python3 -m algo\n"
    )
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *_a, **_k: type("R", (), {"stdout": saida})()
    )
    # So o processo de chrome entra; o python fica de fora.
    assert mod._listar_processos_chrome() == {
        "100": "/usr/bin/chrome --enable-automation"
    }


def test_listar_processos_chrome_timeout(monkeypatch):
    _forcar_windows(monkeypatch)

    def _demora(*_a, **_k):
        raise mod.subprocess.TimeoutExpired(cmd="powershell", timeout=15)

    monkeypatch.setattr(mod.subprocess, "run", _demora)
    assert mod._listar_processos_chrome() == {}


def test_orfaos_da_automacao_exige_as_duas_condicoes(monkeypatch):
    monkeypatch.setattr(
        mod, "_listar_processos_chrome",
        lambda: {
            "100": CMD_PESSOAL,           # velho e pessoal
            "150": CMD_AUTOMACAO,         # velho e da automacao
            "300": CMD_RENDERER_PESSOAL,  # novo e pessoal
            "200": CMD_AUTOMACAO,         # novo E da automacao -> o unico
        },
    )
    assert mod._orfaos_da_automacao({"100", "150"}) == {"200"}
