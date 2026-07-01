"""Inclusão de um documento **externo** (arquivo pronto) no SEI.

Aciona o ícone **"Incluir Documento"** da barra do processo, filtra o tipo
**"Externo"**, preenche o formulário (série/tipo, data de elaboração, **nome na
árvore**, formato e nível de acesso), **anexa o arquivo** e salva. Requer uma
sessão do SEI já autenticada, na unidade correta, com o **processo aberto** —
login, seleção de unidade e acesso ao processo **não** são feitos aqui.

O que é específico de órgão/política é **parâmetro**: a ``tipo_serie`` (série do
documento) e o ``nome_arvore`` (rótulo que o documento recebe na árvore) são
obrigatórios, sem default; o nível de acesso (``"publico"``/``"restrito"`` +
hipótese legal) é configurável e reusa o componente compartilhado
:mod:`~integra.sei.nivel_acesso`. Nenhum valor real é embutido.

O upload é feito pelo Selenium, enviando o caminho do arquivo direto ao
``<input type="file">`` — **sem** dirigir a janela nativa do Windows (nada de
``pywinauto``). O subpacote SEI permanece livre de dependências de desktop.

Escopo desta versão: formato **nato-digital** (o mais comum). "Digitalizado
nesta unidade" (com tipo de conferência) fica como próximo passo.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    UnexpectedTagNameException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import DocumentoExternoError, SeiNavegacaoError
from .gerar_documento import abrir_gerar_documento
from .nivel_acesso import configurar_nivel_acesso, validar_nivel_acesso

_log = logging.getLogger(__name__)

FORMATO_NATO_DIGITAL = "nato_digital"
FORMATO_DIGITALIZADO = "digitalizado"


class InserirDocumentoExterno:
    """Inclui um documento externo (arquivo) num processo aberto do SEI.

    Args:
        driver: WebDriver com o SEI autenticado e o **processo já aberto** (ver
            :class:`~integra.sei.processo.ProcessoSei`).
        tipo_serie: série/tipo do documento externo, **exatamente** como no SEI
            (ex.: ``"Ofício"``, ``"Certidão"``). Obrigatório, sem default.
        nome_arvore: rótulo que o documento recebe **na árvore** do processo
            (campo "Nome na Árvore"). Obrigatório.
        arquivo: caminho do arquivo a anexar. Deve existir; é resolvido para
            caminho absoluto.
        data_elaboracao: data de elaboração no formato ``dd/mm/aaaa``; se
            omitida, usa a data de hoje.
        formato: ``"nato_digital"`` (padrão). ``"digitalizado"`` ainda não é
            suportado nesta versão.
        nivel_acesso: ``"publico"`` (padrão) ou ``"restrito"``.
        hipotese_legal: texto **exato** da hipótese legal no dropdown;
            obrigatório quando ``nivel_acesso="restrito"``.
        timeout: espera máxima por elemento/iframe, em segundos.

    Raises:
        ValueError: se ``tipo_serie``/``nome_arvore``/``arquivo`` faltarem,
            ``formato`` não for suportado, ``nivel_acesso`` for inválido, ou
            restrito sem hipótese legal.
        FileNotFoundError: se ``arquivo`` não existir.
    """

    # Tipo escolhido na tela "Gerar Documento" (o preâmbulo compartilhado —
    # ícone, espera da tela e seleção do tipo — vive em `gerar_documento`).
    TIPO_EXTERNO = "Externo"
    ID_SERIE = "selSerie"
    ID_DATA = "txtDataElaboracao"
    ID_NOME_ARVORE = "txtNomeArvore"
    XPATH_RADIO_NATO = '//*[@id="divOptNato"]/div/label'
    ID_INPUT_ARQUIVO = "filArquivo"
    CSS_INPUT_ARQUIVO_FALLBACK = "input[type='file']"
    # Após o upload, o SEI mostra o nome do arquivo neste span (confirmação).
    CLASSE_NOME_ARQUIVO = "infraSpanNomeArquivo"
    ID_SALVAR = "btnSalvar"

    # Espera máxima pela confirmação do upload (arquivos maiores demoram).
    TIMEOUT_UPLOAD = 60
    # Após "Salvar", o SEI sinaliza campos faltando com um alerta JS; espera
    # curta por esse alerta (ausência = documento salvo).
    TIMEOUT_ALERTA = 2

    def __init__(
        self,
        driver,
        tipo_serie: str,
        nome_arvore: str,
        arquivo: str,
        *,
        data_elaboracao: str | None = None,
        formato: str = FORMATO_NATO_DIGITAL,
        nivel_acesso: str = "publico",
        hipotese_legal: str | None = None,
        timeout: float = 10,
    ):
        if not tipo_serie:
            raise ValueError("tipo_serie (série do documento) é obrigatório")
        if not nome_arvore:
            raise ValueError("nome_arvore é obrigatório")
        if not arquivo:
            raise ValueError("arquivo é obrigatório")
        if formato != FORMATO_NATO_DIGITAL:
            raise ValueError(
                f"formato {formato!r} não suportado nesta versão "
                f"(use {FORMATO_NATO_DIGITAL!r}; 'digitalizado' virá depois)"
            )
        # Valida nível/hipótese pelo componente compartilhado (mesma regra do SEI).
        nivel = validar_nivel_acesso(nivel_acesso, hipotese_legal)

        arquivo_abs = os.path.abspath(arquivo)
        if not os.path.isfile(arquivo_abs):
            raise FileNotFoundError(f"arquivo não encontrado: {arquivo_abs}")

        self.driver = driver
        self.tipo_serie = tipo_serie
        self.nome_arvore = nome_arvore
        self.arquivo = arquivo_abs
        self.data_elaboracao = data_elaboracao or datetime.now().strftime("%d/%m/%Y")
        self.formato = formato
        self.nivel_acesso = nivel
        self.hipotese_legal = hipotese_legal
        self.timeout = timeout

    def inserir(self) -> str:
        """Executa o fluxo completo de inclusão do documento externo.

        Returns:
            O ``nome_arvore`` do documento incluído (confirmação).

        Raises:
            DocumentoExternoError: se algum passo falhar (campo/botão não
                encontrado, upload não confirmado) ou se o SEI recusar o
                documento (alerta de validação).
        """
        try:
            abrir_gerar_documento(
                self.driver, self.TIPO_EXTERNO, timeout=self.timeout
            )
        except SeiNavegacaoError as exc:
            # Preserva o contrato do módulo: todo o fluxo fala DocumentoExternoError.
            raise DocumentoExternoError(str(exc)) from exc
        self._selecionar_serie()
        self._preencher_data()
        self._preencher_nome_arvore()
        self._marcar_nato_digital()
        configurar_nivel_acesso(
            self.driver,
            self.nivel_acesso,
            hipotese_legal=self.hipotese_legal,
            timeout=self.timeout,
        )
        self._anexar_arquivo()
        self._salvar()
        _log.info(
            "Documento externo incluído: %r (série %r)",
            self.nome_arvore,
            self.tipo_serie,
        )
        return self.nome_arvore

    # ----- passos -----

    def _selecionar_serie(self) -> None:
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_SERIE))
            )
        except TimeoutException as exc:
            raise DocumentoExternoError(
                "campo de série (tipo do documento) não encontrado — o "
                "formulário de documento externo carregou?"
            ) from exc
        # selSerie costuma ser um <select>; usa Select por texto exato e, se não
        # for um select (ou o texto não casar como opção), cai para digitação.
        try:
            Select(campo).select_by_visible_text(self.tipo_serie)
        except (NoSuchElementException, UnexpectedTagNameException) as exc:
            # Não é um <select>, ou o texto não casou como opção: digita direto.
            _log.debug("Select direto falhou (%s); tentando digitação", exc)
            campo.send_keys(self.tipo_serie)
            campo.send_keys(Keys.TAB)
        _log.info("Série do documento: %r", self.tipo_serie)

    def _preencher_data(self) -> None:
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_DATA))
            )
        except TimeoutException as exc:
            raise DocumentoExternoError(
                "campo de data de elaboração não encontrado"
            ) from exc
        campo.clear()
        campo.send_keys(self.data_elaboracao)
        _log.info("Data de elaboração: %s", self.data_elaboracao)

    def _preencher_nome_arvore(self) -> None:
        try:
            campo = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_NOME_ARVORE))
            )
        except TimeoutException as exc:
            raise DocumentoExternoError(
                "campo 'Nome na Árvore' não encontrado"
            ) from exc
        campo.clear()
        campo.send_keys(self.nome_arvore)
        _log.info("Nome na árvore: %r", self.nome_arvore)

    def _marcar_nato_digital(self) -> None:
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_RADIO_NATO))
            ).click()
        except TimeoutException as exc:
            raise DocumentoExternoError(
                "opção de formato 'Nato-digital' não encontrada"
            ) from exc
        _log.info("Formato: nato-digital")

    def _anexar_arquivo(self) -> None:
        """Envia o caminho do arquivo direto ao <input type=file> (sem diálogo
        nativo) e aguarda o SEI confirmar o upload pelo nome do arquivo."""
        entrada = self._localizar_input_arquivo()
        entrada.send_keys(self.arquivo)
        _log.info("Arquivo enviado: %s", os.path.basename(self.arquivo))
        self._aguardar_confirmacao_upload()

    def _localizar_input_arquivo(self):
        try:
            return WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_INPUT_ARQUIVO))
            )
        except TimeoutException:
            pass  # tenta o seletor genérico abaixo
        try:
            return self.driver.find_element(
                By.CSS_SELECTOR, self.CSS_INPUT_ARQUIVO_FALLBACK
            )
        except NoSuchElementException as exc:
            raise DocumentoExternoError(
                "campo de upload (input[type=file]) não encontrado"
            ) from exc

    def _aguardar_confirmacao_upload(self) -> None:
        alvo = os.path.basename(self.arquivo).lower()

        def confirmado(driver) -> bool:
            for span in driver.find_elements(
                By.CLASS_NAME, self.CLASSE_NOME_ARQUIVO
            ):
                if alvo in (span.text or "").strip().lower():
                    return True
            return False

        try:
            WebDriverWait(self.driver, self.TIMEOUT_UPLOAD).until(confirmado)
        except TimeoutException as exc:
            raise DocumentoExternoError(
                f"upload de {os.path.basename(self.arquivo)!r} não confirmado "
                f"em {self.TIMEOUT_UPLOAD}s"
            ) from exc
        _log.info("Upload confirmado")

    def _salvar(self) -> None:
        try:
            botao = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.ID, self.ID_SALVAR))
            )
        except TimeoutException as exc:
            raise DocumentoExternoError("botão Salvar não encontrado") from exc
        botao.click()
        self._confirmar_sem_alerta_de_validacao()
        _log.info("Documento salvo")

    def _confirmar_sem_alerta_de_validacao(self) -> None:
        """Após "Salvar", o SEI sinaliza campos faltando com um alerta JS.

        Se houver alerta, o documento **não** foi incluído — levanta com o texto
        do SEI. Ausência de alerta = documento salvo (mesmo padrão do
        :mod:`~integra.sei.iniciar_processo`).
        """
        try:
            alerta = WebDriverWait(self.driver, self.TIMEOUT_ALERTA).until(
                EC.alert_is_present()
            )
        except TimeoutException:
            return  # sem alerta → documento salvo
        texto = (alerta.text or "").strip()
        alerta.accept()
        raise DocumentoExternoError(f"o SEI recusou o documento: {texto}")
