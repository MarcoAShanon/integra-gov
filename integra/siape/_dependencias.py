"""Importação protegida do ``pywinauto`` (extra opcional ``siape``).

O ``pywinauto`` é Windows-only e não é dependência do núcleo do pacote. Este
módulo o importa de forma tolerante: se não estiver instalado, os símbolos ficam
``None`` e :func:`exigir_pywinauto` levanta um erro claro só quando o terminal
3270 for de fato usado — assim o núcleo e a CI (Linux) seguem funcionando, e os
testes podem substituir ``Application``/``clipboard`` por mocks.
"""

from __future__ import annotations

from .exceptions import PywinautoIndisponivel

try:
    from pywinauto import Application, clipboard
    from pywinauto.findwindows import ElementNotFoundError

    PYWINAUTO_DISPONIVEL = True
except ImportError:  # pywinauto ausente (ex.: Linux/CI ou extra não instalado)
    Application = None
    clipboard = None

    class ElementNotFoundError(Exception):  # placeholder p/ blocos ``except``
        """Substituto de ``pywinauto.findwindows.ElementNotFoundError`` quando o
        pywinauto não está instalado."""

    PYWINAUTO_DISPONIVEL = False


def exigir_pywinauto() -> None:
    """Levanta :class:`PywinautoIndisponivel` se o pywinauto não estiver presente."""
    if Application is None:
        raise PywinautoIndisponivel(
            "o módulo SIAPE (terminal 3270) requer o pywinauto. Instale com "
            "'pip install integra-gov[siape]' (somente Windows)."
        )
