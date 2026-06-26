"""Exceções tipadas do pacote ``integra.sei``."""


class SeiError(Exception):
    """Erro base da automação do SEI."""


class SeiNavegacaoError(SeiError):
    """Falha de navegação: iframe/elemento não encontrado ou página inesperada
    (por exemplo, uma sessão que não está autenticada)."""


class ProcessoNaoEncontrado(SeiError):
    """O processo pesquisado não foi aberto — não encontrado ou com número
    divergente do esperado."""
