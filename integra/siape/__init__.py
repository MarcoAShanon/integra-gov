"""integra.siape — automação do SIAPE via terminal 3270 (emulador IBM HOD).

⚠️ **Subpacote opcional, Windows-only.** Requer o extra ``siape``::

    pip install integra-gov[siape]

que instala o ``pywinauto``. A automação se atacha a um emulador de terminal
3270 **já aberto** (você abre o emulador e se autentica); a biblioteca apenas
controla o terminal — não inicia o emulador nem digita credenciais.

Módulos:
  - ``acesso_web``   : início de acesso pela web (SIAPENet) + captura do OTP    ✅ ¹ ²
  - ``lancador``     : executa o módulo HOD baixado e abre o Terminal 3270      ✅ ¹
  - ``controle``     : interação base com o terminal (ler tela, enviar teclas)  ✅ ¹
  - ``conexao``      : acesso/login (código de segurança OTP)                   ✅ ¹
  - ``habilitacao``  : troca de habilitação (ÓRGÃO/UPAG) via TROCAHAB           ✅ ¹
  - ``exceptions``   : exceções tipadas do subpacote                           ✅

¹ Portado, testado (Selenium/pywinauto mockado) e **verificado ao vivo** no
SIAPE: acesso web → captura do OTP → lançamento do HOD → terminal → troca de
habilitação (TROCAHAB).
² ``acesso_web`` é só Selenium (não exige o extra ``siape``/pywinauto).
"""

from .acesso_web import AcessoSiapeWeb
from .conexao import ConexaoTerminal3270
from .controle import ControleTerminal3270
from .exceptions import (
    AcessoSiapeError,
    CodigoSegurancaError,
    HabilitacaoNaoEncontrada,
    LancamentoHodError,
    PywinautoIndisponivel,
    SessaoSiapePerdida,
    SiapeError,
    TerminalError,
    TerminalNaoEncontrado,
    TokenOtpError,
)
from .habilitacao import TrocaHabilitacao
from .lancador import LancadorHod

__all__ = [
    "AcessoSiapeError",
    "AcessoSiapeWeb",
    "CodigoSegurancaError",
    "ConexaoTerminal3270",
    "ControleTerminal3270",
    "HabilitacaoNaoEncontrada",
    "LancadorHod",
    "LancamentoHodError",
    "PywinautoIndisponivel",
    "SessaoSiapePerdida",
    "SiapeError",
    "TerminalError",
    "TerminalNaoEncontrado",
    "TokenOtpError",
    "TrocaHabilitacao",
]
