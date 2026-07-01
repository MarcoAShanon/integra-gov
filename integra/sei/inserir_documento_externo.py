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
import time
from datetime import datetime

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    UnexpectedTagNameException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from .barra_icones import clicar_icone_barra
from .exceptions import DocumentoExternoError
from .iframes import IframesSei
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

    ICONE_INCLUIR = "Incluir Documento"

    ID_FILTRO = "txtFiltro"
    TIPO_EXTERNO = "Externo"
    # Na lista "Escolha o Tipo do Documento", cada tipo é um link; clica-se o de
    # texto exato "Externo" (dentro de tblSeries; com fallback fora dele). Mais
    # robusto que a posição da linha, que muda conforme o filtro/favoritos.
    XPATH_TIPO_EXTERNO = '//*[@id="tblSeries"]//a[normalize-space()="Externo"]'
    XPATH_TIPO_EXTERNO_FALLBACK = '//a[normalize-space()="Externo"]'
    ID_SERIE = "selSerie"
    ID_DATA = "txtDataElaboracao"
    ID_NOME_ARVORE = "txtNomeArvore"
    XPATH_RADIO_NATO = '//*[@id="divOptNato"]/div/label'
    ID_INPUT_ARQUIVO = "filArquivo"
    CSS_INPUT_ARQUIVO_FALLBACK = "input[type='file']"
    # Após o upload, o SEI mostra o nome do arquivo neste span (confirmação).
    CLASSE_NOME_ARQUIVO = "infraSpanNomeArquivo"
    ID_SALVAR = "btnSalvar"

    # A tabela de tipos filtra via AJAX ao digitar; espera curta antes de clicar.
    INTERVALO_FILTRO = 1.0
    # A tela "Gerar Documento" carrega via AJAX após o clique no ícone; intervalo
    # entre tentativas de reentrar no iframe e localizar o campo de filtro.
    INTERVALO_FORM = 0.5
    # Orçamento total (s) para a tela de inclusão aparecer (o SEI às vezes demora).
    TIMEOUT_FORM = 12
    # O clique no ícone às vezes não "pega" (o ícone fica pressionado e não
    # navega); nesse caso reclicamos o ícone e tentamos abrir a tela de novo.
    TENTATIVAS_INCLUIR = 2
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
        filtro = self._incluir_documento_e_abrir_form()
        self._selecionar_tipo_externo(filtro)
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

    def _incluir_documento_e_abrir_form(self):
        """Clica em "Incluir Documento" e devolve o campo de filtro da tela.

        Reclica o ícone se a tela não abrir na 1ª vez (o clique nem sempre
        navega — o ícone pode ficar "pressionado" sem efeito).
        """
        ultimo_erro: DocumentoExternoError | None = None
        for tentativa in range(1, self.TENTATIVAS_INCLUIR + 1):
            clicar_icone_barra(
                self.driver, self.ICONE_INCLUIR, timeout=self.timeout
            )
            try:
                return self._abrir_formulario_e_esperar_filtro()
            except DocumentoExternoError as exc:
                ultimo_erro = exc
                _log.warning(
                    "Tela de inclusão não abriu (tentativa %d/%d); reclicando "
                    "o ícone",
                    tentativa,
                    self.TENTATIVAS_INCLUIR,
                )
        raise ultimo_erro

    def _abrir_formulario_e_esperar_filtro(self):
        """Espera a tela "Gerar Documento" carregar e devolve o campo de filtro.

        Clicar no ícone recarrega o iframe de visualização (AJAX) com a tela de
        seleção de tipo. A troca de conteúdo pode deixar o contexto do driver
        obsoleto, então **reentra no iframe** e procura o ``txtFiltro`` a cada
        tentativa, até o campo aparecer ou esgotar :attr:`TIMEOUT_FORM`.
        """
        deadline = time.monotonic() + self.TIMEOUT_FORM
        ultimo_erro: Exception | None = None
        while True:
            try:
                self.driver.switch_to.default_content()
                IframesSei(self.driver, IframesSei.VISUALIZACAO, timeout=3).navegar()
                return WebDriverWait(self.driver, 2).until(
                    EC.presence_of_element_located((By.ID, self.ID_FILTRO))
                )
            except (TimeoutException, StaleElementReferenceException) as exc:
                ultimo_erro = exc  # iframe ainda não trocou / contexto obsoleto
            if time.monotonic() >= deadline:
                break
            time.sleep(self.INTERVALO_FORM)
        raise DocumentoExternoError(
            "tela de inclusão de documento não carregou (campo de filtro ausente "
            "após 'Incluir Documento' — o ícone pode não ter navegado)"
        ) from ultimo_erro

    def _selecionar_tipo_externo(self, filtro) -> None:
        filtro.clear()
        filtro.send_keys(self.TIPO_EXTERNO)
        time.sleep(self.INTERVALO_FILTRO)  # deixa a lista filtrar (AJAX)
        self._clicar_tipo_externo()
        _log.info('Tipo "Externo" selecionado')

    def _clicar_tipo_externo(self) -> None:
        # Tenta o link "Externo" dentro da tabela de tipos e, se não achar (o
        # container pode variar por versão), o mesmo link em qualquer lugar.
        for xpath in (self.XPATH_TIPO_EXTERNO, self.XPATH_TIPO_EXTERNO_FALLBACK):
            try:
                WebDriverWait(self.driver, self.timeout).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                ).click()
                return
            except TimeoutException:
                continue
        raise DocumentoExternoError(
            'tipo "Externo" não apareceu na lista de tipos após o filtro'
        )

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
