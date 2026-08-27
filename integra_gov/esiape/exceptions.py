"""Exceções tipadas do subpacote e-SIAPE."""

from __future__ import annotations


class EsiapeError(Exception):
    """Base de todos os erros do e-SIAPE."""


class MenuInacessivel(EsiapeError):
    """O menu (lupa de transações) não ficou acessível nem após a máquina de
    estados de recuperação. Se a sessão renasceu, o PIN do certificado pode
    estar sendo pedido numa janela do Windows (fora do alcance do Selenium)."""


class AutenticacaoNaoConfirmada(EsiapeError):
    """A confirmação no app SERPRO ID não chegou dentro do timeout."""


class TransacaoNaoAbriu(EsiapeError):
    """A tela da transação não confirmou (o seletor exclusivo não apareceu).

    Attributes:
        transacao: código da transação pedida.
        seletor_confirmacao: seletor CSS que deveria ter aparecido.
    """

    def __init__(self, transacao: str, seletor_confirmacao: str):
        self.transacao = transacao
        self.seletor_confirmacao = seletor_confirmacao
        super().__init__(
            f"a tela da transação {transacao} não abriu "
            f"(sem {seletor_confirmacao} em nenhum frame visível)"
        )


class HabilitacaoNaoEncontrada(EsiapeError):
    """O órgão pedido não está na grade de habilitações do usuário.

    Attributes:
        orgao: órgão pedido.
        codigos_visiveis: códigos que a grade mostrou.
    """

    def __init__(self, orgao: str, codigos_visiveis: list[str]):
        self.orgao = orgao
        self.codigos_visiveis = list(codigos_visiveis)
        super().__init__(
            f"habilitação para o órgão {orgao} não encontrada na grade "
            f"(códigos visíveis: {', '.join(self.codigos_visiveis) or 'nenhum'})"
        )


class FichaEsiapeIndisponivel(EsiapeError):
    """A matrícula não foi encontrada na habilitação ativa (a mensagem traz
    o que o CIS mostrou). Distinta de "bloco sem dados"."""


class ExtracaoFichaEsiapeInterrompida(EsiapeError):
    """A extração da ficha anual abortou no meio da faixa de blocos.

    Os PDFs dos blocos já salvos ficam no disco; nenhum resultado parcial é
    devolvido como completo.

    Attributes:
        blocos_processados: blocos ``(ano_de, ano_ate)`` concluídos antes da
            falha (com ou sem dados).
        causa: exceção original.
    """

    def __init__(self, blocos_processados: list[tuple[int, int]],
                 causa: BaseException | None):
        self.blocos_processados = list(blocos_processados)
        self.causa = causa
        super().__init__(
            f"extração interrompida após os blocos {self.blocos_processados} "
            f"(causa: {causa!r})"
        )


class PdfImpressoIlegivel(EsiapeError):
    """O PDF baixado da impressão não tem texto legível por máquina.

    A tela imprime, o arquivo aparece na pasta e tem a aparência correta — mas
    se o driver de impressão converteu as fontes em contorno vetorial, não
    sobra um único caractere extraível. O caso conhecido é a impressora
    virtual ``Microsoft Print to PDF`` do Windows.

    Sem esta verificação o arquivo atravessava o restante do fluxo em silêncio
    e a ficha só se revelava inútil muito depois, na hora de ler. Aqui a
    extração aborta no bloco em que o problema apareceu.

    Attributes:
        caminho: o PDF ilegível, deixado no disco para inspeção.
        bloco: o par ``(ano_de, ano_ate)`` que estava sendo impresso.
    """

    def __init__(self, caminho, bloco, motivo: str) -> None:
        self.caminho = caminho
        self.bloco = bloco
        super().__init__(
            f"o PDF do bloco {bloco[0]}-{bloco[1]} saiu ilegível por máquina "
            f"({motivo}): {caminho}. Confira a configuração de impressão do "
            f"Chrome — o destino tem de ser o 'Salvar como PDF' nativo; a "
            f"impressora virtual 'Microsoft Print to PDF' do Windows converte "
            f"as fontes em contorno e destrói o texto. "
            f"Ver docs/uso-basico.md, seção 'Configuração do Chrome'")
