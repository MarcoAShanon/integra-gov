# integra-gov

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
from integra_gov.sei import (
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
from integra_gov.sei import fechar_tela_aviso
fechar_tela_aviso(driver)
```

Mais exemplos em [`examples/`](examples/).

### Criar um processo

`IniciarProcesso.iniciar()` devolve o **número (NUP)** do processo criado:

```python
from integra_gov.sei import IniciarProcesso

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

### Incluir um documento externo (upload de arquivo)

Anexa um arquivo pronto (PDF etc.) como documento externo a um processo **já
aberto**. O upload vai direto ao `<input type=file>` do SEI (sem janela nativa,
sem `pywinauto`). `nome_arvore` é o rótulo do documento **na árvore** do processo:

```python
from integra_gov.sei import InserirDocumentoExterno, ProcessoSei

ProcessoSei(driver, "19975.018906/2026-39").acessar()   # abre o processo

nome = InserirDocumentoExterno(
    driver,
    tipo_serie="Ofício",                    # série EXATA do seu SEI
    nome_arvore="Ofício 123 - Resposta",    # rótulo na árvore
    arquivo="C:/docs/oficio.pdf",           # caminho do arquivo
    nivel_acesso="publico",                 # ou "restrito" (+ hipotese_legal)
).inserir()
print(nome)   # "Ofício 123 - Resposta"
```

Versão atual: formato **nato-digital** (o mais comum). "Digitalizado nesta
unidade" (com tipo de conferência) virá depois.

### Incluir um documento interno (Despacho, Nota Técnica, …)

Gera um documento do próprio SEI num processo **já aberto**, opcionalmente a
partir de um **documento modelo** (o protocolo de um documento base, cujo
conteúdo é clonado — útil para instruções processuais padronizadas em escala).
Após salvar, o SEI abre o editor numa janela nova; o módulo a fecha e devolve o
**rótulo do documento na árvore**:

```python
from integra_gov.sei import IncluirDocumentoInterno, ProcessoSei

ProcessoSei(driver, "19975.018906/2026-39").acessar()   # abre o processo

rotulo = IncluirDocumentoInterno(
    driver,
    tipo_documento="Despacho",       # tipo EXATO da lista do seu SEI
    documento_modelo="12345678",     # opcional: protocolo do documento base (modelo)
    nome_arvore="- Encaminhamento",  # opcional: nome extra na árvore
    nivel_acesso="publico",          # ou "restrito" (+ hipotese_legal)
).incluir()
print(rotulo)   # ex.: "Despacho 12345678"
```

Versão atual: texto inicial **"Documento Modelo"** ou nenhum. "Texto Padrão"
virá depois; a edição do conteúdo será um módulo próprio.

### Editar o conteúdo (preencher um modelo com placeholders)

O padrão para instrução processual **em escala**: a equipe mantém um documento
**modelo** no próprio SEI (com placeholders no texto, ex.: `{{NOME}}`), a
automação **clona** o modelo (`documento_modelo=`) e preenche os campos. A
substituição é injetada direto na API do CKEditor (`getData`/`setData`) — sem
simular teclado, sem "localizar e substituir" na tela, e **sem nenhuma
habilitação institucional** (usa a mesma sessão logada de sempre):

```python
from integra_gov.sei import EditarConteudo, IncluirDocumentoInterno, data_por_extenso

IncluirDocumentoInterno(
    driver, "Despacho",
    documento_modelo="12345678",       # protocolo do modelo com placeholders
).incluir()

contagens = EditarConteudo(driver, {
    "{{NOME}}": "MARIA DA SILVA",
    "{{CPF}}": "111.111.111-11",
    "{{DATA}}": data_por_extenso(),    # "2 de julho de 2026"
}).editar()
```

Rede de segurança: se algum placeholder não for encontrado no documento, o
módulo **fecha o editor sem salvar** e falha listando o que faltou — nada é
gravado pela metade. Os valores são escapados por padrão (texto literal);
`escapar_html=False` injeta todos como HTML cru, ou `chaves_html={...}` injeta
HTML cru **só** nos placeholders escolhidos (veja a seguir).

### Referenciar outro documento (link nativo do SEI)

Um link para outro documento no editor do SEI não é um `<a href>` comum: é uma
**âncora nativa** (`montar_link_documento`) que o SEI resolve na visualização. O
texto visível é o **protocolo** (número visível), mas o link é composto pelo
**`id_documento`** (id **interno**, um número diferente) — capturado pelo
`DocumentosArvore` no campo `DocumentoNo.id_documento`. Injete a âncora como HTML
cru num placeholder, listando-o em `chaves_html`:

```python
from integra_gov.sei import DocumentosArvore, EditarConteudo, montar_link_documento

alvo = DocumentosArvore(driver).listar(contendo="44414392")[0]
link = montar_link_documento(alvo.id_documento, alvo.numero)   # âncora ancora_sei

EditarConteudo(driver, {
    "{{NOME}}": "MARIA DA SILVA",   # texto normal (escapado)
    "{{DOC_REF}}": link,             # HTML cru (o link)
}, chaves_html={"{{DOC_REF}}"}).editar()
```

Só os placeholders em `chaves_html` entram sem escape; o resto continua escapado
(texto literal), tudo numa **única** passada.

### Assinar um documento

Assina o documento selecionado com a **senha do próprio servidor** — a senha é
parâmetro (vem de quem chama, via `getpass`/cofre), **nunca embutida nem
registrada em log**. É o mesmo princípio do SIAPE: você é quem autoriza.

```python
from getpass import getpass
from integra_gov.sei import AssinarDocumento

AssinarDocumento(driver, senha=getpass("Senha do SEI: ")).assinar()
# levanta AssinaturaError se a senha for recusada ou a assinatura não confirmar
```

O módulo **não reporta "assinado" por suposição**: só retorna com sucesso quando
o modal de assinatura fecha sem erro; senha recusada levanta `AssinaturaError`.

> ⚠️ **Governança:** assinar em lote é assinar **sem revisar** cada documento. A
> conferência antes da assinatura é responsabilidade da aplicação que monta o
> fluxo — a biblioteca fornece o mecanismo, não o controle editorial.

### Apontar um documento existente (consultar e selecionar a árvore)

Os módulos de documento (assinar, editar) agem sobre o documento **selecionado**
na árvore. Para apontar um documento existente — e para consultar a árvore como
dados — use `DocumentosArvore`:

```python
from integra_gov.sei import DocumentosArvore, TipoDocumento

arvore = DocumentosArvore(driver)

for d in arvore.listar():                 # todos os documentos, como dados
    print(d.numero, d.tipo.name, d.texto)

arvore.contar(contendo="Despacho")        # quantos "Despacho"
arvore.existe("44414392")                 # há esse documento?

doc = arvore.selecionar("44414392")       # clica (seleciona) pelo protocolo
# agora AssinarDocumento(driver, senha).assinar() age sobre ELE
```

Cada item é um `DocumentoNo` (`texto`, `numero`, `tipo`, `id`, `id_documento`).
Segurança: `selecionar()` **aborta** se o texto casar com vários nós e você não
passar `indice=` — casar pelo número do protocolo (único) evita a ambiguidade.
(O `id_documento` — id **interno**, distinto do protocolo visível — é o que
compõe um link para o documento; veja
[Referenciar outro documento](#referenciar-outro-documento-link-nativo-do-sei).)

Quando o processo tem muitos documentos, o SEI os agrupa em **pastas
colapsadas** (a partir de ~20). `DocumentosArvore` **expande todas as pastas
automaticamente** antes de ler/selecionar, então nenhum documento é perdido;
passe `expandir=False` para desligar, ou chame `arvore.expandir()` à mão.

### Marcadores

Os marcadores do SEI (etiquetas coloridas) aparecem em **dois contextos**, por
isso duas classes. Na tela **Controle de Processos**, `Marcadores` consulta a
lista e filtra os processos por marcador:

```python
from integra_gov.sei import Marcadores

marcadores = Marcadores(driver)
for m in marcadores.listar():                 # todos os marcadores da unidade
    print(m.id, m.nome, m.quantidade, m.cor)

marcadores.selecionar("INTEGRA - RETORNO")    # filtra a lista por esse marcador
marcadores.remover_filtro()                   # volta à lista completa
```

Num **processo aberto**, `MarcadorProcesso` inclui/remove um marcador **daquele**
processo (modal "Gerenciar Marcador"):

```python
from integra_gov.sei import MarcadorProcesso

mp = MarcadorProcesso(driver)
mp.incluir("INTEGRA - RETORNO", "Aguardando retorno")  # mensagem opcional (≤ 250)
mp.listar()                                            # ['INTEGRA - RETORNO', ...]
mp.remover("INTEGRA - RETORNO")
```

### Controle de prazo

Define ou exclui o prazo (em **dias**) de um processo aberto:

```python
from integra_gov.sei import ControlePrazo

ControlePrazo(driver).definir(30)   # prazo de 30 dias (1..9999)
ControlePrazo(driver).excluir()     # remove o prazo
```

### Concluir um processo

Encerra o processo aberto. Distingue o **bloqueio** (documento com hipótese legal
pendente) de uma falha técnica, por exceções:

```python
from integra_gov.sei import ConcluirProcesso
from integra_gov.sei.exceptions import ProcessoBloqueadoError

try:
    ConcluirProcesso(driver).concluir()
except ProcessoBloqueadoError:
    ...   # o SEI recusou: há documento com acesso restrito / hipótese legal pendente
```

### SIAPE (terminal 3270)

O acesso ao SIAPE passa pelo portal SIAPENet (web, com certificado digital) e por
um emulador de terminal 3270 (IBM HOD). Você se autentica; a biblioteca conduz o
resto:

```python
from integra_gov.sei import criar_driver_chrome
from integra_gov.siape import (
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
| `integra_gov.sei.navegador` | Abre o Chrome (ajustes gov) com retry + limpeza de `chromedriver` órfão | ✅ |
| `integra_gov.sei.iframes` | Navegação entre iframes (tolerante a SEI 3.x/4.x) | ✅ |
| `integra_gov.sei.processo` | Acesso a um processo existente | ✅ |
| `integra_gov.sei.selecao_unidade` | Troca a unidade de trabalho | ✅ |
| `integra_gov.sei.tela_aviso` | Fecha o aviso pós-login que bloqueia a tela | ✅ |
| `integra_gov.sei.login` | Autenticação no SEI | ✅ |
| `integra_gov.sei.iniciar_processo` | Criação de um novo processo (devolve o NUP) | ✅ |
| `integra_gov.sei.inserir_documento_externo` | Inclui um documento externo (upload de arquivo) | ✅ |
| `integra_gov.sei.incluir_documento_interno` | Inclui um documento interno (Despacho, Nota Técnica…) | ✅ |
| `integra_gov.sei.editar_conteudo` | Substitui placeholders no editor (injeção CKEditor) | ✅ |
| `integra_gov.sei.assinar_documento` | Assinatura eletrônica (senha do próprio servidor) | ✅ |
| `integra_gov.sei.documentos_arvore` | Consulta/seleção de documentos na árvore | ✅ |
| `integra_gov.sei.marcador` | Marcadores — filtrar a lista e marcar/desmarcar processo | ✅ |
| `integra_gov.sei.controle_prazo` | Define/exclui o prazo (em dias) de um processo | ✅ |
| `integra_gov.sei.concluir_processo` | Conclui (encerra) um processo | ✅ |
| `integra_gov.sei.nivel_acesso` | Nível de acesso (público/restrito) — reutilizável | ✅ |
| `integra_gov.sei.barra_icones` | Clique em ícones da barra do documento — reutilizável | ✅ |
| `integra_gov.sei.gerar_documento` | Tela "Gerar Documento" (escolha do tipo) — reutilizável | ✅ |
| `integra_gov.sei.exceptions` | Exceções tipadas | ✅ |

### SIAPE 3270 — Windows, extra `[siape]`

| Módulo | Descrição | Status |
|--------|-----------|--------|
| `integra_gov.siape.acesso_web` | SIAPENet → certificado (você autentica) → captura do OTP (só Selenium) | ✅ |
| `integra_gov.siape.lancador` | Executa o módulo HOD baixado e abre o Terminal 3270 | ✅ |
| `integra_gov.siape.controle` | Interação base com o terminal (ler tela, enviar teclas) | ✅ |
| `integra_gov.siape.conexao` | Acesso/login (OTP) + acessar transação (`>COMANDO`) | ✅ |
| `integra_gov.siape.habilitacao` | Troca de habilitação (ÓRGÃO/UPAG) via `TROCAHAB` | ✅ |
| `integra_gov.siape.exceptions` | Exceções tipadas | ✅ |

| _(planejado)_ | e-SIAPE (web), demais transações, utilidades | 🔜 |

## Como contribuir

Veja [CONTRIBUTING.md](CONTRIBUTING.md). Contribuições de outros servidores e desenvolvedores são bem-vindas.

## Licença

[MIT](LICENSE). Software livre, no espírito de colaboração entre órgãos públicos.
