"""Criação (abertura) de um novo processo no SEI.

Aciona o menu **"Iniciar Processo"**, escolhe o *tipo* e preenche os campos do
formulário (especificação, classificação por assunto, interessado, observação) e
o nível de acesso, salvando ao fim. Requer uma sessão do SEI já autenticada e na
unidade de trabalho correta — login e seleção de unidade **não** são feitos aqui.

O que é específico de órgão/política é **parâmetro**: o ``tipo`` de processo é
obrigatório (não há padrão embutido — varia por órgão), e o nível de acesso
(``"publico"``/``"restrito"``) com a hipótese legal são configuráveis. Nenhum
valor real (interessado, número, assunto) é embutido: tudo vem de quem chama.

.. note::
   Este módulo espelha os seletores da versão em produção, mas o fluxo de
   criação **ainda não foi verificado ao vivo** neste pacote. Use com cautela.
"""

from __future__ import annotations

import logging
import re
import time

from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import IniciarProcessoError
from .nivel_acesso import configurar_nivel_acesso, validar_nivel_acesso

_log = logging.getLogger(__name__)


class IniciarProcesso:
    """Inicia (cria) um novo processo no SEI.

    Args:
        driver: instância do Selenium WebDriver, com o SEI já autenticado e na
            unidade de trabalho correta.
        tipo: tipo do processo, **exatamente** como aparece no SEI (ex.:
            ``"Arrecadação: Cobrança"``). Obrigatório — não há padrão embutido.
        especificacao: texto do campo "Especificação" (opcional).
        assunto: classificação por assunto; preenchida via autocomplete do SEI
            (opcional).
        interessado: interessado do processo (opcional).
        observacao: texto do campo "Observações desta unidade" (opcional).
        nivel_acesso: ``"publico"`` (padrão) ou ``"restrito"``.
        hipotese_legal: texto **exato** da hipótese legal no dropdown;
            obrigatório quando ``nivel_acesso="restrito"``.
        timeout: tempo máximo de espera por elemento, em segundos.

    Raises:
        ValueError: se ``tipo`` faltar, ``nivel_acesso`` for inválido ou
            ``hipotese_legal`` faltar com acesso restrito.
    """

    XPATH_MENU_INICIAR = '//span[text()="Iniciar Processo"]'
    XPATH_EXIBIR_TODOS = '//img[@title="Exibir todos os tipos"]'
    ID_FILTRO_TIPO = "txtFiltro"
    ID_ESPECIFICACAO = "txtDescricao"
    ID_ASSUNTO = "txtAssunto"
    XPATH_ASSUNTO_PENDENTE = (
        '//option[text()="ASSUNTO - CLASSIFICAÇÃO PENDENTE DE AVALIAÇÃO"]'
    )
    XPATH_REMOVER_ASSUNTOS = '//img[@title="Remover Assuntos Selecionados"]'
    ID_INTERESSADO = "txtInteressadoProcedimento"
    ID_LISTA_INTERESSADOS = "selInteressadosProcedimento"
    ID_OBSERVACOES = "txaObservacoes"
    ID_SALVAR = "btnSalvar"
    # Número Único de Protocolo (NUP) do processo criado, lido do título da aba
    # (o SEI abre o processo após salvar; o título vira "SEI - <NUP>").
    PADRAO_NUP = re.compile(r"\d{4,5}\.\d{6}/\d{4}-\d{2}")

    # A classificação por assunto usa um autocomplete via AJAX; é preciso esperar
    # as sugestões carregarem antes de escolher a primeira.
    INTERVALO_AUTOCOMPLETE = 2.0
    INTERVALO_CURTO = 0.5
    # O SEI valida no submit; campos faltando voltam como alerta JS (ex.: nível
    # de acesso ou classificação). Espera curta por esse alerta após "Salvar".
    TIMEOUT_ALERTA = 2

    def __init__(
        self,
        driver,
        tipo: str,
        *,
        especificacao: str | None = None,
        assunto: str | None = None,
        interessado: str | None = None,
        observacao: str | None = None,
        nivel_acesso: str = "publico",
        hipotese_legal: str | None = None,
        timeout: float = 10,
    ):
        if not tipo:
            raise ValueError("o tipo do processo é obrigatório")
        # Valida nível/hipótese pelo componente compartilhado (mesma regra do SEI).
        nivel = validar_nivel_acesso(nivel_acesso, hipotese_legal)

        self.driver = driver
        self.tipo = tipo
        self.especificacao = especificacao
        self.assunto = assunto
        self.interessado = interessado
        self.observacao = observacao
        self.nivel_acesso = nivel
        self.hipotese_legal = hipotese_legal
        self.timeout = timeout

    def iniciar(self) -> str:
        """Executa o fluxo completo de criação do processo.

        Preenche apenas os campos opcionais que foram informados. Ao fim, clica
        em "Salvar" — o SEI abre o processo recém-criado.

        Premissa: ``tipo`` deve casar **exatamente** com um item da lista de
        tipos do SEI; se não casar, o formulário não carrega e o passo de salvar
        falha com :class:`IniciarProcessoError` (rede de segurança implícita).

        Returns:
            O número (NUP) do processo criado, ex.: ``"19975.014466/2026-41"``.

        Raises:
            IniciarProcessoError: se algum passo falhar (menu/campo/botão não
                encontrado, formulário não carregou) ou se o número do processo
                criado não puder ser confirmado.
        """
        self._clicar_menu_iniciar()
        self._selecionar_tipo()
        if self.especificacao:
            self._preencher_especificacao()
        if self.assunto:
            self._configurar_assunto()
        if self.interessado:
            self._adicionar_interessado()
        if self.observacao:
            self._adicionar_observacao()
        configurar_nivel_acesso(
            self.driver,
            self.nivel_acesso,
            hipotese_legal=self.hipotese_legal,
            timeout=self.timeout,
        )
        self._salvar()
        numero = self._capturar_numero()
        _log.info("Processo iniciado: %s (tipo %r)", numero, self.tipo)
        return numero

    # ----- passos -----

    def _clicar_menu_iniciar(self) -> None:
        try:
            elemento = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_MENU_INICIAR))
            )
        except TimeoutException as exc:
            raise IniciarProcessoError(
                'menu "Iniciar Processo" não encontrado — você está na tela '
                "inicial do SEI (Controle de Processos)?"
            ) from exc
        elemento.click()
        _log.info('Menu "Iniciar Processo" acionado')

    def _selecionar_tipo(self) -> None:
        # Expande a lista completa de tipos, se o ícone existir.
        try:
            self.driver.find_element(By.XPATH, self.XPATH_EXIBIR_TODOS).click()
            _log.debug("Lista de tipos expandida")
        except NoSuchElementException:
            pass  # já expandida ou inexistente nesta tela

        try:
            filtro = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_FILTRO_TIPO))
            )
        except TimeoutException as exc:
            raise IniciarProcessoError(
                "campo de filtro de tipo de processo não carregou"
            ) from exc

        filtro.clear()
        filtro.send_keys(self.tipo)
        filtro.send_keys(Keys.TAB)
        # Confirma o tipo destacado pelo filtro (o foco vai para o item da lista).
        self.driver.switch_to.active_element.send_keys(Keys.ENTER)
        _log.info("Tipo de processo selecionado: %r", self.tipo)

    def _preencher_especificacao(self) -> None:
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_ESPECIFICACAO))
            )
        except TimeoutException as exc:
            raise IniciarProcessoError(
                "campo de especificação não encontrado"
            ) from exc
        campo.clear()
        campo.send_keys(self.especificacao)
        _log.info("Especificação preenchida")

    def _configurar_assunto(self) -> None:
        self._remover_assunto_padrao()
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_ASSUNTO))
            )
        except TimeoutException as exc:
            raise IniciarProcessoError(
                "campo de classificação por assunto não encontrado"
            ) from exc
        campo.clear()
        campo.send_keys(self.assunto)
        time.sleep(self.INTERVALO_AUTOCOMPLETE)  # autocomplete (AJAX) carregar
        campo.send_keys(Keys.ARROW_DOWN)
        time.sleep(self.INTERVALO_CURTO)
        campo.send_keys(Keys.ENTER)
        _log.info("Assunto configurado: %r", self.assunto)

    def _remover_assunto_padrao(self) -> None:
        """Remove a classificação "pendente de avaliação" que o SEI pré-insere,
        se houver (idempotente quanto à *presença* da classificação).

        Se a classificação existe mas o botão "Remover Assuntos" não for
        encontrado, falha alto (não engole o erro) — senão o assunto pendente
        ficaria no processo sem aviso.
        """
        try:
            option = self.driver.find_element(By.XPATH, self.XPATH_ASSUNTO_PENDENTE)
        except NoSuchElementException:
            return  # não há classificação padrão a remover
        option.click()
        try:
            self.driver.find_element(By.XPATH, self.XPATH_REMOVER_ASSUNTOS).click()
        except NoSuchElementException as exc:
            raise IniciarProcessoError(
                "classificação padrão presente, mas o botão 'Remover Assuntos "
                "Selecionados' não foi encontrado"
            ) from exc
        _log.debug("Classificação padrão removida")

    def _adicionar_interessado(self) -> None:
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_INTERESSADO))
            )
        except TimeoutException as exc:
            raise IniciarProcessoError(
                "campo de interessado não encontrado"
            ) from exc
        campo.clear()
        campo.send_keys(self.interessado)
        campo.send_keys(Keys.ENTER)
        # Ao adicionar, o SEI pode abrir um alerta de confirmação.
        self._aceitar_alerta_se_houver()
        # Seleciona o interessado recém-incluído na lista, se ela existir.
        try:
            self.driver.find_element(By.ID, self.ID_LISTA_INTERESSADOS).click()
        except NoSuchElementException:
            pass
        _log.info("Interessado adicionado")

    def _aceitar_alerta_se_houver(self) -> None:
        try:
            self.driver.switch_to.alert.accept()
            _log.debug("Alerta de interessado aceito")
        except NoAlertPresentException:
            pass  # nenhum alerta a tratar

    def _adicionar_observacao(self) -> None:
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_OBSERVACOES))
            )
        except TimeoutException as exc:
            # A observação foi pedida explicitamente; não a descarta em silêncio.
            raise IniciarProcessoError(
                "campo de observação não encontrado"
            ) from exc
        campo.clear()
        campo.send_keys(self.observacao)
        _log.info("Observação adicionada")

    def _salvar(self) -> None:
        try:
            botao = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.ID, self.ID_SALVAR))
            )
        except TimeoutException as exc:
            raise IniciarProcessoError("botão Salvar não encontrado") from exc
        botao.click()
        self._confirmar_sem_alerta_de_validacao()
        _log.info("Processo salvo")

    def _confirmar_sem_alerta_de_validacao(self) -> None:
        """Após "Salvar", o SEI sinaliza campos faltando com um alerta JS.

        Se houver alerta, o processo **não** foi criado — levanta com o texto do
        SEI (ex.: "Informe o nível de acesso", "Informe a classificação por
        assuntos").
        """
        try:
            alerta = WebDriverWait(self.driver, self.TIMEOUT_ALERTA).until(
                EC.alert_is_present()
            )
        except TimeoutException:
            return  # sem alerta → processo salvo
        texto = (alerta.text or "").strip()
        alerta.accept()
        raise IniciarProcessoError(f"o SEI recusou o processo: {texto}")

    def _capturar_numero(self) -> str:
        """Lê o NUP do processo recém-criado no título da aba.

        Após salvar, o SEI abre o processo e o título passa a ``"SEI - <NUP>"``.
        Serve também como confirmação final de que o processo foi criado.

        Raises:
            IniciarProcessoError: se o número não aparecer no título (criação
                não confirmada).
        """
        try:
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: self.PADRAO_NUP.search(d.title or "")
            )
        except TimeoutException as exc:
            raise IniciarProcessoError(
                "processo salvo, mas o número (NUP) não apareceu no título da "
                "aba — criação não confirmada"
            ) from exc
        return self.PADRAO_NUP.search(self.driver.title).group(0)
