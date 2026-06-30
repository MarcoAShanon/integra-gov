# integra

Biblioteca Python de **automação de sistemas do governo federal brasileiro** — hoje o **SEI** (Sistema Eletrônico de Informações) e o **SIAPE** (terminal 3270). O objetivo é ajudar servidores públicos a automatizar tarefas repetitivas de forma segura e reutilizável.

> **Status:** 🚧 em construção. O projeto é publicado **de forma incremental** — cada módulo é generalizado, testado e documentado antes de ser disponibilizado.

## Escopo e princípios

- **Acesso autorizado:** a biblioteca automatiza o acesso que o próprio usuário já possui aos sistemas. Não burla autenticação, captcha nem controles de acesso.
- **Sem dados pessoais no repositório:** nenhum dado real (CPF, nome, número de processo, e-mail) é versionado. Exemplos usam valores fictícios.
- **Reutilizável entre órgãos:** parâmetros específicos de órgão/unidade são **configuráveis**, não embutidos no código.

## Instalação

```bash
pip install -e ".[dev]"     # ambiente de desenvolvimento
pip install -e ".[siape]"   # módulos SIAPE 3270 (Windows; instala o pywinauto)
```

A publicação no PyPI virá quando os primeiros módulos estiverem estáveis. O
núcleo (**SEI**) é multiplataforma; os módulos do **SIAPE 3270** exigem Windows e
o extra `[siape]` (automatizam um emulador de terminal IBM HOD).

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

**Já está logado** numa sessão que controla com seu próprio `driver`? Aí pule o
`LoginSei` e só feche o aviso à mão (idempotente — retorna `0` se não houver):

```python
from integra.sei import fechar_tela_aviso
fechar_tela_aviso(driver)
```

Mais exemplos em [`examples/`](examples/).

### Criar um processo

`IniciarProcesso.iniciar()` devolve o **número (NUP)** do processo criado:

```python
from integra.sei import IniciarProcesso

numero = IniciarProcesso(
    driver,
    tipo="Pessoal: Aposentadoria - Requerimento",   # tipo EXATO do seu SEI
    especificacao="Requerimento de aposentadoria",
    nivel_acesso="publico",                         # ou "restrito" (+ hipotese_legal)
).iniciar()
print(numero)   # ex.: "19975.018906/2026-39"
```

Para acesso restrito, a hipótese legal é obrigatória (texto exato do dropdown):

```python
IniciarProcesso(
    driver, tipo="...",
    nivel_acesso="restrito",
    hipotese_legal="Informação Pessoal (Art. 31 da Lei nº 12.527/2011)",
).iniciar()
```

### SIAPE (terminal 3270)

O acesso ao SIAPE passa pelo portal SIAPENet (web, com certificado digital) e por
um emulador de terminal 3270 (IBM HOD). Você se autentica; a biblioteca conduz o
resto:

```python
from integra.sei import criar_driver_chrome
from integra.siape import (
    AcessoSiapeWeb, LancadorHod, ControleTerminal3270,
    ConexaoTerminal3270, TrocaHabilitacao,
)

driver = criar_driver_chrome()
otp = AcessoSiapeWeb(driver).executar()          # você autentica (PIN/push); captura o OTP
LancadorHod("C:/Users/voce/Downloads").lancar()  # executa o HOD e abre o Terminal 3270

controle = ControleTerminal3270()
conexao = ConexaoTerminal3270(controle, codigo_seguranca=otp)
conexao.conectar()                                               # atacha + OTP + menu

TrocaHabilitacao(controle, orgao="00000", upag="000000000").trocar()  # contexto
conexao.acessar_transacao("GRCOSITPRO", confirmacao="GRCOSITPRO")     # >transação
```

## Módulos

### SEI — multiplataforma (núcleo)

| Módulo | Descrição | Status |
|--------|-----------|--------|
| `integra.sei.navegador` | Abre o Chrome (ajustes gov) com retry + limpeza de `chromedriver` órfão | ✅ |
| `integra.sei.iframes` | Navegação entre iframes (tolerante a SEI 3.x/4.x) | ✅ |
| `integra.sei.processo` | Acesso a um processo existente | ✅ |
| `integra.sei.selecao_unidade` | Troca a unidade de trabalho | ✅ |
| `integra.sei.tela_aviso` | Fecha o aviso pós-login que bloqueia a tela | ✅ |
| `integra.sei.login` | Autenticação no SEI | ✅ |
| `integra.sei.iniciar_processo` | Criação de um novo processo (devolve o NUP) | ✅ |
| `integra.sei.nivel_acesso` | Nível de acesso (público/restrito) — reutilizável | ✅ |
| `integra.sei.exceptions` | Exceções tipadas | ✅ |

### SIAPE 3270 — Windows, extra `[siape]`

| Módulo | Descrição | Status |
|--------|-----------|--------|
| `integra.siape.acesso_web` | SIAPENet → certificado (você autentica) → captura do OTP (só Selenium) | ✅ |
| `integra.siape.lancador` | Executa o módulo HOD baixado e abre o Terminal 3270 | ✅ |
| `integra.siape.controle` | Interação base com o terminal (ler tela, enviar teclas) | ✅ |
| `integra.siape.conexao` | Acesso/login (OTP) + acessar transação (`>COMANDO`) | ✅ |
| `integra.siape.habilitacao` | Troca de habilitação (ÓRGÃO/UPAG) via `TROCAHAB` | ✅ |
| `integra.siape.exceptions` | Exceções tipadas | ✅ |

| _(planejado)_ | e-SIAPE (web), demais transações, utilidades | 🔜 |

## Como contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Contribuições de outros servidores e desenvolvedores são bem-vindas.

## Licença

[MIT](LICENSE). Software livre, no espírito de colaboração entre órgãos públicos.
