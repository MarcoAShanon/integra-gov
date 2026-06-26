"""integra.sei — automação do SEI (Sistema Eletrônico de Informações).

Módulos, portados de forma incremental (já generalizados, testados e
documentados):

  - ``iframes``           : navegação entre os iframes do SEI (3.x/4.x)  ✅
  - ``processo``          : acesso a um processo existente               ✅
  - ``login``             : autenticação no SEI                          ✅ ¹
  - ``exceptions``        : exceções tipadas do pacote                   ✅
  - ``iniciar_processo``  : criação de um novo processo (planejado)

¹ ``login`` ainda não foi verificado contra um SEI real — use com cautela.
"""

from .exceptions import (
    CredenciaisInvalidas,
    ProcessoNaoEncontrado,
    SeiError,
    SeiLoginError,
    SeiNavegacaoError,
)
from .iframes import IframesSei, switch_to_iframe_visualizacao
from .login import LoginSei, montar_url_login
from .processo import ProcessoSei

__all__ = [
    "CredenciaisInvalidas",
    "IframesSei",
    "LoginSei",
    "ProcessoNaoEncontrado",
    "ProcessoSei",
    "SeiError",
    "SeiLoginError",
    "SeiNavegacaoError",
    "montar_url_login",
    "switch_to_iframe_visualizacao",
]
