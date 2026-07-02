"""Exemplo: gerar um documento a partir de um modelo e preencher os placeholders.

Este é o fluxo de **escala**: um documento modelo (mantido no próprio SEI, com
marcadores como {{NOME}}) é clonado e preenchido a cada execução. Repetindo o
laço sobre uma planilha de dados, gera-se um documento por linha.

Pré-requisitos:
  - Você já deve estar LOGADO no SEI na sessão do navegador controlado (ou use
    o módulo `LoginSei`). Este exemplo faz o login de forma manual para não
    embutir credenciais.
  - Crie no seu SEI um "Despacho modelo" com os placeholders usados abaixo e
    ajuste `DOCUMENTO_MODELO` para o protocolo dele.
  - Use SEMPRE dados fictícios.

Regra dos placeholders: digite cada marcador inteiro e de uma vez no modelo,
sem formatar só um pedaço dentro das chaves (senão o editor o fragmenta e a
substituição não o encontra).
"""

import logging

from selenium import webdriver

from integra_gov.sei import (
    EditarConteudo,
    IncluirDocumentoInterno,
    ProcessoSei,
    data_por_extenso,
    fechar_tela_aviso,
)
from integra_gov.sei.exceptions import (
    DocumentoInternoError,
    EditarConteudoError,
    ProcessoNaoEncontrado,
)

logging.basicConfig(level=logging.INFO)

# Número de processo FICTÍCIO — troque pelo seu (o processo deve já existir).
NUMERO_PROCESSO = "00000.000000/0000-00"

TIPO_DOCUMENTO = "Despacho"
DOCUMENTO_MODELO = "12345678"   # protocolo do despacho MODELO (com placeholders)

# Uma linha de "dados" — num caso real, isto viria de uma planilha, num laço.
SUBSTITUICOES = {
    "{{PROCESSO}}": "00000.000000/0000-00",
    "{{NOME}}": "MARIA DA SILVA",
    "{{CPF}}": "111.111.111-11",
    "{{DATA}}": data_por_extenso(),     # data de hoje, por extenso
    "{{SERVIDOR}}": "FULANO DE TAL",
    "{{CARGO}}": "Analista",
}


def main() -> None:
    # 1) Prepare o webdriver e faça login no SEI (aqui, manualmente).
    driver = webdriver.Chrome()
    try:
        driver.get("https://SEU-SEI.exemplo.gov.br/sei/")
        input("Faça login no SEI e tecle ENTER para continuar...")
        fechar_tela_aviso(driver)

        # 2) Abrir o processo que vai receber o documento.
        try:
            ProcessoSei(driver, NUMERO_PROCESSO).acessar()
        except ProcessoNaoEncontrado:
            print(f"Processo {NUMERO_PROCESSO} não encontrado.")
            return

        # 3) Clonar o modelo e 4) preencher os placeholders.
        try:
            IncluirDocumentoInterno(
                driver, TIPO_DOCUMENTO, documento_modelo=DOCUMENTO_MODELO,
            ).incluir()
            contagens = EditarConteudo(driver, SUBSTITUICOES).editar()
        except (DocumentoInternoError, EditarConteudoError) as exc:
            print(f"Falha: {exc}")
            return

        print("Documento gerado e preenchido:")
        for ph, n in contagens.items():
            print(f"  {ph} -> {n} ocorrência(s)")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
