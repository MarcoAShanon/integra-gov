# integra

Biblioteca Python de **automação de sistemas do governo federal brasileiro**, começando pelo **SEI** (Sistema Eletrônico de Informações). O objetivo é ajudar servidores públicos a automatizar tarefas repetitivas de forma segura e reutilizável.

> **Status:** 🚧 em construção. O projeto é publicado **de forma incremental** — cada módulo é generalizado, testado e documentado antes de ser disponibilizado.

## Escopo e princípios

- **Acesso autorizado:** a biblioteca automatiza o acesso que o próprio usuário já possui aos sistemas. Não burla autenticação, captcha nem controles de acesso.
- **Sem dados pessoais no repositório:** nenhum dado real (CPF, nome, número de processo, e-mail) é versionado. Exemplos usam valores fictícios.
- **Reutilizável entre órgãos:** parâmetros específicos de órgão/unidade são **configuráveis**, não embutidos no código.

## Instalação

```bash
pip install -e ".[dev]"   # ambiente de desenvolvimento
```

A publicação no PyPI virá quando os primeiros módulos estiverem estáveis.

## Uso

> 📖 **Guia passo a passo:** veja [`docs/uso-basico.md`](docs/uso-basico.md) —
> explica a sequência inicial (navegador → login → tela de aviso → unidade →
> processo) e o porquê de cada passo.

A sequência canônica, do zero ao processo aberto:

```python
from getpass import getpass
from integra.sei import (
    criar_driver_chrome, LoginSei, SelecaoUnidade, ProcessoSei, IframesSei,
)

# Abre o Chrome com os ajustes de ambiente gov, com retry automático e limpeza
# de chromedriver órfão (cobre o "Chrome instance exited" / navegador que não abre):
driver = criar_driver_chrome()
try:
    # Login: já fecha internamente o aviso pós-login que bloquearia a tela.
    LoginSei(
        driver,
        base_url="https://sei.exemplo.gov.br",  # a URL da SUA instância do SEI
        orgao="MGI",                            # a sigla do SEU órgão
        usuario="seu.usuario",
        senha=getpass("Senha do SEI: "),        # nunca versione a senha
    ).logar()

    # Garantir a unidade de trabalho correta (pela sigla):
    SelecaoUnidade(driver).selecionar("MGI-SGP-DECIPEX-CGPAG-EXANTE")  # sua unidade

    # Abrir um processo existente (levanta ProcessoNaoEncontrado se não achar):
    processo = ProcessoSei(driver, "00000.000000/0000-00")  # número fictício
    processo.acessar()

    # Posicionar na raiz da árvore e navegar até o iframe de visualização:
    processo.ir_para_raiz()
    IframesSei(driver, IframesSei.VISUALIZACAO).navegar()
finally:
    driver.quit()
```

> ⚠️ O módulo `login` ainda **não foi verificado contra um SEI real** — use com
> cautela e reporte problemas.

**Já está logado** numa sessão que controla com seu próprio `driver`? Aí pule o
`LoginSei` e só feche o aviso à mão (idempotente — retorna `0` se não houver):

```python
from integra.sei import fechar_tela_aviso
fechar_tela_aviso(driver)
```

Mais exemplos em [`examples/`](examples/).

## Módulos

| Módulo | Descrição | Status |
|--------|-----------|--------|
| `integra.sei.navegador` | Abre o Chrome (ajustes gov) com retry + limpeza de `chromedriver` órfão | ✅ |
| `integra.sei.iframes` | Navegação entre iframes (tolerante a SEI 3.x/4.x) | ✅ |
| `integra.sei.processo` | Acesso a um processo existente | ✅ |
| `integra.sei.selecao_unidade` | Troca a unidade de trabalho | ✅ |
| `integra.sei.tela_aviso` | Fecha o aviso pós-login que bloqueia a tela | ✅ |
| `integra.sei.exceptions` | Exceções tipadas | ✅ |
| `integra.sei.login` | Autenticação no SEI | ✅ ¹ |
| _(demais)_ | e-SIAPE, SIAPE, utilidades | planejado |

¹ Disponível, mas **ainda não verificado contra um SEI real**. Use com cautela e reporte problemas.

## Como contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Contribuições de outros servidores e desenvolvedores são bem-vindas.

## Licença

[MIT](LICENSE). Software livre, no espírito de colaboração entre órgãos públicos.
