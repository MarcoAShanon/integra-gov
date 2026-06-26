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

> Em breve. O primeiro módulo a ser disponibilizado é o **núcleo do SEI** (login, acesso a processo e navegação de iframes).

## Módulos (roadmap)

| Módulo | Descrição | Status |
|--------|-----------|--------|
| `integra.sei` | Automação do SEI | 🚧 em preparação |
| _(demais)_ | e-SIAPE, SIAPE, utilidades | planejado |

## Como contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Contribuições de outros servidores e desenvolvedores são bem-vindas.

## Licença

[MIT](LICENSE). Software livre, no espírito de colaboração entre órgãos públicos.
