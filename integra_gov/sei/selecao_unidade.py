"""Seleção/troca da unidade de trabalho no SEI.

Cada operador do SEI tem acesso a um conjunto de unidades conforme suas
permissões; a unidade ativa determina o que ele vê e pode fazer. Este módulo
troca para uma unidade específica — idempotente (se já estiver nela, não faz
nada).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import SeiNavegacaoError, UnidadeNaoEncontrada

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Unidade:
    """Uma unidade à qual o operador tem acesso.

    Dado puro, pensado para uma interface LOCAL apresentar a escolha — a
    biblioteca não inclui interface gráfica.
    """

    sigla: str
    descricao: str
    orgao: str
    id: str


class SelecaoUnidade:
    """Troca a unidade de trabalho do SEI.

    Args:
        driver: WebDriver com o SEI autenticado.
        timeout: espera por elemento, em segundos.
    """

    #: Link, no topo do SEI, que mostra a unidade atual e abre a tela de troca.
    CSS_UNIDADE_ATUAL = "a#lnkInfraUnidade"
    #: Radios da tabela de unidades; o ``title`` de cada um é a sigla da unidade.
    CSS_RADIO_UNIDADE = "input[name='chkInfraItem']"

    def __init__(self, driver, timeout: float = 10):
        self.driver = driver
        self.timeout = timeout

    def unidade_atual(self) -> str:
        """Retorna a sigla da unidade de trabalho atual."""
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, self.CSS_UNIDADE_ATUAL)
                )
            )
        except TimeoutException as exc:
            raise SeiNavegacaoError(
                "indicador de unidade (lnkInfraUnidade) não encontrado — "
                "a sessão do SEI está autenticada?"
            ) from exc
        return self._ler_unidade_atual(self.driver)

    def selecionar(self, unidade: str) -> bool:
        """Garante que a unidade de trabalho seja ``unidade`` (pela sigla).

        Args:
            unidade: sigla da unidade (ex.: ``"MGI-SGP-DECIPEX-CGPAG-EXANTE"``).

        Returns:
            ``False`` se já estava na unidade (nada a fazer); ``True`` se trocou.

        Raises:
            UnidadeNaoEncontrada: se a sigla não estiver entre as unidades às
                quais o operador tem acesso.
            SeiNavegacaoError: se a tela de troca não carregar ou não confirmar.
        """
        if self.unidade_atual() == unidade:
            _log.info("Já está na unidade %s", unidade)
            return False

        self._abrir_tela_troca()

        # Cada unidade é um radio cujo title é a sigla; clicá-lo dispara
        # selecionarUnidade(id) — não há botão de confirmar separado.
        seletor = f"{self.CSS_RADIO_UNIDADE}[title='{unidade}']"
        try:
            radio = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, seletor))
            )
        except TimeoutException as exc:
            raise UnidadeNaoEncontrada(
                f"unidade '{unidade}' não encontrada — verifique suas permissões"
            ) from exc

        # O radio do SEI é custom-estilizado; clicar via JavaScript dispara com
        # segurança o onclick (infraSelecionarItens + selecionarUnidade), que faz
        # a troca — o clique nativo nem sempre aciona o handler.
        self.driver.execute_script("arguments[0].click();", radio)

        try:
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: self._ler_unidade_atual(d) == unidade
            )
        except TimeoutException as exc:
            raise SeiNavegacaoError(
                f"troca para '{unidade}' não foi confirmada"
            ) from exc
        _log.info("Unidade %s selecionada", unidade)
        return True

    def listar_unidades(self) -> list[Unidade]:
        """Lê as unidades disponíveis ao operador, **sem** trocar de unidade.

        Abre a tela de troca e devolve os dados — pensado para uma interface
        LOCAL oferecer a escolha ao usuário, que depois chama :meth:`selecionar`
        com a sigla escolhida. (A biblioteca não inclui interface gráfica: isso é
        responsabilidade da aplicação.)

        Returns:
            Lista de :class:`Unidade` (sigla, descrição, órgão, id).

        Raises:
            SeiNavegacaoError: se a tela/lista não carregar.
        """
        self._abrir_tela_troca()
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, self.CSS_RADIO_UNIDADE)
                )
            )
        except TimeoutException as exc:
            raise SeiNavegacaoError("lista de unidades não carregou") from exc

        unidades = []
        for radio in self.driver.find_elements(
            By.CSS_SELECTOR, self.CSS_RADIO_UNIDADE
        ):
            sigla = (radio.get_attribute("title") or "").strip()
            if not sigla:
                continue
            descricao, orgao = "", ""
            try:
                celulas = radio.find_element(
                    By.XPATH, "./ancestor::tr"
                ).find_elements(By.TAG_NAME, "td")
                if len(celulas) >= 4:
                    descricao = celulas[2].text.strip()
                    orgao = celulas[3].text.strip()
            except WebDriverException:
                pass
            unidades.append(
                Unidade(sigla, descricao, orgao, radio.get_attribute("value") or "")
            )
        return unidades

    def _abrir_tela_troca(self) -> None:
        links = self.driver.find_elements(By.CSS_SELECTOR, self.CSS_UNIDADE_ATUAL)
        if not links:
            raise SeiNavegacaoError("link de troca de unidade não encontrado")
        alvo = next((a for a in links if a.is_displayed()), links[0])
        self._clicar(alvo)

    def _ler_unidade_atual(self, driver) -> str:
        # Há mais de um lnkInfraUnidade (layout responsivo); pega o 1º com texto.
        for el in driver.find_elements(By.CSS_SELECTOR, self.CSS_UNIDADE_ATUAL):
            texto = (el.text or "").strip()
            if texto:
                return texto
        return ""

    def _clicar(self, elemento) -> None:
        try:
            elemento.click()
        except WebDriverException:
            self.driver.execute_script("arguments[0].click();", elemento)
