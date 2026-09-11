"""``AssinarDocumento._selecionar_cargo`` — o Cargo/Função do modal.

Achado ao vivo (11/09/2026): com mais de um cargo na unidade, o SEI alerta
"Selecione um Cargo/Função." e não assina. A escolha acontece ANTES da senha:
nada foi assinado quando a lib levanta.
"""

from __future__ import annotations

import pytest

from integra_gov.sei.assinar_documento import AssinarDocumento
from integra_gov.sei.exceptions import AssinaturaError


class _Opcao:
    def __init__(self, valor, texto, selecionada=False):
        self._valor, self.text, self._sel = valor, texto, selecionada
        self.cliques = 0

    def get_attribute(self, nome):
        return self._valor if nome == "value" else None

    def is_selected(self):
        return self._sel

    def click(self):
        self.cliques += 1


class _Select:
    def __init__(self, opcoes):
        self.opcoes = opcoes

    def find_elements(self, by, valor):
        return self.opcoes if valor == "option" else []


class _Driver:
    def __init__(self, select=None, *, so_por_rotulo=False):
        self._select = select
        self._so_por_rotulo = so_por_rotulo

    def find_elements(self, by, valor):
        if self._select is None:
            return []
        if valor == AssinarDocumento.ID_CARGO and not self._so_por_rotulo:
            return [self._select]
        if valor == AssinarDocumento.XPATH_CARGO_POR_ROTULO:
            return [self._select]
        return []


def _assinador(driver, cargo=None):
    return AssinarDocumento(driver, "s3nh4", cargo_funcao=cargo)


def test_sem_select_nao_faz_nada():
    _assinador(_Driver())._selecionar_cargo()  # sem o select: nenhuma exceção


def test_um_cargo_so_e_escolhido_sozinho():
    unico = _Opcao("7", "Analista")
    _assinador(_Driver(_Select([_Opcao("", "Selecione"), unico])))._selecionar_cargo()
    assert unico.cliques == 1


def test_cargo_ja_selecionado_e_mantido():
    a, b = _Opcao("1", "Analista", selecionada=True), _Opcao("2", "Coordenador")
    _assinador(_Driver(_Select([a, b])))._selecionar_cargo()
    assert a.cliques == 0 and b.cliques == 0


def test_varios_cargos_sem_indicacao_levanta_listando():
    a, b = _Opcao("1", "Analista"), _Opcao("2", "Coordenador")
    with pytest.raises(AssinaturaError, match="Analista.*Coordenador"):
        _assinador(_Driver(_Select([_Opcao("", ""), a, b])))._selecionar_cargo()
    assert a.cliques == 0 and b.cliques == 0


def test_cargo_indicado_e_escolhido_pelo_texto_exato():
    a, b = _Opcao("1", "Analista Técnico Executivo "), _Opcao("2", "Coordenador")
    _assinador(_Driver(_Select([a, b])), cargo="Analista Técnico Executivo")._selecionar_cargo()
    assert a.cliques == 1 and b.cliques == 0


def test_cargo_indicado_inexistente_levanta_listando():
    a = _Opcao("1", "Analista")
    with pytest.raises(AssinaturaError, match="'Chefe'.*'Analista'"):
        _assinador(_Driver(_Select([a])), cargo="Chefe")._selecionar_cargo()


def test_cargo_em_branco_equivale_a_nao_informado():
    unico = _Opcao("7", "Analista")
    _assinador(_Driver(_Select([unico])), cargo="   ")._selecionar_cargo()
    assert unico.cliques == 1


def test_select_achado_pelo_rotulo_quando_o_id_nao_bate():
    a, b = _Opcao("1", "Analista Técnico Executivo"), _Opcao("2", "Coordenador(a)")
    driver = _Driver(_Select([_Opcao("", ""), a, b]), so_por_rotulo=True)
    _assinador(driver, cargo="Analista Técnico Executivo")._selecionar_cargo()
    assert a.cliques == 1 and b.cliques == 0
