"""Consulta e seleção de documentos na árvore do processo no SEI.

A árvore de um processo lista seus documentos. Este módulo permite **apontar**
um documento específico (o que destrava assinar/editar um documento existente,
já que a barra de ícones age sobre o nó **selecionado**) e **consultar** a
árvore como dados: listar, contar, identificar tipo (PDF/interno) e extrair o
número (protocolo) de cada nó.

A filosofia do pacote se mantém: a biblioteca devolve **dados e ações**; a
aplicação final decide o que fazer (ex.: "existe uma Nota Técnica? então
assino"). Requer um **processo já aberto** — o acesso não é feito aqui.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from enum import Enum

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import SeiNavegacaoError, SelecaoDocumentoError
from .iframes import IframesSei

_log = logging.getLogger(__name__)


class TipoDocumento(Enum):
    """Tipo do documento, identificado pelo ícone na árvore do SEI.

    Os valores são o trecho do ``src`` do ícone que os distingue.
    """

    PDF = "documento_pdf.svg"
    INTERNO = "documento_interno.svg"
    DESCONHECIDO = "desconhecido"


@dataclass(frozen=True)
class DocumentoNo:
    """Um documento na árvore do processo.

    Attributes:
        texto: rótulo do nó (ex.: ``"Despacho - CGPAG (44414392)"``).
        numero: número (protocolo) extraído do rótulo, ou ``None``.
        tipo: :class:`TipoDocumento` (PDF, interno ou desconhecido).
        id: id do elemento no HTML (quando presente).
    """

    texto: str
    numero: str | None
    tipo: TipoDocumento
    id: str | None


class DocumentosArvore:
    """Consulta e seleção de documentos na árvore do processo aberto.

    Args:
        driver: WebDriver com o SEI autenticado e um **processo aberto**.
        timeout: espera máxima por iframe/elemento, em segundos.
    """

    CLASSE_NO = "infraArvoreNo"
    # Protocolo no fim do rótulo: "(1234567)" ou "1234567".
    PADRAO_NUMERO = re.compile(r"(?:\((\d+)\)|(\d+))\s*$")
    # O SEI agrupa os documentos em pastas colapsadas quando passam de ~20; este
    # botão da barra da árvore abre todas de uma vez (senão os documentos dentro
    # das pastas nem entram no DOM e passam despercebidos).
    XPATH_ABRIR_PASTAS = '//img[@title="Abrir todas as Pastas"]'
    TIMEOUT_EXPANDIR = 3
    # O clique recarrega a árvore com as pastas abertas; espera assentar.
    INTERVALO_EXPANDIR = 1.5

    def __init__(self, driver, *, timeout: float = 10):
        self.driver = driver
        self.timeout = timeout

    def expandir(self) -> bool:
        """Abre **todas as pastas** da árvore (via "Abrir todas as Pastas").

        Idempotente: se o botão não estiver presente (árvore já expandida ou
        processo sem pastas), não faz nada. Chamado por padrão pelos métodos de
        consulta/seleção — normalmente você não precisa invocá-lo à mão.

        Returns:
            ``True`` se expandiu (havia pastas a abrir), ``False`` se já estava
            expandida.
        """
        self._ir_para_arvore()
        try:
            botao = WebDriverWait(self.driver, self.TIMEOUT_EXPANDIR).until(
                EC.element_to_be_clickable((By.XPATH, self.XPATH_ABRIR_PASTAS))
            )
        except TimeoutException:
            self.driver.switch_to.default_content()
            _log.debug("Árvore já expandida (botão 'Abrir todas as Pastas' ausente)")
            return False
        botao.click()
        time.sleep(self.INTERVALO_EXPANDIR)  # o clique recarrega a árvore
        self.driver.switch_to.default_content()
        _log.info("Árvore de documentos expandida (todas as pastas)")
        return True

    # ----- consulta (não muta o processo; devolve dados) -----

    def listar(
        self, contendo: str | None = None, *, expandir: bool = True
    ) -> list[DocumentoNo]:
        """Lista os documentos da árvore (opcionalmente filtrando por texto).

        Args:
            contendo: se informado, só os nós cujo rótulo **contém** este texto.
            expandir: abre as pastas antes de ler (padrão ``True``), para não
                perder documentos em pastas colapsadas.

        Returns:
            Lista de :class:`DocumentoNo` (na ordem da árvore).
        """
        nos = self._nos(contendo, expandir)
        docs = [self._para_documento(el) for el in nos]
        self.driver.switch_to.default_content()
        return docs

    def contar(self, contendo: str | None = None, *, expandir: bool = True) -> int:
        """Conta os documentos da árvore (opcionalmente filtrando por texto)."""
        total = len(self._nos(contendo, expandir))
        self.driver.switch_to.default_content()
        return total

    def existe(self, texto: str, *, expandir: bool = True) -> bool:
        """Diz se há pelo menos um documento cujo rótulo contém ``texto``."""
        if not texto:
            raise ValueError("texto é obrigatório")
        achou = len(self._nos(texto, expandir)) > 0
        self.driver.switch_to.default_content()
        return achou

    # ----- ação -----

    def selecionar(
        self, texto: str, *, indice: int | None = None, expandir: bool = True
    ) -> DocumentoNo:
        """Seleciona (clica) um documento na árvore pelo rótulo.

        Casar pelo **número do protocolo** é o mais seguro (é único). Se o
        ``texto`` casar com **vários** nós e ``indice`` não for informado, a
        seleção é **abortada** (para não escolher o documento errado em
        silêncio) — informe ``indice`` para desambiguar (aceita negativos, ex.:
        ``-1`` para o último).

        Args:
            texto: trecho do rótulo a casar (ex.: o número do documento).
            indice: qual dos nós casados clicar, quando houver mais de um.

        Returns:
            O :class:`DocumentoNo` selecionado.

        Raises:
            ValueError: se ``texto`` faltar.
            SelecaoDocumentoError: se nenhum nó casar, se vários casarem sem
                ``indice``, ou se ``indice`` estiver fora do intervalo.
            SeiNavegacaoError: se a árvore não for acessível.
        """
        if not texto:
            raise ValueError("texto é obrigatório")
        nos = self._nos(texto, expandir)
        if not nos:
            self.driver.switch_to.default_content()
            raise SelecaoDocumentoError(
                f"nenhum documento na árvore contém {texto!r}"
            )
        if len(nos) > 1 and indice is None:
            rotulos = [(el.text or "").strip() for el in nos]
            self.driver.switch_to.default_content()
            raise SelecaoDocumentoError(
                f"{len(nos)} documentos casam com {texto!r} — informe `indice=` "
                "para desambiguar. Casaram: "
                + "; ".join(repr(r) for r in rotulos[:10])
            )
        if indice is not None and not (-len(nos) <= indice < len(nos)):
            self.driver.switch_to.default_content()
            raise SelecaoDocumentoError(
                f"indice {indice} fora do intervalo (há {len(nos)} nó(s) casando)"
            )
        alvo = nos[indice if indice is not None else 0]
        doc = self._para_documento(alvo)
        alvo.click()
        self.driver.switch_to.default_content()
        _log.info("Documento selecionado: %r", doc.texto)
        return doc

    # ----- internos -----

    def _ir_para_arvore(self) -> None:
        self.driver.switch_to.default_content()
        try:
            IframesSei(self.driver, IframesSei.ARVORE, self.timeout).navegar()
        except TimeoutException as exc:
            raise SeiNavegacaoError(
                "não foi possível acessar a árvore do processo (ifrArvore)"
            ) from exc

    def _nos(self, contendo: str | None, expandir: bool) -> list:
        """Nós da árvore (deixa o driver **no** iframe da árvore — quem chama
        volta ao ``default_content`` após extrair o que precisa)."""
        if expandir:
            self.expandir()  # abre pastas colapsadas antes de ler
        self._ir_para_arvore()
        nos = self.driver.find_elements(By.CLASS_NAME, self.CLASSE_NO)
        if contendo:
            nos = [el for el in nos if contendo in (el.text or "")]
        return nos

    def _para_documento(self, el) -> DocumentoNo:
        texto = (el.text or "").strip()
        try:
            eid = el.get_attribute("id")
        except WebDriverException:
            eid = None
        return DocumentoNo(
            texto=texto,
            numero=self._numero(texto),
            tipo=self._tipo(el, eid),
            id=eid,
        )

    def _numero(self, texto: str) -> str | None:
        m = self.PADRAO_NUMERO.search(texto)
        if not m:
            return None
        return m.group(1) or m.group(2)

    def _tipo(self, el, eid: str | None) -> TipoDocumento:
        """Identifica o tipo pelo ``src`` do ícone do nó (melhor esforço)."""
        icone = self._icone(el, eid)
        if icone is None:
            return TipoDocumento.DESCONHECIDO
        try:
            src = icone.get_attribute("src") or ""
        except WebDriverException:
            return TipoDocumento.DESCONHECIDO
        for tipo in (TipoDocumento.PDF, TipoDocumento.INTERNO):
            if tipo.value in src:
                return tipo
        return TipoDocumento.DESCONHECIDO

    def _icone(self, el, eid: str | None):
        """Ícone do nó: derivado do id (``anchor``/``span`` → ``icon``) ou, na
        falta de id, buscado por proximidade na estrutura."""
        if eid:
            for prefixo in ("anchor", "span"):
                if eid.startswith(prefixo):
                    icon_id = "icon" + eid[len(prefixo):]
                    try:
                        return self.driver.find_element(By.ID, icon_id)
                    except NoSuchElementException:
                        return None
        try:
            parent = el.find_element(By.XPATH, "..")
            for img in parent.find_elements(By.TAG_NAME, "img"):
                src = img.get_attribute("src") or ""
                if TipoDocumento.PDF.value in src or TipoDocumento.INTERNO.value in src:
                    return img
        except WebDriverException:
            pass
        return None
