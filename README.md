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

> ⚠️ **Pré-requisito:** você precisa estar **logado no SEI** na sessão do
> navegador controlado pelo Selenium. (O módulo de login virá depois; por ora,
> faça login você mesmo e reaproveite a sessão.)

```python
from selenium import webdriver
from integra.sei import ProcessoSei, IframesSei

driver = webdriver.Chrome()
# ... abra o SEI e faça login nesta sessão ...

# Abrir um processo existente (levanta ProcessoNaoEncontrado se não achar):
processo = ProcessoSei(driver, "00000.000000/0000-00")  # número fictício
processo.acessar()

# Posicionar na raiz da árvore e navegar até o iframe de visualização:
processo.ir_para_raiz()
IframesSei(driver, IframesSei.VISUALIZACAO).navegar()
```

Mais exemplos em [`examples/`](examples/).

## Módulos

| Módulo | Descrição | Status |
|--------|-----------|--------|
| `integra.sei.iframes` | Navegação entre iframes (tolerante a SEI 3.x/4.x) | ✅ |
| `integra.sei.processo` | Acesso a um processo existente | ✅ |
| `integra.sei.exceptions` | Exceções tipadas | ✅ |
| `integra.sei.login` | Autenticação no SEI | planejado |
| _(demais)_ | e-SIAPE, SIAPE, utilidades | planejado |

## Como contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Contribuições de outros servidores e desenvolvedores são bem-vindas.

## Licença

[MIT](LICENSE). Software livre, no espírito de colaboração entre órgãos públicos.
