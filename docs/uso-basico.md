# Guia de uso básico — `integra.sei`

Este guia mostra a **sequência inicial correta** para automatizar o SEI com a
biblioteca: abrir o navegador, fazer login, fechar o aviso pós-login, escolher a
unidade e abrir um processo.

> A biblioteca é **headless**: ela fornece **dados** (ex.: `listar_unidades()`) e
> **ações** (ex.: `selecionar(sigla)`). Ela não desenha telas — qualquer
> interface gráfica fica na *sua* aplicação. Todas as classes recebem um
> `driver` do Selenium pronto.

---

## A sequência canônica

```
criar_driver_chrome()              → abre o Chrome (ajustes gov + limpa órfãos)
LoginSei(...).logar()              → faz login E já fecha a tela de aviso
SelecaoUnidade(driver).selecionar  → garante a unidade de trabalho correta
ProcessoSei(driver, num).acessar() → abre um processo existente
    .ir_para_raiz()                → posiciona na raiz da árvore
IframesSei(driver, ...).navegar()  → entra no iframe de visualização
```

Cada passo e o **porquê** dele estão detalhados abaixo.

---

## 1. Abrir o navegador

Use o helper `criar_driver_chrome()`. Ele abre o Chrome já com os ajustes que
máquinas gerenciadas (gov) costumam exigir (`--no-sandbox`,
`--disable-dev-shm-usage`) e cuida das duas causas comuns de *"Chrome instance
exited"* / navegador que não abre:

1. **Falha transitória na primeira abertura** (antivírus/EDR escaneando o
   binário no primeiro launch). O helper **tenta de novo** automaticamente
   (3 tentativas, com 1 s entre elas) — na prática, a 2ª tentativa quase sempre
   sobe. Ajuste com `tentativas=` e `intervalo=`.
2. **`chromedriver` preso** de uma execução anterior. Antes de **cada**
   tentativa, o helper encerra esses órfãos (seguro — não fecha janelas
   pessoais). A tentativa que falhou pode deixar um zumbi, então limpar a cada
   rodada é o que faz o retry convergir.

Se as tentativas se esgotarem, levanta `NavegadorError` (encadeando a causa
original do Selenium para diagnóstico).

```python
from integra.sei import criar_driver_chrome

driver = criar_driver_chrome()
try:
    ...  # seus passos
finally:
    driver.quit()
```

> **Você não é obrigado a usar o helper.** Por ser headless, a lib aceita
> qualquer `driver` que você criar (`webdriver.Chrome()`, Remote, etc.) — basta
> passá-lo às classes. O helper só evita repetir o boilerplate e centraliza a
> limpeza.

### Quando o navegador insiste em não abrir

A limpeza padrão é **segura**: encerra só o `chromedriver` (exclusivo da
automação), **nunca** as suas janelas de navegação pessoal.

Se mesmo assim o Chrome não subir (ex.: trava no diretório de perfil), há a
opção **destrutiva** — que fecha **todo** o Chrome, inclusive as janelas
pessoais (pode perder trabalho não salvo):

```python
driver = criar_driver_chrome(encerrar_todo_chrome=True)   # ⚠️ fecha tudo
```

Ou chame as funções de limpeza diretamente, sem abrir nada:

```python
from integra.sei import encerrar_chromedriver_orfaos, encerrar_chrome

encerrar_chromedriver_orfaos()   # seguro
encerrar_chrome()                # ⚠️ destrutivo: fecha todas as janelas
```

Outros parâmetros úteis: `headless=True` (sem janela visível) e
`args_extra=("--user-data-dir=...",)` (perfil dedicado, evita travas no perfil
padrão).

---

## 2. Login + tela de aviso (o ponto que mais confunde)

Logo após o login, o SEI quase sempre exibe uma **tela de aviso** que, se não
for fechada, **bloqueia a interação com os demais campos**. A ordem importa.

**Se você usa o `LoginSei`, não precisa fazer nada:** ele já chama
`fechar_tela_aviso()` internamente ao final do `logar()`.

```python
from getpass import getpass
from integra.sei import LoginSei

LoginSei(
    driver,
    base_url="https://sei.exemplo.gov.br",  # a URL da SUA instância
    orgao="MGI",                            # a sigla do SEU órgão
    usuario="seu.usuario",
    senha=getpass("Senha do SEI: "),        # obtenha de forma segura; nunca versione
).logar()
# Aqui a tela de aviso JÁ foi fechada — pode seguir.
```

**Só chame `fechar_tela_aviso()` à mão se você NÃO usou o `LoginSei`** — por
exemplo, se você mesmo fez o login na sessão do navegador e só reaproveita o
`driver`:

```python
from integra.sei import fechar_tela_aviso

# ... você fez login manualmente nesta sessão ...
fechar_tela_aviso(driver)   # idempotente: retorna 0 se não houver aviso
```

`fechar_tela_aviso()` é **idempotente** — chamá-lo sem aviso presente não causa
erro (retorna `0`). Logo, na dúvida, chamá-lo de novo é inofensivo.

### Erros possíveis no login

| Exceção | Quando acontece |
|---------|-----------------|
| `CredenciaisInvalidas` | o SEI rejeitou usuário/senha |
| `SeiLoginError` | o formulário não carregou ou o login não pôde ser confirmado (URL/instância errada, seletor diferente) |

```python
from integra.sei.exceptions import CredenciaisInvalidas, SeiLoginError

try:
    LoginSei(driver, base_url, orgao, usuario, senha).logar()
except CredenciaisInvalidas:
    ...  # usuário/senha errados
except SeiLoginError as exc:
    ...  # algo na instância/seletor; veja a mensagem
```

> ✅ O módulo `login` foi verificado ao vivo contra o SEI 4.1.5 (instância
> ColaboraGov/MGI).

---

## 3. Escolher a unidade de trabalho

O SEI trabalha "dentro de uma unidade". Antes de abrir/instruir um processo,
garanta a unidade certa pela **sigla**:

```python
from integra.sei import SelecaoUnidade
from integra.sei.exceptions import UnidadeNaoEncontrada

sel = SelecaoUnidade(driver)
try:
    sel.selecionar("MGI-SGP-DECIPEX-CGPAG-EXANTE")   # a SUA unidade
except UnidadeNaoEncontrada:
    ...  # a sigla não existe para este usuário
```

Para descobrir as siglas disponíveis (decisão da *sua* aplicação, não da lib):

```python
for u in sel.listar_unidades():
    print(u.sigla, "—", u.descricao)
```

---

## 4. Abrir um processo existente

```python
from integra.sei import ProcessoSei, IframesSei
from integra.sei.exceptions import ProcessoNaoEncontrado

try:
    processo = ProcessoSei(driver, "00000.000000/0000-00")  # número fictício
    processo.acessar()
except ProcessoNaoEncontrado:
    ...  # o processo não existe / não está visível para esta unidade

# Posicionar na raiz da árvore e entrar no iframe de visualização:
processo.ir_para_raiz()
IframesSei(driver, IframesSei.VISUALIZACAO).navegar()
```

---

## Exemplo completo (do zero ao processo aberto)

```python
from getpass import getpass

from integra.sei import (
    criar_driver_chrome,
    LoginSei,
    SelecaoUnidade,
    ProcessoSei,
    IframesSei,
)

driver = criar_driver_chrome()
try:
    LoginSei(
        driver,
        base_url="https://sei.exemplo.gov.br",
        orgao="MGI",
        usuario="seu.usuario",
        senha=getpass("Senha do SEI: "),
    ).logar()                      # já fecha a tela de aviso

    SelecaoUnidade(driver).selecionar("MGI-SGP-DECIPEX-CGPAG-EXANTE")

    processo = ProcessoSei(driver, "00000.000000/0000-00")
    processo.acessar()
    processo.ir_para_raiz()
    IframesSei(driver, IframesSei.VISUALIZACAO).navegar()
finally:
    driver.quit()
```

---

## Boas práticas

- **Senha:** obtenha via `getpass`, variável de ambiente ou cofre de segredos.
  Nunca escreva no código nem versione. A lib não registra a senha em log.
- **Sempre `driver.quit()`** num `finally` — evita deixar `chromedriver` órfão
  (que a limpeza do próximo `criar_driver_chrome()` teria de encerrar).
- **Logs:** a lib usa o `logging` padrão. Para ver o passo a passo:
  ```python
  import logging
  logging.basicConfig(level=logging.INFO)
  ```
- **Trate as exceções tipadas** (`SeiError` é a base de todas) em vez de assumir
  que deu certo — a lib nunca devolve `False` silencioso.
