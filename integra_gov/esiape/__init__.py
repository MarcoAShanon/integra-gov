"""Automação do e-SIAPE web (CIS/Software AG) — fundação.

Navegação por frames visíveis, travessia de popups/relogin do SERPRO,
acesso via SERPRO ID (você autentica) e troca de habilitação (TROCAHAB).

Exemplo mínimo::

    from integra_gov.sei import criar_driver_chrome
    from integra_gov.esiape import AcessoEsiape, TrocaHabilitacaoEsiape

    driver = criar_driver_chrome()
    AcessoEsiape(driver).executar()                       # você confirma no app
    TrocaHabilitacaoEsiape(driver, orgao="00000").trocar()  # órgão fictício
"""

from .acesso import AcessoEsiape
from .exceptions import (
    AutenticacaoNaoConfirmada,
    EsiapeError,
    ExtracaoFichaEsiapeInterrompida,
    FichaEsiapeIndisponivel,
    HabilitacaoNaoEncontrada,
    MenuInacessivel,
    TransacaoNaoAbriu,
)
from .habilitacao import TrocaHabilitacaoEsiape
from .navegacao import (
    esperar_seletor,
    fechar_janelas_extras,
    garantir_menu,
    limpar_flag_relogin,
    limpar_overlay,
    navegar_para_transacao,
    procurar_em_frames,
    relogin_pendente,
)

__all__ = [
    "AcessoEsiape",
    "AutenticacaoNaoConfirmada",
    "EsiapeError",
    "ExtracaoFichaEsiapeInterrompida",
    "FichaEsiapeIndisponivel",
    "HabilitacaoNaoEncontrada",
    "MenuInacessivel",
    "TransacaoNaoAbriu",
    "TrocaHabilitacaoEsiape",
    "esperar_seletor",
    "fechar_janelas_extras",
    "garantir_menu",
    "limpar_flag_relogin",
    "limpar_overlay",
    "navegar_para_transacao",
    "procurar_em_frames",
    "relogin_pendente",
]
