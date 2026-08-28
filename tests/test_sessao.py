"""Testes de ``integra_gov.sei.sessao`` — sem navegador real (Selenium mockado).

O driver fake devolve listas em ``find_elements`` conforme os IDs configurados;
a detecção exige os DOIS campos do formulário de login do SIP."""

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import WebDriverException

from integra_gov.sei.exceptions import SeiError, SessaoExpiradaError
from integra_gov.sei.sessao import levantar_se_sessao_expirada, sessao_expirada


def _driver(ids_presentes=(), erro=None):
    """Driver fake: ``find_elements(By.ID, x)`` → [elemento] se x configurado."""
    driver = MagicMock()
    if erro is not None:
        driver.find_elements.side_effect = erro
    else:
        presentes = set(ids_presentes)
        driver.find_elements.side_effect = (
            lambda by, valor: ["el"] if valor in presentes else []
        )
    return driver


def test_pagina_de_login_detectada():
    driver = _driver({"txtUsuario", "pwdSenha"})
    assert sessao_expirada(driver) is True
    driver.switch_to.default_content.assert_called()  # parte do topo


def test_so_um_campo_nao_e_login():
    assert sessao_expirada(_driver({"txtUsuario"})) is False
    assert sessao_expirada(_driver({"pwdSenha"})) is False


def test_pagina_normal_do_sei_nao_e_login():
    assert sessao_expirada(_driver(set())) is False


def test_driver_morto_devolve_false():
    # Na dúvida o erro original prevalece: o helper nunca vira a causa da falha.
    assert sessao_expirada(_driver(erro=WebDriverException("morto"))) is False


def test_default_content_falhando_devolve_false():
    driver = _driver({"txtUsuario", "pwdSenha"})
    driver.switch_to.default_content.side_effect = WebDriverException("morto")
    assert sessao_expirada(driver) is False


def test_levantar_se_expirada_levanta_com_causa():
    causa = TimeoutError("timeout original")
    with pytest.raises(SessaoExpiradaError, match="login do SEI") as excinfo:
        levantar_se_sessao_expirada(_driver({"txtUsuario", "pwdSenha"}), causa)
    assert excinfo.value.__cause__ is causa
    assert isinstance(excinfo.value, SeiError)  # herda da base do pacote


def test_levantar_se_expirada_noop_com_sessao_viva():
    levantar_se_sessao_expirada(_driver(set()))  # não deve levantar


def test_sessao_expirada_nao_e_navegacao_error():
    # Deliberado (spec): irmã de SeiNavegacaoError, não filha — módulos que
    # capturam SeiNavegacaoError para embrulhar não podem engoli-la.
    from integra_gov.sei.exceptions import SeiNavegacaoError

    assert not issubclass(SessaoExpiradaError, SeiNavegacaoError)


def test_exports_publicos():
    import integra_gov.sei as sei

    assert sei.SessaoExpiradaError is SessaoExpiradaError
    assert sei.sessao_expirada is sessao_expirada
    assert sei.levantar_se_sessao_expirada is levantar_se_sessao_expirada
    assert "SessaoExpiradaError" in sei.__all__
    assert "sessao_expirada" in sei.__all__
    assert "levantar_se_sessao_expirada" in sei.__all__


# ----- login dentro do IFRAME (achado do gate ao vivo de 28/08/2026) -----


def _driver_com_login_no_iframe(*, erro_no_contexto_atual=None):
    """Driver fake posicionado DENTRO de um iframe onde a página de login
    renderizou. Mecanismo verificado ao vivo: o Sair em outra aba deixa o TOPO
    com a página antiga do processo; a operação seguinte recarrega só o iframe,
    e é nele que o formulário do SIP aparece. ``default_content()`` muda o
    contexto para o topo — onde o formulário NÃO está."""
    driver = MagicMock()
    contexto = {"topo": False}
    driver.switch_to.default_content.side_effect = (
        lambda: contexto.__setitem__("topo", True)
    )

    def _find(by, valor):
        if not contexto["topo"] and erro_no_contexto_atual is not None:
            raise erro_no_contexto_atual
        if not contexto["topo"] and valor in {"txtUsuario", "pwdSenha"}:
            return ["el"]
        return []

    driver.find_elements.side_effect = _find
    return driver


def test_login_dentro_do_iframe_e_detectado():
    # A sonda tem de olhar o contexto ATUAL antes de subir ao topo — senão o
    # caso real (login renderizado no iframe) devolve False e a falha sai com
    # o tipo errado (foi o ❌ da checagem 1 do gate de 28/08).
    assert sessao_expirada(_driver_com_login_no_iframe()) is True


def test_login_no_iframe_ainda_termina_no_topo():
    # O efeito colateral documentado (driver no default_content) se mantém.
    driver = _driver_com_login_no_iframe()
    sessao_expirada(driver)
    driver.switch_to.default_content.assert_called()


def test_contexto_atual_stale_nao_impede_a_checagem_no_topo():
    # Iframe destacado (stale) durante a sonda local: cai para o topo em vez
    # de desistir — no fake, o topo não tem o formulário, então False.
    driver = _driver_com_login_no_iframe(
        erro_no_contexto_atual=WebDriverException("frame destacado")
    )
    assert sessao_expirada(driver) is False
    driver.switch_to.default_content.assert_called()
