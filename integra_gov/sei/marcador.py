"""Marcadores do SEI — filtrar a lista por marcador e marcar/desmarcar processos.

O SEI tem *marcadores* (etiquetas coloridas com um nome) que a unidade usa para
organizar processos. Eles aparecem em **dois contextos distintos**, com
pré-condições diferentes — por isso este módulo expõe **duas classes**:

- :class:`Marcadores` — na tela **Controle de Processos** (a lista): consulta os
  marcadores da unidade como **dados** e **filtra** a lista pelos processos de um
  marcador. É *read-only* quanto aos marcadores (não cria nem apaga marcador).
- :class:`MarcadorProcesso` — num **processo aberto**: inclui/remove um marcador
  **daquele** processo pelo modal "Gerenciar Marcador".

Ambas recebem um ``driver`` já autenticado e posicionado no contexto certo (a
biblioteca não faz o acesso/login). Seguem os princípios do pacote: navegação
headless, exceções tipadas (:class:`~integra_gov.sei.exceptions.MarcadorError`,
``ValueError``) em vez de retornos booleanos, e reúso da espinha de navegação
(``clicar_icone_barra`` / :class:`~integra_gov.sei.iframes.IframesSei`).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .barra_icones import clicar_icone_barra
from .exceptions import MarcadorError, SeiNavegacaoError
from .iframes import IframesSei

_log = logging.getLogger(__name__)

#: Pausa (s) após (re)selecionar o nó, antes de clicar o ícone "Gerenciar
#: Marcador" — evita que o clique seja "engolido" pelo reload da visualização
#: (mesmo motivo/valor do ``gerar_documento``; ver ``clicar_icone_barra``).
SETTLE_APOS_NO = 1.2


@dataclass(frozen=True)
class Marcador:
    """Um marcador do SEI, como **dado** (contexto lista).

    Attributes:
        id: id interno usado no ``filtrarMarcador(id)`` do SEI; ``None`` quando
            não pôde ser resolvido (ex.: filtro ativo lido sem cache prévio).
        nome: nome visível do marcador (ex.: ``"INTEGRA - RETORNO"``).
        quantidade: nº de processos com o marcador na unidade, ou ``None``.
        cor: nome da cor do ícone (ex.: ``"vermelho"``), ou ``None``.
    """

    id: int | None
    nome: str
    quantidade: int | None
    cor: str | None


class Marcadores:
    """Consulta e filtro de marcadores na tela **Controle de Processos**.

    Pré-condição: ``driver`` na tela de Controle de Processos (a lista). Opera no
    ``default_content`` — essa tela não usa iframe de conteúdo. Não cria nem
    apaga marcadores (a lista é *read-only* aqui); para marcar/desmarcar um
    processo, use :class:`MarcadorProcesso` num processo aberto.

    Args:
        driver: WebDriver com o SEI autenticado na tela Controle de Processos.
        timeout: espera máxima por elemento, em segundos.
    """

    ID_TABELA_MARCADORES = "tblMarcadores"
    ID_FILTRO = "divFiltroMarcador"
    LINK_VER_MARCADORES = "Ver por marcadores"
    CSS_QUANTIDADE = "a.ancoraPadraoAzul"
    #: id interno no ``onclick`` do link de quantidade: ``filtrarMarcador(123)``.
    PADRAO_ID = re.compile(r"filtrarMarcador\((\d+)\)")
    #: cor no ``src`` do ícone: ``.../marcador_vermelho.svg``.
    PADRAO_COR = re.compile(r"marcador_(\w+)\.svg")

    def __init__(self, driver, *, timeout: float = 10):
        self.driver = driver
        self.timeout = timeout
        self._cache: list[Marcador] = []

    # ----- consulta (não muta a lista; devolve dados) -----

    def listar(self) -> list[Marcador]:
        """Lista os marcadores da unidade (tabela ``tblMarcadores``).

        Garante a visão "Ver por marcadores": se a tabela não estiver presente
        (ex.: a lista está filtrada por um marcador), clica o link para voltar a
        ela. Lê a tabela linha a linha via Selenium + regex e **atualiza o
        cache** interno (usado por :meth:`filtro_ativo`).

        Returns:
            Lista de :class:`Marcador` (na ordem da tabela).

        Raises:
            MarcadorError: se a visão de marcadores não puder ser aberta/lida.
        """
        self.driver.switch_to.default_content()
        self._garantir_visao_marcadores()
        tabela = self.driver.find_element(By.ID, self.ID_TABELA_MARCADORES)
        marcadores = []
        for linha in tabela.find_elements(By.TAG_NAME, "tr"):
            marcador = self._parse_linha(linha)
            if marcador is not None:
                marcadores.append(marcador)
        self._cache = marcadores
        _log.info("%d marcador(es) listado(s)", len(marcadores))
        return marcadores

    def filtro_ativo(self) -> Marcador | None:
        """Marcador em filtro **agora**, ou ``None`` se a lista não está filtrada.

        Lê o ``divFiltroMarcador`` (o "chip" do filtro) e resolve o nome contra o
        cache de :meth:`listar`. **Não** dispara ``listar()`` sozinho: isso
        recarregaria a visão e desfaria justamente o filtro que se quer medir. Se
        o cache estiver vazio (nunca listou), devolve um :class:`Marcador` só com
        o ``nome`` (demais campos ``None``) — chame :meth:`listar` antes para
        obter os detalhes.
        """
        self.driver.switch_to.default_content()
        divs = self.driver.find_elements(By.ID, self.ID_FILTRO)
        if not divs:
            return None
        try:
            if not divs[0].is_displayed():
                return None
            texto = divs[0].text
        except StaleElementReferenceException:
            # O chip do filtro sumiu entre o find e a leitura → sem filtro.
            return None
        nome = self._nome_do_filtro(texto)
        if not nome:
            return None
        for marcador in self._cache:
            if marcador.nome == nome:
                return marcador
        return Marcador(id=None, nome=nome, quantidade=None, cor=None)

    # ----- ação -----

    def selecionar(self, marcador: str | int) -> Marcador:
        """Filtra a lista pelos processos de um marcador.

        Aceita o **id** (int ou string numérica) ou o **nome exato** do marcador;
        por nome, resolve o id via :meth:`listar`. Dispara o
        ``filtrarMarcador(id)`` do SEI e espera a tabela de processos filtrados.

        Args:
            marcador: id (``73047`` ou ``"73047"``) ou nome exato do marcador.

        Returns:
            O :class:`Marcador` selecionado.

        Raises:
            MarcadorError: se o marcador não existir na lista, ou se a tabela de
                processos filtrados não carregar.
        """
        alvo = self._casar(self.listar(), marcador)
        if alvo is None:
            raise MarcadorError(
                f"marcador {marcador!r} não encontrado na lista de Controle de "
                "Processos (confira o id/nome exato via listar())"
            )
        self.driver.switch_to.default_content()
        self.driver.execute_script(f"filtrarMarcador({alvo.id})")
        # filtrarMarcador NAVEGA para a lista de processos filtrada; o sinal
        # confiável de que o filtro pegou é o "chip" divFiltroMarcador — a tabela
        # do resultado varia (tblProcessosRecebidos/Gerados), não uma id única.
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_FILTRO))
            )
        except TimeoutException as exc:
            raise MarcadorError(
                f"o filtro do marcador {alvo.nome!r} não foi aplicado "
                "(o indicador de filtro não apareceu)"
            ) from exc
        _log.info("Lista filtrada pelo marcador %r (id=%s)", alvo.nome, alvo.id)
        return alvo

    def remover_filtro(self) -> None:
        """Remove o filtro de marcador e volta à lista completa.

        Dispara ``filtrarMarcador(null)`` e espera a tabela de marcadores
        reaparecer.

        Raises:
            MarcadorError: se a lista não voltar (tabela de marcadores ausente).
        """
        self.driver.switch_to.default_content()
        self.driver.execute_script("filtrarMarcador(null)")
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_TABELA_MARCADORES))
            )
        except TimeoutException as exc:
            raise MarcadorError(
                "não foi possível remover o filtro (a visão de marcadores não reapareceu)"
            ) from exc
        _log.info("Filtro de marcador removido")

    # ----- internos -----

    def _garantir_visao_marcadores(self) -> None:
        """Garante a visão "Ver por marcadores" (``tblMarcadores`` presente).
        Assume o driver já em ``default_content``.

        Três estados na tela Controle de Processos (verificados ao vivo):

        - já na visão de marcadores → nada a fazer;
        - **filtrado** por um marcador (``divFiltroMarcador`` presente e
          ``tblMarcadores`` ausente) → limpa o filtro com ``filtrarMarcador(null)``,
          que reabre a visão de marcadores (aqui não há link "Ver por marcadores");
        - visão de processos (não filtrada) → clica "Ver por marcadores".
        """
        if self.driver.find_elements(By.ID, self.ID_TABELA_MARCADORES):
            return
        if self.driver.find_elements(By.ID, self.ID_FILTRO):
            # Filtrado: liberar o marcador reabre a visão de marcadores.
            self.driver.execute_script("filtrarMarcador(null)")
            self._esperar_tabela_marcadores("ao liberar o filtro de marcador")
            return
        try:
            link = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.LINK_TEXT, self.LINK_VER_MARCADORES))
            )
        except TimeoutException as exc:
            raise MarcadorError(
                "não estou na tela Controle de Processos ou não achei o link "
                f"{self.LINK_VER_MARCADORES!r}"
            ) from exc
        link.click()
        self._esperar_tabela_marcadores("após 'Ver por marcadores'")

    def _esperar_tabela_marcadores(self, contexto: str) -> None:
        """Espera ``tblMarcadores`` reaparecer; ``MarcadorError`` se não vier."""
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, self.ID_TABELA_MARCADORES))
            )
        except TimeoutException as exc:
            raise MarcadorError(
                f"a tabela de marcadores não apareceu ({contexto})"
            ) from exc

    def _parse_linha(self, linha) -> Marcador | None:
        """Converte uma ``<tr>`` da tabela em :class:`Marcador`; ``None`` se a
        linha não for de marcador (cabeçalho/espaçador)."""
        links = linha.find_elements(By.CSS_SELECTOR, self.CSS_QUANTIDADE)
        if not links:
            return None
        marcador_id = self._extrair_id(links[0].get_attribute("onclick") or "")
        if marcador_id is None:
            return None
        quantidade = self._parse_quantidade(links[0].text)
        cor = None
        for img in linha.find_elements(By.TAG_NAME, "img"):
            cor = self._extrair_cor(img.get_attribute("src") or "")
            if cor:
                break
        celulas = linha.find_elements(By.TAG_NAME, "td")
        nome = celulas[-1].text.strip() if celulas else ""
        return Marcador(id=marcador_id, nome=nome, quantidade=quantidade, cor=cor)

    @classmethod
    def _extrair_id(cls, onclick: str) -> int | None:
        """id interno a partir do ``onclick`` (``filtrarMarcador(123)``)."""
        m = cls.PADRAO_ID.search(onclick or "")
        return int(m.group(1)) if m else None

    @classmethod
    def _extrair_cor(cls, src: str) -> str | None:
        """Cor a partir do ``src`` do ícone (``.../marcador_vermelho.svg``)."""
        m = cls.PADRAO_COR.search(src or "")
        return m.group(1) if m else None

    @staticmethod
    def _parse_quantidade(texto: str) -> int | None:
        """Inteiro da quantidade, tolerando separador de milhar (``1.234``)."""
        limpo = (texto or "").strip().replace(".", "")
        return int(limpo) if limpo.isdigit() else None

    @staticmethod
    def _nome_do_filtro(texto: str) -> str:
        """Nome do marcador a partir do texto do chip de filtro (tira o "×"/"✕"
        de fechar e espaços)."""
        return (texto or "").replace("×", "").replace("✕", "").strip()

    @staticmethod
    def _casar(marcadores: list[Marcador], marcador: str | int) -> Marcador | None:
        """Casa ``marcador`` (id int, id em string numérica, ou nome exato)
        contra uma lista já materializada; ``None`` se nenhum casar."""
        alvo_id: int | None = None
        alvo_nome: str | None = None
        if isinstance(marcador, int):
            alvo_id = marcador
        else:
            texto = str(marcador).strip()
            if texto.isdigit():
                alvo_id = int(texto)
            else:
                alvo_nome = texto
        for atual in marcadores:
            if alvo_id is not None and atual.id == alvo_id:
                return atual
            if alvo_nome is not None and atual.nome == alvo_nome:
                return atual
        return None


class MarcadorProcesso:
    """Inclui/remove marcador de um **processo aberto** (modal "Gerenciar
    Marcador").

    Pré-condição: um processo aberto no ``driver``. Cada operação abre o modal
    "Gerenciar Marcador" pela barra de ícones do documento
    (:func:`~integra_gov.sei.barra_icones.clicar_icone_barra`).

    Args:
        driver: WebDriver com o SEI autenticado e um processo aberto.
        timeout: espera máxima por elemento, em segundos.
    """

    ICONE_GERENCIAR = "Gerenciar Marcador"
    XPATH_ADICIONAR = '//*[@id="btnAdicionar"]'
    CSS_DROPDOWN = ".dd-select"
    CSS_OPCAO = ".dd-option-text"
    XPATH_TEXTO = '//*[@id="txaTexto"]'
    XPATH_SALVAR = '//*[@id="sbmSalvar"]'
    XPATH_CELULA_NOME = "td[2]"
    XPATH_REMOVER = "td[6]//a[img[@src='/infra_css/svg/remover.svg']]"
    #: Limite do campo de mensagem/anotação do SEI, em caracteres.
    LIMITE_MENSAGEM = 250

    def __init__(self, driver, *, timeout: float = 10):
        self.driver = driver
        self.timeout = timeout

    def incluir(self, nome: str, mensagem: str = "") -> None:
        """Inclui o marcador ``nome`` no processo, com ``mensagem`` opcional.

        Abre o modal, aciona "Adicionar", escolhe ``nome`` no dropdown, preenche
        a anotação, salva e confirma pela presença do ícone do marcador na
        árvore.

        Args:
            nome: nome exato do marcador (como aparece no dropdown do modal).
            mensagem: anotação do marcador (até 250 caracteres).

        Raises:
            ValueError: se ``mensagem`` passar de 250 caracteres.
            MarcadorError: se o modal não abrir, se ``nome`` não estiver no
                dropdown (a mensagem lista as opções disponíveis), ou se a
                inclusão não puder ser confirmada.
        """
        if len(mensagem) > self.LIMITE_MENSAGEM:
            raise ValueError(
                f"mensagem excede {self.LIMITE_MENSAGEM} caracteres (tem {len(mensagem)})"
            )
        self._abrir_modal()
        wait = WebDriverWait(self.driver, self.timeout)
        # O modal pode abrir já em modo de listagem; o "Adicionar" alterna para o
        # formulário de inclusão. Se não existir, seguimos (já estamos nele).
        try:
            wait.until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_ADICIONAR))
            ).click()
        except TimeoutException:
            _log.debug("Botão 'Adicionar' ausente; assumindo formulário já aberto")
        try:
            wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.CSS_DROPDOWN))
            ).click()
            opcoes = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, self.CSS_OPCAO))
            )
        except TimeoutException as exc:
            raise MarcadorError("o dropdown de marcadores do modal não abriu") from exc
        # `textContent` (e não `.text`) porque as opções podem estar ocultas até
        # o dropdown renderizar — `.text` do Selenium devolve "" para invisíveis.
        textos = [op.get_attribute("textContent") or "" for op in opcoes]
        indice = self._indice_opcao(textos, nome)
        if indice is None:
            disponiveis = [t.strip() for t in textos if t.strip()]
            raise MarcadorError(
                f"marcador {nome!r} não está disponível no dropdown 'Gerenciar "
                "Marcador'. Opções: " + ", ".join(repr(d) for d in disponiveis)
            )
        opcoes[indice].click()
        try:
            campo = wait.until(EC.element_to_be_clickable((By.XPATH, self.XPATH_TEXTO)))
            campo.clear()
            if mensagem:
                campo.send_keys(mensagem)
            wait.until(EC.element_to_be_clickable((By.XPATH, self.XPATH_SALVAR))).click()
        except TimeoutException as exc:
            raise MarcadorError(
                "não foi possível preencher a mensagem/salvar o marcador"
            ) from exc
        self._confirmar_inclusao(nome)
        _log.info("Marcador %r incluído no processo", nome)

    def remover(self, nome: str) -> None:
        """Remove o marcador ``nome`` do processo.

        Varre a tabela do modal, acha a linha cujo nome (``td[2]``) casa com
        ``nome``, clica remover e aceita o alerta de confirmação.

        Raises:
            MarcadorError: se o modal não abrir, se o processo não tiver esse
                marcador, ou se o alerta de confirmação não aparecer.
        """
        self._abrir_modal()
        wait = WebDriverWait(self.driver, self.timeout)
        for linha in self._linhas_modal(wait):
            celulas = linha.find_elements(By.XPATH, self.XPATH_CELULA_NOME)
            if not celulas or celulas[0].text.strip() != nome:
                continue
            botoes = linha.find_elements(By.XPATH, self.XPATH_REMOVER)
            if not botoes:
                continue
            botoes[0].click()
            try:
                wait.until(EC.alert_is_present()).accept()
            except TimeoutException as exc:
                raise MarcadorError(
                    f"o alerta de confirmação da remoção de {nome!r} não apareceu"
                ) from exc
            _log.info("Marcador %r removido do processo", nome)
            return
        raise MarcadorError(f"o processo não possui o marcador {nome!r}")

    def listar(self) -> list[str]:
        """Nomes dos marcadores **deste** processo (linhas do modal)."""
        self._abrir_modal()
        wait = WebDriverWait(self.driver, self.timeout)
        nomes = []
        for linha in self._linhas_modal(wait):
            celulas = linha.find_elements(By.XPATH, self.XPATH_CELULA_NOME)
            if not celulas:
                continue
            nome = celulas[0].text.strip()
            if nome:
                nomes.append(nome)
        return nomes

    # ----- internos -----

    def _abrir_modal(self) -> None:
        try:
            clicar_icone_barra(
                self.driver,
                self.ICONE_GERENCIAR,
                timeout=self.timeout,
                estabilizar_apos_no=SETTLE_APOS_NO,
            )
        except SeiNavegacaoError as exc:
            raise MarcadorError(
                f"não foi possível abrir o modal '{self.ICONE_GERENCIAR}': {exc}"
            ) from exc

    def _linhas_modal(self, wait) -> list:
        """Linhas de dados da tabela do modal (pula a primeira, de cabeçalho).

        A varredura por linha usa ``find_elements`` (devolve ``[]`` em vez de
        levantar quando o ``td[2]`` não existe). O pacote opera sem espera
        implícita — o driver de ``criar_driver_chrome`` não a define — então
        essas buscas não bloqueiam; um driver externo com implicit wait > 0
        pagaria esse tempo por linha (a fonte zerava/restaurava o implicit wait
        no scan por isso).
        """
        try:
            tabela = wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
        except TimeoutException as exc:
            raise MarcadorError(
                "a tabela de marcadores do processo não foi encontrada no modal"
            ) from exc
        return tabela.find_elements(By.TAG_NAME, "tr")[1:]

    def _confirmar_inclusao(self, nome: str) -> None:
        """Confirma a inclusão pela presença do ícone do marcador (``<img>`` com
        ``title`` contendo o nome) na árvore do processo."""
        self.driver.switch_to.default_content()
        try:
            IframesSei(self.driver, IframesSei.ARVORE, self.timeout).navegar()
        except TimeoutException as exc:
            raise MarcadorError(
                "não foi possível voltar à árvore para confirmar o marcador"
            ) from exc
        xpath = f'//img[contains(@title, "{nome}")]'
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
        except TimeoutException as exc:
            raise MarcadorError(
                f"não foi possível confirmar a inclusão do marcador {nome!r} "
                "(ícone não apareceu na árvore)"
            ) from exc
        self.driver.switch_to.default_content()

    @staticmethod
    def _indice_opcao(textos: list[str], nome: str) -> int | None:
        """Índice da opção cujo texto (após ``strip``) casa **exatamente** com
        ``nome``; ``None`` se nenhuma casar."""
        for i, texto in enumerate(textos):
            if (texto or "").strip() == nome:
                return i
        return None
