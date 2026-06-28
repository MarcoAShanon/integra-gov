"""integra.sei — automação do SEI (Sistema Eletrônico de Informações).

Módulos, portados de forma incremental (já generalizados, testados e
documentados):

  - ``navegador``         : abre o Chrome (ajustes gov) + limpa órfãos   ✅
  - ``iframes``           : navegação entre os iframes do SEI (3.x/4.x)  ✅
  - ``processo``          : acesso a um processo existente               ✅
  - ``login``             : autenticação no SEI                          ✅
  - ``selecao_unidade``   : troca a unidade de trabalho                  ✅
  - ``tela_aviso``        : fecha o aviso pós-login que bloqueia a tela  ✅
  - ``exceptions``        : exceções tipadas do pacote                   ✅
  - ``iniciar_processo``  : criação de um novo processo (planejado)
"""

from .exceptions import (
    CredenciaisInvalidas,
    NavegadorError,
    ProcessoNaoEncontrado,
    SeiError,
    SeiLoginError,
    SeiNavegacaoError,
    UnidadeNaoEncontrada,
)
from .iframes import IframesSei, switch_to_iframe_visualizacao
from .login import LoginSei, montar_url_login
from .navegador import (
    criar_driver_chrome,
    encerrar_chrome,
    encerrar_chromedriver_orfaos,
)
from .processo import ProcessoSei
from .selecao_unidade import SelecaoUnidade, Unidade
from .tela_aviso import fechar_tela_aviso

__all__ = [
    "CredenciaisInvalidas",
    "IframesSei",
    "LoginSei",
    "NavegadorError",
    "ProcessoNaoEncontrado",
    "ProcessoSei",
    "SeiError",
    "SeiLoginError",
    "SeiNavegacaoError",
    "SelecaoUnidade",
    "Unidade",
    "UnidadeNaoEncontrada",
    "criar_driver_chrome",
    "encerrar_chrome",
    "encerrar_chromedriver_orfaos",
    "fechar_tela_aviso",
    "montar_url_login",
    "switch_to_iframe_visualizacao",
]
