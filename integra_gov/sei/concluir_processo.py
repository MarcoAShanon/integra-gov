"""Conclusão (encerramento) de um processo no SEI.

Com um processo aberto, aciona o ícone **"Concluir Processo"** e trata os
caminhos que o SEI apresenta conforme a versão:

- **SEI 4.x**: carrega o formulário "Conclusão de Processo" no
  ``ifrConteudoVisualizacao`` (o rádio "Somente concluir" já vem marcado) e
  exige um clique em **Salvar** (``sbmSalvar``).
- **SEI < 4.0 (legado)**: um *alert* de confirmação — que o módulo aceita.
- **Bloqueio** (qualquer versão): o SEI recusa a conclusão quando há documento
  com hipótese legal (acesso restrito) pendente — via *alert* ("Não é possível
  concluir…") ou via ``div.alert-danger`` no próprio formulário; nesse caso
  levanta :class:`~integra_gov.sei.exceptions.ProcessoBloqueadoError`.

Confiabilidade: nada de ``bool``/``dict`` silencioso — sucesso retorna ``None``,
falha técnica levanta :class:`~integra_gov.sei.exceptions.ConcluirProcessoError`
e o bloqueio levanta a subclasse ``ProcessoBloqueadoError`` (para quem faz
conclusão em lote distinguir "bloqueado" de "falhou"). Reusa
:func:`~integra_gov.sei.barra_icones.clicar_icone_barra`.
"""

from __future__ import annotations

import logging

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    UnexpectedAlertPresentException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .barra_icones import clicar_icone_barra
from .exceptions import (
    ConcluirProcessoError,
    ProcessoBloqueadoError,
    SeiNavegacaoError,
)

_log = logging.getLogger(__name__)

#: Pausa (s) após (re)selecionar o nó, antes de clicar o ícone — evita o clique
#: "engolido" pelo reload da visualização (ver clicar_icone_barra/gerar_documento).
SETTLE_APOS_NO = 1.2

#: Trechos (minúsculos; com e sem acento) da crítica de bloqueio do SEI.
_MARCAS_BLOQUEIO = ("não é possível concluir", "nao e possivel concluir")
#: Mensagem-base do bloqueio por documento restrito.
_MSG_BLOQUEIO = (
    "o SEI não concluiu o processo: há documento(s) com acesso restrito / "
    "hipótese legal pendente"
)


class ConcluirProcesso:
    """Conclui (encerra) o processo aberto no SEI.

    Args:
        driver: WebDriver com o SEI autenticado e um processo aberto.
        timeout: espera máxima por elemento/iframe/alerta, em segundos.
    """

    ICONE = "Concluir Processo"
    ID_IFRAME_FORM = "ifrConteudoVisualizacao"
    ID_BOTAO_SALVAR = "sbmSalvar"
    CSS_ALERTA_ERRO = "div.alert-danger"
    #: Espera do alert imediato (bloqueio/confirmação legado). Curta porque no
    #: SEI 4.x normalmente não há alert (o fluxo é pelo formulário).
    TIMEOUT_ALERTA = 3

    def __init__(self, driver, *, timeout: float = 10):
        self.driver = driver
        self.timeout = timeout

    def concluir(self) -> None:
        """Conclui o processo aberto.

        Raises:
            ProcessoBloqueadoError: se o SEI recusar a conclusão por haver
                documento com hipótese legal (acesso restrito) pendente.
            ConcluirProcessoError: se o ícone/formulário/botão de conclusão não
                for encontrado ou a conclusão não puder ser executada.
        """
        self.driver.switch_to.default_content()
        try:
            clicar_icone_barra(
                self.driver,
                self.ICONE,
                timeout=self.timeout,
                estabilizar_apos_no=SETTLE_APOS_NO,
            )
            # 1) Alert imediato: bloqueio ("não é possível concluir") ou
            #    confirmação legado (< 4.0). Sem alert → formulário (SEI 4.x).
            alerta = self._alerta_opcional(min(self.TIMEOUT_ALERTA, self.timeout))
            if alerta is not None:
                self._tratar_alerta(alerta)
                return
            # 2) Formulário "Conclusão de Processo" (SEI 4.x).
            self._concluir_pelo_formulario()
        except SeiNavegacaoError as exc:
            raise ConcluirProcessoError(
                f"não foi possível acionar '{self.ICONE}': {exc}"
            ) from exc
        except UnexpectedAlertPresentException:
            # Um alert surgiu durante o clique/navegação OU a fase do formulário
            # (o alert de bloqueio/confirmação pode vir a qualquer momento —
            # paridade com a fonte). Trata-o como bloqueio/confirmação.
            alerta = self._alerta_opcional(min(self.TIMEOUT_ALERTA, self.timeout))
            if alerta is None:
                raise ConcluirProcessoError(
                    "um alerta inesperado surgiu durante a conclusão e não pôde "
                    "ser lido"
                )
            self._tratar_alerta(alerta)
            return
        _log.info("Processo concluído (formulário SEI 4.x)")

    # ----- internos -----

    def _alerta_opcional(self, timeout: float):
        """Devolve o alerta se aparecer em ``timeout`` s; ``None`` caso contrário."""
        try:
            return WebDriverWait(self.driver, timeout).until(EC.alert_is_present())
        except TimeoutException:
            return None

    def _tratar_alerta(self, alerta) -> None:
        """Aceita o alerta e classifica: bloqueio → exceção; senão, sucesso
        (confirmação legado)."""
        texto = (alerta.text or "").lower()
        _log.debug("Alerta da conclusão: %r", texto)
        alerta.accept()
        self.driver.switch_to.default_content()
        if self._eh_bloqueio(texto):
            raise self._bloqueado()
        _log.info("Processo concluído (confirmação legado)")

    def _concluir_pelo_formulario(self) -> None:
        self.driver.switch_to.default_content()
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.frame_to_be_available_and_switch_to_it(
                    (By.ID, self.ID_IFRAME_FORM)
                )
            )
        except TimeoutException as exc:
            raise ConcluirProcessoError(
                "o formulário de conclusão não carregou "
                f"(iframe {self.ID_IFRAME_FORM!r} ausente)"
            ) from exc

        # Bloqueio exibido no próprio formulário (SEI 4.x) como div.alert-danger.
        if self._formulario_bloqueado():
            self.driver.switch_to.default_content()
            raise self._bloqueado(no_formulario=True)

        try:
            botao = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.ID, self.ID_BOTAO_SALVAR))
            )
        except TimeoutException as exc:
            # Salvar não apareceu: pode ser um bloqueio que renderizou tarde.
            bloqueado = self._formulario_bloqueado()
            self.driver.switch_to.default_content()
            if bloqueado:
                raise self._bloqueado(no_formulario=True) from exc
            raise ConcluirProcessoError(
                f"o botão Salvar da conclusão ({self.ID_BOTAO_SALVAR}) não apareceu"
            ) from exc
        # Clique via JS: o botão do formulário nem sempre responde ao click nativo.
        self.driver.execute_script("arguments[0].click();", botao)
        self.driver.switch_to.default_content()
        # Sinal de conclusão (verificado ao vivo, SEI 4.1.5): após Salvar, a
        # visualização do processo passa a exibir "Processo não possui andamentos
        # abertos". Uma confirmação programática desse sinal é um endurecimento
        # futuro — exige fixar ao vivo o frame exato onde a mensagem aparece
        # (ifrConteudoVisualizacao vs. o ifrVisualizacao aninhado).

    def _formulario_bloqueado(self) -> bool:
        """``True`` se o formulário traz a crítica de bloqueio (``div.alert-danger``
        com "não é possível concluir")."""
        for div in self.driver.find_elements(By.CSS_SELECTOR, self.CSS_ALERTA_ERRO):
            try:
                texto = (div.text or "").lower()
            except StaleElementReferenceException:
                continue
            if self._eh_bloqueio(texto):
                return True
        return False

    def _bloqueado(self, *, no_formulario: bool = False) -> ProcessoBloqueadoError:
        detalhe = " (crítica no formulário)" if no_formulario else ""
        return ProcessoBloqueadoError(_MSG_BLOQUEIO + detalhe)

    @staticmethod
    def _eh_bloqueio(texto: str) -> bool:
        return any(m in texto for m in _MARCAS_BLOQUEIO)
