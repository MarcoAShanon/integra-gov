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
  - ``iniciar_processo``  : criação de um novo processo                  ✅
  - ``nivel_acesso``      : nível de acesso (público/restrito) — compartilhado ✅
  - ``barra_icones``      : clique em ícones da barra do documento — compartilhado ✅
  - ``inserir_documento_externo`` : inclui um documento externo (upload)  ✅
  - ``gerar_documento``   : tela "Gerar Documento" (escolha do tipo) — compartilhado ✅
  - ``incluir_documento_interno`` : inclui um documento interno (Despacho…) ✅
  - ``editar_conteudo``   : substitui placeholders no editor (CKEditor)    ✅
"""

from .barra_icones import clicar_icone_barra
from .editar_conteudo import EditarConteudo, data_por_extenso
from .exceptions import (
    CredenciaisInvalidas,
    DocumentoExternoError,
    DocumentoInternoError,
    EditarConteudoError,
    IniciarProcessoError,
    NavegadorError,
    NivelAcessoError,
    ProcessoNaoEncontrado,
    SeiError,
    SeiLoginError,
    SeiNavegacaoError,
    UnidadeNaoEncontrada,
)
from .gerar_documento import abrir_gerar_documento
from .iframes import IframesSei, switch_to_iframe_visualizacao
from .incluir_documento_interno import IncluirDocumentoInterno
from .iniciar_processo import IniciarProcesso
from .inserir_documento_externo import InserirDocumentoExterno
from .login import LoginSei, montar_url_login
from .navegador import (
    criar_driver_chrome,
    encerrar_chrome,
    encerrar_chromedriver_orfaos,
)
from .nivel_acesso import configurar_nivel_acesso
from .processo import ProcessoSei
from .selecao_unidade import SelecaoUnidade, Unidade
from .tela_aviso import fechar_tela_aviso

__all__ = [
    "CredenciaisInvalidas",
    "DocumentoExternoError",
    "DocumentoInternoError",
    "EditarConteudo",
    "EditarConteudoError",
    "IframesSei",
    "IncluirDocumentoInterno",
    "IniciarProcesso",
    "IniciarProcessoError",
    "InserirDocumentoExterno",
    "LoginSei",
    "NavegadorError",
    "NivelAcessoError",
    "ProcessoNaoEncontrado",
    "ProcessoSei",
    "SeiError",
    "SeiLoginError",
    "SeiNavegacaoError",
    "SelecaoUnidade",
    "Unidade",
    "UnidadeNaoEncontrada",
    "abrir_gerar_documento",
    "clicar_icone_barra",
    "configurar_nivel_acesso",
    "criar_driver_chrome",
    "data_por_extenso",
    "encerrar_chrome",
    "encerrar_chromedriver_orfaos",
    "fechar_tela_aviso",
    "montar_url_login",
    "switch_to_iframe_visualizacao",
]
