"""Detecção de sessão do SEI caída (página de login no meio do fluxo).

Quando a sessão deixa de estar autenticada (expirou por inatividade, alguém saiu
do sistema, ou nunca houve login), o SIP redireciona qualquer requisição para a
página de login — e a próxima operação da automação falha. Este módulo detecta
essa condição e a tipifica como :class:`~integra_gov.sei.exceptions.SessaoExpiradaError`.

Mecanismo, não política: a lib detecta e levanta; relogar/pausar/abortar é
decisão de quem chama."""

from __future__ import annotations

import logging

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from .exceptions import SessaoExpiradaError
from .login import LoginSei

_log = logging.getLogger(__name__)

#: Mensagem padrão do pacote para sessão caída (única fonte).
_MSG_SESSAO_EXPIRADA = (
    "a página atual é a de login do SEI — a sessão não está mais autenticada "
    "(expirou, foi encerrada, ou não houve login)"
)


def sessao_expirada(driver) -> bool:
    """``True`` se a página atual é a de login do SEI (sessão não autenticada).

    Detecta pela presença SIMULTÂNEA dos campos ``txtUsuario`` e ``pwdSenha``
    do formulário do SIP (IDs de :class:`~integra_gov.sei.login.LoginSei` —
    estáveis entre instâncias, ao contrário da URL, que varia por órgão). A
    checagem é imediata (``find_elements``, sem espera) — roda em caminhos de
    falha e não pode custar timeout. Não distingue *por que* a sessão não está
    autenticada (expirou / derrubada / nunca logou).

    A sonda olha o contexto ATUAL antes de subir ao topo. Mecanismo verificado
    ao vivo (gate de 28/08/2026): quando a sessão é encerrada em outra aba, o
    topo continua com a página antiga do SEI renderizada; a operação seguinte
    recarrega só o **iframe**, e é dentro dele que o formulário de login
    aparece. Uma checagem que partisse direto do topo não o veria. Se o
    contexto atual estiver inutilizável (frame destacado), a decisão cai para
    o topo.

    Atenção ao critério: ``pwdSenha`` NÃO é exclusivo da página de login — o
    modal de assinatura do SEI reusa esse id. A detecção depende da CONJUNÇÃO
    com ``txtUsuario``; um frame legítimo que um dia tenha os dois campos
    produziria falso positivo.

    Em qualquer ``WebDriverException`` da fase do topo devolve ``False``: na
    dúvida, o erro original prevalece — e também porque um falso "sessão
    caiu = não executada", vindo de um driver em estado duvidoso, faria um
    orquestrador repetir a operação. Uma detecção positiva no contexto atual
    é descartada se o ``default_content()`` seguinte falhar, pela mesma
    regra.

    Efeito colateral: no caminho sem erro, deixa o driver posicionado no
    ``default_content``, mesmo quando detecta no contexto atual (se o próprio
    switch falhar, o driver fica onde estava e a função devolve ``False``).
    Quem a chamar avulso deve re-navegar depois.
    """
    try:
        try:
            caiu = _formulario_login_presente(driver)  # contexto atual (iframe?)
        except WebDriverException:
            caiu = False  # frame destacado/inutilizável — decide no topo
        driver.switch_to.default_content()
        if not caiu:
            caiu = _formulario_login_presente(driver)
    except WebDriverException:
        return False
    if caiu:
        _log.debug("Página de login do SEI detectada — sessão não autenticada")
    return caiu


def _formulario_login_presente(driver) -> bool:
    """``True`` se o contexto atual do driver tem os DOIS campos do SIP."""
    usuario = driver.find_elements(By.ID, LoginSei.TXT_USUARIO)
    senha = driver.find_elements(By.ID, LoginSei.PWD_SENHA)
    return bool(usuario) and bool(senha)


def levantar_se_sessao_expirada(
    driver, causa: BaseException | None = None
) -> None:
    """Levanta :class:`SessaoExpiradaError` se a sessão caiu; senão, no-op.

    Companheiro de :func:`sessao_expirada` para caminhos de falha: encadeia o
    erro original em ``causa`` (``raise ... from causa``). Útil também a
    orquestradores, para reclassificar uma falha qualquer::

        try:
            operacao(driver)
        except SeiError as exc:
            levantar_se_sessao_expirada(driver, exc)  # reclassifica se caiu
            raise
    """
    if sessao_expirada(driver):
        raise SessaoExpiradaError(_MSG_SESSAO_EXPIRADA) from causa
