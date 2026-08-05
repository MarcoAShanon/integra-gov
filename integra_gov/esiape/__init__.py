"""Automação do e-SIAPE web (CIS/Software AG) — fundação.

Navegação por frames visíveis, travessia de popups/relogin do SERPRO,
acesso via SERPRO ID (você autentica) e troca de habilitação (TROCAHAB).
"""

from .exceptions import (
    AutenticacaoNaoConfirmada,
    EsiapeError,
    HabilitacaoNaoEncontrada,
    MenuInacessivel,
    TransacaoNaoAbriu,
)

__all__ = [
    "AutenticacaoNaoConfirmada",
    "EsiapeError",
    "HabilitacaoNaoEncontrada",
    "MenuInacessivel",
    "TransacaoNaoAbriu",
]
