"""Testes de ``integra_gov.sei.marcador`` — lógica pura (Selenium mockado).

Cobre o que não precisa de um WebDriver real: o dataclass :class:`Marcador`, as
regex de id/cor, o parse da quantidade, a resolução nome/id, a validação da
mensagem e a resolução do dropdown por nome exato. Os fakes abaixo respondem só
ao mínimo que cada método consome (``find_element``/``find_elements``,
``execute_script``, ``switch_to``) — abrir a tela/modal real fica para a
verificação ao vivo.
"""

from __future__ import annotations

import dataclasses

import pytest
from selenium.common.exceptions import NoAlertPresentException

from integra_gov.sei.exceptions import MarcadorError
from integra_gov.sei.marcador import Marcador, MarcadorProcesso, Marcadores


# --------------------------------------------------------------------------- #
# Marcador (dataclass frozen)
# --------------------------------------------------------------------------- #


def test_marcador_campos():
    m = Marcador(id=73047, nome="INTEGRA - RETORNO", quantidade=12, cor="vermelho")
    assert (m.id, m.nome, m.quantidade, m.cor) == (73047, "INTEGRA - RETORNO", 12, "vermelho")


def test_marcador_e_frozen():
    m = Marcador(id=1, nome="X", quantidade=None, cor=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.nome = "Y"  # type: ignore[misc]


def test_marcador_aceita_campos_none():
    # id/quantidade/cor são opcionais (ex.: filtro ativo lido sem cache).
    m = Marcador(id=None, nome="SÓ NOME", quantidade=None, cor=None)
    assert m.id is None and m.quantidade is None and m.cor is None


# --------------------------------------------------------------------------- #
# Marcadores: regex e parse (puro)
# --------------------------------------------------------------------------- #


def test_padrao_id_regex():
    assert Marcadores.PADRAO_ID.search("filtrarMarcador(73047)").group(1) == "73047"


def test_padrao_cor_regex():
    assert Marcadores.PADRAO_COR.search("/infra_css/svg/marcador_vermelho.svg").group(1) == "vermelho"


def test_extrair_id_do_onclick():
    assert Marcadores._extrair_id("javascript:filtrarMarcador(73047);") == 73047
    assert Marcadores._extrair_id("filtrarMarcador(null)") is None
    assert Marcadores._extrair_id("") is None


def test_extrair_cor_do_src():
    assert Marcadores._extrair_cor("https://sei/infra_css/svg/marcador_azul.svg") == "azul"
    assert Marcadores._extrair_cor("/outra/imagem.svg") is None


def test_parse_quantidade():
    assert Marcadores._parse_quantidade(" 1.234 ") == 1234
    assert Marcadores._parse_quantidade("7") == 7
    assert Marcadores._parse_quantidade("") is None
    assert Marcadores._parse_quantidade("—") is None


def test_nome_do_filtro():
    assert Marcadores._nome_do_filtro("INTEGRA - RETORNO ×") == "INTEGRA - RETORNO"
    assert Marcadores._nome_do_filtro("  ✕  ") == ""


# --------------------------------------------------------------------------- #
# Marcadores._casar: resolução nome/id (puro)
# --------------------------------------------------------------------------- #


_LISTA = [
    Marcador(id=73047, nome="INTEGRA - RETORNO", quantidade=3, cor="vermelho"),
    Marcador(id=88001, nome="URGENTE", quantidade=1, cor="laranja"),
]


def test_casar_por_id_inteiro():
    assert Marcadores._casar(_LISTA, 88001).nome == "URGENTE"


def test_casar_por_id_string_numerica():
    assert Marcadores._casar(_LISTA, "73047").nome == "INTEGRA - RETORNO"


def test_casar_por_nome_exato():
    assert Marcadores._casar(_LISTA, "URGENTE").id == 88001


def test_casar_nome_parcial_nao_resolve():
    # resolução é por nome EXATO (determinística); parcial não casa.
    assert Marcadores._casar(_LISTA, "URG") is None


def test_casar_inexistente_devolve_none():
    assert Marcadores._casar(_LISTA, 99999) is None
    assert Marcadores._casar(_LISTA, "NÃO EXISTE") is None


# --------------------------------------------------------------------------- #
# Marcadores: métodos que tocam o driver (Selenium mockado)
# --------------------------------------------------------------------------- #


class _Switch:
    def __init__(self, alerta=None):
        self._alerta = alerta

    def default_content(self):
        pass

    @property
    def alert(self):
        if self._alerta is None:
            raise NoAlertPresentException()
        return self._alerta


class _MarcadoresDriver:
    """Driver mínimo: registra ``execute_script`` e devolve elemento para
    qualquer ``find_element`` (satisfaz as esperas de presença)."""

    def __init__(self):
        self.switch_to = _Switch()
        self.scripts: list[str] = []

    def execute_script(self, script, *args):
        self.scripts.append(script)
        return None

    def find_element(self, by, value):
        return object()


def test_selecionar_por_id_dispara_filtro():
    drv = _MarcadoresDriver()
    m = Marcadores(drv, timeout=1)
    m.listar = lambda: [Marcador(73047, "RETORNO", 3, "vermelho")]  # type: ignore[method-assign]
    alvo = m.selecionar(73047)
    assert alvo.id == 73047
    assert any("filtrarMarcador(73047)" in s for s in drv.scripts)


def test_selecionar_por_nome_resolve_id():
    drv = _MarcadoresDriver()
    m = Marcadores(drv, timeout=1)
    m.listar = lambda: [Marcador(73047, "INTEGRA - RETORNO", 3, "vermelho")]  # type: ignore[method-assign]
    alvo = m.selecionar("INTEGRA - RETORNO")
    assert alvo.id == 73047
    assert any("filtrarMarcador(73047)" in s for s in drv.scripts)


def test_selecionar_inexistente_levanta_marcadorerror():
    drv = _MarcadoresDriver()
    m = Marcadores(drv, timeout=1)
    m.listar = lambda: [Marcador(1, "A", 5, "verde")]  # type: ignore[method-assign]
    with pytest.raises(MarcadorError):
        m.selecionar("NÃO EXISTE")


def test_remover_filtro_dispara_null():
    drv = _MarcadoresDriver()
    Marcadores(drv, timeout=1).remover_filtro()
    assert any("filtrarMarcador(null)" in s for s in drv.scripts)


class _FiltroDiv:
    def __init__(self, texto, displayed=True):
        self._texto = texto
        self._displayed = displayed

    def is_displayed(self):
        return self._displayed

    @property
    def text(self):
        return self._texto


class _FiltroDriver:
    def __init__(self, div=None):
        self.switch_to = _Switch()
        self._div = div

    def find_elements(self, by, value):
        return [self._div] if self._div is not None else []


def test_filtro_ativo_sem_filtro_retorna_none():
    assert Marcadores(_FiltroDriver(None), timeout=1).filtro_ativo() is None


def test_filtro_ativo_div_oculta_retorna_none():
    drv = _FiltroDriver(_FiltroDiv("INTEGRA - RETORNO ×", displayed=False))
    assert Marcadores(drv, timeout=1).filtro_ativo() is None


def test_filtro_ativo_resolve_do_cache():
    drv = _FiltroDriver(_FiltroDiv("INTEGRA - RETORNO ×"))
    m = Marcadores(drv, timeout=1)
    m._cache = [Marcador(73047, "INTEGRA - RETORNO", 3, "vermelho")]
    ativo = m.filtro_ativo()
    assert ativo is not None and ativo.id == 73047 and ativo.cor == "vermelho"


def test_filtro_ativo_sem_cache_melhor_esforco():
    drv = _FiltroDriver(_FiltroDiv("SÓ NOME ×"))
    ativo = Marcadores(drv, timeout=1).filtro_ativo()
    assert ativo is not None and ativo.nome == "SÓ NOME" and ativo.id is None


# --------------------------------------------------------------------------- #
# MarcadorProcesso: validação e resolução do dropdown (puro)
# --------------------------------------------------------------------------- #


def test_incluir_mensagem_longa_levanta_valueerror():
    with pytest.raises(ValueError):
        MarcadorProcesso(None).incluir("QUALQUER", "a" * 251)


def test_incluir_valida_limite_antes_de_navegar():
    mp = MarcadorProcesso(object(), timeout=1)

    def _boom():
        raise RuntimeError("chegou ao modal")

    mp._abrir_modal = _boom  # type: ignore[method-assign]
    # 251 caracteres: barra na validação, não chega a abrir o modal.
    with pytest.raises(ValueError):
        mp.incluir("X", "a" * 251)
    # 250 caracteres (no limite): passa da validação e chega ao modal.
    with pytest.raises(RuntimeError):
        mp.incluir("X", "a" * 250)


def test_indice_opcao_nome_exato():
    assert MarcadorProcesso._indice_opcao(["ALFA", "BETA", "GAMA"], "BETA") == 1


def test_indice_opcao_ignora_espacos():
    assert MarcadorProcesso._indice_opcao(["  BETA  "], "BETA") == 0


def test_indice_opcao_sem_correspondencia():
    assert MarcadorProcesso._indice_opcao(["ALFA", "BETA"], "DELTA") is None
    assert MarcadorProcesso._indice_opcao(["ALFA", "BETA"], "BET") is None


# --------------------------------------------------------------------------- #
# MarcadorProcesso: remover/listar sobre a tabela do modal (Selenium mockado)
# --------------------------------------------------------------------------- #


class _Alert:
    def __init__(self):
        self.accepted = False

    def accept(self):
        self.accepted = True


class _Cell:
    def __init__(self, text):
        self.text = text


class _RemLink:
    def __init__(self):
        self.clicked = False

    def click(self):
        self.clicked = True


class _Row:
    def __init__(self, nome, tem_remover=True):
        self._nome = nome
        self.link = _RemLink() if tem_remover else None

    def find_elements(self, by, value):
        if value == MarcadorProcesso.XPATH_CELULA_NOME:
            return [_Cell(self._nome)] if self._nome is not None else []
        if value == MarcadorProcesso.XPATH_REMOVER:
            return [self.link] if self.link is not None else []
        return []


class _Table:
    def __init__(self, rows):
        self._rows = rows

    def find_elements(self, by, value):
        return self._rows if value == "tr" else []


class _ModalDriver:
    def __init__(self, rows, alerta=None):
        self.switch_to = _Switch(alerta)
        self._table = _Table(rows)

    def find_element(self, by, value):
        return self._table


def _mp(rows, alerta=None):
    """MarcadorProcesso com ``_abrir_modal`` neutralizado e driver de tabela."""
    mp = MarcadorProcesso(_ModalDriver(rows, alerta), timeout=1)
    mp._abrir_modal = lambda: None  # type: ignore[method-assign]
    return mp


def test_remover_marcador_presente_clica_e_confirma():
    alvo = _Row("URGENTE")
    alerta = _Alert()
    mp = _mp([_Row("CABEÇALHO", tem_remover=False), alvo], alerta)
    mp.remover("URGENTE")
    assert alvo.link.clicked is True
    assert alerta.accepted is True


def test_remover_marcador_ausente_levanta():
    mp = _mp([_Row("CABEÇALHO", tem_remover=False), _Row("OUTRO")], _Alert())
    with pytest.raises(MarcadorError):
        mp.remover("URGENTE")


def test_listar_marcadores_do_processo():
    mp = _mp([_Row("CABEÇALHO"), _Row("URGENTE"), _Row("RETORNO"), _Row(None)])
    assert mp.listar() == ["URGENTE", "RETORNO"]


# --------------------------------------------------------------------------- #
# MarcadorProcesso.incluir: dropdown sem a opção pedida → MarcadorError
# --------------------------------------------------------------------------- #


class _Opcao:
    def __init__(self, texto):
        self._texto = texto

    def get_attribute(self, name):
        return self._texto if name == "textContent" else None


class _Clicavel:
    """btnAdicionar / .dd-select: sempre clicável."""

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def click(self):
        pass


class _DropdownDriver:
    """Driver do fluxo do dropdown de ``incluir``: botão/seletor sempre
    clicáveis; as opções (``.dd-option-text``) vêm de ``textos``."""

    def __init__(self, textos):
        self._opcoes = [_Opcao(t) for t in textos]

    def find_element(self, by, value):
        return _Clicavel()

    def find_elements(self, by, value):
        return self._opcoes if value == MarcadorProcesso.CSS_OPCAO else []


def test_incluir_opcao_ausente_levanta_marcadorerror():
    mp = MarcadorProcesso(_DropdownDriver(["ALFA", "BETA"]), timeout=1)
    mp._abrir_modal = lambda: None  # type: ignore[method-assign]
    with pytest.raises(MarcadorError) as exc:
        mp.incluir("GAMA")
    # a mensagem lista as opções disponíveis
    msg = str(exc.value)
    assert "GAMA" in msg and "ALFA" in msg and "BETA" in msg


# --------------------------------------------------------------------------- #
# Marcadores.listar / _parse_linha: parse real da tabela (Selenium mockado)
# --------------------------------------------------------------------------- #


class _QtdLink:
    def __init__(self, onclick, texto):
        self._onclick = onclick
        self.text = texto

    def get_attribute(self, name):
        return self._onclick if name == "onclick" else None


class _ImgSrc:
    def __init__(self, src):
        self._src = src

    def get_attribute(self, name):
        return self._src if name == "src" else None


class _TdText:
    def __init__(self, texto):
        self.text = texto


class _MarkRow:
    """Uma ``<tr>`` da tabela de marcadores (contexto lista)."""

    def __init__(self, onclick=None, qtd="", src=None, tds=None):
        self._qtd = [_QtdLink(onclick, qtd)] if onclick is not None else []
        self._imgs = [_ImgSrc(src)] if src is not None else []
        self._tds = [_TdText(t) for t in (tds or [])]

    def find_elements(self, by, value):
        if value == Marcadores.CSS_QUANTIDADE:
            return self._qtd
        if value == "img":
            return self._imgs
        if value == "td":
            return self._tds
        return []


class _MarkTable:
    def __init__(self, linhas):
        self._linhas = linhas

    def find_elements(self, by, value):
        return self._linhas if value == "tr" else []


class _ListDriver:
    def __init__(self, tabela):
        self.switch_to = _Switch()
        self._tabela = tabela

    def find_elements(self, by, value):
        # _garantir_visao_marcadores: tabela já presente (não clica "Ver por...")
        return [self._tabela] if value == Marcadores.ID_TABELA_MARCADORES else []

    def find_element(self, by, value):
        return self._tabela


def test_parse_linha_valida():
    linha = _MarkRow(
        onclick="filtrarMarcador(73047)",
        qtd="3",
        src="/infra_css/svg/marcador_vermelho.svg",
        tds=["", "INTEGRA - RETORNO"],
    )
    marc = Marcadores(object(), timeout=1)._parse_linha(linha)
    assert marc == Marcador(id=73047, nome="INTEGRA - RETORNO", quantidade=3, cor="vermelho")


def test_parse_linha_sem_link_none():
    # cabeçalho/espaçador (sem link de quantidade) → None
    assert Marcadores(object(), timeout=1)._parse_linha(_MarkRow(onclick=None)) is None


def test_parse_linha_onclick_sem_id_none():
    # link presente mas sem filtrarMarcador(<id>) numérico → None
    linha = _MarkRow(onclick="filtrarMarcador(null)", qtd="", tds=["X"])
    assert Marcadores(object(), timeout=1)._parse_linha(linha) is None


def test_listar_monta_marcadores_e_atualiza_cache():
    linhas = [
        _MarkRow(onclick=None),  # cabeçalho → ignorado
        _MarkRow(
            onclick="filtrarMarcador(73047)", qtd="3",
            src="/svg/marcador_vermelho.svg", tds=["", "INTEGRA - RETORNO"],
        ),
        _MarkRow(
            onclick="filtrarMarcador(88001)", qtd="1.234",
            src="/svg/marcador_azul.svg", tds=["URGENTE"],
        ),
    ]
    m = Marcadores(_ListDriver(_MarkTable(linhas)), timeout=1)
    marcs = m.listar()
    assert [x.id for x in marcs] == [73047, 88001]
    assert [x.nome for x in marcs] == ["INTEGRA - RETORNO", "URGENTE"]
    assert marcs[1].quantidade == 1234 and marcs[1].cor == "azul"
    assert m._cache == marcs  # cache atualizado (usado por filtro_ativo)


class _RecoveryDriver:
    """Estado FILTRADO: sem tblMarcadores, com divFiltroMarcador. Após
    ``filtrarMarcador(null)``, a visão de marcadores reaparece."""

    def __init__(self):
        self.switch_to = _Switch()
        self.scripts: list[str] = []
        self._filtrado = True

    def execute_script(self, script, *args):
        self.scripts.append(script)
        if "filtrarMarcador(null)" in script:
            self._filtrado = False

    def find_elements(self, by, value):
        if value == Marcadores.ID_TABELA_MARCADORES:
            return [] if self._filtrado else [_MarkTable([])]
        if value == Marcadores.ID_FILTRO:
            return [object()] if self._filtrado else []
        return []

    def find_element(self, by, value):
        return _MarkTable([])


def test_garantir_visao_recupera_de_filtro_ativo():
    # filtrado → recupera limpando o filtro (filtrarMarcador(null)), NÃO clicando
    # "Ver por marcadores" (que não existe na visão filtrada).
    drv = _RecoveryDriver()
    Marcadores(drv, timeout=1)._garantir_visao_marcadores()
    assert any("filtrarMarcador(null)" in s for s in drv.scripts)
