"""Ficha anual cobrindo TODOS os órgãos por onde o servidor passou.

A ficha anual (FPEMFICHAF) só enxerga o órgão ATIVO — quem migrou perde os
anos anteriores SILENCIOSAMENTE. Este módulo encadeia: CDCOINDFUN (órgão
anterior) → extrai a faixa do órgão → troca a habilitação → repete; mescla
tudo e SEMPRE declara o que não conseguiu cobrir (``lacunas``).

Regra validada em produção: o ano da VIRADA pertence aos DOIS órgãos —
quem entrou no órgão novo em DEZ deixa JAN-NOV no órgão anterior.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from .dados_funcionais import DadosFuncionaisOrgao
from .exceptions import EsiapeError
from .ficha_anual import FichaAnualServidor
from .habilitacao import TrocaHabilitacaoEsiape
from .navegacao import (
    fechar_janelas_extras,
    limpar_overlay,
    relogin_pendente,
)

_log = logging.getLogger(__name__)


@dataclass
class ResultadoMultiOrgao:
    """Resultado do encadeamento — lacunas SEMPRE declaradas."""

    pdf: Path | None = None
    trilha: list[tuple[str, str, int, int]] = field(default_factory=list)
    lacunas: list[str] = field(default_factory=list)
    falhas_tecnicas: list[str] = field(default_factory=list)
    voltou_ao_orgao_inicial: bool = True
    duracao_s: float = 0.0


class FichaMultiOrgao:
    """Encadeia a extração da ficha anual pelos órgãos do servidor.

    Args:
        driver: WebDriver com a sessão do e-SIAPE autenticada.
        orgao_inicial: órgão da habilitação de partida (e de retorno).
        pasta_saida: destino dos PDFs.
        max_saltos: limite de órgãos encadeados (salvaguarda).
    """

    TENTATIVAS_POR_FAIXA = 2

    def __init__(self, driver, orgao_inicial: str, pasta_saida: Path,
                 max_saltos: int = 5):
        self.driver = driver
        self.orgao_inicial = str(orgao_inicial).strip()
        self.pasta_saida = Path(pasta_saida)
        self.max_saltos = max_saltos

    def extrair(self, matricula: str, ano_inicial: int, ano_final: int
                ) -> ResultadoMultiOrgao:
        """Percorre a cadeia de órgãos e devolve o resultado consolidado.

        Nunca levanta por lacuna legítima — entrega o que cobriu com as
        ``lacunas`` declaradas.
        """
        inicio = time.monotonic()
        r = ResultadoMultiOrgao()
        orgao, mat = self.orgao_inicial, str(matricula).strip()
        pendente_ate = int(ano_final)
        visitados: set[tuple[str, str]] = set()
        pdfs: list[tuple[int, Path]] = []

        fechar_janelas_extras(self.driver)
        limpar_overlay(self.driver)
        self._rehabilitar_se_relogin(orgao)

        for _salto in range(self.max_saltos):
            if (orgao, mat) in visitados:
                _log.warning("Ciclo detectado em %s/%s — parando", orgao, mat)
                break
            visitados.add((orgao, mat))

            dados = DadosFuncionaisOrgao(self.driver).consultar(mat, orgao)
            ano_de = (max(int(ano_inicial), dados.ano_ingresso)
                      if dados.ano_ingresso else int(ano_inicial))

            if ano_de <= pendente_ate:
                pdf = self._extrair_faixa(mat, ano_de, pendente_ate, orgao)
                if pdf is not None:
                    pdfs.append((ano_de, pdf))
                    r.trilha.append((orgao, mat, ano_de, pendente_ate))
                else:
                    msg = (f"{ano_de}-{pendente_ate} (órgão {orgao}): "
                           f"extração falhou após "
                           f"{self.TENTATIVAS_POR_FAIXA} tentativas")
                    r.lacunas.append(msg)
                    r.falhas_tecnicas.append(msg)

            if ano_de <= int(ano_inicial):
                _log.info("Cobertura alcançou %d — completo", ano_inicial)
                break
            if not dados.orgao_anterior:
                r.lacunas.append(
                    f"{ano_inicial}-{ano_de - 1}: sem órgão anterior no "
                    f"CDCOINDFUN")
                break
            # o ano da VIRADA pertence aos DOIS órgãos
            pendente_ate = ano_de
            mat = dados.matricula_anterior or mat
            try:
                TrocaHabilitacaoEsiape(self.driver,
                                       orgao=dados.orgao_anterior).trocar()
            except EsiapeError as exc:
                falta = f"{ano_inicial}-{pendente_ate}"
                _log.error("Sem habilitação no órgão %s: %s",
                           dados.orgao_anterior, exc)
                r.lacunas.append(
                    f"{falta}: sem habilitação no órgão "
                    f"{dados.orgao_anterior}")
                r.falhas_tecnicas.append(
                    f"{falta}: sem habilitação no órgão "
                    f"{dados.orgao_anterior}")
                break
            orgao = dados.orgao_anterior
        else:
            r.lacunas.append(f"limite de {self.max_saltos} saltos atingido")

        self._voltar_ao_orgao_inicial(orgao, r)

        if pdfs:
            ordenados = [p for _, p in sorted(pdfs)]
            destino = (self.pasta_saida
                       / f"ficha_{matricula}_{ano_inicial}_{ano_final}"
                         f"_multiorgao.pdf")
            if len(ordenados) == 1:
                import shutil

                shutil.copy2(ordenados[0], destino)
            else:
                FichaAnualServidor._mesclar(ordenados, destino)
            r.pdf = destino
        if r.lacunas:
            _log.warning("Ficha entregue com lacunas: %s",
                         "; ".join(r.lacunas))
        r.duracao_s = time.monotonic() - inicio
        return r

    # ----- passos internos -----

    def _rehabilitar_se_relogin(self, orgao: str) -> None:
        """Relogin atravessado = habilitação no padrão do usuário — re-troca
        ANTES de consultar (senão 'sem dados' FALSO = lacuna silenciosa)."""
        if not relogin_pendente(self.driver):
            return
        _log.warning("Relogin pendente — refazendo a habilitação no órgão %s",
                     orgao)
        TrocaHabilitacaoEsiape(self.driver, orgao=orgao).trocar()

    def _extrair_faixa(self, matricula: str, ano_de: int, ano_ate: int,
                       orgao: str) -> Path | None:
        """Uma faixa com retry (falha intermitente de popup não pode custar
        a pessoa). ``None`` = falhou todas as tentativas."""
        for tentativa in range(1, self.TENTATIVAS_POR_FAIXA + 1):
            fechar_janelas_extras(self.driver)
            limpar_overlay(self.driver)
            self._rehabilitar_se_relogin(orgao)
            try:
                resultado = FichaAnualServidor(
                    self.driver, pasta_saida=self.pasta_saida
                ).extrair(matricula, ano_de, ano_ate)
            except Exception as exc:
                _log.warning("Faixa %d-%d falhou (tentativa %d): %s",
                             ano_de, ano_ate, tentativa, exc)
                time.sleep(2)
                continue
            fechar_janelas_extras(self.driver)
            if resultado.pdf is not None:
                # nome único por órgão (a próxima faixa não pode sobrescrever)
                unico = resultado.pdf.with_name(
                    resultado.pdf.stem + f"_org{orgao}.pdf")
                if unico.exists():
                    unico.unlink()
                resultado.pdf.rename(unico)
                return unico
            return None  # faixa legitimamente sem dados
        return None

    def _voltar_ao_orgao_inicial(self, orgao_atual: str,
                                 r: ResultadoMultiOrgao) -> None:
        """Devolve a habilitação ao órgão inicial (a próxima pessoa do
        chamador falharia no órgão errado). Sinaliza quando não consegue."""
        if orgao_atual == self.orgao_inicial:
            return
        for _tentativa in range(3):
            try:
                TrocaHabilitacaoEsiape(self.driver,
                                       orgao=self.orgao_inicial).trocar()
                return
            except EsiapeError as exc:
                _log.warning("Retorno ao órgão %s falhou: %s",
                             self.orgao_inicial, exc)
                time.sleep(2)
        r.voltou_ao_orgao_inicial = False
        r.falhas_tecnicas.append(
            f"sessão ficou no órgão {orgao_atual} (não voltou para "
            f"{self.orgao_inicial})")
