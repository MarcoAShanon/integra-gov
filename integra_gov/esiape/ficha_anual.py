"""Ficha financeira anual do servidor/aposentado/instituidor (FPEMFICHAF).

O e-SIAPE limita cada consulta a 15 anos: a faixa é dividida em BLOCOS, cada
bloco vira um PDF (renomeado antes do seguinte — a tela salva sempre com o
mesmo nome) e tudo é mesclado em ordem cronológica ao final.

Semântica de honestidade (validada em produção): bloco com ERRO aborta a
pessoa inteira (:class:`ExtracaoFichaEsiapeInterrompida`); bloco SEM DADOS
não é erro — a mensagem do CIS é a evidência, nunca um timeout.
"""

from __future__ import annotations

import logging
# time: não usado nesta task (esqueleto) — mantido pois os testes
# monkeypatcham fmod.time.sleep; Tasks 3-4 passam a usá-lo diretamente.
import time  # noqa: F401
from dataclasses import dataclass, field
from pathlib import Path

_log = logging.getLogger(__name__)


@dataclass
class ResultadoFichaEsiape:
    """Resultado da extração da ficha anual em blocos."""

    pdf: Path | None = None
    pdfs_blocos: list[Path] = field(default_factory=list)
    blocos_com_dados: list[tuple[int, int]] = field(default_factory=list)
    blocos_sem_dados: list[tuple[int, int]] = field(default_factory=list)
    duracao_s: float = 0.0


class FichaAnualServidor:
    """Extrai a ficha anual (FPEMFICHAF) da matrícula na habilitação ATIVA.

    Args:
        driver: WebDriver com a sessão do e-SIAPE autenticada.
        pasta_saida: destino dos PDFs (bloco e mesclado).
        pasta_download: pasta de download do Chrome (default: subpasta
            ``_download_esiape`` de ``pasta_saida``). DEVE coincidir com a
            configuração do driver — ver docs.
    """

    TRANSACAO = "FPEMFICHAF"
    MAX_ANOS_POR_CONSULTA = 15

    SEL_CONSULTA_ONLINE = '[data-testtoolid="onClickBtnConsultaOnline"]'
    SEL_MATRICULA = '[data-testtoolid="w_matr_infor_alfa"]'
    SEL_ANO_INICIO = '[data-testtoolid="w_ano_inicio"]'
    SEL_ANO_FIM = '[data-testtoolid="w_ano_fim"]'
    SEL_GERAR_RELATORIO = '[data-testtoolid="onClickBtnGerarTodosSemestres"]'
    SEL_IMPRIMIR = '[data-testtoolid="w_report.onGeneratePrintVersion"]'
    SEL_SAIR = '[data-testtoolid="onClickBtnSair"]'
    MSG_SEM_DADOS = "NAO HOUVE DADOS PARA CRITERIO SOLICITADO"

    TIMEOUT_TELA = 30
    TIMEOUT_CONSULTA = 30
    TIMEOUT_POPUP = 20
    TIMEOUT_DOWNLOAD = 60
    DELAY_CURTO = 0.3
    DELAY_PADRAO = 1.0

    def __init__(self, driver, pasta_saida: Path,
                 pasta_download: Path | None = None):
        self.driver = driver
        self.pasta_saida = Path(pasta_saida)
        self.pasta_saida.mkdir(parents=True, exist_ok=True)
        self.pasta_download = (Path(pasta_download) if pasta_download
                               else self.pasta_saida / "_download_esiape")
        self.pasta_download.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _dividir_blocos(cls, ano_ini: int, ano_fim: int
                        ) -> list[tuple[int, int]]:
        """Divide ``[ano_ini, ano_fim]`` em blocos de até 15 anos."""
        blocos: list[tuple[int, int]] = []
        ini = int(ano_ini)
        while ini <= int(ano_fim):
            ate = min(ini + cls.MAX_ANOS_POR_CONSULTA - 1, int(ano_fim))
            blocos.append((ini, ate))
            ini = ate + 1
        return blocos

    def extrair(self, matricula: str, ano_inicial: int, ano_final: int
                ) -> ResultadoFichaEsiape:
        """Extrai a ficha da faixa completa (blocos + mesclagem).

        Raises:
            ValueError: parâmetros inválidos.
            FichaEsiapeIndisponivel: matrícula não encontrada.
            ExtracaoFichaEsiapeInterrompida: bloco com erro (carrega
                ``blocos_processados`` e ``causa``).
        """
        matricula = str(matricula).strip()
        if not matricula:
            raise ValueError("matricula é obrigatória")
        if int(ano_inicial) > int(ano_final):
            raise ValueError(
                f"faixa invertida: {ano_inicial} > {ano_final}")
        raise NotImplementedError  # Tasks 3-4
