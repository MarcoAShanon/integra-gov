"""Lançamento do módulo HOD do SIAPE (abre o emulador de Terminal 3270).

Depois do acesso web (:class:`~integra_gov.siape.acesso_web.AcessoSiapeWeb`), o
navegador baixa um arquivo ``hodcivws*.jsp`` que, ao ser executado, abre o
emulador (via Java Web Start). Este módulo localiza esse arquivo, o executa,
conduz o **Painel de controle** do HOD e aguarda a janela do **Terminal 3270**.

⚠️ **Windows-only** (usa ``os.startfile`` + ``pywinauto``) e depende do HOD/Java
instalados. A condução do "Painel de controle" (TAB×5 + ENTER) é **frágil e
específica de versão** — best-effort; se mudar, ajuste ``TABS_PAINEL`` ou faça
esse passo manualmente.
"""

from __future__ import annotations

import glob
import logging
import os
import time

from . import _dependencias as _dep
from .exceptions import LancamentoHodError

_log = logging.getLogger(__name__)


class LancadorHod:
    """Executa o módulo HOD baixado e conduz até a janela do Terminal 3270.

    Args:
        download_folder: pasta onde o navegador salvou o ``hodcivws*.jsp``.
        padrao_arquivo: glob do módulo baixado (parametrizável).
        titulo_painel: título exato da janela "Painel de controle" do HOD.
        titulo_terminal: regex do título da janela do Terminal 3270.
    """

    PADRAO_ARQUIVO = "hodcivws*.jsp"
    TITULO_PAINEL = "Painel de controle"
    TITULO_TERMINAL = "^Terminal 3270.*"

    TABS_PAINEL = 5
    TIMEOUT_PAINEL = 100.0
    TIMEOUT_TERMINAL = 100.0
    INTERVALO_CONEXAO = 1.0
    DELAY_FOCO = 3.0
    DELAY_TAB = 0.5

    def __init__(
        self,
        download_folder: str,
        padrao_arquivo: str = PADRAO_ARQUIVO,
        titulo_painel: str = TITULO_PAINEL,
        titulo_terminal: str = TITULO_TERMINAL,
    ):
        self.download_folder = download_folder
        self.padrao_arquivo = padrao_arquivo
        self.titulo_painel = titulo_painel
        self.titulo_terminal = titulo_terminal

    def lancar(self) -> None:
        """Localiza o módulo, executa, conduz o painel e aguarda o terminal.

        Raises:
            LancamentoHodError: se o arquivo não existir, não puder ser executado,
                o painel não puder ser conduzido ou o terminal não aparecer.
            PywinautoIndisponivel: se o extra ``siape`` não estiver instalado.
        """
        arquivo = self.localizar_modulo()
        self.executar_modulo(arquivo)
        self._conduzir_painel()
        self._aguardar_terminal()
        _log.info("Terminal 3270 disponível")

    def localizar_modulo(self) -> str:
        """Devolve o caminho do ``hodcivws*.jsp`` mais recente na pasta."""
        padrao = os.path.join(self.download_folder, self.padrao_arquivo)
        arquivos = glob.glob(padrao)
        if not arquivos:
            raise LancamentoHodError(
                f"nenhum arquivo {self.padrao_arquivo!r} em "
                f"{self.download_folder!r} — o menu SIAPE chegou a disparar o "
                "download?"
            )
        recente = max(arquivos, key=os.path.getctime)
        _log.info("Módulo HOD localizado: %s", os.path.basename(recente))
        return recente

    def executar_modulo(self, caminho: str) -> None:
        """Executa o ``.jsp`` baixado (abre o emulador via Java Web Start)."""
        iniciar = getattr(os, "startfile", None)
        if iniciar is None:
            raise LancamentoHodError(
                "os.startfile indisponível — o lançamento do HOD é Windows-only"
            )
        try:
            iniciar(caminho)
        except OSError as exc:
            raise LancamentoHodError(
                f"falha ao executar {caminho!r}: {exc}"
            ) from exc
        _log.info("Módulo HOD em execução (abrindo o emulador)")

    def _conduzir_painel(self) -> None:
        app = self._conectar(
            self.TIMEOUT_PAINEL, self.titulo_painel, title=self.titulo_painel
        )
        try:
            dlg = app[self.titulo_painel]
            dlg.set_focus()
            time.sleep(self.DELAY_FOCO)
            for _ in range(self.TABS_PAINEL):
                dlg.type_keys("{TAB}")
                time.sleep(self.DELAY_TAB)
            dlg.type_keys("{ENTER}")
        except Exception as exc:  # noqa: BLE001
            raise LancamentoHodError(
                f"falha ao conduzir o Painel de controle: {exc}"
            ) from exc
        _log.info("Painel de controle conduzido (TAB×%d + ENTER)", self.TABS_PAINEL)

    def _aguardar_terminal(self) -> None:
        self._conectar(
            self.TIMEOUT_TERMINAL,
            "Terminal 3270",
            title_re=self.titulo_terminal,
        )
        _log.info("Janela do Terminal 3270 detectada")

    def _conectar(self, timeout: float, descricao: str, **kwargs):
        """Conecta a uma janela com retry até ``timeout`` (s)."""
        _dep.exigir_pywinauto()
        decorrido = 0.0
        while decorrido < timeout:
            try:
                return _dep.Application().connect(**kwargs)
            except _dep.ElementNotFoundError:
                # Janela ainda não disponível — aguarda e tenta de novo.
                # (Erros inesperados propagam, em vez de virarem timeout.)
                time.sleep(self.INTERVALO_CONEXAO)
                decorrido += self.INTERVALO_CONEXAO
        raise LancamentoHodError(
            f"janela {descricao!r} não apareceu em {timeout:.0f}s"
        )
