"""Criação do WebDriver do Chrome e limpeza de processos presos.

A biblioteca é **headless** — todas as classes recebem um ``driver`` pronto, e
você pode criá-lo como quiser. Este módulo é apenas uma **conveniência opcional**
que abre o Chrome já com os ajustes que ambientes gerenciados (gov) costumam
exigir, e que, antes de abrir, faz a limpeza de processos ``chromedriver``
presos — a causa mais comum do erro *"Chrome instance exited"* / navegador que
não abre nessas máquinas.

Segurança da limpeza:
  - :func:`encerrar_chromedriver_orfaos` (padrão) encerra **somente** o
    ``chromedriver``, exclusivo da automação — **não** fecha as janelas de
    navegação pessoal do usuário;
  - :func:`encerrar_chrome` é **destrutiva** e fecha TODO o Chrome (inclusive
    as janelas pessoais); por isso é opt-in explícito.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from collections.abc import Sequence

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions

from .exceptions import NavegadorError

_log = logging.getLogger(__name__)

# Ajustes exigidos por ambientes gerenciados/gov para o Chrome subir.
_ARGS_GOV = ("--no-sandbox", "--disable-dev-shm-usage")


def _matar_processos(nomes: Sequence[str]) -> None:
    """Encerra à força os processos cujos nomes lógicos são dados.

    Tolerante: se o processo não existe (ou o comando não está disponível na
    plataforma), apenas segue — nunca levanta.
    """
    windows = sys.platform.startswith("win")
    for nome in nomes:
        cmd = (
            ["taskkill", "/F", "/IM", f"{nome}.exe"]
            if windows
            else ["pkill", "-x", nome]
        )
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            _log.debug("Comando '%s' indisponível nesta plataforma", cmd[0])


def encerrar_chromedriver_orfaos() -> None:
    """Encerra processos ``chromedriver`` presos de execuções anteriores.

    **Seguro:** o ``chromedriver`` é exclusivo da automação Selenium — encerrá-lo
    **não** fecha as janelas de navegação pessoal do usuário. Resolve a maioria
    dos erros *"Chrome instance exited"* / navegador que não abre em máquinas
    gerenciadas (gov).
    """
    _log.info("Encerrando processos chromedriver órfãos")
    _matar_processos(("chromedriver",))


def encerrar_chrome() -> None:
    """⚠️ **DESTRUTIVO:** encerra TODO o Chrome, inclusive as janelas pessoais.

    Use só como último recurso, quando o navegador insiste em não abrir mesmo
    após :func:`encerrar_chromedriver_orfaos` (ex.: trava no diretório de perfil).
    Fecha **todas** as janelas de Chrome do usuário — pode causar perda de
    trabalho não salvo.
    """
    _log.warning(
        "Encerrando TODOS os processos do Chrome (inclui as janelas pessoais)"
    )
    _matar_processos(("chromedriver", "chrome"))


def criar_driver_chrome(
    *,
    headless: bool = False,
    limpar_chromedriver: bool = True,
    encerrar_todo_chrome: bool = False,
    tentativas: int = 3,
    intervalo: float = 1.0,
    args_extra: Sequence[str] | None = None,
    options: ChromeOptions | None = None,
) -> webdriver.Chrome:
    """Abre o Chrome com os ajustes de ambiente gov e devolve o driver.

    O Selenium Manager baixa/gerencia o ``chromedriver`` automaticamente.

    Em máquinas gerenciadas (gov), a **primeira** abertura às vezes falha com
    *"Chrome instance exited"* — uma falha transitória (antivírus/EDR escaneando
    o binário no primeiro launch, primeira execução do Chrome). Por isso esta
    função **tenta de novo** algumas vezes, encerrando ``chromedriver`` presos
    antes de cada tentativa (a tentativa que falhou pode deixar um órfão).

    Args:
        headless: se ``True``, roda sem janela visível (``--headless=new``).
        limpar_chromedriver: encerra ``chromedriver`` órfãos antes de cada
            tentativa (seguro; ver :func:`encerrar_chromedriver_orfaos`). Padrão
            ``True``.
        encerrar_todo_chrome: ⚠️ destrutivo — encerra TODO o Chrome antes de cada
            tentativa (ver :func:`encerrar_chrome`). Quando ``True``, dispensa
            ``limpar_chromedriver`` (já é um superconjunto). Padrão ``False``.
        tentativas: número máximo de tentativas de abrir o Chrome. Padrão ``3``.
        intervalo: espera (s) entre tentativas. Padrão ``1.0``.
        args_extra: argumentos adicionais para o Chrome (ex.: um
            ``--user-data-dir`` dedicado).
        options: um ``ChromeOptions`` próprio a reaproveitar; os ajustes gov e
            os ``args_extra`` são acrescentados a ele.

    Returns:
        O ``webdriver.Chrome`` aberto. Lembre de chamar ``driver.quit()`` ao fim.

    Raises:
        NavegadorError: se o Chrome não subir após ``tentativas`` tentativas.
    """
    options = options if options is not None else ChromeOptions()
    for arg in _ARGS_GOV:
        options.add_argument(arg)
    if headless:
        options.add_argument("--headless=new")
    for arg in args_extra or ():
        options.add_argument(arg)

    ultimo_erro: WebDriverException | None = None
    for tentativa in range(1, tentativas + 1):
        if encerrar_todo_chrome:
            encerrar_chrome()
        elif limpar_chromedriver:
            encerrar_chromedriver_orfaos()
        try:
            _log.info(
                "Abrindo o Chrome (tentativa %d/%d)", tentativa, tentativas
            )
            return webdriver.Chrome(options=options)
        except WebDriverException as exc:
            ultimo_erro = exc
            _log.warning(
                "Chrome não subiu (tentativa %d/%d): %s",
                tentativa,
                tentativas,
                str(exc).splitlines()[0],
            )
            if tentativa < tentativas:
                time.sleep(intervalo)

    raise NavegadorError(
        f"não foi possível abrir o Chrome após {tentativas} tentativa(s) — "
        "veja o log do chromedriver para a causa"
    ) from ultimo_erro
