"""Testes de fumaça: o pacote importa e expõe metadados básicos."""

import integra_gov
import integra_gov.sei  # noqa: F401  (garante que o subpacote importa)


def test_versao_exposta():
    assert isinstance(integra_gov.__version__, str)
    assert integra_gov.__version__


def test_subpacote_sei_importa():
    import integra_gov.sei as sei

    assert hasattr(sei, "__all__")
