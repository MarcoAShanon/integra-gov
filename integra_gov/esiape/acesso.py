"""Acesso ao e-SIAPE web via SERPRO ID — VOCÊ autentica (app no celular).

A lib navega, aciona o certificado e ESPERA a sua confirmação no app; nunca
digita PIN/senha e não registra credenciais em log.
"""

from __future__ import annotations

import logging
import time

from selenium.webdriver.common.by import By

from .exceptions import AutenticacaoNaoConfirmada, MenuInacessivel
from .navegacao import (
    SELETOR_BTN_AVANCAR,
    SELETOR_BTN_PULAR,
    SELETOR_LUPA,
    garantir_menu,
    limpar_flag_relogin,
    procurar_em_frames,
)

_log = logging.getLogger(__name__)


class AcessoEsiape:
    """Realiza o acesso ao e-SIAPE web (SERPRO ID + travessia de entrada).

    Args:
        driver: WebDriver (ex.: ``integra_gov.sei.criar_driver_chrome()``).
        timeout_confirmacao: segundos de espera pela confirmação no app.
    """

    URL_ESIAPE = ("https://esiape.sigepe.gov.br/modsiape/servlet/StartCISPage"
                  "?PAGEURL=/cisnatural/NatLogon.html"
                  "&xciParameters.natsession=modsiape")
    XPATH_BOTAO_CERTIFICADO = (
        "//*[self::button or self::a]"
        "[contains(translate(., 'certifcado', 'CERTIFCADO'), 'CERTIFICADO')]"
    )
    INTERVALO_POLL = 2.0

    def __init__(self, driver, timeout_confirmacao: float = 180):
        self.driver = driver
        self.timeout_confirmacao = timeout_confirmacao

    def executar(self) -> None:
        """Login completo: URL → certificado → confirmação no app → menu.

        Raises:
            AutenticacaoNaoConfirmada: confirmação não chegou no timeout.
            MenuInacessivel: autenticou mas o menu não ficou acessível.
        """
        _log.info("Acessando o e-SIAPE: %s", self.URL_ESIAPE)
        self.driver.get(self.URL_ESIAPE)
        time.sleep(2)
        self._acionar_certificado()
        self._esperar_confirmacao_no_app()
        if not garantir_menu(self.driver):
            raise MenuInacessivel(
                "autenticação confirmada, mas o menu de transações não ficou "
                "acessível (veja o log da travessia); se a sessão renasceu, "
                "o PIN do certificado pode estar sendo pedido numa janela "
                "do Windows"
            )
        # relogin de ENTRADA não é pendência: a sessão está no estado
        # padrão esperado e a primeira troca de habilitação é explícita.
        limpar_flag_relogin(self.driver)
        _log.info("Acesso ao e-SIAPE concluído — menu acessível")

    # ----- passos internos -----

    def _acionar_certificado(self) -> None:
        """Clica o botão de certificado se a página de login o mostrar."""
        try:
            botoes = self.driver.find_elements(By.XPATH,
                                               self.XPATH_BOTAO_CERTIFICADO)
            if botoes:
                botoes[0].click()
                _log.info("Botão de certificado acionado — CONFIRME no app "
                          "SERPRO ID")
        except Exception as exc:
            _log.warning("Botão de certificado não acionado (%s) — a página "
                         "pode já estar autenticada", exc)

    def _esperar_confirmacao_no_app(self) -> None:
        """Poll até uma tela pós-login aparecer (AVANÇAR/Pular/lupa)."""
        limite = time.monotonic() + self.timeout_confirmacao
        while time.monotonic() < limite:
            for seletor in (SELETOR_BTN_AVANCAR, SELETOR_BTN_PULAR,
                            SELETOR_LUPA):
                if procurar_em_frames(self.driver, seletor) is not None:
                    _log.info("Autenticação detectada")
                    return
            time.sleep(self.INTERVALO_POLL)
        raise AutenticacaoNaoConfirmada(
            f"a confirmação no app SERPRO ID não chegou em "
            f"{self.timeout_confirmacao:.0f}s"
        )
