# Guia de uso básico — `integra_gov`

Este guia mostra a **sequência inicial correta** para automatizar o SEI com a
biblioteca: abrir o navegador, fazer login, fechar o aviso pós-login, escolher a
unidade e abrir um processo — e, por fim, as **operações sobre o processo**
(criar, instruir com documentos, marcar, dar prazo e concluir).

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
from integra_gov.sei import criar_driver_chrome

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
from integra_gov.sei import encerrar_chromedriver_orfaos, encerrar_chrome

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
from integra_gov.sei import LoginSei

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
from integra_gov.sei import fechar_tela_aviso

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
from integra_gov.sei.exceptions import CredenciaisInvalidas, SeiLoginError

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
from integra_gov.sei import SelecaoUnidade
from integra_gov.sei.exceptions import UnidadeNaoEncontrada

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
from integra_gov.sei import ProcessoSei, IframesSei
from integra_gov.sei.exceptions import ProcessoNaoEncontrado

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
from integra_gov.sei import IniciarProcesso
from integra_gov.sei.exceptions import IniciarProcessoError

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
from integra_gov.sei import ProcessoSei, InserirDocumentoExterno
from integra_gov.sei.exceptions import DocumentoExternoError

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
from integra_gov.sei import IncluirDocumentoInterno
from integra_gov.sei.exceptions import DocumentoInternoError

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
from integra_gov.sei import (
    IncluirDocumentoInterno, EditarConteudo, data_por_extenso,
)
from integra_gov.sei.exceptions import DocumentoInternoError, EditarConteudoError

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
  use `EditarConteudo(..., escapar_html=False)` (todos os valores como HTML cru)
  ou `chaves_html={...}` para injetar HTML cru **só** nos placeholders escolhidos
  — útil para pôr um link no meio de campos de texto (veja a seguir).

### Referenciar outro documento (link no meio do texto)

Às vezes o documento precisa **apontar para outro documento** do processo (ex.:
"conforme a Nota Técnica X"). No editor do SEI isso **não** é um `<a href>`
comum: é uma **âncora nativa** que o SEI resolve na hora de visualizar. A
biblioteca monta essa âncora com `montar_link_documento(id_documento, protocolo)`
e a injeta num placeholder como **HTML cru** — por isso você lista esse
placeholder em `chaves_html`:

```python
from integra_gov.sei import (
    DocumentosArvore, EditarConteudo, montar_link_documento,
)

# O id_documento (id interno, ≠ do protocolo visível) vem da árvore:
alvo = DocumentosArvore(driver).listar(contendo="44414392")[0]
link = montar_link_documento(alvo.id_documento, alvo.numero)

EditarConteudo(driver, {
    "{{NOME}}": "MARIA DA SILVA",   # texto normal (escapado)
    "{{DOC_REF}}": link,             # HTML cru: o link para o documento
}, chaves_html={"{{DOC_REF}}"}).editar()
```

Só os placeholders em `chaves_html` entram sem escape; o resto continua como
texto literal — tudo numa passada só. O **texto visível** do link é o protocolo
(número do documento) e o **id interno** (`id_documento`) é o que o SEI usa para
resolver o link — dois números diferentes do mesmo documento.

### Apontar um documento existente

Os módulos que agem sobre um documento (assinar, editar) operam sobre o
documento **selecionado** na árvore. No fluxo encadeado (criar → preencher →
assinar) o documento recém-criado já fica selecionado. Para agir sobre um
documento **já existente**, aponte-o com `DocumentosArvore` — que também lê a
árvore como dados:

```python
from integra_gov.sei import DocumentosArvore

arvore = DocumentosArvore(driver)

for d in arvore.listar():            # árvore como dados (expande as pastas)
    print(d.numero, d.tipo.name, d.texto)

arvore.selecionar("44414392")        # clica o documento pelo protocolo
# agora AssinarDocumento / EditarConteudo agem sobre ELE
```

Dois pontos:

- **Pastas colapsadas:** o SEI agrupa os documentos em pastas quando passam de
  ~20. `DocumentosArvore` **expande tudo automaticamente** antes de ler/apontar
  (`expandir=False` desliga), então nenhum documento fica invisível.
- **Ambiguidade:** casar pelo **número do protocolo** (único) é o mais seguro. Se
  o texto casar com vários nós, `selecionar()` **aborta** com
  `SelecaoDocumentoError` — passe `indice=` para desambiguar.

### Baixar um documento (download)

Baixa o documento **selecionado** na árvore como **dado** — sem a janela nativa
"Salvar como" nem a pasta de download do Chrome. `DownloadDocumento` lê a URL de
download e busca o arquivo com `fetch()` **dentro da sessão logada** (reusa
cookies e SSL, o que ainda resolve os certificados `.gov.br`):

```python
from integra_gov.sei import DocumentosArvore, DownloadDocumento
from integra_gov.sei.exceptions import DownloadDocumentoError

DocumentosArvore(driver).selecionar("35551895")   # aponta um documento EXTERNO

try:
    doc = DownloadDocumento(driver).baixar()
except DownloadDocumentoError as exc:
    ...  # URL não encontrada, fetch falhou (ex.: sessão expirada), conteúdo ilegível

# doc é um DocumentoBaixado: bytes + metadados (a lib NÃO escreve em disco por si)
print(len(doc.conteudo), doc.content_type, doc.extensao, doc.nome_sugerido)
caminho = doc.salvar("downloads")                 # grava downloads/<nome>.<ext> → Path
```

Dois pontos:

- **Externo, não interno:** o download pega o **arquivo anexado** (PDF, DOCX…) de
  um documento **externo/enviado**. Um documento **interno** do SEI é HTML gerado
  pelo sistema e não tem anexo para baixar (vira PDF por outro caminho).
- **Dado, não arquivo:** `baixar()` devolve os bytes e o `nome_sugerido` (do
  `Content-Disposition`); só `salvar(pasta, nome=...)` grava em disco — a lib
  segue headless.

### Assinar um documento

Assina o documento **selecionado** com a **senha do próprio servidor** — a senha
é parâmetro (via `getpass`/cofre), **nunca embutida nem registrada em log**:

```python
from getpass import getpass
from integra_gov.sei import AssinarDocumento
from integra_gov.sei.exceptions import AssinaturaError

try:
    AssinarDocumento(driver, senha=getpass("Senha do SEI: ")).assinar()
except AssinaturaError as exc:
    ...  # senha recusada, ou a assinatura não pôde ser confirmada
```

`assinar()` **confirma pela verdade**: só conclui quando o documento passa a
exibir os marcadores reais de assinatura do SEI ("assinado eletronicamente
por…", código CRC) — nunca reporta "assinado" por suposição; senha recusada
levanta `AssinaturaError`.

> ⚠️ **Governança:** assinar em lote é assinar **sem revisar** cada documento. A
> conferência antes da assinatura é responsabilidade da aplicação que monta o
> fluxo — a biblioteca fornece o mecanismo, não o controle editorial.

### Incluir um documento em bloco de assinatura

O bloco de assinatura junta documentos para serem **assinados em lote** — útil
quando o signatário é de outra unidade, ou para assinar vários de uma vez. Com o
documento **selecionado na árvore**, inclua-o num bloco existente:

```python
from integra_gov.sei import DocumentosArvore, IncluirDocumentoBloco
from integra_gov.sei.exceptions import BlocoAssinaturaError

DocumentosArvore(driver).selecionar("59028410")   # aponta o documento

try:
    IncluirDocumentoBloco(driver, "648852", ["59028410"]).incluir()
except BlocoAssinaturaError as exc:
    ...  # bloco inexistente, protocolo ausente na tela, ou recusa do SEI
```

Três pontos:

- **`bloco`** casa pelo **value** (id numérico) **ou** pelo **texto** da opção; se
  não existir, o erro **lista os blocos disponíveis** da unidade.
- **`protocolos`** são os números dos documentos (só dígitos — não o NUP
  formatado). Se **algum** não aparecer na tela do bloco, **nada é incluído** (a
  operação é tudo-ou-nada).
- **Confirmação:** verificado ao vivo (SEI 4.1.5), a tela do bloco **não muda** no
  sucesso — não há mensagem nem o formulário some. Por isso o módulo confirma pela
  **ausência de recusa**: após o submit ser processado, sem alerta e sem erro
  inline = aceito. Um diálogo é sempre tratado como recusa (nunca confirmado às
  cegas). Confira no bloco quando quiser a prova visual.

### Marcadores (etiquetas do processo)

Os **marcadores** do SEI (etiquetas coloridas) aparecem em **dois contextos** —
por isso duas classes. Na tela **Controle de Processos** (a lista), `Marcadores`
consulta e filtra:

```python
from integra_gov.sei import Marcadores

marcadores = Marcadores(driver)             # driver na tela Controle de Processos
for m in marcadores.listar():               # marcadores da unidade, como dados
    print(m.id, m.nome, m.quantidade, m.cor)

marcadores.selecionar("INTEGRA - RETORNO")  # filtra a lista por esse marcador
marcadores.remover_filtro()                 # volta à lista completa
```

Num **processo aberto**, `MarcadorProcesso` marca/desmarca **aquele** processo
pelo modal "Gerenciar Marcador":

```python
from integra_gov.sei import MarcadorProcesso

mp = MarcadorProcesso(driver)                          # processo aberto
mp.incluir("INTEGRA - RETORNO", "Aguardando retorno")  # mensagem opcional (≤ 250)
mp.listar()                                            # ['INTEGRA - RETORNO', ...]
mp.remover("INTEGRA - RETORNO")
```

`selecionar()` casa por **nome exato** ou **id** e falha com `MarcadorError` se o
marcador não existir. `incluir()` valida a mensagem (≤ 250 caracteres) e confirma
a inclusão pelo ícone do marcador na árvore.

### Controle de prazo

Define ou remove o **prazo** (em dias) de um processo aberto — o "Controle de
Prazo" do SEI:

```python
from integra_gov.sei import ControlePrazo

ControlePrazo(driver).definir(30)   # prazo de 30 dias (valida 1..9999)
ControlePrazo(driver).excluir()     # remove o prazo
```

`definir()` levanta `ValueError` fora da faixa `1..9999` e `ControlePrazoError`
se a tela do prazo não abrir/responder.

### Concluir (encerrar) um processo

Encerra o processo aberto. O ponto importante é distinguir um **bloqueio do SEI**
de uma **falha técnica**, feito por exceções:

```python
from integra_gov.sei import ConcluirProcesso
from integra_gov.sei.exceptions import ConcluirProcessoError, ProcessoBloqueadoError

try:
    ConcluirProcesso(driver).concluir()
except ProcessoBloqueadoError:
    ...   # o SEI recusou: há documento com acesso restrito / hipótese legal pendente
except ConcluirProcessoError:
    ...   # falha técnica (ícone ou formulário de conclusão não encontrado)
```

`ProcessoBloqueadoError` é **subclasse** de `ConcluirProcessoError` — um
`except ConcluirProcessoError` genérico pega os dois, mas você pode tratar o
bloqueio à parte (útil ao concluir **em lote**: "pulei este porque está
bloqueado" ≠ "falhou"). O módulo trata o formulário do SEI 4.x e o alert de
confirmação do legado.

### Enviar o processo a outra unidade

Tramita o processo aberto para outra unidade (pelo autocomplete do SEI):

```python
from integra_gov.sei import EnviarProcesso

EnviarProcesso(driver, "MGI-SGP-DECIPEX-CGPAG").enviar()

# manter aberto também na unidade atual (tramitação em paralelo):
EnviarProcesso(driver, "MGI-SGP-DECIPEX-CGPAG", manter_aberto=True).enviar()
```

A unidade é casada **exata** (a sigla — distinguindo a unidade-pai de sub-unidades
com sigla prefixada) e o módulo **confirma que ela entrou na lista de destinos**
antes de enviar, para não mandar para o lugar errado. `EnviarProcessoError` se a
unidade não puder ser selecionada ou o SEI recusar. Para envio **entre órgãos**,
passe `orgao=` com o texto exato da opção do dropdown de órgão.

---

## 6. Sessão expirada no meio do fluxo

O SEI derruba a sessão por inatividade, ou quando alguém sai do sistema
explicitamente — **não** por login simultâneo em outro lugar. Quando isso
acontece no meio de uma automação, a página atual vira a de login.

```python
from integra_gov.sei import SessaoExpiradaError

try:
    processo.acessar("00000.000000/0000-00")
except SessaoExpiradaError:
    # A sessão caiu. A operação NÃO foi executada pelo SEI (a requisição foi
    # redirecionada ao login). Logue de novo e repita:
    LoginSei(driver, BASE_URL, ORGAO, usuario, senha).logar()
    processo.acessar("00000.000000/0000-00")
```

Pontos que detectam: a navegação de iframes (`IframesSei` /
`switch_to_iframe_visualizacao`), o acesso a processo (`ProcessoSei.acessar` e a
confirmação do acesso), a barra de ícones (`clicar_icone_barra`) e a criação de
processo (`IniciarProcesso`).

**Uma exceção deliberada:** no `IniciarProcesso` a detecção vale só **até o
clique em "Salvar"**. Depois dele o processo pode existir, e dizer "a requisição
não foi executada" faria um orquestrador repetir a etapa e criar o processo duas
vezes — então a falha continua `IniciarProcessoError`, para conferência humana.

Para reclassificar uma falha em **código próprio** — um ponto que você
instrumentou fora dos módulos acima —, os helpers públicos continuam
disponíveis:

```python
from integra_gov.sei import SeiError, levantar_se_sessao_expirada

try:
    operacao(driver)
except SeiError as exc:
    levantar_se_sessao_expirada(driver, exc)  # vira SessaoExpiradaError se caiu
    raise
```

Use-o apenas em falhas **sem efeito já produzido** — reclassificar depois do
efeito repete a operação no relogin.

---

## Exemplo completo (do zero ao processo aberto)

```python
from getpass import getpass

from integra_gov.sei import (
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

---

## Ficha anual do pensionista (SIAPE 3270)

`FichaAnualPensionista` (`integra_gov.siape.ficha_pensionista`) extrai a ficha
financeira anual de **uma** pensionista, para uma faixa de anos, pela transação
`>FPEMPSFICF` do terminal 3270. Um **PDF por ano** com dados; ano sem dados
(código `(0034)` do SIAPE) **não é erro** — entra em `anos_sem_dados` no
resultado.

### Pré-requisitos

Diferente do SEI (headless, via Selenium), o SIAPE 3270 automatiza um emulador
de terminal na tela — o que impõe restrições próprias:

- **Terminal já conectado**: uma `ControleTerminal3270` já atachada e
  autenticada (`ConexaoTerminal3270(...).conectar()`), como na sequência do
  [README](../README.md#uso).
- **Habilitação certa já ativa**: troque com `TrocaHabilitacao(...).trocar()`
  **antes** de chamar `extrair()` — o módulo não escolhe nem confere a
  habilitação por você.
- **Impressora de PDF configurada como saída do SIAPE**: a ficha "sai" pelo
  fluxo de impressão do terminal (`>FPEMPSFICF` → confirmação → janela nativa
  "Salvar Saída de Impressão como"). O parâmetro `impressora` (padrão
  `"Microsoft Print to PDF"`) só é usado nas mensagens de erro, para você
  conferir a impressora ativa — o módulo **não** troca a impressora do SIAPE.
- **Sessão Windows GUI interativa**: `pywinauto` opera janelas nativas na tela;
  não roda numa sessão puramente headless/RDP desconectada.
- **Execução serial**: clipboard e foco de janela são recursos **globais** do
  Windows — não rode duas extrações (nem outra automação que use clipboard) ao
  mesmo tempo na mesma sessão.
- **Locale do Windows em pt-BR**: os textos que o módulo casa na tela (ex.:
  `"NAO EXISTEM DADOS"`, o título da janela "Salvar Saída de Impressão como")
  são os que o SIAPE/Windows produzem em português.

### Exemplo

```python
from pathlib import Path
from integra_gov.siape import FichaAnualPensionista

ficha = FichaAnualPensionista(controle, pasta_saida=Path("fichas/"))
resultado = ficha.extrair("0000000", 2008, 2026)
print(resultado.anos_com_dados, resultado.anos_sem_dados)
# pensão múltipla: informe matricula_instituidor= (senão InstituidorObrigatorio
# lista as opções da tela para você escolher)
```

`resultado` é um `ResultadoFichaAnual`: `pdfs` (caminhos salvos, um por ano com
dados — `ficha_<matricula>_<ano>.pdf` em `pasta_saida`), `anos_com_dados`,
`anos_sem_dados` e `duracao_s`.

### Exceções

| Exceção | Quando acontece |
|---------|-----------------|
| `InstituidorObrigatorio` | pensão múltipla e `matricula_instituidor` não foi informada (ou não está entre as opções da tela) — `matriculas_encontradas` traz as matrículas listadas, para você escolher e chamar de novo |
| `FichaIndisponivel` | a matrícula da pensionista é inexistente ou não está acessível na habilitação ativa (distinto de "ano sem dados") |
| `ExtracaoFichaInterrompida` | a extração abortou no meio da faixa de anos — `anos_processados` traz os anos já concluídos (com ou sem dados) e `causa` a exceção original; os PDFs já salvos permanecem em disco |
| `SessaoSiapePerdida` | a sessão do terminal caiu durante a automação (estado irrecuperável — reinicie a sessão) |
| `TransacaoError` | falha ao confirmar a transação (ex.: nem a janela de salvar nem o `(0034)` apareceram a tempo — geralmente a impressora ativa do SIAPE não é a esperada) |

> `TransacaoError` e `SessaoSiapePerdida` ocorridas **durante o loop de anos**
> chegam ao chamador embrulhadas em `ExtracaoFichaInterrompida.causa`; só
> falhas no **posicionamento** (antes do loop) chegam puras — capture
> `ExtracaoFichaInterrompida` e inspecione `.causa` para tratar as duas.

```python
from integra_gov.siape import FichaAnualPensionista, InstituidorObrigatorio

try:
    resultado = FichaAnualPensionista(controle, pasta_saida).extrair("0000000", 2020, 2026)
except InstituidorObrigatorio as exc:
    print(exc.matriculas_encontradas)   # escolha uma e chame de novo com matricula_instituidor=
```

> As constantes de espera (`DELAY_PADRAO`, `ESPERA_MSG_IMPRESSAO`,
> `TIMEOUT_JANELA_SALVAR`, etc.) são **atributos de classe** — ajustáveis por
> subclasse ou instância (`FichaAnualPensionista.TIMEOUT_JANELA_SALVAR = 30.0`)
> em máquinas mais lentas, sem alterar o módulo.

---

## Fluxo do e-SIAPE web

Diferente do SIAPE 3270 (terminal), o e-SIAPE web roda no **mesmo `driver`**
do SEI — é a interface CIS/Software AG do SERPRO, acessada por navegador. A
sequência básica:

```
criar_driver_chrome()                          → abre o Chrome (mesmo helper do SEI)
AcessoEsiape(driver).executar()                 → SERPRO ID: você confirma no app
TrocaHabilitacaoEsiape(driver, orgao=...).trocar()  → contexto do órgão certo
navegar_para_transacao(driver, "COD", seletor)  → abre uma transação pelo atalho
```

```python
from integra_gov.sei import criar_driver_chrome
from integra_gov.esiape import AcessoEsiape, TrocaHabilitacaoEsiape

driver = criar_driver_chrome()
try:
    AcessoEsiape(driver).executar()                        # você confirma no app
    TrocaHabilitacaoEsiape(driver, orgao="00000").trocar()  # órgão fictício
finally:
    driver.quit()
```

`AcessoEsiape.executar()` levanta `AutenticacaoNaoConfirmada` se a confirmação
no app SERPRO ID não chegar no `timeout_confirmacao` (padrão 180s), e
`MenuInacessivel` se autenticar mas o menu de transações não ficar acessível.
`TrocaHabilitacaoEsiape(...).trocar()` levanta `HabilitacaoNaoEncontrada` se o
órgão não estiver na grade (lista os códigos vistos), ou `EsiapeError` se o
modal de confirmação não aparecer ou o cabeçalho não refletir a troca.

### As 6 mecânicas do CIS

O CIS (Software AG) tem um comportamento próprio que a fundação (`navegacao.py`)
trata de forma centralizada, validado ao vivo (03–04/08/2026):

1. **Frames ocultos guardam telas velhas.** Os iframes `WA0`/`WA1`/`WA2` se
   revezam e o CIS mantém as telas **anteriores** vivas nos frames que ficam
   ocultos — só o frame **visível** é a tela atual. `procurar_em_frames`/
   `frames_visiveis` sempre ignoram frames ocultos, mesmo quando eles têm o
   mesmo seletor que você procura (senão a automação lê dados de uma tela
   morta).
2. **Popups modais fecham pelo X do topo.** Avisos do CIS (ex.: "UORG DO
   CORREIO DO USUARIO DESATIVADA") bloqueiam a navegação até serem
   **fechados de fato** — escondê-los via CSS não conta como lido. O X fica
   na barra de título do documento do **topo** (`fechar_popups_cis`), e pode
   reaparecer (respawn) até 2x antes de fechar de vez; a máquina de estados
   de `garantir_menu` converge mesmo assim.
3. **Relogin do SERPRO reseta a habilitação (flag no driver).** A tela de
   relogin (botão AVANÇAR) significa sessão **nova**: a habilitação volta ao
   padrão do usuário. `garantir_menu` seta uma flag no próprio `driver` ao
   atravessá-la; veja [a semântica de `relogin_pendente`](#semântica-de-relogin_pendente)
   abaixo.
4. **A cortina de transição pode ficar presa.** `#OPA`/`.FLASHPageSwitch` é a
   cortina que o CIS mostra entre telas; presa, ela intercepta **todo**
   clique (`element click intercepted`) e derruba o lote inteiro.
   `limpar_overlay` espera sumir sozinha e, se não sumir, esconde via JS
   (seguro — é decorativa).
5. **A lupa é o atalho de transação.** O cabeçalho tem um ícone de lupa
   (`onMenuClickPesqTrans`) que abre um campo de transação + botão Ir —
   `navegar_para_transacao` usa esse atalho (lupa → digitar o código → Ir) e
   só declara sucesso quando o **seletor exclusivo da tela-destino** aparece
   (nunca falso positivo).
6. **TROCAHAB só efetiva no "Sim" + confirmação pelo cabeçalho.**
   `TrocaHabilitacaoEsiape` seleciona a linha da grade do órgão pedido, o que
   abre um modal "Confirma ?" num frame próprio — só o botão **Sim** efetiva
   a troca. E mesmo depois do clique, o módulo só declara sucesso quando o
   **cabeçalho** (`w_menu_orgao_usu`) passa a refletir o novo órgão —
   clicar Sim não é garantia por si só.

### Semântica de `relogin_pendente`

`relogin_pendente(driver)` responde: *"um relogin foi atravessado e a
habilitação ainda NÃO foi refeita?"*. Isso importa porque uma sessão que
renasce (relogin) volta para a habilitação **padrão** do usuário — se a
automação seguir consultando/atuando como se estivesse no órgão anterior, o
SIAPE não erra: ele responde **"sem dados"** para o órgão errado, uma lacuna
silenciosa que passa despercebida num lote.

- `garantir_menu` seta a flag (`driver._esiape_relogin_pendente = True`)
  sempre que atravessa a tela de relogin (AVANÇAR).
- `navegar_para_transacao` falha (`False`) a tentativa **que atravessou** o
  relogin; após um `False`, cheque `relogin_pendente(driver)` e refaça a
  habilitação (`TrocaHabilitacaoEsiape.trocar()`) antes de repetir — um
  *retry* cego com a lupa já visível **não** é bloqueado.
- `TrocaHabilitacaoEsiape.trocar()` limpa a flag (`limpar_flag_relogin`) ao
  confirmar a troca — inclusive quando o cabeçalho já mostra o órgão pedido
  (nada a fazer, mas a flag é limpa do mesmo jeito).
- `AcessoEsiape.executar()` limpa a flag ao final: um relogin de **entrada**
  (o primeiro da sessão) não é pendência — é o estado padrão esperado, e a
  primeira troca de habilitação já é explícita no fluxo.

Na prática: depois de qualquer `navegar_para_transacao` que devolver `False`,
verifique `relogin_pendente(driver)` — se `True`, refaça a
`TrocaHabilitacaoEsiape(...).trocar()` para o órgão em uso antes de repetir a
tentativa.

```python
from integra_gov.esiape import navegar_para_transacao, relogin_pendente
from integra_gov.esiape import TrocaHabilitacaoEsiape

if not navegar_para_transacao(driver, "COD", seletor_confirmacao):
    if relogin_pendente(driver):
        TrocaHabilitacaoEsiape(driver, orgao="00000").trocar()
        navegar_para_transacao(driver, "COD", seletor_confirmacao)
```

> **Verificado ao vivo em 2026-08-05:** login SERPRO ID (com travessia real da tela de relogin), troca de habilitação ida-e-volta e navegação por transação confirmada pelo seletor — sem correções necessárias.
> As mecânicas foram validadas ao vivo num lote real do pacote **privado**
> (14 extrações); a versão generalizada/publicada aqui ainda não teve
> verificação própria ao vivo.

---

## Ficha anual e multi-órgão (e-SIAPE)

Com a habilitação certa já ativa (seção anterior), dois módulos extraem a
ficha financeira anual (`FPEMFICHAF`) pela web: `FichaAnualServidor` para
**um único órgão** (o mais simples) e `FichaMultiOrgao` quando o servidor
**migrou de órgão** ao longo da carreira.

### Blocos de até 15 anos

O e-SIAPE limita cada consulta a **15 anos**. `FichaAnualServidor.extrair()`
divide a faixa pedida em blocos (`[2008, 2022]`, `[2023, 2026]`, …), consulta
e imprime cada um, e **mescla tudo em ordem cronológica** num único PDF ao
final (`pypdf`, dependência do núcleo — não é extra opcional):

```python
from pathlib import Path
from integra_gov.esiape import FichaAnualServidor

ficha = FichaAnualServidor(driver, pasta_saida=Path("fichas/"))
resultado = ficha.extrair("0000000", 2008, 2026)   # matrícula fictícia
```

### A pasta de download do driver

A impressão do bloco passa pelo fluxo de download do Chrome — o e-SIAPE não
oferece um endpoint direto para o PDF. Por isso o `driver` **precisa estar
configurado** para baixar automaticamente (sem o diálogo nativo "Salvar
como") na **mesma pasta** que `pasta_download` aponta. Por padrão,
`pasta_download` é a subpasta `_download_esiape` dentro de `pasta_saida`; se
o seu `driver` usa outro destino de download, passe-o explicitamente:

```python
ficha = FichaAnualServidor(
    driver, pasta_saida=Path("fichas/"),
    pasta_download=Path("C:/Users/voce/Downloads"),  # deve bater com o Chrome
)
```

Se o PDF não aparecer nessa pasta a tempo, o módulo levanta `TimeoutError`
com essa pergunta explícita na mensagem — é o sintoma mais comum de
desalinhamento entre `pasta_download` e a configuração real do navegador.

### Configuração do Chrome (obrigatória)

A impressão do bloco só salva o PDF de fato se o `driver` do Chrome estiver
configurado assim. Sem isso há **três** desfechos, e o terceiro é o
traiçoeiro:

1. a impressão trava num diálogo nativo;
2. é bloqueada silenciosamente;
3. **sai um PDF pela impressora virtual do Windows** (`Microsoft Print to
   PDF`), com aparência correta e **sem uma única letra legível por máquina**
   — as fontes viram contorno vetorial.

O terceiro é o pior porque parece sucesso: o arquivo aparece na pasta, tem
páginas, abre no leitor. Só na hora de **ler** a ficha é que se descobre que
não há nada extraível.

Desde então o módulo **recusa esse arquivo**: depois do download, `ficha_anual`
confere a camada de texto com
[`tem_camada_de_texto()`](#ler-uma-ficha-financeira) e aborta o bloco com
`PdfImpressoIlegivel` — que aponta para esta seção. O PDF ruim fica no disco
com o nome bruto, para inspeção, e **não** recebe o nome de bloco, para não se
passar por resultado bom.

```python
import json
from selenium.webdriver.chrome.options import Options as ChromeOptions
from integra_gov.sei import criar_driver_chrome

destino = {"recentDestinations": [{"id": "Save as PDF", "origin": "local", "account": ""}],
           "selectedDestinationId": "Save as PDF", "version": 2}
opts = ChromeOptions()
opts.add_experimental_option("prefs", {
    "download.default_directory": str(PASTA_DOWNLOAD),
    "savefile.default_directory": str(PASTA_DOWNLOAD),
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "plugins.always_open_pdf_externally": True,
    "plugins.plugins_disabled": ["Chrome PDF Viewer"],
    "profile.default_content_settings.popups": 0,
    "profile.default_content_setting_values.automatic_downloads": 1,
    "printing.print_preview_sticky_settings.appState": json.dumps(destino),
})
driver = criar_driver_chrome(options=opts,
                            args_extra=["--kiosk-printing", "--disable-popup-blocking"])
```

Três pontos são críticos, descobertos ao vivo: sem
`automatic_downloads: 1` o Chrome bloqueia o download disparado pelo popup
de impressão (conta como download automático "extra" e passa a exigir
confirmação manual); sem fixar `selectedDestinationId: "Save as PDF"` no
`appState`, o `--kiosk-printing` manda a impressão para a impressora padrão
do Windows e abre o diálogo nativo "Salvar como", travando a automação à
espera de um clique que nunca vem; e `PASTA_DOWNLOAD` aqui precisa ser
exatamente a mesma pasta passada em `pasta_download` (seção anterior) — a
divergência entre as duas é a causa mais comum do `TimeoutError` citado
acima.

### Bloco sem dados não é erro

Cada bloco é resolvido por **evidência**, nunca por timeout silencioso: ou o
botão "Gerar Relatório" aparece (há dados — o bloco é impresso e entra em
`resultado.blocos_com_dados`), ou o CIS responde com a mensagem de "sem
dados para o critério solicitado" (entra em `resultado.blocos_sem_dados`,
sem gerar PDF). As duas situações são esperadas e **não** interrompem a
extração dos blocos seguintes.

Um **erro de verdade** no meio de um bloco (popup que não abre, sessão que
cai, timeout sem nenhuma das duas evidências) **aborta a pessoa inteira**:
`ExtracaoFichaEsiapeInterrompida` carrega `blocos_processados` (o que já foi
concluído, com ou sem dados) e `causa` (a exceção original) — os PDFs já
salvos permanecem em disco para diagnóstico, mas nenhum resultado parcial é
devolvido como se fosse completo.

```python
from integra_gov.esiape import ExtracaoFichaEsiapeInterrompida, FichaEsiapeIndisponivel

try:
    resultado = ficha.extrair("0000000", 2008, 2026)
except ExtracaoFichaEsiapeInterrompida as exc:
    print(exc.blocos_processados, exc.causa)
except FichaEsiapeIndisponivel:
    ...  # matrícula não encontrada na habilitação ativa (distinto de "sem dados")
```

### Multi-órgão: cobrindo quem migrou

`FichaAnualServidor` só enxerga o órgão da habilitação **ativa** — quem
migrou de órgão perde os anos anteriores **silenciosamente** nessa consulta
simples. `FichaMultiOrgao` encadeia a extração: consulta `CDCOINDFUN`
(`DadosFuncionaisOrgao`) para descobrir o órgão anterior e o ano de ingresso,
extrai a faixa do órgão atual, troca a habilitação (`TrocaHabilitacaoEsiape`)
e repete, até esgotar a cadeia ou alcançar o ano inicial pedido:

```python
from pathlib import Path
from integra_gov.esiape import FichaMultiOrgao

multi = FichaMultiOrgao(
    driver, orgao_inicial="00000", pasta_saida=Path("fichas/"),  # órgão fictício
)
resultado = multi.extrair("0000000", 2008, 2026)
```

Assim como `FichaAnualServidor`, `FichaMultiOrgao` também aceita
`pasta_download=` — repassada a cada `FichaAnualServidor` interno da cadeia
(uma faixa por órgão), pelo mesmo motivo: precisa coincidir com a pasta de
download configurada no `driver`.

Pontos importantes do resultado (`ResultadoMultiOrgao`):

- **O ano da virada pertence aos dois órgãos.** Quem entrou no órgão novo em
  dezembro deixou janeiro–novembro no órgão anterior — o módulo repete esse
  ano de fronteira nas duas consultas de propósito (evita perder o mês da
  troca), então `trilha` pode conter faixas com sobreposição de um ano nas
  bordas.
- **`trilha`** registra a cadeia percorrida: uma tupla
  `(orgao, matricula, ano_de, ano_ate)` por órgão visitado, na ordem em que
  foi consultado (do mais recente ao mais antigo).
- **`lacunas`** é a lista (sempre não-oculta) do que **não** foi coberto:
  faixa sem habilitação no órgão anterior, órgão anterior não encontrado no
  `CDCOINDFUN`, faixa que esgotou as tentativas técnicas, a consulta de
  dados funcionais (`CDCOINDFUN`) falhou, ou o limite de `max_saltos` foi
  atingido. `extrair()` **nunca levanta** por uma lacuna legítima — entrega
  o que conseguiu cobrir com as lacunas declaradas, para o chamador decidir
  o que fazer.
- **`falhas_tecnicas`** é o subconjunto de `lacunas` de origem **técnica**
  (timeout, sessão perdida, habilitação recusada) — distinto de uma lacuna
  **estrutural** (não há órgão anterior registrado: a cadeia realmente
  termina ali). Útil para saber se vale a pena repetir a extração.
- **`voltou_ao_orgao_inicial`** confirma que a habilitação foi devolvida ao
  `orgao_inicial` ao final (a próxima pessoa do lote não pode ser consultada
  no órgão errado). Quando `False`, `falhas_tecnicas` traz o motivo — trate
  como sinal para reabilitar manualmente antes de seguir o lote.

```python
print(resultado.pdf)                 # PDF único, mesclado em ordem cronológica
print(resultado.trilha)              # [(orgao, matricula, ano_de, ano_ate), ...]
if resultado.lacunas:
    print("cobertura incompleta:", resultado.lacunas)
if not resultado.voltou_ao_orgao_inicial:
    print("ATENÇÃO — reabilitar antes do próximo da fila:",
          resultado.falhas_tecnicas)
```

---

## Ler uma ficha financeira

Os módulos anteriores **produzem** o PDF da ficha. Este o **lê de volta como
dados**: recebe o arquivo — de servidor, aposentado, pensionista ou
instituidor — e devolve os lançamentos estruturados. Ele não decide nada de
negócio; quem escolhe o que fazer com os números é o script que consome.

```python
from integra_gov.ficha_financeira import ler_ficha_financeira

ficha = ler_ficha_financeira("ficha.pdf")   # caminho, bytes ou arquivo aberto

print(ficha.identificacao.nome, ficha.identificacao.tipo.value)
print(ficha.exercicio, ficha.emitido_em)

for lanc in ficha.lancamentos:
    print(lanc.competencia, lanc.rubrica, lanc.descricao,
          lanc.valor, lanc.natureza.value)
```

Consultas de conveniência (leitura, não regra de negócio):

```python
ficha.rubricas()                    # ('00597', '00599', '00600')
ficha.competencias()                # (Competencia(2024, 1), ...)
ficha.por_rubrica("00597")          # em ordem cronológica ("597" também acha)
ficha.por_competencia(2024, 11)     # tudo que caiu em novembro
ficha.por_natureza(Natureza.DESCONTO)
ficha.totais_de(2024, 11)           # os totais IMPRESSOS daquele mês
ficha.to_dict()                     # serializável em JSON (Decimal → texto)
```

### Um PDF pode conter várias fichas

`esiape.ficha_anual` mescla blocos de até 15 anos e `esiape.ficha_multi_orgao`
mescla vários órgãos num arquivo só — com **matrícula e órgão mudando entre
páginas**. Ler isso como "uma ficha" misturaria pessoas diferentes. A unidade
de retorno é *uma identidade em um exercício*:

```python
from integra_gov.ficha_financeira import ler_fichas_financeiras

for ficha in ler_fichas_financeiras("ficha_0000000_2008_2026.pdf"):
    print(ficha.identificacao.matricula, ficha.identificacao.orgao_codigo,
          ficha.exercicio, ficha.origem.paginas)
```

`ler_ficha_financeira()` atende o caso simples e levanta `MultiplasFichasError`
quando há mais de uma — devolver a primeira seria escolher em silêncio por
quem chamou.

### A leitura se autoconfere

A soma dos lançamentos de cada mês é comparada com o `TOTAL BRUTO`,
`TOTAL DESCONTOS` e `TOTAL LÍQUIDO` **impressos na própria ficha**. Isso não é
enfeite: é o que impede um erro de leitura de virar um número silenciosamente
trocado.

```python
if ficha.consistente:               # gate de uma checagem só
    ...
else:
    for aviso in ficha.avisos:
        print(aviso.codigo, aviso.competencia, aviso.mensagem)

    for total in ficha.totais:      # granularidade por mês
        if not total.confere:
            print("não fecha:", total.competencia)
```

Os códigos de aviso são **estáveis** (`CodigoAviso.MES_NAO_CONFERE`,
`NATUREZA_INDEFINIDA`, `TOTAIS_AUSENTES`, `PAGINA_ILEGIVEL`), para decisão
programática sem casar substring de mensagem.

Duas classes de problema, tratadas de forma diferente de propósito:

- **Divergência aritmética** (os totais não fecham) vira aviso e
  `confere=False`. O dado degradado fica à vista e o consumidor decide.
  `ler_fichas_financeiras(..., strict=True)` transforma em exceção.
- **Perda de dado** (uma linha da tabela não reconhecida) levanta **sempre**,
  com a linha e a página no payload. Total que não fecha é honesto por
  construção; linha descartada em silêncio some sem rastro e deixa a ficha
  parecendo íntegra estando incompleta.

Mês sem totais impressos **não** é mês conferido: sai com `confere=False` e
`TOTAIS_AUSENTES`. Não houve divergência porque não houve conferência.

### A coluna R/D e a natureza dos lançamentos

A ficha **não** imprime o marcador `R/D` em toda linha: ele aparece onde o
grupo começa e as linhas seguintes o herdam. A biblioteca resolve isso na
ordem impressa e expõe os dois lados:

```python
lanc.natureza             # Natureza.RENDIMENTO / DESCONTO / INDEFINIDA
lanc.natureza_declarada   # "R", "D" ou None (herdado)
lanc.natureza_inferida    # True quando veio por herança
```

A mesma rubrica pode ter naturezas **opostas** em meses diferentes — a 00599
(adiantamento da gratificação natalina) é crédito em junho e débito em
novembro. A natureza é do **lançamento**, nunca da rubrica.

`Natureza.INDEFINIDA` é a admissão honesta de que não deu para determinar
(linha sem marcador e sem grupo anterior). O mês que a contém nunca é dado por
conferido, mesmo que os números batam: a soma está incompleta dos dois lados.

### O PDF precisa ter camada de texto

A biblioteca **não faz OCR** — reconhecer dígito por dígito em valor monetário
troca centavos sem avisar. Um PDF impresso por um driver que converte as fontes
em contorno vetorial fica visualmente perfeito e completamente ilegível por
máquina. O caso conhecido é a impressora virtual **`Microsoft Print to PDF`**
do Windows.

Qualquer PDF que preserve o texto serve, **não importa a origem**: se o sistema
oferecer download direto do arquivo, é a via mais segura (o PDF vem pronto do
servidor, sem passar por driver de impressão); se for impressão, use um destino
que não vetorize as fontes.

O guard é público e reutilizável — vale para qualquer PDF que você acabou de
gerar, não só para ficha financeira:

```python
from integra_gov.ficha_financeira import tem_camada_de_texto

if not tem_camada_de_texto(caminho):
    ...   # ilegível por máquina: obtenha outro antes de seguir o pipeline
```

Sem essa verificação, um PDF assim atravessa o pipeline inteiro em silêncio e
entrega uma ficha sem lançamento nenhum, como se fosse uma ficha vazia
legítima. `ler_fichas_financeiras()` já falha com `PdfSemTextoError` nesse caso,
explicando o que fazer.

### Os dois layouts

São lidos o **relatório do SIAPE mainframe** (`L.A54120.DE`, monoespaçado,
largura fixa, seis meses por página) e a **impressão web do e-SIAPE** (tabela
por `|`, dois semestres por página). Cada página é classificada pelo seu
próprio detector, então um PDF mesclado pode misturar os dois — `origem.layout`
diz de onde cada ficha veio.

Página com texto que não corresponde a nenhum dos dois levanta
`LayoutNaoReconhecidoError`, com o número da página.

Os dois foram validados contra PDFs reais. No caso do e-SIAPE, o corte por `|`
foi escolhido por ser mais resistente que posição de coluna às variações da
extração — e o round-trip confirmou: a estrutura sobrevive intacta, e o ruído da
impressão (cabeçalho com data/hora, rodapé com a URL e o `SESSIONID`) é
descartado sem virar lançamento.
