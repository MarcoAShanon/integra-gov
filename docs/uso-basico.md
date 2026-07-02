# Guia de uso básico — `integra.sei`

Este guia mostra a **sequência inicial correta** para automatizar o SEI com a
biblioteca: abrir o navegador, fazer login, fechar o aviso pós-login, escolher a
unidade e abrir um processo — e, por fim, as **operações sobre o processo**
(criar um processo, incluir um documento externo).

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

Por padrão a janela abre **maximizada** (`maximizar=True`). Isso é importante no
SEI: ele é **responsivo** e, em janela estreita, colapsa a barra de ícones e
alguns elementos somem do DOM, quebrando a automação. No headless usa uma
viewport larga (`--window-size=1920,1080`) pelo mesmo motivo.

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

## 5. Operações sobre o processo

Com a sessão autenticada e na unidade certa (seções 1–3), a biblioteca oferece
ações que **agem sobre um processo**. Nada de valor de órgão é embutido: tipo,
série, nível de acesso e hipótese legal são **parâmetros** que casam com o texto
**exato** do seu SEI.

### Criar um novo processo

`IniciarProcesso.iniciar()` cria o processo e **devolve o número (NUP)**:

```python
from integra.sei import IniciarProcesso
from integra.sei.exceptions import IniciarProcessoError

try:
    numero = IniciarProcesso(
        driver,
        tipo="Tipo Exato do seu SEI",   # obrigatório; sem default (varia por órgão)
        especificacao="...",            # opcional
        interessado="...",              # opcional
        nivel_acesso="publico",         # ou "restrito" (+ hipotese_legal)
    ).iniciar()
    print(numero)                       # ex.: "00000.000000/0000-00"
except IniciarProcessoError as exc:
    ...  # menu/campo não encontrado, ou o SEI recusou (ex.: "Informe o nível de acesso")
```

Para acesso **restrito**, a hipótese legal é obrigatória (texto exato do dropdown):

```python
IniciarProcesso(
    driver, tipo="...",
    nivel_acesso="restrito",
    hipotese_legal="Informação Pessoal (Art. 31 da Lei nº 12.527/2011)",
).iniciar()
```

### Incluir um documento externo (upload de arquivo)

Anexa um arquivo pronto (PDF etc.) a um processo **já aberto** (acesse-o antes com
`ProcessoSei(...).acessar()`). O upload vai direto ao `<input type=file>` do SEI —
**sem** janela nativa nem `pywinauto`. `tipo_serie` é a opção do dropdown
**"Tipo do Documento"** e `nome_arvore` é o **rótulo na árvore**:

```python
from integra.sei import ProcessoSei, InserirDocumentoExterno
from integra.sei.exceptions import DocumentoExternoError

ProcessoSei(driver, "00000.000000/0000-00").acessar()   # abre o processo

try:
    nome = InserirDocumentoExterno(
        driver,
        tipo_serie="Ofício",                  # opção EXATA do "Tipo do Documento"
        nome_arvore="Ofício 123 - Resposta",  # rótulo na árvore
        arquivo="caminho/para/arquivo.pdf",   # caminho do arquivo (deve existir)
        nivel_acesso="publico",               # ou "restrito" (+ hipotese_legal)
    ).inserir()
    print(nome)                               # o nome_arvore confirmado
except DocumentoExternoError as exc:
    ...  # campo/botão não encontrado, upload não confirmado, ou o SEI recusou
```

Escopo atual: formato **nato-digital**. O nível de acesso reusa o mesmo
componente do `iniciar_processo` (restrito exige `hipotese_legal`).

### Incluir um documento interno (Despacho, Nota Técnica, …)

Gera um documento do próprio SEI num processo **já aberto**, opcionalmente a
partir de um **documento modelo** — o protocolo de um documento base cujo
conteúdo é clonado (útil para instruções processuais padronizadas em escala).
Após salvar, o SEI abre o editor de conteúdo numa **janela nova**: o módulo
confirma a criação por essa janela, **fecha-a** e devolve o driver à janela
principal, retornando o **rótulo do documento na árvore**:

```python
from integra.sei import IncluirDocumentoInterno
from integra.sei.exceptions import DocumentoInternoError

try:
    rotulo = IncluirDocumentoInterno(
        driver,
        tipo_documento="Despacho",       # tipo EXATO da lista do seu SEI
        documento_modelo="12345678",     # opcional: protocolo do doc base (modelo)
        nome_arvore="- Encaminhamento",  # opcional: nome extra na árvore
        nivel_acesso="publico",          # ou "restrito" (+ hipotese_legal)
    ).incluir()
    print(rotulo)                        # ex.: "Despacho 12345678"
except DocumentoInternoError as exc:
    ...  # tela/campo não encontrado, SEI recusou, ou editor não abriu
```

Escopo atual: texto inicial **"Documento Modelo"** ou nenhum ("Texto Padrão"
virá depois). Para **preencher** o documento clonado, veja a seção seguinte.

### Preencher um modelo com dados (o fluxo de escala)

Esta é a combinação que faz sentido para gerar **muitos** documentos com uma
instrução padrão (dezenas, centenas, milhares): um **documento modelo** com
*placeholders*, clonado e preenchido a cada execução.

**1. Crie o modelo no próprio SEI (uma vez).** Num processo de referência da sua
unidade, escreva — pelo editor do SEI — um documento por tipo (um "Despacho
modelo", uma "Nota Técnica modelo") com marcadores no texto:

```
Processo nº {{PROCESSO}}

Solicito atender a demanda do interessado sr(a). nome: {{NOME}}; cpf: {{CPF}}

Brasília, {{DATA}}.

{{SERVIDOR}}
{{CARGO}}
```

Anote o **protocolo** do modelo (o número na árvore). O conteúdo do modelo (e
seus placeholders) fica **no SEI**, mantido pela área de negócio — a biblioteca
não embute nenhum template.

> **Regra de ouro dos placeholders:** digite cada marcador **inteiro e de uma
> vez** (`{{NOME}}`), sem formatar só um pedaço dentro das chaves. O editor
> guarda o texto como HTML; formatar parcialmente (ou corrigir uma letra no
> meio) pode **fragmentar** o marcador em nós separados, e a substituição por
> texto não o encontra mais. Formatar o marcador **inteiro** (negrito em todo o
> `{{SERVIDOR}}`) é seguro — o valor herda o estilo.

**2. Clone e preencha na automação.** `IncluirDocumentoInterno` com
`documento_modelo=` clona o modelo; `EditarConteudo` injeta os valores direto na
API do editor (CKEditor), sem simular teclado e sem "localizar/substituir" na
tela:

```python
from integra.sei import (
    IncluirDocumentoInterno, EditarConteudo, data_por_extenso,
)
from integra.sei.exceptions import DocumentoInternoError, EditarConteudoError

try:
    IncluirDocumentoInterno(
        driver, "Despacho", documento_modelo="12345678",
    ).incluir()

    contagens = EditarConteudo(driver, {
        "{{PROCESSO}}": "19975.120202/2023-82",
        "{{NOME}}": "MARIA DA SILVA",
        "{{CPF}}": "111.111.111-11",
        "{{DATA}}": data_por_extenso(),        # "2 de julho de 2026"
        "{{SERVIDOR}}": "FULANO DE TAL",
        "{{CARGO}}": "Analista",
    }).editar()
    print(contagens)   # {"{{NOME}}": 1, ...} — quantas ocorrências de cada
except (DocumentoInternoError, EditarConteudoError) as exc:
    ...  # criação ou edição falhou (veja a mensagem)
```

Pontos que valem saber:

- **Data é responsabilidade sua**, não do modelo (o clone traz a data de quando
  o modelo foi escrito). Use o helper `data_por_extenso()` — data pt-BR por
  extenso, sem depender do locale `pt_BR` estar instalado na máquina.
- **Assinatura fica de fora do corpo.** O "Documento assinado eletronicamente /
  NOME / Cargo" é o carimbo que o SEI gera **na assinatura** — não faça dele um
  placeholder (a não ser que, no seu órgão, nome/cargo também sejam digitados no
  corpo, como no exemplo acima).
- **Rede de segurança:** se um placeholder do dicionário **não** existir no
  documento, `EditarConteudo` **fecha o editor sem salvar** e levanta
  `EditarConteudoError` listando os faltantes — nada é gravado pela metade (pega
  tanto erro de digitação no dicionário quanto marcador fragmentado no modelo).
- **Escape:** os valores são inseridos como **texto literal** por padrão
  (caracteres como `&`, `<`, `>` são escapados). Para injetar HTML de propósito,
  use `EditarConteudo(..., escapar_html=False)` — aí o HTML é sua
  responsabilidade (precisa ser válido e usar as classes CSS do SEI).

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
