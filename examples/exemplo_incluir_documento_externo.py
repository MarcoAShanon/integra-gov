"""Exemplo: incluir um documento externo (upload de arquivo) num processo.

Pré-requisitos:
  - Você já deve estar LOGADO no SEI na sessão do navegador controlado (ou use
    o módulo `LoginSei`). Este exemplo faz o login de forma manual para não
    embutir credenciais.
  - Ajuste `TIPO_SERIE` para uma opção que exista EXATAMENTE no dropdown
    "Tipo do Documento" do seu SEI, e `ARQUIVO` para um caminho válido.
  - Use SEMPRE dados fictícios.

O upload vai direto ao `<input type=file>` do SEI (sem janela nativa nem
`pywinauto`). `InserirDocumentoExterno.inserir()` devolve o `nome_arvore`.
"""

import logging

from selenium import webdriver

from integra.sei import InserirDocumentoExterno, ProcessoSei, fechar_tela_aviso
from integra.sei.exceptions import DocumentoExternoError, ProcessoNaoEncontrado

logging.basicConfig(level=logging.INFO)

# Número de processo FICTÍCIO — troque pelo seu (o processo deve já existir).
NUMERO_PROCESSO = "00000.000000/0000-00"

# Ajuste para o texto EXATO do dropdown "Tipo do Documento" do seu SEI.
TIPO_SERIE = "Ofício"
NOME_ARVORE = "Ofício 123 - Resposta"   # rótulo do documento na árvore
ARQUIVO = "caminho/para/arquivo.pdf"    # caminho do arquivo (deve existir)
NIVEL_ACESSO = "publico"   # ou "restrito" (aí informe HIPOTESE_LEGAL)
# Texto EXATO da opção no dropdown do SEI (só usado se NIVEL_ACESSO="restrito"):
HIPOTESE_LEGAL = "Informação Pessoal (Art. 31 da Lei nº 12.527/2011)"


def main() -> None:
    # 1) Prepare o webdriver e faça login no SEI (aqui, manualmente).
    driver = webdriver.Chrome()
    try:
        driver.get("https://SEU-SEI.exemplo.gov.br/sei/")
        input("Faça login no SEI e tecle ENTER para continuar...")

        # O SEI costuma exibir um aviso pós-login que bloqueia a tela.
        fechar_tela_aviso(driver)

        # 2) Abrir o processo que vai receber o documento.
        try:
            ProcessoSei(driver, NUMERO_PROCESSO).acessar()
        except ProcessoNaoEncontrado:
            print(f"Processo {NUMERO_PROCESSO} não encontrado.")
            return

        # 3) Incluir o documento externo (upload).
        try:
            nome = InserirDocumentoExterno(
                driver,
                TIPO_SERIE,
                NOME_ARVORE,
                ARQUIVO,
                nivel_acesso=NIVEL_ACESSO,
                hipotese_legal=HIPOTESE_LEGAL if NIVEL_ACESSO == "restrito" else None,
            ).inserir()
        except DocumentoExternoError as exc:
            print(f"Falha ao incluir documento: {exc}")
            return

        print(f"Documento incluído. Nome na árvore: {nome!r}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
