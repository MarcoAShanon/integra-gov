"""Exemplo: criar (iniciar) um novo processo no SEI.

Pré-requisitos:
  - Você já deve estar LOGADO no SEI na sessão do navegador controlado (ou use
    o módulo `LoginSei`). Este exemplo faz o login de forma manual para não
    embutir credenciais.
  - Ajuste `TIPO` para um tipo que exista EXATAMENTE no seu SEI (varia por
    órgão) — sem isso o formulário não carrega.
  - Use SEMPRE dados fictícios.

`IniciarProcesso.iniciar()` devolve o número (NUP) do processo criado.
"""

import logging

from selenium import webdriver

from integra_gov.sei import IniciarProcesso, fechar_tela_aviso
from integra_gov.sei.exceptions import IniciarProcessoError

logging.basicConfig(level=logging.INFO)

# Ajuste para o texto EXATO do seu SEI (não há default — varia por órgão).
TIPO = "Tipo Exemplo: Ajuste para o seu SEI"
ESPECIFICACAO = "Exemplo de especificação"
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

        # 2) Criar o processo (a partir da tela de Controle de Processos).
        try:
            numero = IniciarProcesso(
                driver,
                TIPO,
                especificacao=ESPECIFICACAO or None,
                nivel_acesso=NIVEL_ACESSO,
                hipotese_legal=HIPOTESE_LEGAL if NIVEL_ACESSO == "restrito" else None,
            ).iniciar()
        except IniciarProcessoError as exc:
            print(f"Falha ao iniciar processo: {exc}")
            return

        print(f"Processo criado. NÚMERO (NUP): {numero}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
