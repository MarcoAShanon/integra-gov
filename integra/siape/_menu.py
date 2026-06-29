"""Menu principal / linha de comando do SIAPE 3270 (lógica compartilhada).

Tanto a troca de habilitação (:mod:`integra.siape.habilitacao`) quanto o acesso a
transações (:meth:`integra.siape.conexao.ConexaoTerminal3270.acessar_transacao`)
precisam garantir que o terminal está no **menu principal** — com a linha de
comando ``COMANDO.....`` disponível — antes de digitar. Esta lógica vive aqui
para ser reutilizada pelos dois (sem duplicação).
"""

from __future__ import annotations

import logging
import time

from .controle import ControleTerminal3270
from .exceptions import TerminalError

_log = logging.getLogger(__name__)

# Âncora e posição da linha de comando na tela do SIAPE.
TEXTO_LINHA_COMANDO = "COMANDO....."
POSICAO_LINHA_COMANDO = (22, 2, 22, 13)

MAX_TENTATIVAS_MENU = 3
DELAY_MENU = 0.5


def linha_comando_disponivel(controle: ControleTerminal3270) -> bool:
    """``True`` se a linha de comando (``COMANDO.....``) está visível na tela."""
    try:
        tela = controle.copiar_tela()
    except TerminalError:
        return False
    trecho = controle.extrair_texto(tela, *POSICAO_LINHA_COMANDO)
    return bool(trecho) and trecho.strip() == TEXTO_LINHA_COMANDO


def garantir_menu_principal(controle: ControleTerminal3270) -> None:
    """Garante que o terminal está no menu principal (linha de comando pronta).

    Se não estiver, sai da tela atual com ``F3`` → ``F2`` e tenta de novo.

    Raises:
        TerminalError: se o menu não for alcançado após as tentativas.
    """
    for _ in range(MAX_TENTATIVAS_MENU):
        if linha_comando_disponivel(controle):
            return
        controle.enviar_teclas("{F3}")  # sai da tela atual
        time.sleep(DELAY_MENU)
        controle.enviar_teclas("{F2}")  # confirma/entra
        time.sleep(DELAY_MENU)
    raise TerminalError("não foi possível retornar ao menu principal do SIAPE")
