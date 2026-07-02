"""Exceções tipadas do pacote ``integra.sei``."""


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


class SeiLoginError(SeiError):
    """Falha no login do SEI (formulário não carregou ou login não confirmado)."""


class CredenciaisInvalidas(SeiLoginError):
    """Usuário ou senha rejeitados pelo SEI."""


class UnidadeNaoEncontrada(SeiError):
    """A unidade pedida não está entre as que o operador pode acessar."""
