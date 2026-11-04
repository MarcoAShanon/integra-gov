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


class _NoFundoDaArvore:
    """Nó abaixo da área visível do ifrArvore (altura fixa): no SEI 5.0.4 o
    clique nativo cai fora do iframe -- ElementClickInterceptedException."""

    text = "Despacho 1234567"

    def get_attribute(self, nome):
        return {"id": "anchor7654321",
                "href": "controlador.php?acao=arvore_visualizar&id_procedimento=1&id_documento=7654321"
                }.get(nome)

    def click(self):
        from selenium.common.exceptions import ElementClickInterceptedException
        raise ElementClickInterceptedException("Element is not clickable at point (1, 2)")


class _DriverFalso:
    def __init__(self):
        self.scripts = []
        self.switch_to = self

    def default_content(self):
        pass

    def execute_script(self, script, *args):
        self.scripts.append((script, args))


class _BotaoForaDaBorda:
    """"Abrir todas as Pastas" além da borda do ifrArvore (300px): um rótulo
    longo deixou a árvore com 749px e o ícone ficou em x=320..344 -- o clique
    nativo dava "element click intercepted at point (331, 18)" (processo real
    da EXANTE, 04/11/2026)."""

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def click(self):
        from selenium.common.exceptions import ElementClickInterceptedException
        raise ElementClickInterceptedException("Element is not clickable at point (331, 18)")


class _ArvoreQueRecarrega(_DriverFalso):
    """O clique (JS) no link recarrega o ifrArvore: a página marcada some."""

    def __init__(self):
        super().__init__()
        self.botao = _BotaoForaDaBorda()
        self.marcada = False
        self.recarregou = False

    def frame(self, nome):
        pass

    def find_element(self, by, valor):
        return self.botao

    def execute_script(self, script, *args):
        self.scripts.append((script, args))
        if "frameElement" in script:
            return ["ifrArvore"]
        if "= true" in script:
            self.marcada = True
        elif "!window." in script:
            return not self.marcada
        elif "click()" in script and args and args[0] is self.botao:
            self.marcada = False
            self.recarregou = True
        return None


def test_expandir_clica_via_javascript_e_espera_a_arvore_recarregar(monkeypatch):
    monkeypatch.setattr(DocumentosArvore, "_ir_para_arvore", lambda self: None)
    driver = _ArvoreQueRecarrega()

    assert DocumentosArvore(driver).expandir() is True

    assert driver.recarregou
    cliques = [s for s, a in driver.scripts if "click()" in s]
    assert cliques and "scrollIntoView" in cliques[0]


def test_selecionar_rola_ate_o_no_e_clica_via_javascript(monkeypatch):
    no = _NoFundoDaArvore()
    driver = _DriverFalso()
    monkeypatch.setattr(DocumentosArvore, "_nos", lambda self, texto, expandir: [no])
    monkeypatch.setattr(DocumentosArvore, "_tipo", lambda self, el, eid: TipoDocumento.INTERNO)

    doc = DocumentosArvore(driver).selecionar("1234567")

    assert doc.numero == "1234567"
    (script, args), = driver.scripts
    assert "scrollIntoView" in script and "arguments[0].click()" in script
    assert args == (no,)


def test_documento_no_tem_id_documento():
    d = DocumentoNo(
        texto="Despacho (123)",
        numero="123",
        tipo=TipoDocumento.INTERNO,
        id="anchor456",
        id_documento="456",
    )
    assert d.id_documento == "456"
