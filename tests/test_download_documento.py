"""Testes de ``integra_gov.sei.download_documento`` — lógica pura (Selenium mockado).

Cobre a extração da URL, o ``fetch`` (via ``execute_async_script`` mockado), a
decodificação base64, a detecção de extensão e o ``salvar`` — sem WebDriver real
nem rede. ``switch_to_iframe_visualizacao`` é neutralizado.
"""

from __future__ import annotations

import base64

import pytest
from selenium.common.exceptions import NoSuchElementException, WebDriverException

from integra_gov.sei import download_documento as dd
from integra_gov.sei.download_documento import DocumentoBaixado, DownloadDocumento
from integra_gov.sei.exceptions import DownloadDocumentoError

URL = "https://sei/controlador.php?acao=documento_download_anexo&id_documento=1"


# ----- fakes de Selenium -----


class _Iframe:
    def __init__(self, src):
        self._src = src

    def get_attribute(self, name):
        return self._src if name == "src" else None


class _Switch:
    def default_content(self):
        pass

    def frame(self, ref):
        pass


class _Driver:
    def __init__(self, *, src=None, async_result=None):
        self._src = src
        self.async_result = async_result
        self.switch_to = _Switch()
        self.script_timeout = None

    def find_element(self, by, value):
        if value == dd.ID_IFRAME_HTML:
            if self._src is None:
                raise NoSuchElementException(value)
            return _Iframe(self._src)
        raise NoSuchElementException(value)

    def set_script_timeout(self, t):
        self.script_timeout = t

    def execute_async_script(self, script, *args):
        return self.async_result


@pytest.fixture(autouse=True)
def _neutraliza(monkeypatch):
    def _switch(driver, timeout=10):
        return "ifrConteudoVisualizacao"

    monkeypatch.setattr(dd, "switch_to_iframe_visualizacao", _switch)


def _data_url(conteudo: bytes, tipo="application/pdf") -> str:
    return f"data:{tipo};base64," + base64.b64encode(conteudo).decode()


def _driver_ok(conteudo=b"%PDF-1.4 fake", *, tipo="application/pdf", disp=""):
    return _Driver(
        src=URL,
        async_result={
            "data": _data_url(conteudo, tipo),
            "contentType": tipo,
            "contentDisp": disp,
            "size": len(conteudo),
        },
    )


# ----- baixar: caminho feliz -----


def test_baixar_pdf():
    conteudo = b"%PDF-1.4 conteudo"
    doc = DownloadDocumento(_driver_ok(conteudo), timeout=1).baixar()
    assert doc.conteudo == conteudo
    assert doc.content_type == "application/pdf"
    assert doc.extensao == ".pdf"
    assert doc.nome_sugerido is None


def test_baixar_extensao_e_nome_do_disposition():
    drv = _driver_ok(
        b"x",
        tipo="application/octet-stream",
        disp='attachment; filename="Parecer 123.docx"',
    )
    doc = DownloadDocumento(drv, timeout=1).baixar()
    assert doc.extensao == ".docx"
    assert doc.nome_sugerido == "Parecer 123.docx"


# ----- baixar: SEI 4.0 (ifrArvoreHtml no ifrVisualizacao ANINHADO) -----


class _FrameRef:
    """Elemento-frame devolvido por ``find_element(By.NAME, 'ifrVisualizacao')``."""

    def __init__(self, destino):
        self.destino = destino


class _SwitchAninhado:
    def __init__(self, driver):
        self._d = driver

    def default_content(self):
        self._d.pos = "top"

    def frame(self, ref):
        self._d.pos = ref.destino
        if ref.destino == "visualizacao":
            self._d.desceu = True


class _DriverAninhado:
    """Modela a árvore de iframes do SEI 4.0: ``switch_to_iframe_visualizacao``
    para no wrapper ``ifrConteudoVisualizacao``; o ``ifrArvoreHtml`` (cujo ``src``
    é a URL de download) só é alcançável DENTRO do ``ifrVisualizacao`` aninhado.
    Prova que o download desce essa camada extra."""

    def __init__(self, *, src=URL, async_result):
        self._src = src
        self.async_result = async_result
        self.pos = "top"
        self.desceu = False
        self.switch_to = _SwitchAninhado(self)
        self.script_timeout = None

    def entrar_wrapper(self):
        self.pos = "wrapper"
        return "ifrConteudoVisualizacao"

    def find_element(self, by, value):
        if value == "ifrVisualizacao":
            if self.pos == "wrapper":
                return _FrameRef("visualizacao")
            raise NoSuchElementException(value)  # SEI < 4.0: já estamos nele
        if value == dd.ID_IFRAME_HTML:
            if self.pos == "visualizacao":
                return _Iframe(self._src)
            raise NoSuchElementException(value)  # ainda no wrapper → não acha
        raise NoSuchElementException(value)

    def set_script_timeout(self, t):
        self.script_timeout = t

    def execute_async_script(self, script, *args):
        return self.async_result


def test_baixar_sei40_desce_para_ifrvisualizacao_aninhado(monkeypatch):
    conteudo = b"%PDF-1.4 aninhado"
    drv = _DriverAninhado(
        src=URL,
        async_result={
            "data": _data_url(conteudo),
            "contentType": "application/pdf",
            "contentDisp": "",
            "size": len(conteudo),
        },
    )
    # switch_to_iframe_visualizacao deixa o driver no WRAPPER, não no conteúdo.
    monkeypatch.setattr(
        dd,
        "switch_to_iframe_visualizacao",
        lambda driver, timeout=10: driver.entrar_wrapper(),
    )
    doc = DownloadDocumento(drv, timeout=1).baixar()
    assert doc.conteudo == conteudo
    assert drv.desceu, "deveria ter descido para o ifrVisualizacao aninhado"


# ----- baixar: falhas -----


def test_iframe_ausente_levanta():
    with pytest.raises(DownloadDocumentoError, match="ifrArvoreHtml"):
        DownloadDocumento(_Driver(src=None), timeout=0).baixar()


def test_url_vazia_levanta():
    with pytest.raises(DownloadDocumentoError, match="src vazio"):
        DownloadDocumento(_Driver(src=""), timeout=1).baixar()


def test_fetch_erro_levanta():
    drv = _Driver(src=URL, async_result={"error": "TypeError: Failed to fetch"})
    with pytest.raises(DownloadDocumentoError, match="fetch"):
        DownloadDocumento(drv, timeout=1).baixar()


def test_dataurl_sem_virgula_levanta():
    drv = _Driver(
        src=URL,
        async_result={"data": "sem-virgula", "contentType": "", "contentDisp": "", "size": 0},
    )
    with pytest.raises(DownloadDocumentoError, match="base64"):
        DownloadDocumento(drv, timeout=1).baixar()


def test_base64_invalido_levanta():
    # tem vírgula, mas o base64 em si é inválido (comprimento/padding)
    drv = _Driver(
        src=URL,
        async_result={"data": "data:application/pdf;base64,AB", "contentType": "application/pdf",
                      "contentDisp": "", "size": 0},
    )
    with pytest.raises(DownloadDocumentoError, match="decodificar"):
        DownloadDocumento(drv, timeout=1).baixar()


def test_fetch_lanca_excecao_selenium_levanta():
    class _Boom(_Driver):
        def execute_async_script(self, script, *args):
            raise WebDriverException("timeout do script async")

    with pytest.raises(DownloadDocumentoError, match="fetch"):
        DownloadDocumento(_Boom(src=URL), timeout=1).baixar()


def test_fetch_resultado_nao_dict_levanta():
    drv = _Driver(src=URL, async_result=None)  # não-dict → 'falhou'
    with pytest.raises(DownloadDocumentoError, match="falhou"):
        DownloadDocumento(drv, timeout=1).baixar()


# ----- helpers puros -----


def test_detectar_extensao():
    d = DownloadDocumento._detectar_extensao
    assert d("application/pdf", "") == ".pdf"
    assert d("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "") == ".docx"
    assert d("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "") == ".xlsx"
    assert d("application/vnd.ms-excel", "") == ".xls"  # formato legado
    assert d("text/html", "") == ".html"
    assert d("application/octet-stream", 'filename="x.TXT"') == ".txt"  # do nome, minúsculo
    assert d("application/pdf", 'filename="doc.docx"') == ".docx"  # nome vence content-type
    assert d("qualquer/coisa", "") == ".pdf"  # fallback


def test_nome_do_disposition():
    n = DownloadDocumento._nome_do_disposition
    assert n('attachment; filename="Parecer 1.pdf"') == "Parecer 1.pdf"
    assert n("attachment; filename=doc.docx") == "doc.docx"
    assert n("") is None


# ----- DocumentoBaixado.salvar -----


def test_salvar_usa_nome_sugerido(tmp_path):
    doc = DocumentoBaixado(b"abc", "application/pdf", ".pdf", "Parecer.pdf")
    caminho = doc.salvar(tmp_path)
    assert caminho == tmp_path / "Parecer.pdf"
    assert caminho.read_bytes() == b"abc"


def test_salvar_nome_customizado(tmp_path):
    doc = DocumentoBaixado(b"x", "application/pdf", ".pdf", None)
    caminho = doc.salvar(tmp_path, "meu_parecer")
    assert caminho == tmp_path / "meu_parecer.pdf"


def test_salvar_sem_nome_usa_documento(tmp_path):
    doc = DocumentoBaixado(b"x", "", ".pdf", None)
    assert doc.salvar(tmp_path).name == "documento.pdf"


def test_salvar_cria_pasta(tmp_path):
    doc = DocumentoBaixado(b"x", "", ".pdf", None)
    destino = doc.salvar(tmp_path / "nova" / "sub", "a")
    assert destino.read_bytes() == b"x"
