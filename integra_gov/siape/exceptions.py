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


class InstituidorObrigatorio(SiapeError):
    """A pensionista tem mais de um instituidor e ``matricula_instituidor``
    não foi informada (ou não está entre as opções da tela).

    Attributes:
        matriculas_encontradas: matrículas listadas na tela de seleção,
            para o chamador decidir qual usar.
    """

    def __init__(self, matriculas_encontradas: list[str]):
        self.matriculas_encontradas = list(matriculas_encontradas)
        super().__init__(
            "a pensionista tem mais de um instituidor; informe "
            "matricula_instituidor. Matrículas na tela: "
            + (", ".join(self.matriculas_encontradas) or "(nenhuma legível)")
        )


class FichaIndisponivel(SiapeError):
    """O fluxo não chegou à tela da ficha (matrícula inexistente ou sem
    acesso na habilitação ativa). Distinta de "ano sem dados"."""


class ExtracaoFichaInterrompida(SiapeError):
    """A extração abortou no meio da faixa de anos.

    Os PDFs dos anos já salvos ficam no disco; nenhum resultado parcial é
    devolvido como completo.

    Attributes:
        anos_processados: anos concluídos (com ou sem dados) antes da falha.
        causa: exceção original.
    """

    def __init__(self, anos_processados: list[int], causa: BaseException | None):
        self.anos_processados = list(anos_processados)
        self.causa = causa
        super().__init__(
            f"extração interrompida após os anos {self.anos_processados} "
            f"(causa: {causa!r})"
        )
