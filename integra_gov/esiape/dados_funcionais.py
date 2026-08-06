"""Dados individuais funcionais (CDCOINDFUN): órgão anterior e ingresso.

A transação resolve deterministicamente a descoberta do órgão anterior de
quem migrou — sem sondar ficha mês a mês. 3 telas: (1) órgão EXPLÍCITO +
matrícula, (2) checkboxes do que consultar, (3) resultado lido por TEXTO.

ARMADILHA REAL: o marcador da tela 3 tem que ser "Cadastramento no SIAPE" —
"INGRESSO NO ÓRGÃO" também é rótulo de checkbox da tela 2 e faz parsear a
tela errada (concluindo "sem órgão anterior" incorretamente).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from selenium.webdriver.common.by import By

from .exceptions import TransacaoNaoAbriu
from .navegacao import (
    esperar_seletor,
    frames_visiveis,
    ir_para_frame,
    navegar_para_transacao,
)

_log = logging.getLogger(__name__)

_MESES = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
          "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}


def _ano_de(texto: str | None) -> int | None:
    """Ano de uma data SIAPE ``DDMMMAAAA`` (ex.: ``01DEZ2014``)."""
    m = re.match(r"(\d{2})([A-Z]{3})(\d{4})", (texto or "").strip().upper())
    if not m or m.group(2) not in _MESES:
        return None
    return int(m.group(3))


@dataclass
class DadosFuncionais:
    """Resultado do CDCOINDFUN (campos ilegíveis ficam ``None``)."""

    orgao_anterior: str | None
    matricula_anterior: str | None
    ano_ingresso: int | None
    cadastramento_siape: str | None


class DadosFuncionaisOrgao:
    """Consulta o CDCOINDFUN para descobrir o órgão anterior do servidor."""

    TRANSACAO = "CDCOINDFUN"
    SEL_MATRICULA = '[data-testtoolid="w_matr_infor_alfa"]'
    SEL_ORGAO = '[data-testtoolid="w_orgao_infor"]'
    SEL_PESQUISAR_1 = '[data-testtoolid="onClickbtnPesquisar"]'
    SEL_PESQUISAR_2 = '[data-testtoolid="onClickbtnConsulta"]'
    CHECKBOXES = ("w_orgao_atual", "w_orgao_origem", "w_ing_orgao")
    MARCADOR_RESULTADO = "CADASTRAMENTO NO SIAPE"
    TIMEOUT = 30

    def __init__(self, driver):
        self.driver = driver

    # ----- parsing -----

    @staticmethod
    def _extrair(texto: str) -> DadosFuncionais:
        """Extrai os campos do texto da tela 3 (ilegível → ``None``)."""
        def busca(padrao: str) -> str | None:
            m = re.search(padrao, texto, re.I)
            return m.group(1).strip() if m else None

        anter = busca(r"[OÓ]RG[AÃ]O/MATR[IÍ]C\s*ANTER\.?:\s*"
                      r"([0-9]+\s*/\s*[0-9]+)")
        orgao_ant = mat_ant = None
        if anter:
            partes = [p.strip() for p in anter.split("/")]
            orgao_ant = partes[0] or None
            mat_ant = partes[1] if len(partes) > 1 else None

        cadastramento = busca(
            r"Cadastramento no SIAPE:\s*([0-9]{2}[A-Z]{3}[0-9]{4})")
        ocorrencia = busca(
            r"DATA OCORRENCIA\s*:\s*([0-9]{2}[A-Z]{3}[0-9]{4})")
        # a data que importa é a do ingresso no órgão atual: ocorrência,
        # caindo no cadastramento quando ela não vier
        ano = _ano_de(ocorrencia) or _ano_de(cadastramento)
        return DadosFuncionais(orgao_ant, mat_ant, ano, cadastramento)

    # ----- navegação -----

    def consultar(self, matricula: str, orgao: str) -> DadosFuncionais:
        """Executa as 3 telas e devolve os dados.

        ``orgao`` é EXPLÍCITO: ao encadear trocas de habilitação não dá para
        confiar no órgão default do formulário.

        Raises:
            TransacaoNaoAbriu: alguma tela não confirmou.
        """
        if not navegar_para_transacao(self.driver, self.TRANSACAO,
                                      self.SEL_MATRICULA,
                                      timeout=self.TIMEOUT):
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SEL_MATRICULA)

        campo_orgao = self.driver.find_element(By.CSS_SELECTOR, self.SEL_ORGAO)
        campo_orgao.clear()
        campo_orgao.send_keys(str(orgao).strip())
        campo = self.driver.find_element(By.CSS_SELECTOR, self.SEL_MATRICULA)
        campo.clear()
        campo.send_keys(str(matricula).strip())
        self.driver.find_element(By.CSS_SELECTOR, self.SEL_PESQUISAR_1).click()

        # tela 2 (em OUTRO frame — os WA* se revezam)
        primeiro = f'[data-testtoolid="{self.CHECKBOXES[0]}"]'
        if esperar_seletor(self.driver, primeiro,
                           timeout=self.TIMEOUT) is None:
            raise TransacaoNaoAbriu(self.TRANSACAO, primeiro)
        for tid in self.CHECKBOXES:
            try:
                cb = self.driver.find_element(
                    By.CSS_SELECTOR, f'[data-testtoolid="{tid}"]')
                cb.click()
            except Exception as exc:
                _log.warning("Checkbox %s não marcado: %s", tid, exc)
        self.driver.find_element(By.CSS_SELECTOR, self.SEL_PESQUISAR_2).click()

        time.sleep(1.0)  # deixa a tela 2 sair de cena (armadilha do rótulo)
        texto = self._esperar_texto(self.MARCADOR_RESULTADO)
        if texto is None:
            raise TransacaoNaoAbriu(self.TRANSACAO,
                                    f"texto '{self.MARCADOR_RESULTADO}'")
        dados = self._extrair(texto)
        if dados.orgao_anterior:
            _log.info("Órgão anterior: %s (matrícula %s), ingresso %s",
                      dados.orgao_anterior, dados.matricula_anterior,
                      dados.ano_ingresso)
        else:
            _log.info("Sem órgão anterior registrado")
        return dados

    def _esperar_texto(self, marcador: str) -> str | None:
        """Espera o marcador textual em algum frame VISÍVEL; texto ou None."""
        limite = time.monotonic() + self.TIMEOUT
        while time.monotonic() < limite:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            for caminho in frames_visiveis(self.driver):
                if not ir_para_frame(self.driver, caminho):
                    continue
                try:
                    texto = self.driver.execute_script(
                        "return document.body ? document.body.innerText : ''"
                    ) or ""
                except Exception:
                    continue
                if marcador.upper() in texto.upper():
                    return texto
            time.sleep(0.5)
        return None
