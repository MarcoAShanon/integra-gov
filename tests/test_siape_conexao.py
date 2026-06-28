"""Testes de ``integra.siape.conexao`` — controle de terminal mockado.

O ``ControleTerminal3270`` é substituído por um ``MagicMock`` (com ``spec``), de
modo que os testes verificam o fluxo de acesso/OTP/UORG sem pywinauto.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from integra.siape import conexao as mod
from integra.siape.conexao import ConexaoTerminal3270
from integra.siape.controle import ControleTerminal3270
from integra.siape.exceptions import CodigoSegurancaError


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)


def _controle_fake(tela="tela qualquer", trecho_uorg=""):
    """Controle mockado: copiar_tela devolve ``tela``; extrair_texto, ``trecho_uorg``."""
    c = MagicMock(spec=ControleTerminal3270)
    c.copiar_tela.return_value = tela
    c.extrair_texto.return_value = trecho_uorg
    return c


def test_conectar_sem_otp_faz_sequencia_inicial():
    c = _controle_fake()
    conn = ConexaoTerminal3270(controle=c)  # codigo_seguranca=None
    conn.conectar()

    c.conectar.assert_called_once()
    # Sequência inicial: F3 depois F2.
    assert call("{F3}") in c.enviar_teclas.call_args_list
    assert any(
        ch.args and ch.args[0] == "{F2}" for ch in c.enviar_teclas.call_args_list
    )
    assert conn.esta_conectado() is True


def test_sem_otp_nao_digita_codigo():
    c = _controle_fake()
    ConexaoTerminal3270(controle=c).conectar()
    # Nenhuma tecla numérica de OTP foi digitada.
    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert all("{ENTER}" not in t or t == "{F3}" or t == "{F2}" for t in enviados)


def test_conectar_com_otp_digita_codigo_quando_tela_presente():
    c = _controle_fake(tela="<< COD. SEGURANCA >> informe o token")
    conn = ConexaoTerminal3270(controle=c, codigo_seguranca="123456")
    conn.conectar()
    c.enviar_teclas.assert_any_call("123456{ENTER}")


def test_otp_tela_nao_aparece_levanta_erro():
    c = _controle_fake(tela="outra tela sem o marcador")
    conn = ConexaoTerminal3270(controle=c, codigo_seguranca="123456")
    with pytest.raises(CodigoSegurancaError):
        conn.conectar()
    # Não digitou o código em tela errada.
    assert call("123456{ENTER}") not in c.enviar_teclas.call_args_list


def test_uorg_nao_cadastrada_envia_f3():
    c = _controle_fake(trecho_uorg="UORG DO CORREIO DO USUARIO NAO CADASTRADA")
    ConexaoTerminal3270(controle=c).conectar()
    # F3 do tratamento de UORG (além do F3 da sequência inicial) → ao menos 2 F3.
    f3s = [ch for ch in c.enviar_teclas.call_args_list if ch.args and ch.args[0] == "{F3}"]
    assert len(f3s) >= 2


def test_enviar_comando_e_capturar_tela_delegam():
    c = _controle_fake(tela="conteudo")
    conn = ConexaoTerminal3270(controle=c)
    conn.enviar_comando("{F8}")
    c.enviar_teclas.assert_any_call("{F8}")
    assert conn.capturar_tela() == "conteudo"


def test_esta_conectado_inicialmente_falso():
    assert ConexaoTerminal3270(controle=_controle_fake()).esta_conectado() is False


def test_otp_invalido_no_construtor_levanta():
    with pytest.raises(ValueError):
        ConexaoTerminal3270(controle=_controle_fake(), codigo_seguranca="12345")


def test_otp_unicode_no_construtor_levanta():
    # "²³⁴⁵⁶⁷": isdigit() seria True, mas não são dígitos ASCII digitáveis.
    with pytest.raises(ValueError):
        ConexaoTerminal3270(
            controle=_controle_fake(), codigo_seguranca="²³⁴⁵⁶⁷"
        )


def test_uorg_coordenadas_reais_disparam_f3(monkeypatch):
    # Usa o extrair_texto REAL sobre uma tela montada, ancorando POSICAO_UORG.
    from integra.siape.controle import ControleTerminal3270

    largura = ControleTerminal3270.CARACTERES_POR_LINHA
    mensagem = "UORG DO CORREIO DO USUARIO NAO CADASTRADA"
    linhas = [" " * largura for _ in range(23)]
    # Mensagem na linha 23 (índice 22), começando na coluna 2.
    linhas[22] = (" " + mensagem).ljust(largura)
    tela = "".join(linhas)

    c = MagicMock(spec=ControleTerminal3270)
    c.copiar_tela.return_value = tela
    c.extrair_texto.side_effect = ControleTerminal3270.extrair_texto.__get__(
        ControleTerminal3270()
    )

    ConexaoTerminal3270(controle=c).conectar()
    assert call("{F3}") in c.enviar_teclas.call_args_list
