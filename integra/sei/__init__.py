"""integra.sei — automação do SEI (Sistema Eletrônico de Informações).

Módulos planejados, portados de forma incremental (já generalizados, testados
e documentados):

  - ``login``             : autenticação no SEI
  - ``processo``          : acesso a um processo existente (via pesquisa rápida)
  - ``iframes``           : navegação entre os iframes do SEI, tolerante às
                            estruturas do SEI 3.x e 4.x
  - ``iniciar_processo``  : criação de um novo processo
  - _(demais conforme o roadmap)_

Nada é exposto ainda — este é o esqueleto inicial. Veja o CHANGELOG.
"""

from typing import List

__all__: List[str] = []
