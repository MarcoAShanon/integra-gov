"""Inclusão de um documento **interno** (gerado no SEI) num processo aberto.

Aciona **"Incluir Documento"**, escolhe o tipo interno (``"Despacho"``,
``"Nota Técnica"``, …) na tela "Gerar Documento" — preâmbulo compartilhado em
:mod:`~integra_gov.sei.gerar_documento` — e preenche o formulário: **texto inicial**
("Documento Modelo", com o protocolo de um documento base, ou nenhum), **nome na
árvore** e nível de acesso, salvando ao fim. Requer uma sessão autenticada, na
unidade correta, com o **processo aberto**.

Após salvar, o SEI abre o **editor de conteúdo numa janela nova**. Este módulo a
**fecha** e devolve o driver à janela principal — a criação é confirmada pela
abertura do editor, e o retorno é o **rótulo do documento na árvore** (ex.:
``"Despacho 12345678"``). Editar o conteúdo será um módulo próprio.

O que é específico de órgão/política é **parâmetro**: ``tipo_documento`` é
obrigatório (texto exato, varia por órgão); o ``documento_modelo`` (protocolo do
documento cujo conteúdo serve de base — os *modelos pré-definidos*) é opcional;
nível de acesso e hipótese legal reusam :mod:`~integra_gov.sei.nivel_acesso`.
Nenhum valor real é embutido.

Escopo desta versão: texto inicial "Documento Modelo" ou nenhum. "Texto Padrão"
(dropdown de padrões do órgão) fica como próximo passo.
"""

from __future__ import annotations

import logging

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import DocumentoInternoError, SeiNavegacaoError
from .gerar_documento import abrir_gerar_documento
from .iframes import IframesSei
from .nivel_acesso import configurar_nivel_acesso, validar_nivel_acesso

_log = logging.getLogger(__name__)


class IncluirDocumentoInterno:
    """Inclui um documento interno (gerado no SEI) num processo aberto.

    Args:
        driver: WebDriver com o SEI autenticado e o **processo já aberto** (ver
            :class:`~integra_gov.sei.processo.ProcessoSei`).
        tipo_documento: tipo do documento, **exatamente** como na lista do SEI
            (ex.: ``"Despacho"``, ``"Nota Técnica"``). Obrigatório, sem default.
            Para documento **externo** (upload de arquivo), use
            :class:`~integra_gov.sei.inserir_documento_externo.InserirDocumentoExterno`.
        nome_arvore: rótulo extra do documento **na árvore** (campo "Nome na
            Árvore"); opcional — o SEI compõe ``tipo + nome``.
        documento_modelo: protocolo SEI do documento cujo conteúdo serve de
            **modelo** (texto inicial "Documento Modelo"), ex.: ``"12345678"``.
            Opcional; sem ele o texto inicial fica em "Nenhum".
        nivel_acesso: ``"publico"`` (padrão) ou ``"restrito"``.
        hipotese_legal: texto **exato** da hipótese legal no dropdown;
            obrigatório quando ``nivel_acesso="restrito"``.
        timeout: espera máxima por elemento/iframe/janela, em segundos.

    Raises:
        ValueError: se ``tipo_documento`` faltar (ou for ``"Externo"``),
            ``nivel_acesso`` for inválido, ou restrito sem hipótese legal.
    """

    XPATH_RADIO_DOC_MODELO = '//*[@id="divOptProtocoloDocumentoTextoBase"]/div/label'
    ID_PROTOCOLO_MODELO = "txtProtocoloDocumentoTextoBase"
    ID_NOME_ARVORE = "txtNomeArvore"
    ID_SALVAR = "btnSalvar"
    # Nó selecionado na árvore após salvar: o documento recém-criado.
    CSS_NO_SELECIONADO = ".infraArvoreNoSelecionado"

    # Após "Salvar", o SEI sinaliza campos faltando com um alerta JS; espera
    # curta por esse alerta (ausência = documento salvo).
    TIMEOUT_ALERTA = 2

    def __init__(
        self,
        driver,
        tipo_documento: str,
        *,
        nome_arvore: str | None = None,
        documento_modelo: str | None = None,
        nivel_acesso: str = "publico",
        hipotese_legal: str | None = None,
        timeout: float = 10,
    ):
        if not tipo_documento:
            raise ValueError("tipo_documento é obrigatório")
        if tipo_documento.strip().lower() == "externo":
            raise ValueError(
                "para documento externo (upload de arquivo) use "
                "InserirDocumentoExterno"
            )
        # Valida nível/hipótese pelo componente compartilhado (mesma regra do SEI).
        nivel = validar_nivel_acesso(nivel_acesso, hipotese_legal)

        self.driver = driver
        self.tipo_documento = tipo_documento
        self.nome_arvore = nome_arvore
        self.documento_modelo = documento_modelo
        self.nivel_acesso = nivel
        self.hipotese_legal = hipotese_legal
        self.timeout = timeout

    def incluir(self) -> str:
        """Executa o fluxo completo de inclusão do documento interno.

        Ao fim, o editor de conteúdo (janela nova) é fechado e o driver volta à
        janela principal do SEI.

        Returns:
            O rótulo do documento criado na árvore (ex.: ``"Despacho 12345678"``).

        Raises:
            DocumentoInternoError: se algum passo falhar (tela/campo/botão não
                encontrado), o SEI recusar o documento (alerta de validação), o
                editor não abrir após salvar (criação não confirmada) ou o
                rótulo na árvore não puder ser lido.
        """
        try:
            abrir_gerar_documento(
                self.driver, self.tipo_documento, timeout=self.timeout
            )
        except SeiNavegacaoError as exc:
            # Preserva o contrato do módulo: todo o fluxo fala DocumentoInternoError.
            raise DocumentoInternoError(str(exc)) from exc
        if self.documento_modelo:
            self._configurar_documento_modelo()
        if self.nome_arvore:
            self._preencher_nome_arvore()
        configurar_nivel_acesso(
            self.driver,
            self.nivel_acesso,
            hipotese_legal=self.hipotese_legal,
            timeout=self.timeout,
        )
        self._salvar_e_fechar_editor()
        rotulo = self._capturar_rotulo_arvore()
        _log.info(
            "Documento interno incluído: %r (tipo %r)", rotulo, self.tipo_documento
        )
        return rotulo

    # ----- passos -----

    def _configurar_documento_modelo(self) -> None:
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_RADIO_DOC_MODELO))
            ).click()
        except TimeoutException as exc:
            raise DocumentoInternoError(
                "opção 'Documento Modelo' (texto inicial) não encontrada — o "
                "formulário do documento carregou?"
            ) from exc
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_PROTOCOLO_MODELO))
            )
        except TimeoutException as exc:
            raise DocumentoInternoError(
                "campo do protocolo do documento modelo não encontrado"
            ) from exc
        campo.clear()
        campo.send_keys(self.documento_modelo)
        _log.info("Documento modelo: %r", self.documento_modelo)

    def _preencher_nome_arvore(self) -> None:
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_NOME_ARVORE))
            )
        except TimeoutException as exc:
            raise DocumentoInternoError(
                "campo 'Nome na Árvore' não encontrado"
            ) from exc
        campo.clear()
        campo.send_keys(self.nome_arvore)
        _log.info("Nome na árvore: %r", self.nome_arvore)

    def _salvar_e_fechar_editor(self) -> None:
        """Salva e confirma pela abertura do editor (janela nova), fechando-o.

        A janela do editor é a confirmação forte de que o documento foi criado.
        Ela é fechada em seguida — edição de conteúdo é responsabilidade de um
        módulo próprio — e o driver volta à janela principal do SEI.
        """
        janela_principal = self.driver.current_window_handle
        janelas_antes = set(self.driver.window_handles)

        try:
            botao = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.ID, self.ID_SALVAR))
            )
        except TimeoutException as exc:
            raise DocumentoInternoError("botão Salvar não encontrado") from exc
        botao.click()
        self._confirmar_sem_alerta_de_validacao()

        try:
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: set(d.window_handles) - janelas_antes
            )
        except TimeoutException as exc:
            raise DocumentoInternoError(
                "a janela do editor não abriu após salvar — criação não "
                "confirmada (verifique a árvore do processo)"
            ) from exc

        janela_editor = (set(self.driver.window_handles) - janelas_antes).pop()
        self.driver.switch_to.window(janela_editor)
        self.driver.close()
        self.driver.switch_to.window(janela_principal)
        _log.info("Documento salvo (editor aberto e fechado)")

    def _confirmar_sem_alerta_de_validacao(self) -> None:
        """Após "Salvar", o SEI sinaliza campos faltando com um alerta JS.

        Se houver alerta, o documento **não** foi criado — levanta com o texto
        do SEI (mesmo padrão do :mod:`~integra_gov.sei.iniciar_processo`).
        """
        try:
            alerta = WebDriverWait(self.driver, self.TIMEOUT_ALERTA).until(
                EC.alert_is_present()
            )
        except TimeoutException:
            return  # sem alerta → segue para a confirmação pelo editor
        texto = (alerta.text or "").strip()
        alerta.accept()
        raise DocumentoInternoError(f"o SEI recusou o documento: {texto}")

    def _capturar_rotulo_arvore(self) -> str:
        """Lê o rótulo do documento recém-criado na árvore do processo.

        Após salvar, o SEI seleciona o novo documento na árvore; o texto do nó
        selecionado é o rótulo (ex.: ``"Despacho 12345678"``) — que serve de
        confirmação adicional e de retorno útil para logas/planilhas de quem
        automatiza em escala.
        """
        try:
            IframesSei(self.driver, IframesSei.ARVORE, self.timeout).navegar()
        except TimeoutException as exc:
            raise DocumentoInternoError(
                "documento criado (o editor abriu), mas a árvore do processo "
                "não pôde ser acessada para ler o rótulo"
            ) from exc

        def rotulo_presente(driver):
            for no in driver.find_elements(
                By.CSS_SELECTOR, self.CSS_NO_SELECIONADO
            ):
                texto = (no.text or "").strip()
                if texto:
                    return texto
            return False

        try:
            return WebDriverWait(self.driver, self.timeout).until(rotulo_presente)
        except TimeoutException as exc:
            raise DocumentoInternoError(
                "documento criado (o editor abriu), mas o rótulo na árvore não "
                "pôde ser lido"
            ) from exc
