"""Exemplo: abrir um processo no SEI e posicionar na raiz da árvore.

Pré-requisitos:
  - Você já deve estar LOGADO no SEI na sessão do navegador controlado. Este
    pacote automatiza o acesso autorizado; o login não é feito por este exemplo
    (o módulo de login virá depois).
  - Use SEMPRE dados fictícios. O número abaixo é um placeholder.
"""

import logging

from selenium import webdriver

from integra.sei import IframesSei, ProcessoSei
from integra.sei.exceptions import ProcessoNaoEncontrado

logging.basicConfig(level=logging.INFO)

# Número de processo FICTÍCIO — troque pelo seu.
NUMERO_PROCESSO = "00000.000000/0000-00"


def main() -> None:
    # 1) Prepare seu webdriver e faça login no SEI (ou reutilize uma sessão já
    #    autenticada). Aqui usamos um Chrome local como exemplo.
    driver = webdriver.Chrome()
    try:
        driver.get("https://SEU-SEI.exemplo.gov.br/sei/")
        input("Faça login no SEI e tecle ENTER para continuar...")

        # 2) Abrir o processo (levanta ProcessoNaoEncontrado se não achar).
        processo = ProcessoSei(driver, NUMERO_PROCESSO)
        try:
            processo.acessar()
        except ProcessoNaoEncontrado:
            print(f"Processo {NUMERO_PROCESSO} não encontrado.")
            return

        # 3) Posicionar na raiz da árvore e abrir o iframe de visualização.
        processo.ir_para_raiz()
        IframesSei(driver, IframesSei.VISUALIZACAO).navegar()

        print("Processo aberto e posicionado com sucesso.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
