"""integra.sei — automação do SEI (Sistema Eletrônico de Informações).

Módulos, portados de forma incremental (já generalizados, testados e
documentados):

  - ``iframes``           : navegação entre os iframes do SEI, tolerante às
                            estruturas do SEI 3.x e 4.x  ✅
  - ``processo``          : acesso a um processo existente (planejado)
  - ``login``             : autenticação no SEI (planejado)
  - ``iniciar_processo``  : criação de um novo processo (planejado)
"""

from .iframes import IframesSei, switch_to_iframe_visualizacao

__all__ = ["IframesSei", "switch_to_iframe_visualizacao"]
