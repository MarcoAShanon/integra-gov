"""integra.sei — automação do SEI (Sistema Eletrônico de Informações).

Módulos, portados de forma incremental (já generalizados, testados e
documentados):

  - ``iframes``           : navegação entre os iframes do SEI (3.x/4.x)  ✅
  - ``processo``          : acesso a um processo existente               ✅
  - ``exceptions``        : exceções tipadas do pacote                   ✅
  - ``login``             : autenticação no SEI (planejado)
  - ``iniciar_processo``  : criação de um novo processo (planejado)
"""

from .exceptions import ProcessoNaoEncontrado, SeiError, SeiNavegacaoError
from .iframes import IframesSei, switch_to_iframe_visualizacao
from .processo import ProcessoSei

__all__ = [
    "IframesSei",
    "ProcessoNaoEncontrado",
    "ProcessoSei",
    "SeiError",
    "SeiNavegacaoError",
    "switch_to_iframe_visualizacao",
]
