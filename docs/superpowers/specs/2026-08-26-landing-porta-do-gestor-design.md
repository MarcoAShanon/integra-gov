# Design — a porta do gestor: o que a página exige e por quantos caminhos se fala com ela

*26/08/2026. Escopo: o TEXTO de três fatias já publicadas (`01b-gestor`,
`05-conversao` e uma linha da `03-contexto`), mais um canal de contato novo no
fecho da 05.*

*Não muda estrutura, token, primitiva nem contrato. Muda o que a página **exige**
do leitor e quantas **portas** ela oferece.*

## 0. Enquadramento — herdado, e vale por inteiro

Vale integralmente o § 0 da spec de 20/08 (`2026-08-20-landing-divulgacao-design.md`):
**parceria entre gestores, não relação comercial.** Nada aqui o revoga.

Esta spec acrescenta um corolário que faltava e que é a raiz das quatro decisões
abaixo:

> Numa parceria entre pares, **quem convida não estabelece requisitos de
> admissão.** Uma lista de pré-requisitos técnicos na porta de entrada é um
> formulário de qualificação — o gesto de quem seleciona clientes, não o de quem
> chama um colega para conversar.

## 1. O problema

A fatia `01b-gestor` foi escrita (commit `e9b83d2`) para derrubar uma objeção
única: *"isso é coisa de TI, eu não tenho equipe."* Ela derruba a objeção e, no
mesmo bloco, **reintroduz a objeção como requisito**:

- exige *"alguém que leia e ajuste código Python — ou que topa aprender"*;
- condiciona a *"uma máquina Windows"* (com a justificativa do terminal 3270);
- manda o gestor para a fatia 05 por um botão — e a 05 é um formulário-por-e-mail
  que pede a versão do SEI, se as máquinas são Windows e se há alguém que
  programe.

O leitor lê "você não precisa ser técnico", clica, e três telas abaixo encontra
exatamente a barreira de que acabou de ser dispensado. **A página se desmente no
clique que ela mesma pediu.**

Havia ainda um terceiro ponto, na `03-contexto`, que só apareceu na varredura:
o cartão da comparação honesta lista *"Para começar — alguém da equipe lê e
ajusta Python"*, e é para lá que a 01b aponta ao dizer que a comparação está
adiante.

## 2. As quatro decisões do usuário — 26/08/2026, verbatim

> **D1.** *"precisamos de uma abordagem ainda menos técnica, não gostaria de
> falar neste trecho que o gestor precisa de algum disposto a aprender python e
> sim tentar buscar mais informações sobre o projeto"*

O degrau de entrada não é ter um programador. É **querer conhecer o projeto**. O
gestor não decide nada nesta seção; ele descobre que vale a pena olhar.

> **D2.** *"não citar que precisa de uma máquina windows somente se for utilizar
> o SIAPE já que o que executamos online é por custo próprio sem apoio do
> governo, dificilmente outros servidores estarão dispostos à isto"*

O motivo importa e fica registrado: dizer *"Windows só se for o SIAPE"* abre a
pergunta seguinte — *e se não for?* —, cuja resposta hoje é **servidor online
pago do próprio bolso, sem apoio institucional**. Não se abre essa porta, porque
ela leva a um custo que nenhum outro servidor vai querer assumir.

> **D3.** *"Não quero limitar no texto que estamos limitados a contato por
> e-mail e nada mais"*

> **D4.** *"não quero fechar portas e nem possibilidades"*

D4 é o princípio de que D1–D3 são casos. Ele governa também o parágrafo do
limite (§ 4.4 e § 5.5 abaixo).

## 3. Decisões de desenho desta sessão

Todas confirmadas pelo usuário no brainstorm de 26/08.

| # | decisão | alternativa descartada |
|---|---|---|
| E1 | **Escopo: 01b + 05 no mesmo trabalho**, mais uma linha da 03 | corrigir só a 01b (deixaria a página contraditória no clique) |
| E2 | **A lista de pré-requisitos permanece**, sem os dois itens técnicos | trocá-la por um convite sem lista |
| E3 | **O item da pessoa fica, reescrito sem Python** — 4 itens, não 3 | 3 itens (deixaria *"quem faz?"* sem resposta, e o leitor completa com "TI") |
| E4 | **Canais: e-mail como um caminho entre outros + canal direto (WhatsApp/telefone)** | GitHub como canal; videoconferência como porta de entrada própria |
| E5 | **O limite continua dito, sem "Termina aí"** — divisão de trabalho, não recusa | tirar o limite inteiro (criaria expectativa de suporte insustentável) |
| E6 | **A linha da 03 é reescrita junto** | deixá-la (contradição) ou apagá-la (perderia um custo real) |

**O número do canal direto: `(24) 98849-3257`**, ao lado do e-mail institucional
`marco.aurelio-silva@gestao.gov.br`, que continua.

O custo de publicar um número em página aberta — raspagem por robô, spam
permanente, cache e índice que não se desfazem — foi apresentado ao usuário
antes da decisão, e a decisão é dele.

## 4. A fatia `01b-gestor`

### 4.1 O cartão de pré-requisitos

Título: `O que a sua unidade precisa ter` → **`O que já basta para começar`**.

Faz par deliberado com o `O que você não precisa ter para começar` da fatia 05:
um diz o que basta, o outro o que não é exigido.

Quatro pares na `.ficha` (era cinco):

| `dt` | `dd` |
|---|---|
| **Uma pessoa da própria área** | Quem já faz esse trabalho hoje e conhece a regra por dentro. Não precisa ser da área de TI, nem cuidar só disso. |
| **Um fluxo, não o setor** | *(inalterado)* |
| **O acesso que já existe** | *(o `dd` fica inalterado — inclusive o "que o perfil **dela** já alcança", cujo antecedente continua sendo o primeiro par. Só o `dt`, que era "O acesso que ela já tem", perde o pronome.)* |
| **A sua autorização** | *(inalterado)* |

**Sai por inteiro** o par `Uma máquina Windows` / `Só se o fluxo passar pelo
terminal 3270 do SIAPE…` (D2).

### 4.2 O parágrafo da objeção

Mantido, com uma frase acrescentada ao fim — é D1 virada texto:

> "E você não precisa decidir nada agora: o primeiro passo é conhecer o que já
> existe e ver se alguma parte serve para o seu caso."

**Não use "pronto"** aqui nem em lugar nenhum: é uma das quatro palavras vetadas
pelo `verificar.py` (§ 8, item 3).

### 4.3 O mapa — item *Piloto assistido*

De:

> "Uma conversa de diagnóstico e a indicação do caminho, **por e-mail**.
> **Termina aí**: quem implanta, testa e opera depois é a sua equipe."

Para:

> "Uma conversa de diagnóstico sobre o seu fluxo e a indicação do caminho. Quem
> implanta e opera é a sua equipe, que conhece o órgão."

### 4.4 A promessa

De:

> "…**E termina aí**: não há acompanhamento depois dela, não há prazo combinado e
> ninguém do INTEGRA implanta, configura ou opera nada dentro do seu órgão."

Para:

> "A conversa é uma videoconferência de diagnóstico sobre o seu fluxo e a
> indicação do caminho — quais blocos servem e onde isso costuma travar. Quem
> implanta, configura e opera é a sua equipe, que conhece o órgão por dentro;
> daí em diante a conversa segue se fizer sentido para os dois lados."

O limite continua **dito** — não há suporte, não há implantação por nós — mas
como divisão de trabalho. E não se combina prazo nem acompanhamento, porque a
frase não combina nada: ela deixa em aberto.

### 4.5 O comentário de projeto no topo do arquivo

Reescrito no mesmo commit. Ele hoje **justifica por escrito** o Python, o Windows
e o "termina aí" — comentário desatualizado é armadilha para a próxima sessão.
Preservar: a justificativa do fundo `--bg` (a lacuna do § 4.1 do contrato), a do
`.btn-s` secundário e a de "nenhum número novo".

## 5. A fatia `05-conversao`

### 5.1 O cartão do pedido

Título: `O que mandar no e-mail.` → **`O que ajuda a conversa a render.`**

Abertura, hoje *"Não há formulário nesta página, e não vai haver…"* →

> "Escreva, ligue ou chame no WhatsApp — como for mais fácil para você. O que faz
> a conversa render é chegar com estas seis coisas em mãos, em texto corrido
> mesmo, na ordem que você quiser."

A negação do formulário sai: ela era uma porta se fechando (D4).

### 5.2 Dois dos seis itens

| item | passa a |
|---|---|
| **Os sistemas** | "Quais estão no fluxo: SEI (o nosso é o `4.1.5`), SIAPE — pelo terminal antigo ou pelo e-SIAPE na web —, Sigepe, planilha, e-mail." |
| **Quem vai tocar** | "Quem faz esse trabalho hoje na sua unidade e quem assina a decisão. Como a implantação é do seu órgão, essa é a resposta que mais pesa." |

Some a frase do Windows (D2) e some a exigência de Python (D1). O `3270` como
jargão sai junto — *"o terminal antigo"* diz ao gestor-usuário o que ele precisa
saber; o `4.1.5` fica, em `.num`, porque é dado que a resposta dele deve conter.

**O aviso de não mandar dado pessoal** (CPF, matrícula, processo real) fica
**intocado**. É regra de privacidade, não de tom.

### 5.3 O gatilho do meio

De *"…programa, ou tem aí alguém que programe, e quer saber o que reaproveitar
antes de escrever código do zero"* para:

> "…tem aí alguém que já mexe com planilha, macro ou automação e quer saber o que
> dá para reaproveitar antes de começar do zero;"

Deixa a porta aberta ao leitor técnico sem exigir que ele exista. A frase
seguinte — *"Não precisa ser da área de TI. Precisa ter o problema e ter o
acesso."* — fica como está: agora ela é verdade em toda a página.

### 5.4 O cartão dos passos

Título: `O que acontece depois do e-mail.` → **`O que acontece depois que você
chama.`**

Primeiro passo, hoje *"Começa pelo seu e-mail, escrito com os seis itens da
lista."* →

> "Começa pelo seu contato — e-mail, telefone ou WhatsApp, como preferir."

Os outros dois passos (videoconferência de diagnóstico; indicação do caminho)
ficam.

### 5.5 O parágrafo do limite

Mesma decisão do § 4.4: sai o "Termina aí" e a negação em série; fica a divisão
de trabalho e a continuidade em aberto. **Permanece** a frase de registro:

> "Do outro lado há um servidor público com o próprio trabalho para tocar, não
> uma central de atendimento."

Ela não fecha porta — diz o registro da conversa, e é § 0 puro.

### 5.6 O fecho — o canal novo

- A linha `.endereco` passa a trazer **o e-mail e o `(24) 98849-3257`**.
- `.acoes` passa a três botões: **Escrever o e-mail** (`.btn-p`) ·
  **Chamar no WhatsApp** (`.btn-s`, `https://wa.me/5524988493257`) ·
  **Abrir o repositório** (`.btn-s`).
- O parágrafo `.fuga` é reescrito para mencionar os dois canais, preservando o
  seu ponto atual: quem prefere não falar com ninguém tem o repositório, e esse
  caminho não passa por conversa nenhuma.
- O `.rodape .contato` ganha a linha **telefone**.

**Tipografia do número:** o telefone é número (§ 5.4 do contrato) *e*
identificador que o leitor copia (§ 5.4-b, item 5). Nos dois casos vai em mono.
`.endereco` **já é mono** (`05-conversao.css:136`), então ali ele herda; no
`.rodape .contato` é preciso conferir o computado do link e, se o bloco não for
mono, o número entra em `.num`.

### 5.7 O comentário de projeto no topo do arquivo

Diz hoje, por escrito: *"Não há formulário, newsletter, **WhatsApp**, prazo, fila
nem acompanhamento."* Reescrito no mesmo commit.

## 6. A fatia `03-contexto` — uma linha

No cartão da comparação honesta:

> `Para começar` — *"Alguém da equipe lê e ajusta Python."*
> → **"Alguém da própria área acompanha o roteiro."**

Mantém o custo dito (a automação exige alguém por perto, e o cartão existe para
pôr os dois preços à vista) sem transformar linguagem de programação em
pré-requisito. É o buraco por onde a correção vazaria: a 01b manda o leitor
exatamente para lá.

## 7. O que NÃO muda, e por quê

1. **A fatia 04 (`#oferta`)** — diz *"biblioteca Python"* e marca o módulo do
   SIAPE com a etiqueta *"extra · Windows"*. Ali é **descrição do que o pacote
   é**, num catálogo técnico, não exigência feita ao leitor. A página continua
   dizendo a verdade sobre a sua natureza; ela só para de cobrá-la na porta.
2. **Nenhum número de resultado muda**, e nenhum entra. (O telefone do § 5.6 é
   dado de contato, não indicador.) O `−89%` e a sua divergência
   com a revista seguem como estão (§ 5.3-b do contrato) — é item do ciclo de
   conteúdo pendente, não deste trabalho.
3. **O aviso de dado pessoal**, as garantias (`sem contrato / sem fornecedor /
   sem licitação / sem senha embutida / sem habilitação especial`) e o link do
   repositório: intocados.
4. **Nenhum token, primitiva, breakpoint ou regra de contrato** é criado ou
   alterado. A lacuna do § 4.1 (a sexta faixa) **continua aberta** — ver § 10.

## 8. Restrições que este trabalho toca

1. **`.acoes` com três botões** (contrato § 8.3-e). A primitiva já resolve:
   abaixo de 768px vira coluna com `width:100%` e `align-self:stretch`,
   independentemente do alinhamento do pai. Nenhum CSS novo.
2. **`.ficha` com quatro pares** (§ 8.3-k). Cada par continua com o `<div>` de
   agrupamento — sem ele o `<dl>` perde a semântica.
3. **Palavras vetadas** (`verificar.py`): `completo`, `pronto`, `finalizado`,
   `fecha o ciclo`. A `FRASES_PERMITIDAS` **não é ampliada** por este trabalho.
4. **Privacidade / CPF**: verificado antes de escrever a spec — `24988493257`
   **não** passa no dígito verificador do módulo 11, e os regexes não casam
   dentro de `tel:+55…` nem de `wa.me/55…`. O número **não** dispara o portão.
5. **Sem dependência de JavaScript**: nenhum texto, link ou botão alterado é
   gerado por script. Os `.rise` continuam escondidos só por `.js .rise`.
6. **Alvo de toque 44×44** (§ 8.4-b): o botão novo e o link do telefone entram
   nas regras que já existem (`.endereco a` e `.rodape .contato a` já carregam
   `min-height:44px`); o `.btn` é garantido pela primitiva.

## 9. Verificação

O ciclo do `site/README.md`, sem atalho — **os quatro têm de passar**:

1. `site/montar.py` (regenera o `index.html`; **nunca editar o `index.html`**)
2. `site/verificar.py`
3. `site/auditar_contrato.py`
4. `pytest tests/test_site.py`

Além dos quatro, duas checagens de olho que os portões não fazem:

- **Ler a 01b e a 05 em sequência**, como o leitor faz ao clicar no botão:
  nenhuma exigência da 05 pode contradizer o que a 01b acabou de dispensar.
- **Conferir os três links novos** (`mailto:`, `tel:`, `wa.me`) no navegador — o
  portão vê que o `href` existe, não que ele está correto.

**Publicação:** o redeploy do `site/README.md` (assets primeiro, página por
último) só acontece com **ordem explícita do usuário**, e este trabalho não a
tem. Ele também não substitui as duas revisões que a 01b ainda deve: crítico
cego e sessão de revisão dedicada.

## 10. O que fica em aberto

1. **A lacuna do § 4.1 do contrato** (a alternância de fundos fixada em cinco
   fatias, sem linha para a sexta) **continua aberta**. A 01b segue com `--bg`
   por decisão registrada no comentário dela; virar lei no contrato é trabalho
   à parte.
2. **A 01b continua sem crítico cego e sem sessão de revisão**, e agora a 05
   também tem texto novo não revisado por terceiro.
3. **O ciclo de conteúdo pendente** da spec de 20/08 segue intacto: nenhum órgão
   adotante citado, nenhuma linha de Python para o leitor técnico, a divergência
   do `−89%` não explicada na página, e a densidade (~2.640 palavras).
4. **O custo do número publicado** é permanente e não reversível por edição:
   cache e índice de busca guardam o que já foi servido.
