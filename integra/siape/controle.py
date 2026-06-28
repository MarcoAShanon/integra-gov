"""Controle de baixo nível do Terminal 3270 do SIAPE (emulador IBM HOD).

Esta é a **camada base**: atacha-se a uma janela de emulador de terminal 3270
**já aberta**, lê a tela (via área de transferência) e envia teclas/comandos por
coordenadas. As camadas de acesso (:mod:`integra.siape.conexao`) e de troca de
habilitação (:mod:`integra.siape.habilitacao`) usam esta classe para toda a
interação com o terminal.

Requisitos:
  - Windows com o ``pywinauto`` instalado (``pip install integra-gov[siape]``);
  - um emulador de terminal 3270 (ex.: IBM HOD) **aberto** com a sessão do SIAPE.

A biblioteca **não** abre o emulador nem digita credenciais — apenas automatiza a
interação com o terminal que você já abriu e no qual você se autenticou.
"""

from __future__ import annotations

import logging
import re
import time

from . import _dependencias as _dep
from .exceptions import SessaoSiapePerdida, TerminalError, TerminalNaoEncontrado

_log = logging.getLogger(__name__)


class ControleTerminal3270:
    """Interage com a janela do Terminal 3270 (ler tela, enviar teclas).

    Args:
        titulo: regex do título da janela do emulador (padrão: o do IBM HOD).
            Parametrizável porque o título pode variar conforme o emulador.
    """

    # O HOD nomeia a janela como "Terminal 3270 - A - XXXXXXXX"; o sufixo
    # distingue da janela "Painel de controle" (mesmo SunAwtFrame).
    TITULO_PADRAO = "^Terminal 3270 - .*"

    # Largura da tela 3270 conforme vem pelo clipboard (inclui a quebra).
    CARACTERES_POR_LINHA = 82

    # Delays (s). O SIAPE não lida bem com comandos enviados sem intervalo.
    DELAY_PADRAO = 0.1
    DELAY_FOCO = 0.05
    DELAY_ENTRE_COMANDOS = 0.003
    DELAY_CLIPBOARD = 0.5
    DELAY_RECONEXAO = 0.5
    # Backoff ao ler o clipboard quando ele está ocupado (Histórico da Área de
    # Transferência, OneDrive, antivírus, o próprio pywinauto): 1.0s … 3.0s.
    DELAY_CLIPBOARD_BASE = 1.0
    DELAY_CLIPBOARD_MAX = 3.0

    def __init__(self, titulo: str = TITULO_PADRAO):
        self.titulo = titulo
        self._app = None
        self._dlg = None

    # ----- conexão -----

    def _conectar(self, forcar: bool = False) -> None:
        """Atacha-se à janela do Terminal 3270 (reusa a conexão se ainda válida).

        Raises:
            PywinautoIndisponivel: se o extra ``siape`` não estiver instalado.
            TerminalNaoEncontrado: se não houver janela de Terminal 3270 aberta.
            TerminalError: para outras falhas de conexão.
        """
        _dep.exigir_pywinauto()

        if self._dlg is not None and not forcar:
            try:
                self._dlg.window_text()  # ainda válida?
                return
            except Exception:
                self._app = self._dlg = None

        try:
            self._app = _dep.Application().connect(title_re=self.titulo)
            self._dlg = self._app.window(title_re=self.titulo)
            _log.debug("Conectado ao terminal: %s", self._dlg.window_text())
        except _dep.ElementNotFoundError as exc:
            self._app = self._dlg = None
            raise TerminalNaoEncontrado(
                f"janela do Terminal 3270 (título ~ {self.titulo!r}) não "
                "encontrada — o emulador HOD está aberto?"
            ) from exc
        except Exception as exc:
            self._app = self._dlg = None
            raise TerminalError(
                f"erro ao conectar ao Terminal 3270: {exc}"
            ) from exc

    def conectar(self) -> None:
        """Atacha-se à janela do Terminal 3270 (fail-fast se não estiver aberta).

        As demais operações também se conectam sob demanda; este método é útil
        para validar a presença do terminal antes de começar.

        Raises:
            PywinautoIndisponivel, TerminalNaoEncontrado, TerminalError.
        """
        self._conectar()

    def desconectar(self) -> None:
        """Libera a conexão com o terminal (não fecha o emulador)."""
        self._app = self._dlg = None

    # ----- envio de teclas -----

    def enviar_teclas(self, comando: str, aguardar: float | None = None) -> None:
        """Envia um comando de teclas ao terminal, garantindo o foco.

        Em caso de falha transitória, reconecta e tenta uma vez mais.

        Args:
            comando: sequência ``pywinauto`` (ex.: ``"{F3}"``, ``"^a"``, texto).
            aguardar: espera após o comando (s); usa ``DELAY_PADRAO`` se ``None``.

        Raises:
            TerminalError: se não conseguir enviar após a tentativa de reconexão.
        """
        ultimo_erro: Exception | None = None
        for tentativa in range(2):
            try:
                self._conectar(forcar=(tentativa > 0))
                self._dlg.set_focus()
                time.sleep(self.DELAY_FOCO)
                self._dlg.type_keys(comando)
                time.sleep(self.DELAY_ENTRE_COMANDOS)
                time.sleep(aguardar if aguardar is not None else self.DELAY_PADRAO)
                return
            except TerminalNaoEncontrado:
                raise
            except Exception as exc:  # falha transitória de envio/foco
                ultimo_erro = exc
                self._app = self._dlg = None
                time.sleep(self.DELAY_RECONEXAO)
        # Esgotou o despacho mesmo após reconectar: a sessão SIAPE caiu (a janela
        # estava lá, mas não respondeu) — estado irrecuperável; aborte e reinicie.
        raise SessaoSiapePerdida(
            f"o Terminal 3270 não respondeu ao comando {comando!r} "
            "(sessão SIAPE perdida — reinicie o acesso)"
        ) from ultimo_erro

    # ----- leitura de tela -----

    def copiar_tela(self, max_tentativas: int = 10) -> str:
        """Copia todo o texto da tela do terminal (via ``Ctrl+A``/``Ctrl+C``).

        Faz retry com backoff quando o clipboard está temporariamente ocupado.

        Args:
            max_tentativas: leituras do clipboard antes de desistir.

        Returns:
            O conteúdo textual da tela.

        Raises:
            TerminalError: se a tela não puder ser lida após ``max_tentativas``.
        """
        self._conectar()
        self.enviar_teclas("^a", aguardar=self.DELAY_PADRAO)
        self.enviar_teclas("^c", aguardar=self.DELAY_CLIPBOARD)

        ultimo_erro: Exception | None = None
        for tentativa in range(max_tentativas):
            try:
                tela = _dep.clipboard.GetData()
                if tela:
                    return tela
            except Exception as exc:
                ultimo_erro = exc
            time.sleep(
                min(self.DELAY_CLIPBOARD_MAX, self.DELAY_CLIPBOARD_BASE + 0.2 * tentativa)
            )

        raise TerminalError(
            "não foi possível ler a tela do Terminal 3270 (clipboard ocupado). "
            "Considere desligar o Histórico da Área de Transferência do Windows "
            f"(Configurações → Sistema → Área de Transferência). Último erro: "
            f"{ultimo_erro}"
        )

    def extrair_texto(
        self,
        tela: str,
        linha_inicial: int,
        coluna_inicial: int,
        linha_final: int,
        coluna_final: int,
    ) -> str:
        """Extrai o texto de uma área da tela (coordenadas 1-indexadas).

        Args:
            tela: conteúdo retornado por :meth:`copiar_tela`.

        Raises:
            ValueError: se ``tela`` for vazia.
        """
        if not tela:
            raise ValueError("tela vazia — nada a extrair")
        if (
            linha_inicial < 1
            or coluna_inicial < 1
            or linha_final < linha_inicial
            or coluna_final < coluna_inicial
        ):
            raise ValueError(
                f"coordenadas inválidas (1-indexadas): "
                f"({linha_inicial},{coluna_inicial})..({linha_final},{coluna_final})"
            )
        inicio = (linha_inicial - 1) * self.CARACTERES_POR_LINHA + coluna_inicial - 1
        fim = (linha_final - 1) * self.CARACTERES_POR_LINHA + coluna_final
        return tela[inicio:fim]

    def buscar_texto(self, texto_alvo: str) -> tuple[int, int] | None:
        """Procura ``texto_alvo`` na tela e devolve ``(linha, coluna)``.

        Returns:
            A posição 1-indexada, ou ``None`` se o texto não estiver na tela
            (ausência é dado, não erro).
        """
        tela = self.copiar_tela()
        match = re.search(re.escape(texto_alvo), tela)
        if not match:
            return None
        inicio = match.start()
        linha = inicio // self.CARACTERES_POR_LINHA + 1
        coluna = inicio % self.CARACTERES_POR_LINHA + 1
        return linha, coluna

    def verificar_texto_presente(
        self,
        texto_esperado: str,
        linha: int,
        coluna_inicio: int,
        coluna_fim: int,
    ) -> bool:
        """``True`` se ``texto_esperado`` aparece na área indicada da tela."""
        tela = self.copiar_tela()
        trecho = self.extrair_texto(tela, linha, coluna_inicio, linha, coluna_fim)
        return texto_esperado in trecho

    def obter_linha_completa(self, linha: int) -> str:
        """Devolve o conteúdo completo de uma linha da tela."""
        tela = self.copiar_tela()
        return self.extrair_texto(tela, linha, 1, linha, self.CARACTERES_POR_LINHA)

    # ----- escrita -----

    def mover_cursor(self, linha: int, coluna: int) -> None:
        """Move o cursor para ``(linha, coluna)`` (comando ``"linha,coluna"``)."""
        self.enviar_teclas(f"{linha},{coluna}", aguardar=self.DELAY_PADRAO)

    def escrever_texto(self, texto: str, linha: int, coluna: int) -> None:
        """Posiciona o cursor e escreve ``texto`` na tela."""
        self.mover_cursor(linha, coluna)
        self.enviar_teclas(texto, aguardar=self.DELAY_PADRAO)

    def limpar_area(
        self,
        linhas: list[int],
        coluna_inicio: int,
        coluna_fim: int,
        retornar_cursor: tuple[int, int] = (16, 8),
    ) -> None:
        """Limpa uma área da tela sobrescrevendo com espaços.

        Args:
            linhas: linhas a limpar.
            coluna_inicio: coluna inicial da área.
            coluna_fim: coluna final da área (inclusive).
            retornar_cursor: posição para onde levar o cursor ao fim.
        """
        self._conectar()
        espacos = " " * (coluna_fim - coluna_inicio + 1)
        for linha in linhas:
            self.mover_cursor(linha, coluna_inicio)
            self.enviar_teclas(espacos, aguardar=self.DELAY_PADRAO)
        self.mover_cursor(*retornar_cursor)
