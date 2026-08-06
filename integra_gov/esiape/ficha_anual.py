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
import time
from dataclasses import dataclass, field
from pathlib import Path

from selenium.webdriver.common.by import By

from .exceptions import FichaEsiapeIndisponivel, TransacaoNaoAbriu
from .navegacao import (
    esperar_seletor,
    frames_visiveis,
    ir_para_frame,
    navegar_para_transacao,
    procurar_em_frames,
)

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

    # ----- consulta de um bloco -----

    def _consultar_bloco(self, matricula: str, ano_de: int, ano_ate: int
                         ) -> bool:
        """Abre a tela, consulta o período e responde se HÁ dados.

        ``False`` SÓ quando o CIS respondeu com a mensagem de "sem dados" —
        nunca por timeout (timeout sem resposta clara vira exceção).
        """
        if not navegar_para_transacao(self.driver, self.TRANSACAO,
                                      self.SEL_CONSULTA_ONLINE,
                                      timeout=self.TIMEOUT_TELA):
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SEL_CONSULTA_ONLINE)
        self.driver.find_element(By.CSS_SELECTOR,
                                 self.SEL_CONSULTA_ONLINE).click()
        time.sleep(self.DELAY_PADRAO)

        if esperar_seletor(self.driver, self.SEL_MATRICULA,
                           timeout=self.TIMEOUT_TELA) is None:
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SEL_MATRICULA)
        campo = self.driver.find_element(By.CSS_SELECTOR, self.SEL_MATRICULA)
        campo.clear()
        campo.send_keys(matricula)
        time.sleep(self.DELAY_CURTO)
        for seletor, valor in ((self.SEL_ANO_INICIO, str(ano_de)),
                               (self.SEL_ANO_FIM, str(ano_ate))):
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, seletor)
                el.clear()
                el.send_keys(valor)
                time.sleep(self.DELAY_CURTO)
            except Exception as exc:
                raise TransacaoNaoAbriu(self.TRANSACAO, seletor) from exc

        # dispara a consulta (ENTER no campo de ano final)
        self.driver.find_element(By.CSS_SELECTOR, self.SEL_ANO_FIM
                                 ).send_keys("\n")

        # decide por EVIDÊNCIA: relatório disponível OU mensagem de sem-dados
        limite = time.monotonic() + self.TIMEOUT_CONSULTA
        while time.monotonic() < limite:
            if procurar_em_frames(self.driver,
                                  self.SEL_GERAR_RELATORIO) is not None:
                _log.info("Bloco %d-%d: consulta com dados", ano_de, ano_ate)
                return True
            texto = self._texto_da_tela()
            if self.MSG_SEM_DADOS in texto.upper():
                _log.info("Bloco %d-%d: sem dados no período", ano_de, ano_ate)
                self._sair_da_tela()
                return False
            time.sleep(self.DELAY_CURTO)
        raise FichaEsiapeIndisponivel(
            f"matrícula {matricula}: a consulta {ano_de}-{ano_ate} não "
            f"respondeu nem com relatório nem com '{self.MSG_SEM_DADOS}' em "
            f"{self.TIMEOUT_CONSULTA}s — matrícula fora da habilitação ativa?"
        )

    def _texto_da_tela(self) -> str:
        """Texto concatenado de TODOS os frames visíveis (best-effort)."""
        textos: list[str] = []
        try:
            self.driver.switch_to.default_content()
        except Exception:
            return ""
        for caminho in frames_visiveis(self.driver):
            if not ir_para_frame(self.driver, caminho):
                continue
            try:
                textos.append(self.driver.execute_script(
                    "return document.body ? document.body.innerText : ''"
                ) or "")
            except Exception:
                continue
        return "\n".join(textos)

    def _sair_da_tela(self) -> None:
        """Clica Sair para voltar ao menu (best-effort)."""
        try:
            if procurar_em_frames(self.driver, self.SEL_SAIR) is not None:
                self.driver.find_element(By.CSS_SELECTOR, self.SEL_SAIR).click()
                time.sleep(self.DELAY_PADRAO)
        except Exception as exc:
            _log.warning("Sair falhou (ignorado): %s", exc)
