# Torna tests/ um pacote: os módulos de teste do e-SIAPE importam
# tests._pdf_sintetico, e sem __init__.py isso só resolve quando o pytest é
# invocado como `python -m pytest` (que põe o CWD no sys.path). Com o pacote,
# o pytest insere a RAIZ do repo no sys.path e o import vale em qualquer
# invocação — inclusive o `pytest -q` do CI.
