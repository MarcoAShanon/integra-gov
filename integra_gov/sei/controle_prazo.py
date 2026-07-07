"""Controle de prazo de um processo no SEI (ícone "Controle de Prazo").

Com um processo aberto, o SEI permite marcar um **prazo** (em dias) para o
processo — usado como lembrete/controle de acompanhamento. Este módulo aciona o
ícone **"Controle de Prazo"** da barra do processo e:

- :meth:`ControlePrazo.definir` — define um prazo de N dias;
- :meth:`ControlePrazo.excluir` — remove o prazo existente.

**Melhoria sobre a fonte:** o módulo de origem usava o valor mágico
``prazo="0"`` (string) para significar "excluir". Aqui as duas intenções são
métodos distintos — :meth:`definir` recebe ``dias: int`` e :meth:`excluir` não
recebe nada — sem valor mágico e com validação de faixa (``1..9999``).

Escopo: prazo por **dias** (como a fonte). "Data específica" fica como evolução
futura. Reusa :func:`~integra_gov.sei.barra_icones.clicar_icone_barra` para o
preâmbulo de navegação (selecionar o nó na árvore e descer ao iframe de
visualização), então basta ter o processo aberto no ``driver``.

Confiabilidade: nada de ``bool`` silencioso — entrada inválida levanta
``ValueError`` e qualquer falha da UI levanta
:class:`~integra_gov.sei.exceptions.ControlePrazoError`.
"""

from __future__ import annotations

import logging

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .barra_icones import clicar_icone_barra
from .exceptions import ControlePrazoError, SeiNavegacaoError

_log = logging.getLogger(__name__)

#: Menor prazo aceito, em dias (a UI do SEI não aceita 0/negativos).
DIAS_MIN = 1
#: Maior prazo aceito, em dias (o campo do SEI trava em 9999).
DIAS_MAX = 9999
#: Pausa (s) após (re)selecionar o nó, antes de clicar o ícone — evita que o
#: clique seja "engolido" pelo reload da visualização (ícone pressionado sem
#: navegar). Mesmo motivo/valor do ``gerar_documento`` (ver clicar_icone_barra).
SETTLE_APOS_NO = 1.2


class ControlePrazo:
    """Define ou exclui o prazo do processo aberto no SEI.

    Pré-condição: o ``driver`` está com um **processo aberto** (o nó do processo
    selecionado na árvore, ou selecionável por
    :func:`~integra_gov.sei.barra_icones.clicar_icone_barra`).

    Args:
        driver: WebDriver com o SEI autenticado e o processo aberto.
        timeout: espera máxima por elemento/alerta, em segundos.
    """

    #: ``title`` do ícone da barra que abre a tela de controle de prazo.
    ICONE = "Controle de Prazo"
    #: Rótulo da opção "dias" (marca o modo "prazo em dias").
    XPATH_OPCAO_DIAS = '//*[@id="divOptDias"]/div/label'
    #: Campo numérico com a quantidade de dias.
    XPATH_CAMPO_DIAS = '//*[@id="txtDias"]'
    #: Botão que confirma a definição do prazo.
    XPATH_BTN_CONFIRMAR = '//*[@id="sbmDefinirControlePrazo"]'
    #: Botão que remove o prazo existente (dispara um alerta de confirmação).
    XPATH_BTN_EXCLUIR = '//*[@id="btnExcluir"]'

    def __init__(self, driver, *, timeout: float = 10):
        self.driver = driver
        self.timeout = timeout

    def definir(self, dias: int) -> None:
        """Define o prazo do processo em ``dias`` dias.

        Valida a faixa **antes** de abrir a tela (não abre a UI para um valor
        inválido), aciona "Controle de Prazo", seleciona a opção "dias",
        preenche o campo e confirma.

        Args:
            dias: quantidade de dias do prazo; deve estar em ``1..9999``.

        Raises:
            ValueError: se ``dias`` não for um inteiro em ``1..9999``.
            ControlePrazoError: se a tela/campo/botão de controle de prazo não
                for encontrado ou não puder ser acionado.
        """
        dias = _validar_dias(dias)
        self._abrir()
        self._selecionar_opcao_dias()
        self._preencher_dias(dias)
        self._confirmar()
        _log.info("Prazo de %d dia(s) definido", dias)

    def excluir(self) -> None:
        """Remove o prazo do processo.

        Aciona "Controle de Prazo", clica em Excluir e **aceita o alerta** de
        confirmação — a exclusão só é dada por feita quando o alerta aparece e é
        aceito.

        Raises:
            ControlePrazoError: se o botão Excluir não for encontrado (por
                exemplo, o processo não tem prazo) ou o alerta de confirmação
                não aparecer.
        """
        self._abrir()
        self._clicar_excluir()
        self._aceitar_alerta()
        _log.info("Prazo removido")

    # ----- passos -----

    def _abrir(self) -> None:
        """Aciona o ícone "Controle de Prazo" (preâmbulo de navegação incluso)."""
        try:
            clicar_icone_barra(
                self.driver,
                self.ICONE,
                timeout=self.timeout,
                estabilizar_apos_no=SETTLE_APOS_NO,
            )
        except SeiNavegacaoError as exc:
            raise ControlePrazoError(
                f"não foi possível abrir 'Controle de Prazo': {exc}"
            ) from exc

    def _selecionar_opcao_dias(self) -> None:
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_OPCAO_DIAS))
            ).click()
        except TimeoutException as exc:
            raise ControlePrazoError(
                "opção 'dias' do controle de prazo não encontrada (divOptDias)"
            ) from exc

    def _preencher_dias(self, dias: int) -> None:
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_CAMPO_DIAS))
            )
        except TimeoutException as exc:
            raise ControlePrazoError(
                "campo de dias do controle de prazo não encontrado (txtDias)"
            ) from exc
        campo.click()
        # Re-busca o campo após o clique: selecionar o modo "dias" pode
        # re-renderizar o input, e a referência anterior ficaria stale.
        campo = self.driver.find_element(By.XPATH, self.XPATH_CAMPO_DIAS)
        campo.clear()
        campo.send_keys(str(dias))

    def _confirmar(self) -> None:
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_BTN_CONFIRMAR))
            ).click()
        except TimeoutException as exc:
            raise ControlePrazoError(
                "botão de confirmação do prazo não encontrado "
                "(sbmDefinirControlePrazo)"
            ) from exc

    def _clicar_excluir(self) -> None:
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_BTN_EXCLUIR))
            ).click()
        except TimeoutException as exc:
            raise ControlePrazoError(
                "botão Excluir não encontrado (btnExcluir) — o processo pode "
                "não ter prazo definido"
            ) from exc

    def _aceitar_alerta(self) -> None:
        try:
            alerta = WebDriverWait(self.driver, self.timeout).until(
                EC.alert_is_present()
            )
        except TimeoutException as exc:
            raise ControlePrazoError(
                "o SEI não pediu confirmação para excluir o prazo (alerta "
                "ausente) — a exclusão não foi confirmada"
            ) from exc
        alerta.accept()


def _validar_dias(dias: int) -> int:
    """Valida o prazo em dias e o devolve inalterado.

    Args:
        dias: quantidade de dias pretendida.

    Returns:
        O próprio ``dias``, quando válido.

    Raises:
        ValueError: se ``dias`` não for um inteiro (``bool`` não conta) ou
            estiver fora da faixa ``1..9999``.
    """
    if isinstance(dias, bool) or not isinstance(dias, int):
        raise ValueError(
            f"dias deve ser um inteiro (recebi {type(dias).__name__})"
        )
    if not DIAS_MIN <= dias <= DIAS_MAX:
        raise ValueError(
            f"dias deve estar entre {DIAS_MIN} e {DIAS_MAX} (recebi {dias})"
        )
    return dias
