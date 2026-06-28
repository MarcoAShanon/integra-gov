"""Acesso/login ao SIAPE pelo Terminal 3270 (sequência inicial + OTP).

Conecta-se ao emulador 3270 já aberto e executa a sequência de entrada do SIAPE:
trata a tela de **código de segurança (OTP)** quando aplicável, a mensagem de
**UORG não cadastrada**, e a sequência inicial de teclas até o menu.

Sobre o código de segurança (OTP): o SIAPE pode exibir a tela ``COD. SEGURANCA``
pedindo o token de 6 dígitos do portal SIAPENet. Por padrão (``codigo_seguranca``
``None``), **você digita o OTP** no terminal — a biblioteca não o manuseia. Se
preferir automatizar, passe o código e ele será digitado **somente** se a tela
correta for detectada (nunca em tela diferente).

Toda a interação com o terminal passa por um :class:`ControleTerminal3270`.
"""

from __future__ import annotations

import logging
import re
import time

from .controle import ControleTerminal3270
from .exceptions import CodigoSegurancaError, TerminalError

_log = logging.getLogger(__name__)


class ConexaoTerminal3270:
    """Executa o acesso/login no SIAPE via Terminal 3270.

    Args:
        controle: um :class:`ControleTerminal3270` a reutilizar (compartilhe-o
            com a troca de habilitação). Se ``None``, um é criado.
        titulo: regex do título da janela do emulador (usado só quando
            ``controle`` é ``None``).
        codigo_seguranca: token OTP de 6 dígitos. ``None`` (padrão) deixa a etapa
            **manual** — você digita o código no terminal.
    """

    MENSAGEM_UORG_NAO_CADASTRADA = "UORG DO CORREIO DO USUARIO NAO CADASTRADA"
    # A tela do terminal vem sem acentos pelo clipboard.
    MENSAGEM_COD_SEGURANCA = "COD. SEGURANCA"
    POSICAO_UORG_CORREIO = (23, 2, 23, 42)

    TIMEOUT_OTP = 10.0
    INTERVALO_OTP = 1.0
    DELAY_ESTABILIZACAO = 3.0
    DELAY_PADRAO = 0.5

    def __init__(
        self,
        controle: ControleTerminal3270 | None = None,
        titulo: str | None = None,
        codigo_seguranca: str | None = None,
    ):
        if codigo_seguranca is not None and not re.fullmatch(
            r"[0-9]{6}", codigo_seguranca
        ):
            # ASCII estrito: ``\d``/``isdigit`` aceitariam dígitos unicode que o
            # terminal 3270 não consegue digitar.
            raise ValueError(
                "codigo_seguranca deve ter exatamente 6 dígitos ASCII (0-9)"
            )
        if controle is None:
            controle = (
                ControleTerminal3270(titulo)
                if titulo is not None
                else ControleTerminal3270()
            )
        self.controle = controle
        self.codigo_seguranca = codigo_seguranca
        self._conectado = False

    def conectar(self) -> None:
        """Executa o acesso completo ao Terminal 3270.

        Fluxo: atacha à janela → insere OTP (se fornecido) → trata UORG →
        sequência inicial (F3 → F2).

        Raises:
            PywinautoIndisponivel, TerminalNaoEncontrado, TerminalError: da
                camada de terminal.
            CodigoSegurancaError: se o OTP foi fornecido mas a tela
                ``COD. SEGURANCA`` não apareceu.
        """
        self.controle.conectar()
        self._inserir_codigo_seguranca()
        self._tratar_mensagem_uorg()
        self._sequencia_inicial()
        self._conectado = True
        _log.info("Terminal 3270 conectado")

    def _inserir_codigo_seguranca(self) -> None:
        if self.codigo_seguranca is None:
            _log.info("Código de segurança não fornecido — etapa OTP é manual")
            return

        decorrido = 0.0
        detectada = False
        while decorrido < self.TIMEOUT_OTP:
            try:
                tela = self.controle.copiar_tela()
            except TerminalError:
                tela = ""
            if tela and self.MENSAGEM_COD_SEGURANCA in tela:
                detectada = True
                break
            time.sleep(self.INTERVALO_OTP)
            decorrido += self.INTERVALO_OTP

        if not detectada:
            raise CodigoSegurancaError(
                f"a tela '{self.MENSAGEM_COD_SEGURANCA}' não apareceu em "
                f"{self.TIMEOUT_OTP:.0f}s — o código não foi digitado (evita "
                "injetar caracteres em tela errada)"
            )

        self.controle.enviar_teclas(self.codigo_seguranca + "{ENTER}")
        _log.info("Código de segurança (OTP) inserido")

    def _tratar_mensagem_uorg(self) -> None:
        try:
            tela = self.controle.copiar_tela()
        except TerminalError:
            _log.debug("tela ilegível ao checar UORG; pulando tratamento")
            return  # sem tela legível agora; não é fatal aqui
        trecho = self.controle.extrair_texto(tela, *self.POSICAO_UORG_CORREIO)
        if trecho and self.MENSAGEM_UORG_NAO_CADASTRADA in trecho:
            _log.warning("UORG não cadastrada detectada — pressionando F3")
            self.controle.enviar_teclas("{F3}")

    def _sequencia_inicial(self) -> None:
        time.sleep(self.DELAY_ESTABILIZACAO)
        self.controle.enviar_teclas("{F3}")  # garante menu limpo
        self.controle.enviar_teclas("{F2}", aguardar=self.DELAY_PADRAO)  # entra

    # ----- utilitários -----

    def esta_conectado(self) -> bool:
        """``True`` se :meth:`conectar` concluiu com sucesso."""
        return self._conectado

    def mantem_hod_ativo(self) -> None:
        """Mantém a sessão HOD viva (envia F2)."""
        self.controle.enviar_teclas("{F2}")

    def enviar_comando(self, comando: str) -> None:
        """Envia um comando de teclas ao terminal (delegado ao controle)."""
        self.controle.enviar_teclas(comando)

    def capturar_tela(self) -> str:
        """Devolve o texto atual da tela do terminal."""
        return self.controle.copiar_tela()

    def desconectar(self) -> None:
        """Libera a conexão com o terminal (não fecha o emulador)."""
        self.controle.desconectar()
        self._conectado = False
