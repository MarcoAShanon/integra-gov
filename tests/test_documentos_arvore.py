"""Testes de ``integra_gov.sei.documentos_arvore`` — parte pura (sem WebDriver).

Cobre a extração do ``id_documento`` do ``href`` do nó e o campo novo do
:class:`DocumentoNo`. A navegação/seleção real (que precisa do Selenium) fica
para a verificação ao vivo.
"""

from __future__ import annotations

from integra_gov.sei.documentos_arvore import (
    DocumentoNo,
    DocumentosArvore,
    TipoDocumento,
)


def test_id_documento_extraido_do_href():
    href = (
        "controlador.php?acao=arvore_visualizar&acao_origem=procedimento_visualizar"
        "&id_procedimento=33279119&id_documento=33279120&infra_sistema=100000100"
    )
    m = DocumentosArvore.PADRAO_ID_DOCUMENTO.search(href)
    assert m and m.group(1) == "33279120"


def test_raiz_traz_so_id_procedimento():
    # A raiz do processo não tem id_documento (só id_procedimento) — não casa.
    raiz = "controlador.php?acao=arvore_visualizar&id_procedimento=33279119"
    assert DocumentosArvore.PADRAO_ID_DOCUMENTO.search(raiz) is None


def test_pasta_href_javascript_nao_casa():
    assert (
        DocumentosArvore.PADRAO_ID_DOCUMENTO.search(
            "javascript:abrirFecharPasta('PASTA1');"
        )
        is None
    )


def test_documento_no_tem_id_documento():
    d = DocumentoNo(
        texto="Despacho (123)",
        numero="123",
        tipo=TipoDocumento.INTERNO,
        id="anchor456",
        id_documento="456",
    )
    assert d.id_documento == "456"
