"""Troca de habilitação (ÓRGÃO/UPAG) no SIAPE via comando ``TROCAHAB``.

Entra na tela de troca de habilitação, procura a habilitação desejada
percorrendo as páginas e a seleciona. Mantém o histórico da última habilitação
para evitar trocas redundantes.

Suporta os dois modelos de acesso do SIAPE — qual deles aparece na tela
depende do **perfil de acesso** de cada pessoa:

- **por UNIDADE** (clássico): habilitação ÓRGÃO + UPAG, linha com a coluna
  UNIDADE preenchida;
- **por ÓRGÃO** (categoria OPERAC): a coluna UNIDADE vem vazia e o nível de
  acesso é ``ORGAO`` — nesse perfil não há UPAG a informar.

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
    """Troca a habilitação ativa no SIAPE (por ÓRGÃO+UPAG ou a nível de ÓRGÃO).

    Args:
        controle: o :class:`ControleTerminal3270` conectado ao terminal.
        orgao: código do órgão. Único argumento obrigatório.
        upag: código da UPAG (opcional). Quando informada, a busca tenta
            primeiro a habilitação clássica ÓRGÃO+UPAG e, se não existir mais
            (acesso migrado), cai automaticamente para a habilitação a nível
            de ÓRGÃO. Quando omitida (ou vazia/só espaços), busca direto a
            habilitação a nível de ÓRGÃO.
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

    def __init__(
        self,
        controle: ControleTerminal3270,
        orgao: str,
        upag: str | None = None,
    ):
        self.controle = controle
        self.orgao = str(orgao).strip()
        self.upag = str(upag).strip() if upag is not None else ""
        if not self.orgao:
            raise ValueError("orgao é obrigatório")
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
        self._buscar_e_selecionar(self._candidatos_busca())
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

    def _candidatos_busca(self) -> list[tuple[re.Pattern[str], str]]:
        """Monta os candidatos de busca, em ordem de preferência.

        Quando ``upag`` foi informada, o candidato exato ÓRGÃO+UPAG vem
        primeiro (comportamento clássico, acesso a nível de UNIDADE); o
        candidato de nível ÓRGÃO (coluna UNIDADE vazia, nível de acesso
        ``ORGAO``) vem sempre por último, como fallback para os perfis que
        têm a habilitação nesse nível. Sem ``upag``, só o candidato de nível
        ÓRGÃO é tentado.

        A ordem importa: se o fallback fosse tentado primeiro, quem tem as
        DUAS linhas (unidade e órgão) passaria a cair sempre na mais ampla —
        mudança de comportamento silenciosa para o acesso por unidade.
        """
        candidatos: list[tuple[re.Pattern[str], str]] = []
        if self.upag:
            upag_formatada = self.upag.zfill(self.UPAG_DIGITOS)
            # Tolera espaçamento variável entre ÓRGÃO e UPAG e zeros à
            # esquerda na UPAG (a tela pode formatar diferente do
            # ``orgao + upag.zfill(9)``).
            candidatos.append(
                (
                    re.compile(re.escape(self.orgao) + r"\s+0*" + re.escape(self.upag)),
                    f"ÓRGÃO+UPAG ({self.orgao} {upag_formatada})",
                )
            )
        # O 'ORGAO' logo após os brancos (coluna UNIDADE vazia) é o
        # discriminador: não casa com linhas de unidade nem com órgãos
        # vizinhos (ex.: 40804/40806 não casam com o padrão de 40805).
        candidatos.append(
            (
                re.compile(re.escape(self.orgao) + r"\s+ORGAO\b"),
                f"nível ÓRGÃO ({self.orgao})",
            )
        )
        return candidatos

    @staticmethod
    def _descricao_candidatos(candidatos: list[tuple[re.Pattern[str], str]]) -> str:
        return " | ".join(descricao for _padrao, descricao in candidatos)

    # ----- busca paginada -----

    def _buscar_e_selecionar(
        self, candidatos: list[tuple[re.Pattern[str], str]]
    ) -> None:
        for _pagina in range(self.MAX_PAGINAS):
            tela = self._normalizar(self.controle.copiar_tela())
            for padrao, descricao in candidatos:
                linha = self._linha_do_texto(tela, padrao)
                if linha is not None:
                    _log.info(
                        "Habilitação encontrada na linha %d (%s)", linha, descricao
                    )
                    self._selecionar_na_linha(linha)
                    return
            if self._tem_proxima_pagina(tela):
                self.controle.enviar_teclas("{F8}")
                time.sleep(self.DELAY_PADRAO)
            else:
                raise HabilitacaoNaoEncontrada(
                    "habilitação não encontrada nas páginas do SIAPE "
                    f"(candidatos tentados: {self._descricao_candidatos(candidatos)})"
                )
        raise HabilitacaoNaoEncontrada(
            f"habilitação não encontrada após {self.MAX_PAGINAS} páginas "
            f"(candidatos tentados: {self._descricao_candidatos(candidatos)})"
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

    def _linha_do_texto(self, tela: str, padrao: re.Pattern[str]) -> int | None:
        """Linha (1-indexada) do candidato ``padrao`` **na área da lista**.

        Considera só linhas ``>= LINHA_INICIO_LISTA``: ignora um eventual eco do
        ÓRGÃO/UPAG no cabeçalho ou na linha de comando (que daria ``num_tabs``
        negativo) e exige que o casamento esteja de fato na lista selecionável.
        ``tela`` já deve estar normalizada (:meth:`_normalizar`) — a tela real
        do 3270 às vezes usa NBSP em vez de espaço comum.
        """
        for match in padrao.finditer(tela):
            linha = match.start() // self.CARACTERES_POR_LINHA + 1
            if linha >= self.LINHA_INICIO_LISTA:
                return linha
        return None

    def _tem_proxima_pagina(self, tela: str) -> bool:
        return self.TEXTO_CONTINUA in tela
