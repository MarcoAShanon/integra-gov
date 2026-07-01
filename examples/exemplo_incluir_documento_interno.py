"""Exemplo: incluir um documento interno (Despacho, Nota Técnica, …) num processo.

Pré-requisitos:
  - Você já deve estar LOGADO no SEI na sessão do navegador controlado (ou use
    o módulo `LoginSei`). Este exemplo faz o login de forma manual para não
    embutir credenciais.
  - Ajuste `TIPO_DOCUMENTO` para um tipo que exista EXATAMENTE na lista do seu
    SEI. `DOCUMENTO_MODELO` (opcional) é o protocolo de um documento base cujo
    conteúdo será clonado.
  - Use SEMPRE dados fictícios.

Após salvar, o SEI abre o editor numa janela nova; o módulo a fecha e devolve o
rótulo do documento na árvore (ex.: "Despacho 12345678").
"""

import logging

from selenium import webdriver

from integra.sei import IncluirDocumentoInterno, ProcessoSei, fechar_tela_aviso
from integra.sei.exceptions import DocumentoInternoError, ProcessoNaoEncontrado

logging.basicConfig(level=logging.INFO)

# Número de processo FICTÍCIO — troque pelo seu (o processo deve já existir).
NUMERO_PROCESSO = "00000.000000/0000-00"

TIPO_DOCUMENTO = "Despacho"     # tipo EXATO da lista do seu SEI
NOME_ARVORE = "- Encaminhamento"   # opcional (vazio = sem nome extra)
DOCUMENTO_MODELO = ""           # opcional — protocolo do documento base (modelo)
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

        # 3) Incluir o documento interno.
        try:
            rotulo = IncluirDocumentoInterno(
                driver,
                TIPO_DOCUMENTO,
                nome_arvore=NOME_ARVORE or None,
                documento_modelo=DOCUMENTO_MODELO or None,
                nivel_acesso=NIVEL_ACESSO,
                hipotese_legal=HIPOTESE_LEGAL if NIVEL_ACESSO == "restrito" else None,
            ).incluir()
        except DocumentoInternoError as exc:
            print(f"Falha ao incluir documento: {exc}")
            return

        print(f"Documento criado. Rótulo na árvore: {rotulo!r}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
