"""Exceções tipadas do pacote ``integra_gov.sei``."""


class SeiError(Exception):
    """Erro base da automação do SEI."""


class SeiNavegacaoError(SeiError):
    """Falha de navegação: iframe/elemento não encontrado ou página inesperada
    (por exemplo, uma sessão que não está autenticada)."""


class NavegadorError(SeiError):
    """Não foi possível abrir o navegador (ex.: o Chrome não subiu mesmo após as
    tentativas — ``"Chrome instance exited"`` em ambiente gerenciado)."""


class ProcessoNaoEncontrado(SeiError):
    """O processo pesquisado não foi aberto — não encontrado ou com número
    divergente do esperado."""


class IniciarProcessoError(SeiError):
    """Falha ao iniciar (criar) um novo processo: um campo/botão do formulário
    não foi encontrado ou o SEI não aceitou o processo."""


class NivelAcessoError(SeiError):
    """Falha ao configurar o nível de acesso (Público/Restrito + hipótese legal)
    de um processo ou documento — radio/dropdown não encontrado ou hipótese
    legal ausente no dropdown."""


class DocumentoExternoError(SeiError):
    """Falha ao incluir um documento externo: um campo/botão do formulário não
    foi encontrado, o arquivo não pôde ser anexado/confirmado, ou o SEI não
    aceitou o documento."""


class DocumentoInternoError(SeiError):
    """Falha ao incluir um documento interno (Despacho, Nota Técnica, …): um
    campo/botão do formulário não foi encontrado, o SEI não aceitou o documento,
    ou a criação não pôde ser confirmada (editor não abriu / rótulo ilegível)."""


class EditarConteudoError(SeiError):
    """Falha ao editar o conteúdo de um documento no editor do SEI: o editor
    não abriu/carregou, um placeholder pedido não foi encontrado no texto, ou o
    salvamento não pôde ser executado."""


class AssinaturaError(SeiError):
    """Falha ao assinar um documento no SEI: o modal de assinatura não abriu, a
    senha foi recusada, ou a assinatura não pôde ser **confirmada** (o módulo
    nunca reporta "assinado" sem confirmação)."""


class SelecaoDocumentoError(SeiError):
    """Falha ao selecionar um documento na árvore: nenhum nó casou com o texto,
    ou vários casaram sem um ``indice`` para desambiguar."""


class SeiLoginError(SeiError):
    """Falha no login do SEI (formulário não carregou ou login não confirmado)."""


class CredenciaisInvalidas(SeiLoginError):
    """Usuário ou senha rejeitados pelo SEI."""


class UnidadeNaoEncontrada(SeiError):
    """A unidade pedida não está entre as que o operador pode acessar."""


class MarcadorError(SeiError):
    """Falha ao operar marcadores no SEI: a tela/tabela de marcadores ou o modal
    "Gerenciar Marcador" não foi encontrado, o marcador pedido não existe (na
    lista ou no dropdown), ou a inclusão/remoção não pôde ser confirmada."""


class ControlePrazoError(SeiError):
    """Falha ao definir/excluir o controle de prazo de um processo: o ícone
    "Controle de Prazo", um campo/botão do modal, ou a confirmação da operação
    não foi encontrado/executado."""


class ConcluirProcessoError(SeiError):
    """Falha ao concluir (encerrar) um processo no SEI: o ícone "Concluir
    Processo" ou o formulário/botão de conclusão não foi encontrado, ou a
    conclusão não pôde ser executada."""


class ProcessoBloqueadoError(ConcluirProcessoError):
    """O SEI recusou concluir o processo porque há documento(s) com acesso
    restrito / hipótese legal pendente. É subclasse de ``ConcluirProcessoError``
    para o chamador distinguir "bloqueado" (estado real) de uma falha técnica."""


class EnviarProcessoError(SeiError):
    """Falha ao enviar um processo a outra unidade: o ícone/formulário de envio
    não foi encontrado, a unidade destino não pôde ser selecionada (autocomplete
    não a inseriu na lista), ou o SEI recusou o envio (alerta de erro)."""
