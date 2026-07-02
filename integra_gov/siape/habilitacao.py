"""Troca de habilitação (ÓRGÃO/UPAG) no SIAPE via comando ``TROCAHAB``.

Entra na tela de troca de habilitação, procura a habilitação desejada
(ÓRGÃO + UPAG) percorrendo as páginas e a seleciona. Mantém o histórico da última
habilitação para evitar trocas redundantes.

Requer um terminal já conectado/autenticado — use :class:`ConexaoTerminal3270`
para o acesso, e compartilhe o mesmo :class:`ControleTerminal3270`.
"""

from __future__ import annotations

import logging
import re
import time

from ._menu import garantir_menu_principal
from .controle import ControleTerminal3270
from .exceptions import HabilitacaoNaoEncontrada, TerminalError

_log = logging.getLogger(__name__)


class TrocaHabilitacao:
    """Troca a habilitação (ÓRGÃO/UPAG) ativa no SIAPE.

    Args:
        controle: o :class:`ControleTerminal3270` conectado ao terminal.
        orgao: código do órgão.
        upag: código da UPAG.
    """

    COMANDO_TROCAHAB = "TROCAHAB"
    TEXTO_CONTINUA = "CONTINUA ==>"

    LINHA_INICIO_LISTA = 12

    TECLA_SELECIONAR = "X"
    TECLA_CONFIRMAR = "S"

    MAX_PAGINAS = 20
    UPAG_DIGITOS = 9  # padrão SIAPE: UPAG formatada com zeros à esquerda

    # Geometria da tela (mesma da camada base; fixada aqui para não depender de
    # um ``controle`` mockado nos testes).
    CARACTERES_POR_LINHA = ControleTerminal3270.CARACTERES_POR_LINHA

    DELAY_PADRAO = 0.5
    DELAY_CURTO = 0.1

    def __init__(self, controle: ControleTerminal3270, orgao: str, upag: str):
        self.controle = controle
        self.orgao = str(orgao).strip()
        self.upag = str(upag).strip()
        if not self.orgao or not self.upag:
            raise ValueError("orgao e upag são obrigatórios")
        self._ultimo_orgao: str | None = None
        self._ultima_upag: str | None = None

    def trocar(self) -> None:
        """Executa a troca de habilitação completa.

        Idempotente quanto ao destino: se a última troca já foi para este
        ÓRGÃO/UPAG, não faz nada.

        Raises:
            HabilitacaoNaoEncontrada: se a habilitação não estiver nas páginas.
            TerminalError / TerminalNaoEncontrado / PywinautoIndisponivel: da
                camada de terminal.
        """
        if not self._precisa_trocar():
            _log.info(
                "Habilitação já está em ÓRGÃO=%s, UPAG=%s", self.orgao, self.upag
            )
            return

        garantir_menu_principal(self.controle)
        self._enviar_comando_trocahab()
        self._buscar_e_selecionar(self._texto_busca())
        self._ultimo_orgao, self._ultima_upag = self.orgao, self.upag
        _log.info("Habilitação trocada: ÓRGÃO=%s, UPAG=%s", self.orgao, self.upag)

    # ----- histórico -----

    def _precisa_trocar(self) -> bool:
        if self._ultimo_orgao is None or self._ultima_upag is None:
            return True
        return not (self.orgao == self._ultimo_orgao and self.upag == self._ultima_upag)

    def habilitacao_atual(self) -> tuple[str | None, str | None]:
        """Última habilitação aplicada por esta instância (``(orgao, upag)``)."""
        return self._ultimo_orgao, self._ultima_upag

    def resetar_historico(self) -> None:
        """Força a próxima :meth:`trocar` a executar (esquece o histórico)."""
        self._ultimo_orgao = self._ultima_upag = None

    # ----- comando -----

    def _enviar_comando_trocahab(self) -> None:
        self.controle.enviar_teclas(self.COMANDO_TROCAHAB)
        self.controle.enviar_teclas("{ENTER}")
        time.sleep(self.DELAY_PADRAO)

    def _texto_busca(self) -> str:
        return f"{self.orgao} {self.upag.zfill(self.UPAG_DIGITOS)}"

    # ----- busca paginada -----

    def _buscar_e_selecionar(self, texto_busca: str) -> None:
        for _pagina in range(self.MAX_PAGINAS):
            tela = self._normalizar(self.controle.copiar_tela())
            linha = self._linha_do_texto(tela)
            if linha is not None:
                self._selecionar_na_linha(linha)
                return
            if self._tem_proxima_pagina(tela):
                self.controle.enviar_teclas("{F8}")
                time.sleep(self.DELAY_PADRAO)
            else:
                raise HabilitacaoNaoEncontrada(
                    f"habilitação {texto_busca!r} não encontrada nas páginas "
                    "do SIAPE"
                )
        raise HabilitacaoNaoEncontrada(
            f"habilitação {texto_busca!r} não encontrada após "
            f"{self.MAX_PAGINAS} páginas"
        )

    def _selecionar_na_linha(self, linha: int) -> None:
        num_tabs = linha - self.LINHA_INICIO_LISTA
        if num_tabs < 0:
            raise TerminalError(
                f"linha {linha} inválida (antes do início da lista, "
                f"linha {self.LINHA_INICIO_LISTA})"
            )
        for _ in range(num_tabs):
            self.controle.enviar_teclas("{TAB}")
            time.sleep(self.DELAY_CURTO)
        self.controle.enviar_teclas(self.TECLA_SELECIONAR)  # marca com X
        self.controle.enviar_teclas("{ENTER}")
        self.controle.enviar_teclas(self.TECLA_CONFIRMAR)  # confirma com S
        self.controle.enviar_teclas("{ENTER}")
        self.controle.enviar_teclas("{F2}")  # volta ao menu
        _log.info("Habilitação selecionada na linha %d", linha)

    # ----- utilitários de tela -----

    @staticmethod
    def _normalizar(tela: str) -> str:
        return tela.replace("\xa0", " ")

    def _padrao_busca(self) -> re.Pattern[str]:
        # Tolera espaçamento variável entre ÓRGÃO e UPAG e zeros à esquerda na
        # UPAG (a tela pode formatar diferente do ``orgao + upag.zfill(9)``).
        return re.compile(re.escape(self.orgao) + r"\s+0*" + re.escape(self.upag))

    def _linha_do_texto(self, tela: str) -> int | None:
        """Linha (1-indexada) da habilitação **na área da lista**.

        Considera só linhas ``>= LINHA_INICIO_LISTA``: ignora um eventual eco do
        ÓRGÃO/UPAG no cabeçalho ou na linha de comando (que daria ``num_tabs``
        negativo) e exige que o casamento esteja de fato na lista selecionável.
        """
        for match in self._padrao_busca().finditer(tela):
            linha = match.start() // self.CARACTERES_POR_LINHA + 1
            if linha >= self.LINHA_INICIO_LISTA:
                return linha
        return None

    def _tem_proxima_pagina(self, tela: str) -> bool:
        return self.TEXTO_CONTINUA in tela
