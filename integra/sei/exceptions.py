"""Exceções tipadas do pacote ``integra.sei``."""


class SeiError(Exception):
    """Erro base da automação do SEI."""


class SeiNavegacaoError(SeiError):
    """Falha de navegação: iframe/elemento não encontrado ou página inesperada
    (por exemplo, uma sessão que não está autenticada)."""


class ProcessoNaoEncontrado(SeiError):
    """O processo pesquisado não foi aberto — não encontrado ou com número
    divergente do esperado."""


class SeiLoginError(SeiError):
    """Falha no login do SEI (formulário não carregou ou login não confirmado)."""


class CredenciaisInvalidas(SeiLoginError):
    """Usuário ou senha rejeitados pelo SEI."""


class UnidadeNaoEncontrada(SeiError):
    """A unidade pedida não está entre as que o operador pode acessar."""
