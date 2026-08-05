"""Troca de habilitação (ÓRGÃO) no e-SIAPE web — transação TROCAHAB.

Mecânica validada ao vivo: a grade CIS lista as habilitações; selecionar a
linha abre o modal "Confirma ?" (frame próprio) e SÓ o "Sim" efetiva; a
troca só é declarada quando o CABEÇALHO reflete o novo órgão. Ao confirmar,
limpa a flag de relogin (ver ``navegacao.relogin_pendente``).
"""

from __future__ import annotations

import logging
import re
import time

from selenium.webdriver.common.by import By

from .exceptions import (
    EsiapeError,
    HabilitacaoNaoEncontrada,
    TransacaoNaoAbriu,
)
from .navegacao import (
    esperar_seletor,
    limpar_flag_relogin,
    navegar_para_transacao,
    procurar_em_frames,
)

_log = logging.getLogger(__name__)


class TrocaHabilitacaoEsiape:
    """Troca a habilitação de ÓRGÃO ativa na sessão do e-SIAPE web.

    Args:
        driver: WebDriver com a sessão do e-SIAPE autenticada.
        orgao: código do órgão de destino (ex.: ``"00000"``).
    """

    TRANSACAO = "TROCAHAB"
    SELETOR_GRADE_LINHAS = "table.TEXTGRIDTable tr"
    SELETOR_ORGAO_ATIVO = '[data-testtoolid="w_menu_orgao_usu"]'
    SELETOR_BTN_SIM = '[data-testtoolid="onClickBtnSim"]'
    SELETOR_HOME_MENU = '[data-testtoolid="onMenuClickHome"]'

    TIMEOUT_TELA = 20
    TIMEOUT_MODAL = 8
    TIMEOUT_CONFIRMACAO = 20
    INTERVALO_POLL = 0.25

    _PADRAO_CODIGO = re.compile(r"\b(\d{5})\b")

    def __init__(self, driver, orgao: str):
        self.driver = driver
        self.orgao = str(orgao).strip()
        if not self.orgao:
            raise ValueError("orgao é obrigatório")

    def orgao_atual(self) -> str | None:
        """Órgão ativo lido do cabeçalho (ex.: ``"40805"``); ``None`` se
        ilegível."""
        try:
            if procurar_em_frames(self.driver, self.SELETOR_ORGAO_ATIVO) is None:
                return None
            el = self.driver.find_element(By.CSS_SELECTOR,
                                          self.SELETOR_ORGAO_ATIVO)
            texto = (el.text or el.get_attribute("innerText") or "").strip()
            return texto.split("-")[0].strip() or None
        except Exception as exc:
            _log.warning("Não consegui ler o órgão ativo: %s", exc)
            return None

    def trocar(self) -> None:
        """Efetiva a troca (ou nada, se o cabeçalho já mostra o destino).

        Raises:
            TransacaoNaoAbriu: a tela TROCAHAB não confirmou.
            HabilitacaoNaoEncontrada: o órgão não está na grade.
            EsiapeError: o "Sim" não apareceu ou o cabeçalho não refletiu.
        """
        if self.orgao_atual() == self.orgao:
            _log.info("Habilitação já está no órgão %s", self.orgao)
            limpar_flag_relogin(self.driver)
            return

        if not navegar_para_transacao(self.driver, self.TRANSACAO,
                                      self.SELETOR_GRADE_LINHAS,
                                      timeout=self.TIMEOUT_TELA):
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SELETOR_GRADE_LINHAS)

        self._selecionar_linha_do_orgao()
        self._confirmar_modal()
        self._exigir_cabecalho_no_destino()
        self._voltar_ao_menu()
        limpar_flag_relogin(self.driver)
        _log.info("Habilitação trocada para o órgão %s", self.orgao)

    # ----- passos internos -----

    def _selecionar_linha_do_orgao(self) -> None:
        """Clica a linha da grade cujo código é o órgão (linha 0 = cabeçalho)."""
        linhas = self.driver.find_elements(By.CSS_SELECTOR,
                                           self.SELETOR_GRADE_LINHAS)
        codigos_vistos: list[str] = []
        for linha in linhas[1:]:
            codigos = self._PADRAO_CODIGO.findall(linha.text or "")
            if not codigos:
                continue
            if codigos[0] == self.orgao:
                linha.click()
                _log.info("Linha do órgão %s selecionada", self.orgao)
                return
            codigos_vistos.append(codigos[0])
        raise HabilitacaoNaoEncontrada(self.orgao, codigos_vistos)

    def _confirmar_modal(self) -> None:
        """O modal 'Confirma ?' (frame próprio) é quem efetiva — clica Sim."""
        if esperar_seletor(self.driver, self.SELETOR_BTN_SIM,
                           timeout=self.TIMEOUT_MODAL) is None:
            raise EsiapeError(
                "o modal 'Confirma ?' não apareceu após selecionar a linha — "
                "a troca NÃO foi efetivada"
            )
        self.driver.find_element(By.CSS_SELECTOR, self.SELETOR_BTN_SIM).click()
        time.sleep(0.5)

    def _exigir_cabecalho_no_destino(self) -> None:
        """Sucesso SÓ quando o cabeçalho reflete o novo órgão."""
        limite = time.monotonic() + self.TIMEOUT_CONFIRMACAO
        while time.monotonic() < limite:
            atual = self.orgao_atual()
            if atual == self.orgao:
                return
            time.sleep(self.INTERVALO_POLL)
        raise EsiapeError(
            f"cliquei 'Sim' mas o cabeçalho não refletiu o órgão "
            f"{self.orgao} em {self.TIMEOUT_CONFIRMACAO}s "
            f"(atual: {self.orgao_atual()!r}) — troca NÃO confirmada"
        )

    def _voltar_ao_menu(self) -> None:
        """Deixa a sessão no menu (best-effort; falha não mascara a troca)."""
        try:
            if procurar_em_frames(self.driver, self.SELETOR_HOME_MENU) is None:
                return
            self.driver.find_element(By.CSS_SELECTOR,
                                     self.SELETOR_HOME_MENU).click()
            time.sleep(1.2)
            self.driver.switch_to.default_content()
        except Exception as exc:
            _log.warning("Falha ao voltar ao menu (ignorada): %s", exc)
