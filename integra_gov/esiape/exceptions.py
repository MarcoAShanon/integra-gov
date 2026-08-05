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
