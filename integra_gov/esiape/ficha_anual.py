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

from .exceptions import (
    ExtracaoFichaEsiapeInterrompida,
    FichaEsiapeIndisponivel,
    TransacaoNaoAbriu,
)
from .navegacao import (
    esperar_seletor,
    fechar_janelas_extras,
    frames_visiveis,
    ir_para_frame,
    limpar_overlay,
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

        inicio = time.monotonic()
        resultado = ResultadoFichaEsiape()
        try:
            for ano_de, ano_ate in self._dividir_blocos(ano_inicial, ano_final):
                if not self._consultar_bloco(matricula, ano_de, ano_ate):
                    resultado.blocos_sem_dados.append((ano_de, ano_ate))
                    continue
                caminho = self._imprimir_bloco(matricula, ano_de, ano_ate)
                resultado.blocos_com_dados.append((ano_de, ano_ate))
                resultado.pdfs_blocos.append(caminho)
        except Exception as exc:
            blocos = sorted(resultado.blocos_com_dados
                            + resultado.blocos_sem_dados)
            raise ExtracaoFichaEsiapeInterrompida(blocos, exc) from exc

        if resultado.pdfs_blocos:
            destino = (self.pasta_saida
                       / f"ficha_{matricula}_{ano_inicial}_{ano_final}.pdf")
            if len(resultado.pdfs_blocos) == 1:
                import shutil

                shutil.copy2(resultado.pdfs_blocos[0], destino)
            else:
                self._mesclar(resultado.pdfs_blocos, destino)
            resultado.pdf = destino
        resultado.duracao_s = time.monotonic() - inicio
        _log.info("Matrícula %s: %d bloco(s) com dados, %d sem, %.1fs",
                  matricula, len(resultado.blocos_com_dados),
                  len(resultado.blocos_sem_dados), resultado.duracao_s)
        return resultado

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

    # ----- impressão de um bloco (sequência estabilizada em produção) -----

    def _imprimir_bloco(self, matricula: str, ano_de: int, ano_ate: int
                        ) -> Path:
        """Gera o relatório, imprime via popup e devolve o PDF RENOMEADO.

        O popup de impressão é a origem histórica da degradação de sessão:
        fechamos por handle Selenium (confiável) e SÓ então retornamos à
        janela principal com refresh.
        """
        self._limpar_downloads_orfaos()
        fechar_janelas_extras(self.driver)
        limpar_overlay(self.driver)
        handle_principal = self.driver.current_window_handle
        handles_antes = list(self.driver.window_handles)

        if esperar_seletor(self.driver, self.SEL_GERAR_RELATORIO,
                           timeout=self.TIMEOUT_TELA) is None:
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SEL_GERAR_RELATORIO)
        self.driver.find_element(By.CSS_SELECTOR,
                                 self.SEL_GERAR_RELATORIO).click()
        time.sleep(self.DELAY_PADRAO)

        if esperar_seletor(self.driver, self.SEL_IMPRIMIR,
                           timeout=self.TIMEOUT_TELA) is None:
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SEL_IMPRIMIR)
        self.driver.find_element(By.CSS_SELECTOR, self.SEL_IMPRIMIR).click()

        popup = self._aguardar_popup(handles_antes)
        pdf_bruto = self._aguardar_pdf_estavel()
        if popup is not None:
            self._fechar_popup(popup)
        self._retornar_apos_impressao(handle_principal)

        destino = (self.pasta_saida
                   / f"ficha_{matricula}_{ano_de}_{ano_ate}.pdf")
        if destino.exists():
            destino.unlink()
        pdf_bruto.rename(destino)
        _log.info("Bloco %d-%d salvo em %s", ano_de, ano_ate, destino)
        return destino

    def _aguardar_popup(self, handles_antes: list) -> str | None:
        """Handle do popup de impressão (``None`` se não abriu — o download
        pode disparar mesmo assim; quem decide é o PDF no disco)."""
        limite = time.monotonic() + self.TIMEOUT_POPUP
        while time.monotonic() < limite:
            novos = [h for h in self.driver.window_handles
                     if h not in handles_antes]
            if novos:
                return novos[0]
            time.sleep(self.DELAY_CURTO)
        _log.warning("Popup de impressão não detectado em %.0fs",
                     self.TIMEOUT_POPUP)
        return None

    def _aguardar_pdf_estavel(self) -> Path:
        """Espera UM PDF aparecer na pasta de download e ficar estável
        (tamanho constante em 2 leituras). Erro honesto no timeout."""
        limite = time.monotonic() + self.TIMEOUT_DOWNLOAD
        tamanho_anterior: dict[Path, int] = {}
        while time.monotonic() < limite:
            pdfs = sorted(self.pasta_download.glob("*.pdf"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
            if pdfs:
                atual = pdfs[0]
                tamanho = atual.stat().st_size
                if tamanho > 0 and tamanho_anterior.get(atual) == tamanho:
                    return atual
                tamanho_anterior[atual] = tamanho
            time.sleep(self.DELAY_CURTO)
        raise TimeoutError(
            f"o PDF do bloco não apareceu em {self.pasta_download} em "
            f"{self.TIMEOUT_DOWNLOAD}s — a pasta de download do driver "
            f"coincide com pasta_download?")

    def _fechar_popup(self, popup_handle: str) -> None:
        """Fecha o popup por handle Selenium (retry); JS como fallback."""
        for _tentativa in range(2):
            try:
                if popup_handle not in self.driver.window_handles:
                    return
                self.driver.switch_to.window(popup_handle)
                self.driver.close()
                time.sleep(self.DELAY_CURTO)
                if popup_handle not in self.driver.window_handles:
                    return
            except Exception:
                pass
        try:  # fallback JS
            if popup_handle in self.driver.window_handles:
                self.driver.switch_to.window(popup_handle)
                self.driver.execute_script("window.close();")
        except Exception:
            pass
        if popup_handle in self.driver.window_handles:
            _log.warning("Popup de impressão resistiu — janela órfã será "
                         "varrida por fechar_janelas_extras")

    def _retornar_apos_impressao(self, handle_principal: str) -> None:
        """Volta à janela principal, refresh e contexto raiz (a página fica
        em carregamento eterno sem o refresh — comportamento real do CIS)."""
        try:
            if handle_principal in self.driver.window_handles:
                self.driver.switch_to.window(handle_principal)
            elif self.driver.window_handles:
                self.driver.switch_to.window(self.driver.window_handles[0])
            self.driver.refresh()
            self.driver.switch_to.default_content()
            time.sleep(self.DELAY_PADRAO)
        except Exception as exc:
            _log.warning("Retorno pós-impressão com falha (%s)", exc)

    def _limpar_downloads_orfaos(self) -> None:
        """Remove PDFs de tentativas anteriores da pasta de download (o
        'mais recente' confundiria resto antigo com o bloco atual)."""
        for pdf in self.pasta_download.glob("*.pdf"):
            try:
                pdf.unlink()
                _log.debug("Órfão removido: %s", pdf.name)
            except OSError:
                pass

    # ----- mesclagem -----

    @staticmethod
    def _mesclar(pdfs: list[Path], destino: Path) -> Path:
        """Mescla os PDFs em ordem (pypdf) e devolve o destino."""
        from pypdf import PdfWriter

        w = PdfWriter()
        for pdf in pdfs:
            w.append(str(pdf))
        with open(destino, "wb") as f:
            w.write(f)
        w.close()
        return destino
