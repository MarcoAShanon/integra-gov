"""Automação do e-SIAPE web (CIS/Software AG) — fundação.

Navegação por frames visíveis, travessia de popups/relogin do SERPRO,
acesso via SERPRO ID (você autentica), troca de habilitação (TROCAHAB) e
dados pessoais de servidor (CDCOINDPES, lidos do PDF impresso) e de
pensionista (CDCOPSBENE, lidos do formulário).

Exemplo mínimo::

    from integra_gov.sei import criar_driver_chrome
    from integra_gov.esiape import AcessoEsiape, TrocaHabilitacaoEsiape

    driver = criar_driver_chrome()
    AcessoEsiape(driver).executar()                       # você confirma no app
    TrocaHabilitacaoEsiape(driver, orgao="00000").trocar()  # órgão fictício
"""

from .acesso import AcessoEsiape
from .dados_funcionais import DadosFuncionais, DadosFuncionaisOrgao
from .dados_pensionista import DadosPensionista, DadosPessoaisPensionista
from .dados_pessoais import DadosPessoais, DadosPessoaisServidor, ler_dados_pessoais
from .exceptions import (
    AutenticacaoNaoConfirmada,
    DadosPessoaisIndisponiveis,
    EsiapeError,
    ExtracaoFichaEsiapeInterrompida,
    FichaEsiapeIndisponivel,
    HabilitacaoNaoEncontrada,
    MenuInacessivel,
    PdfImpressoIlegivel,
    TransacaoNaoAbriu,
)
from .ficha_anual import FichaAnualServidor, ResultadoFichaEsiape
from .ficha_multi_orgao import FichaMultiOrgao, ResultadoMultiOrgao
from .habilitacao import TrocaHabilitacaoEsiape
from .impressao import imprimir_via_popup
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
    "DadosFuncionais",
    "DadosFuncionaisOrgao",
    "DadosPensionista",
    "DadosPessoaisPensionista",
    "DadosPessoais",
    "DadosPessoaisIndisponiveis",
    "DadosPessoaisServidor",
    "EsiapeError",
    "ExtracaoFichaEsiapeInterrompida",
    "FichaAnualServidor",
    "FichaEsiapeIndisponivel",
    "FichaMultiOrgao",
    "HabilitacaoNaoEncontrada",
    "MenuInacessivel",
    "PdfImpressoIlegivel",
    "ResultadoFichaEsiape",
    "ResultadoMultiOrgao",
    "TransacaoNaoAbriu",
    "TrocaHabilitacaoEsiape",
    "esperar_seletor",
    "fechar_janelas_extras",
    "garantir_menu",
    "imprimir_via_popup",
    "ler_dados_pessoais",
    "limpar_flag_relogin",
    "limpar_overlay",
    "navegar_para_transacao",
    "procurar_em_frames",
    "relogin_pendente",
]
