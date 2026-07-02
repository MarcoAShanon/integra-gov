"""Exemplo: apontar um documento existente pelo protocolo e assiná-lo.

⚠️ Assinar é um ato oficial e pessoal. Use um documento de teste. A senha vem do
getpass — não fica salva, não é registrada em log.

Pré-requisitos:
  - Você já deve estar LOGADO no SEI na sessão do navegador controlado (ou use
    o módulo `LoginSei`). Este exemplo faz o login de forma manual para não
    embutir credenciais.
  - Ajuste NUMERO_PROCESSO e PROTOCOLO_DOC (o número de um documento do processo
    que você tenha permissão de assinar).
  - Use SEMPRE dados fictícios.

`DocumentosArvore.selecionar(protocolo)` aponta o documento (expandindo as
pastas colapsadas); `AssinarDocumento(driver, senha).assinar()` age sobre o
documento selecionado e só conclui se o SEI confirmar a assinatura.
"""

import logging
from getpass import getpass

from selenium import webdriver

from integra.sei import (
    AssinarDocumento,
    DocumentosArvore,
    ProcessoSei,
    fechar_tela_aviso,
)
from integra.sei.exceptions import (
    AssinaturaError,
    ProcessoNaoEncontrado,
    SelecaoDocumentoError,
)

logging.basicConfig(level=logging.INFO)

# Dados FICTÍCIOS — troque pelos seus.
NUMERO_PROCESSO = "00000.000000/0000-00"
PROTOCOLO_DOC = "12345678"   # número do documento a assinar


def main() -> None:
    driver = webdriver.Chrome()
    try:
        driver.get("https://SEU-SEI.exemplo.gov.br/sei/")
        input("Faça login no SEI e tecle ENTER para continuar...")
        fechar_tela_aviso(driver)

        try:
            ProcessoSei(driver, NUMERO_PROCESSO).acessar()
        except ProcessoNaoEncontrado:
            print(f"Processo {NUMERO_PROCESSO} não encontrado.")
            return

        # 1) Apontar o documento existente pelo protocolo (expande as pastas).
        arvore = DocumentosArvore(driver)
        try:
            doc = arvore.selecionar(PROTOCOLO_DOC)
        except SelecaoDocumentoError as exc:
            print(f"Não foi possível apontar o documento: {exc}")
            return
        print(f"Documento apontado: {doc.texto!r}")

        # 2) Assinar (senha do próprio servidor, obtida com segurança).
        try:
            AssinarDocumento(driver, senha=getpass("Senha do SEI: ")).assinar()
        except AssinaturaError as exc:
            print(f"Falha ao assinar: {exc}")
            return

        print("Documento assinado com sucesso.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
