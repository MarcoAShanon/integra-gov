"""Download de um documento do SEI — headless, via ``fetch`` na sessão logada.

Baixa o documento **selecionado na árvore** sem depender da janela nativa
"Salvar como" nem da pasta de download do Chrome: extrai a URL de download do
``src`` do iframe ``ifrArvoreHtml`` e a busca com ``fetch()`` dentro do próprio
navegador (``execute_async_script``), reusando os cookies/SSL da sessão — o que
resolve, de quebra, os certificados de sites ``.gov.br``.

O método :meth:`DownloadDocumento.baixar` devolve o conteúdo como **dado**
(:class:`DocumentoBaixado`: bytes + metadados) — a lib não escreve em disco por
si; use :meth:`DocumentoBaixado.salvar` quando quiser gravar o arquivo.
"""

from __future__ import annotations

import base64
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from selenium.common.exceptions import (
    JavascriptException,
    NoSuchElementException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .exceptions import DownloadDocumentoError, SeiNavegacaoError
from .iframes import switch_to_iframe_visualizacao

_log = logging.getLogger(__name__)

#: Iframe (aninhado na visualização) cujo ``src`` é a URL de download.
ID_IFRAME_HTML = "ifrArvoreHtml"
#: No SEI 4.0 o ``ifrArvoreHtml`` fica dentro deste iframe de conteúdo, que por
#: sua vez está dentro do wrapper ``ifrConteudoVisualizacao``.
NOME_IFRAME_VISUALIZACAO = "ifrVisualizacao"
#: Timeout (s) do ``fetch`` assíncrono (arquivos grandes).
TIMEOUT_FETCH = 30

# fetch(url) reusando cookies/SSL da sessão → dataURL base64 + headers relevantes.
_JS_FETCH = """
var url = arguments[0];
var callback = arguments[arguments.length - 1];
fetch(url, {credentials: 'include'})
    .then(function (r) {
        if (!r.ok) { throw new Error('HTTP ' + r.status + ' ' + r.statusText); }
        var ct = r.headers.get('Content-Type') || '';
        var cd = r.headers.get('Content-Disposition') || '';
        return r.blob().then(function (b) { return {blob: b, ct: ct, cd: cd}; });
    })
    .then(function (res) {
        var reader = new FileReader();
        reader.onloadend = function () {
            callback({data: reader.result, contentType: res.ct,
                      contentDisp: res.cd, size: res.blob.size});
        };
        reader.readAsDataURL(res.blob);
    })
    .catch(function (err) { callback({error: err.toString()}); });
"""


@dataclass(frozen=True)
class DocumentoBaixado:
    """Um documento do SEI baixado, como **dado** (não escreve em disco por si).

    Attributes:
        conteudo: bytes do arquivo.
        content_type: cabeçalho ``Content-Type`` da resposta.
        extensao: extensão detectada (ex.: ``".pdf"``), com o ponto.
        nome_sugerido: nome do arquivo do ``Content-Disposition``, ou ``None``.
    """

    conteudo: bytes
    content_type: str
    extensao: str
    nome_sugerido: str | None

    def salvar(self, pasta, nome: str | None = None) -> Path:
        """Escreve o conteúdo em ``pasta/<nome><extensao>`` e devolve o ``Path``.

        Args:
            pasta: pasta destino (criada se não existir).
            nome: nome-base do arquivo, **sem** extensão. Se ``None``, usa o
                ``nome_sugerido`` (sem a extensão) ou ``"documento"``.

        Returns:
            O ``Path`` do arquivo salvo.
        """
        pasta = Path(pasta)
        pasta.mkdir(parents=True, exist_ok=True)
        base = nome or self._nome_base()
        destino = pasta / f"{base}{self.extensao}"
        destino.write_bytes(self.conteudo)
        _log.info("Documento salvo: %s (%d bytes)", destino, len(self.conteudo))
        return destino

    def _nome_base(self) -> str:
        return Path(self.nome_sugerido).stem if self.nome_sugerido else "documento"


class DownloadDocumento:
    """Baixa o documento **selecionado** na árvore do processo no SEI.

    Pré-condição: o documento já deve estar **selecionado na árvore** (ex.: via
    :meth:`~integra_gov.sei.documentos_arvore.DocumentosArvore.selecionar`).

    Args:
        driver: WebDriver com o SEI autenticado e um documento selecionado.
        timeout: espera máxima por iframe/elemento, em segundos.
    """

    def __init__(self, driver, *, timeout: float = 10):
        self.driver = driver
        self.timeout = timeout

    def baixar(self) -> DocumentoBaixado:
        """Baixa o documento selecionado e devolve o conteúdo + metadados.

        Returns:
            :class:`DocumentoBaixado` (bytes + content_type + extensão + nome).

        Raises:
            DownloadDocumentoError: se a URL de download não for encontrada, o
                ``fetch`` falhar (inclusive HTTP 4xx/5xx — ex.: sessão expirada
                devolvendo a página de login), ou o conteúdo não puder ser
                decodificado.

        Nota: durante o download, ajusta o *script timeout* do driver para
        ``TIMEOUT_FETCH`` (30 s), para tolerar arquivos grandes.
        """
        url = self._extrair_url()
        resultado = self._fetch(url)
        content_type = resultado.get("contentType") or ""
        content_disp = resultado.get("contentDisp") or ""
        conteudo = self._decodificar(resultado)
        extensao = self._detectar_extensao(content_type, content_disp)
        nome = self._nome_do_disposition(content_disp)
        _log.info(
            "Documento baixado: %d bytes, %r → %s",
            len(conteudo), content_type, extensao,
        )
        return DocumentoBaixado(
            conteudo=conteudo,
            content_type=content_type,
            extensao=extensao,
            nome_sugerido=nome,
        )

    # ----- internos -----

    def _extrair_url(self) -> str:
        """URL de download = ``src`` do iframe ``ifrArvoreHtml``.

        A árvore de iframes do documento é (SEI 4.1.5, verificado ao vivo)::

            top → ifrConteudoVisualizacao → ifrVisualizacao → ifrArvoreHtml

        ``switch_to_iframe_visualizacao`` para no wrapper ``ifrConteudoVisualizacao``;
        o ``ifrArvoreHtml`` fica no ``ifrVisualizacao`` **aninhado**, então é
        preciso descer essa camada extra antes de localizá-lo (:meth:`_descer_para_conteudo`).
        Converte qualquer falha do Selenium (inclusive um iframe que ficou *stale*
        no reload) em ``DownloadDocumentoError``."""
        try:
            self.driver.switch_to.default_content()
            switch_to_iframe_visualizacao(self.driver, timeout=self.timeout)
            self._descer_para_conteudo()
            iframe = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, ID_IFRAME_HTML))
            )
            url = iframe.get_attribute("src")
        except (WebDriverException, SeiNavegacaoError) as exc:
            raise DownloadDocumentoError(
                f"não foi possível localizar a URL de download (iframe "
                f"{ID_IFRAME_HTML!r}) — há um documento selecionado na árvore?"
            ) from exc
        finally:
            self._voltar_default()
        if not url:
            raise DownloadDocumentoError(
                f"o iframe {ID_IFRAME_HTML!r} não tem URL de download (src vazio)"
            )
        return url

    def _descer_para_conteudo(self) -> None:
        """Desce a camada extra do SEI 4.0: do wrapper ``ifrConteudoVisualizacao``
        (onde :func:`switch_to_iframe_visualizacao` parou) para o ``ifrVisualizacao``
        aninhado, que contém o ``ifrArvoreHtml``. Em SEI < 4.0 (sem wrapper) já
        estamos no ``ifrVisualizacao`` e não há o que descer — o iframe aninhado
        não existe e a operação é um no-op."""
        try:
            nested = self.driver.find_element(By.NAME, NOME_IFRAME_VISUALIZACAO)
        except NoSuchElementException:
            return
        self.driver.switch_to.frame(nested)

    def _voltar_default(self) -> None:
        try:
            self.driver.switch_to.default_content()
        except WebDriverException:
            pass

    def _fetch(self, url: str) -> dict:
        try:
            self.driver.set_script_timeout(TIMEOUT_FETCH)
            resultado = self.driver.execute_async_script(_JS_FETCH, url)
        except (JavascriptException, WebDriverException) as exc:
            raise DownloadDocumentoError(
                f"falha ao baixar o documento via fetch: {exc}"
            ) from exc
        if not isinstance(resultado, dict) or "error" in resultado:
            erro = resultado.get("error") if isinstance(resultado, dict) else resultado
            raise DownloadDocumentoError(f"o fetch do documento falhou: {erro}")
        return resultado

    @staticmethod
    def _decodificar(resultado: dict) -> bytes:
        data_url = resultado.get("data") or ""
        if "," not in data_url:
            raise DownloadDocumentoError(
                "resposta do download sem conteúdo base64 (dataURL inválido)"
            )
        try:
            return base64.b64decode(data_url.split(",", 1)[1])
        except ValueError as exc:  # binascii.Error é subclasse de ValueError
            raise DownloadDocumentoError(
                "não foi possível decodificar o conteúdo do documento"
            ) from exc

    @staticmethod
    def _detectar_extensao(content_type: str, content_disp: str) -> str:
        """Extensão do arquivo: prioriza o nome original (Content-Disposition),
        senão infere do ``Content-Type``; fallback ``.pdf``."""
        nome = DownloadDocumento._nome_do_disposition(content_disp)
        if nome and Path(nome).suffix:
            return Path(nome).suffix.lower()
        ct = content_type.lower()
        if "pdf" in ct:
            return ".pdf"
        if "word" in ct or "wordprocessingml" in ct:
            return ".docx"
        if "spreadsheetml" in ct or "spreadsheet" in ct:
            return ".xlsx"
        if "excel" in ct:  # application/vnd.ms-excel (formato legado)
            return ".xls"
        if "html" in ct:
            return ".html"
        return ".pdf"  # documentos do SEI são majoritariamente PDF

    @staticmethod
    def _nome_do_disposition(content_disp: str) -> str | None:
        m = re.search(r'filename[^;=\n]*=(["\']?)([^"\';]+)\1', content_disp or "")
        return m.group(2) if m else None
