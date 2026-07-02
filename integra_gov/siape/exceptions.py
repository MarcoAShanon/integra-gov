"""Exceções tipadas do subpacote ``integra_gov.siape`` (terminal 3270)."""


class SiapeError(Exception):
    """Erro base da automação do SIAPE via terminal 3270."""


class PywinautoIndisponivel(SiapeError):
    """O extra ``siape`` (pywinauto) não está instalado.

    Instale com ``pip install integra-gov[siape]`` (somente Windows).
    """


class TerminalNaoEncontrado(SiapeError):
    """A janela do Terminal 3270 (emulador HOD) não foi encontrada.

    O emulador precisa estar **aberto** antes de automatizar — a biblioteca
    apenas se atacha a ele, não o inicia.
    """


class TerminalError(SiapeError):
    """Falha ao interagir com o Terminal 3270 (ler a tela ou enviar teclas)."""


class SessaoSiapePerdida(SiapeError):
    """A sessão SIAPE caiu durante a automação (estado irrecuperável).

    Diferente de um erro de negócio do SIAPE (mensagem na tela): aqui o próprio
    terminal não respondeu mais (janela sumiu, duplicou ou desconectou). A
    automação deve ser interrompida e a sessão reiniciada.
    """


class CodigoSegurancaError(SiapeError):
    """A tela de código de segurança (OTP) não foi detectada ou não foi aceita."""


class HabilitacaoNaoEncontrada(SiapeError):
    """A habilitação (ÓRGÃO/UPAG) pedida não foi encontrada nas páginas do SIAPE."""


class AcessoSiapeError(SiapeError):
    """Falha no início de acesso ao SIAPE pela web (portal SIAPENet)."""


class TokenOtpError(AcessoSiapeError):
    """O código OTP não pôde ser capturado/validado na página do SIAPENet."""


class LancamentoHodError(SiapeError):
    """Falha ao localizar/executar o módulo HOD baixado ou ao chegar ao terminal."""


class TransacaoError(SiapeError):
    """Falha ao acessar/confirmar uma transação do SIAPE (``>COMANDO``)."""
