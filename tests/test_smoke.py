"""Testes de fumaça: o pacote importa e expõe metadados básicos."""

import integra
import integra.sei  # noqa: F401  (garante que o subpacote importa)


def test_versao_exposta():
    assert isinstance(integra.__version__, str)
    assert integra.__version__


def test_subpacote_sei_importa():
    import integra.sei as sei

    assert hasattr(sei, "__all__")
