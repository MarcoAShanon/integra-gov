# A porta do gestor — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** tirar da landing as três exigências que barram o gestor não-técnico na
porta de entrada (Python, máquina Windows, contato só por e-mail) e abrir um
segundo canal de contato, sem que a página deixe de dizer a verdade sobre o que
a automação custa.

**Architecture:** a página é **montada**, não editada — `site/parts/` tem uma
fatia por seção e `site/montar.py` concatena em `site/index.html`. Toda tarefa
aqui edita **fatias**, nunca o `index.html`. Cada tarefa começa por um teste em
`tests/test_site.py` que falha porque o texto vetado ainda está no arquivo, e
termina com os portões da fatia passando e um commit.

**Tech Stack:** HTML/CSS estáticos, Python 3 (montador, verificador e auditor
próprios), pytest.

## Global Constraints

Valores copiados **verbatim** da spec
`docs/superpowers/specs/2026-08-26-landing-porta-do-gestor-design.md`.

1. **Nunca editar `site/index.html`.** Ele é gerado; a edição se perde na
   próxima montagem (`site/README.md`).
2. **`site/parts/contrato.md` é lei.** Nenhuma tarefa aqui cria ou altera token,
   primitiva, breakpoint ou regra de contrato.
3. **Palavras vetadas no texto visível** (`site/verificar.py`, linha 36):
   `completo`, `pronto`, `finalizado`, `fecha o ciclo`. A tupla
   `FRASES_PERMITIDAS` **não é ampliada** por este trabalho.
4. **Nenhum número de resultado muda, e nenhum entra.** O `−89%` e a sua
   divergência com a revista seguem como estão (contrato § 5.3-b).
5. **Todo número visível vai em mono**, dentro de `.num` (contrato § 5.4).
   Exceção única: número dentro de `.pill`.
6. **O e-mail institucional é `marco.aurelio-silva@gestao.gov.br`** e continua.
   **O canal direto é `(24) 98849-3257`** — `tel:+5524988493257` e
   `https://wa.me/5524988493257`.
7. **A fatia `04-oferta` não é tocada.** Ela diz "biblioteca Python" e marca o
   módulo do SIAPE com "extra · Windows" porque é **catálogo técnico**, não
   exigência feita ao leitor (spec § 7.1).
8. **Publicação externa (redeploy) NÃO faz parte deste plano.** Só com ordem
   explícita do usuário, e ela não foi dada.
9. Comando dos portões, sempre com caminho absoluto do venv do repo:
   `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe`

## File Structure

| arquivo | responsabilidade | tarefas |
|---|---|---|
| `tests/test_site.py` | portão de regressão do texto: o helper `_fatia()` e os testes que cobram cada decisão | 1, 2, 3, 4 |
| `site/parts/01b-gestor.html` | a porta do gestor — o cartão do que basta, o mapa, a promessa | 1 |
| `site/parts/03-contexto.html` | a comparação honesta — uma linha | 2 |
| `site/parts/05-conversao.html` | o convite: o pedido, os gatilhos, os passos, o limite, o fecho e o rodapé | 3, 4 |
| `CHANGELOG.md` | registro da mudança | 5 |

Nenhum arquivo é criado. Nenhum CSS é tocado — as quatro tarefas mexem só em
texto e em `href`, e a única mudança estrutural (um terceiro `.btn` dentro do
`.acoes` que já existe) é absorvida pela primitiva (contrato § 8.3-e).

---

### Task 1: A fatia 01b — a porta para de exigir

**Files:**
- Modify: `tests/test_site.py` (acrescentar no fim do arquivo)
- Modify: `site/parts/01b-gestor.html`

**Interfaces:**
- Produces: o helper `_fatia(nome: str) -> str`, usado pelas Tasks 2, 3 e 4.
  Recebe o nome da fatia **sem extensão** (ex.: `"01b-gestor"`) e devolve o HTML
  do arquivo **com os comentários `<!-- -->` removidos**.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente no **fim** de `tests/test_site.py`:

```python
# ---------------------------------------------------------------- o texto
def _fatia(nome: str) -> str:
    """O HTML de uma fatia SEM os comentarios de projeto — ou seja, o texto
    que o leitor ve.

    Tirar o comentario nao e detalhe: os vetos abaixo cobram o texto
    PUBLICADO, e o comentario de cada fatia precisa poder dizer o que saiu e
    por que ("aqui exigia-se Python; saiu em 26/08"). Sem esta linha, o
    proprio registro da decisao derrubaria o teste que a decisao criou."""
    bruto = (SITE / "parts" / f"{nome}.html").read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", " ", bruto, flags=re.S)


def test_a_porta_do_gestor_nao_exige_programador_nem_maquina():
    """A 01b existe para derrubar "isso e coisa de TI, eu nao tenho equipe" e,
    no mesmo bloco, reintroduzia a objecao como requisito: exigia alguem que
    lesse Python e uma maquina Windows.

    Decisao do usuario em 26/08/2026 (spec 2026-08-26-landing-porta-do-gestor,
    D1 e D2): o degrau de entrada e querer conhecer o projeto, nao ter um
    programador. O Windows sai junto porque dizer "Windows so se for o SIAPE"
    abre a pergunta seguinte, cuja resposta e servidor online pago do proprio
    bolso."""
    texto = _fatia("01b-gestor")
    assert "Python" not in texto
    assert "Windows" not in texto
    assert "3270" not in texto


def test_a_porta_do_gestor_nao_fecha_no_e_mail_nem_termina_ai():
    """D3 e D4: nao limitar o contato ao e-mail, e nao fechar portas. O
    limite continua DITO (quem implanta e a equipe do orgao) — o que sai e a
    porta batendo."""
    texto = _fatia("01b-gestor")
    assert "termina aí" not in texto.lower()
    assert "por e-mail" not in texto
    assert "não há acompanhamento" not in texto


def test_a_porta_do_gestor_diz_o_que_basta_e_quem_faz():
    """O cartao passa a dizer o que basta, e mantem UM item sobre pessoa. Sem
    ele os tres restantes (fluxo, acesso, autorizacao) nao respondem "quem
    faz?" — e o leitor completa a lacuna com "entao e TI mesmo", que e
    exatamente a objecao que a secao existe para derrubar."""
    texto = _fatia("01b-gestor")
    assert "O que já basta para começar" in texto
    assert "Uma pessoa da própria área" in texto
    assert "O que a sua unidade precisa ter" not in texto
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -k porta_do_gestor -q
```

Esperado: **3 failed**. O primeiro falha em `assert "Python" not in texto`; o
terceiro, em `assert "O que já basta para começar" in texto`.

- [ ] **Step 3: O cartão de pré-requisitos**

Em `site/parts/01b-gestor.html`, troque o `<h4>`:

```html
          <h4>O que a sua unidade precisa ter</h4>
```

por:

```html
          <h4>O que já basta para começar</h4>
```

Troque o primeiro par do `<dl>`:

```html
            <div>
              <dt>Uma pessoa</dt>
              <dd>Alguém que leia e ajuste código Python — ou que topa aprender. Não precisa ser da área de TI, nem cuidar só disso.</dd>
            </div>
```

por:

```html
            <div>
              <dt>Uma pessoa da própria área</dt>
              <dd>Quem já faz esse trabalho hoje e conhece a regra por dentro. Não precisa ser da área de TI, nem cuidar só disso.</dd>
            </div>
```

Troque **só o `<dt>`** do terceiro par (o `<dd>` fica igual — o "dela" dele tem
como antecedente o primeiro par, que continua existindo):

```html
              <dt>O acesso que ela já tem</dt>
```

por:

```html
              <dt>O acesso que já existe</dt>
```

Apague **o par inteiro** da máquina Windows:

```html
            <div>
              <dt>Uma máquina Windows</dt>
              <dd>Só se o fluxo passar pelo terminal <span class="num">3270</span> do SIAPE, que roda apenas lá. O resto do pacote não depende disso.</dd>
            </div>
```

- [ ] **Step 4: A frase nova no parágrafo da objeção**

No `<p>` do bloco da objeção, que hoje termina em `…o núcleo é código aberto sob
licença MIT.</p>`, acrescente uma frase antes do `</p>`:

```html
 E você não precisa decidir nada agora: o primeiro passo é conhecer o que já existe e ver se alguma parte serve para o seu caso.</p>
```

**Não escreva "pronto"** — é palavra vetada (Global Constraint 3). "existe" é a
palavra escolhida, e o motivo está na spec § 4.2.

- [ ] **Step 5: O item do mapa e a promessa**

Troque o `<p>` do item *Piloto assistido* na `<ul class="mapa">`:

```html
          <p>Uma conversa de diagnóstico e a indicação do caminho, por e-mail. Termina aí: quem implanta, testa e opera depois é a sua equipe.</p>
```

por:

```html
          <p>Uma conversa de diagnóstico sobre o seu fluxo e a indicação do caminho. Quem implanta e opera é a sua equipe, que conhece o órgão.</p>
```

Troque o parágrafo `.promessa` inteiro:

```html
      <p class="promessa">A conversa é uma videoconferência de diagnóstico sobre o seu fluxo e a indicação do caminho — quais blocos servem e onde isso costuma travar. E termina aí: não há acompanhamento depois dela, não há prazo combinado e ninguém do INTEGRA implanta, configura ou opera nada dentro do seu órgão.</p>
```

por:

```html
      <p class="promessa">A conversa é uma videoconferência de diagnóstico sobre o seu fluxo e a indicação do caminho — quais blocos servem e onde isso costuma travar. Quem implanta, configura e opera é a sua equipe, que conhece o órgão por dentro; daí em diante a conversa segue se fizer sentido para os dois lados.</p>
```

- [ ] **Step 6: O comentário de projeto no topo do arquivo**

O comentário `<!-- ... -->` que abre o arquivo **justifica por escrito** o que
acabou de sair, e comentário desatualizado é armadilha para a próxima sessão.

Um parágrafo dele ficou **falso**. Troque:

```
     A PROMESSA e a mesma da faixa 05, repetida aqui em uma frase para quem
     ler SO esta secao: conversa de diagnostico e indicacao do caminho, sem
     acompanhamento, sem prazo e sem ninguem implantando nada la dentro.
```

por:

```
     A PROMESSA e a mesma da faixa 05, repetida aqui em uma frase para quem
     ler SO esta secao: conversa de diagnostico e indicacao do caminho, e a
     implantacao e do orgao que adotar. O limite continua DITO — ninguem daqui
     configura ou opera nada la dentro —, mas como divisao de trabalho, e nao
     como porta batendo: nao se combina prazo nem acompanhamento porque a
     frase nao combina nada, e a conversa segue se fizer sentido para os dois
     lados. O "termina ai" que estava aqui saiu em 26/08/2026 (D4: "nao quero
     fechar portas e nem possibilidades").
```

E acrescente, logo **antes** do parágrafo `NUMEROS:`, o registro da decisão que
esvaziou o cartão — sem ele a próxima sessão repõe o que saiu:

```
     O QUE O CARTAO NAO PEDE, e e decisao de 26/08/2026: nao pede quem leia
     Python (D1) nem maquina Windows (D2). O degrau de entrada e querer
     conhecer o projeto — numa parceria entre pares quem convida nao
     estabelece requisito de admissao, e uma lista tecnica na porta e
     formulario de qualificacao. O Windows saiu junto porque "Windows so se
     for o SIAPE" abre a pergunta seguinte, cuja resposta hoje e servidor
     online pago do proprio bolso. O item da PESSOA ficou, reescrito sem a
     exigencia: sem ele os tres restantes nao respondem "quem faz?", e o
     leitor completa a lacuna com "entao e TI mesmo" — a objecao que esta
     secao existe para derrubar. Ha portao:
     tests/test_site.py::test_a_porta_do_gestor_nao_exige_programador_nem_maquina.
```

**Preserve intactas** as três justificativas que continuam valendo:

- o parágrafo **FUNDO — `.faixa` (`--bg`)** e a lacuna do § 4.1 do contrato;
- o parágrafo **O CONTROLE** (por que o `.btn-s` é secundário e aponta para a
  faixa 05 em vez do `mailto:`);
- o parágrafo **NÚMEROS** (nenhum número novo).

- [ ] **Step 7: Rodar os testes e os portões da fatia**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q
```

Esperado: **todos passam** (os 3 novos inclusive).

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/montar.py --so 01b-gestor
```

Esperado: `site/preview-01b-gestor.html` gerado.

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/verificar.py site/preview-01b-gestor.html
```

Esperado: `verificar: sem achados (preview-01b-gestor.html)`, código 0.

- [ ] **Step 8: Commit**

```bash
git add tests/test_site.py site/parts/01b-gestor.html
git commit -m "feat(site): a porta do gestor para de exigir programador e maquina"
```

---

### Task 2: A fatia 03 — a linha por onde a correção vazaria

**Files:**
- Modify: `tests/test_site.py`
- Modify: `site/parts/03-contexto.html:46`

**Interfaces:**
- Consumes: `_fatia(nome)` da Task 1.

- [ ] **Step 1: Escrever o teste que falha**

Acrescente no fim de `tests/test_site.py`:

```python
def test_a_comparacao_honesta_nao_transforma_python_em_pre_requisito():
    """A 01b dispensa o requisito tecnico e, no mapa, manda o leitor para o
    #contexto — onde o cartao "Automatizar com o INTEGRA" dizia "Para comecar:
    alguem da equipe le e ajusta Python". O leitor saia pela porta da frente e
    reencontrava a exigencia tres secoes abaixo.

    O CUSTO continua dito: o cartao existe para por os dois precos a vista, e
    "acompanha o roteiro" mantem que a automacao exige alguem por perto. O que
    sai e a linguagem de programacao como condicao de entrada."""
    texto = _fatia("03-contexto")
    assert "Python" not in texto
    assert "Alguém da própria área acompanha o roteiro." in texto
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -k comparacao_honesta -q
```

Esperado: **1 failed**, em `assert "Python" not in texto`.

- [ ] **Step 3: Trocar a linha**

Em `site/parts/03-contexto.html`, dentro do `<div class="card ficha via">`:

```html
            <div><dt>Para começar</dt><dd>Alguém da equipe lê e ajusta Python.</dd></div>
```

por:

```html
            <div><dt>Para começar</dt><dd>Alguém da própria área acompanha o roteiro.</dd></div>
```

Os outros cinco pares do cartão **não mudam** — inclusive
`Se a tela mudar / O roteiro quebra e precisa de conserto`, que é o preço que
esta seção existe para mostrar.

- [ ] **Step 4: Rodar os testes e o portão da fatia**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q
```

Esperado: todos passam.

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/montar.py --so 03-contexto
```

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/verificar.py site/preview-03-contexto.html
```

Esperado: `verificar: sem achados (preview-03-contexto.html)`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_site.py site/parts/03-contexto.html
git commit -m "fix(site): a comparacao honesta diz o custo sem exigir Python"
```

---

### Task 3: A fatia 05 — o convite para de qualificar quem escreve

**Files:**
- Modify: `tests/test_site.py`
- Modify: `site/parts/05-conversao.html`

**Interfaces:**
- Consumes: `_fatia(nome)` da Task 1.

Esta tarefa mexe **só no texto** da 05. O canal novo é a Task 4.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente no fim de `tests/test_site.py`:

```python
def test_o_convite_nao_exige_programador_nem_maquina():
    """A 05 e o destino do botao da 01b. Ela pedia a versao do SEI, se as
    maquinas eram Windows e se havia alguem que programasse — ou seja, a
    barreira de que a 01b acabara de dispensar o leitor, tres telas abaixo.
    Uma pagina que se desmente no clique que ela mesma pediu."""
    texto = _fatia("05-conversao")
    assert "Python" not in texto
    assert "Windows" not in texto
    assert "3270" not in texto


def test_o_convite_nao_nega_o_formulario_nem_termina_ai():
    """D3 e D4. "Nao ha formulario nesta pagina, e nao vai haver" e "Termina
    ai" sao as duas portas se fechando; o limite continua dito no positivo
    (quem implanta e a equipe do orgao), e a frase de registro — "nao uma
    central de atendimento" — permanece, porque ela diz o registro da conversa
    sem fechar nada."""
    texto = _fatia("05-conversao")
    assert "não vai haver" not in texto
    assert "termina aí" not in texto.lower()
    assert "não uma central de atendimento" in texto
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -k o_convite -q
```

Esperado: **2 failed**.

- [ ] **Step 3: O cartão do pedido — título e abertura**

```html
          <h3>O que mandar no e-mail.</h3>
          <p class="intro">Não há formulário nesta página, e não vai haver. O que faz a conversa render é o e-mail já chegar com estas seis coisas — em texto corrido mesmo, na ordem que você quiser.</p>
```

por:

```html
          <h3>O que ajuda a conversa a render.</h3>
          <p class="intro">Escreva, ligue ou chame no WhatsApp — como for mais fácil para você. O que faz a conversa render é chegar com estas seis coisas em mãos, em texto corrido mesmo, na ordem que você quiser.</p>
```

- [ ] **Step 4: Os dois itens do `<dl>`**

```html
            <dd>Quais estão no fluxo e em que versão: SEI (o nosso é o <span class="num">4.1.5</span>), SIAPE pelo terminal <span class="num">3270</span>, Sigepe, planilha, e-mail. Diga também se as máquinas da equipe são Windows — o <span class="num">3270</span> só roda lá.</dd>
```

por:

```html
            <dd>Quais estão no fluxo: SEI (o nosso é o <span class="num">4.1.5</span>), SIAPE — pelo terminal antigo ou pelo e-SIAPE na web —, Sigepe, planilha, e-mail.</dd>
```

O `4.1.5` continua em `.num` (Global Constraint 5). O `3270` sai como jargão:
"o terminal antigo" diz ao gestor-usuário o que ele precisa saber.

E:

```html
            <dd>Se há aí alguém que programe em Python — ou que topa aprender — e quem assina a decisão na sua unidade. Como a implantação é do seu órgão, essa é a resposta que mais pesa.</dd>
```

por:

```html
            <dd>Quem faz esse trabalho hoje na sua unidade e quem assina a decisão. Como a implantação é do seu órgão, essa é a resposta que mais pesa.</dd>
```

**Não toque** no `<p class="aviso">` de não mandar dado pessoal (CPF, matrícula,
processo real): é regra de privacidade, não de tom.

- [ ] **Step 5: O gatilho do meio**

```html
            <li>…programa, ou tem aí alguém que programe, e quer saber o que reaproveitar antes de escrever código do zero;</li>
```

por:

```html
            <li>…tem aí alguém que já mexe com planilha, macro ou automação e quer saber o que dá para reaproveitar antes de começar do zero;</li>
```

O `<p class="fecha">` seguinte — *"Não precisa ser da área de TI. Precisa ter o
problema e ter o acesso."* — **fica como está**: agora ele é verdade na página
inteira.

- [ ] **Step 6: O cartão dos passos e o limite**

```html
          <div class="sub"><h3>O que acontece depois do e-mail.</h3></div>
```

por:

```html
          <div class="sub"><h3>O que acontece depois que você chama.</h3></div>
```

O primeiro `<li>`:

```html
            <li>Começa pelo seu e-mail, escrito com os seis itens da lista.</li>
```

por:

```html
            <li>Começa pelo seu contato — e-mail, telefone ou WhatsApp, como preferir.</li>
```

Os outros dois `<li>` **não mudam**. E o parágrafo do limite:

```html
          <p class="limite">Termina aí. Não há acompanhamento depois dessa conversa, não há prazo combinado e ninguém do INTEGRA implanta, configura ou opera nada dentro do seu órgão. Do outro lado do e-mail há um servidor público com o próprio trabalho para tocar, não uma central de atendimento.</p>
```

por:

```html
          <p class="limite">Quem implanta, configura e opera é a sua equipe, que conhece o órgão por dentro — daí em diante a conversa segue se fizer sentido para os dois lados. Do outro lado há um servidor público com o próprio trabalho para tocar, não uma central de atendimento.</p>
```

- [ ] **Step 7: Rodar os testes e o portão da fatia**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q
```

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/montar.py --so 05-conversao
```

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/verificar.py site/preview-05-conversao.html
```

Esperado: todos passam; `verificar: sem achados (preview-05-conversao.html)`.

- [ ] **Step 8: Commit**

```bash
git add tests/test_site.py site/parts/05-conversao.html
git commit -m "feat(site): o convite para de qualificar quem escreve"
```

---

### Task 4: A fatia 05 — o segundo canal

**Files:**
- Modify: `tests/test_site.py`
- Modify: `site/parts/05-conversao.html` (bloco `.fecho` e bloco `.rodape`)

**Interfaces:**
- Consumes: `_fatia(nome)` da Task 1.

- [ ] **Step 1: Escrever o teste que falha**

Acrescente no fim de `tests/test_site.py`:

```python
def test_o_convite_oferece_mais_de_um_caminho():
    """D3: "nao quero limitar no texto que estamos limitados a contato por
    e-mail e nada mais". O e-mail continua e continua sendo o primario; o que
    entra e um segundo caminho, para quem prefere falar a escrever.

    O numero foi conferido contra o portao de privacidade antes de entrar:
    24988493257 nao passa no digito verificador do modulo 11, entao nao e
    falso positivo de CPF (ver test_telefone_de_onze_digitos_...)."""
    texto = _fatia("05-conversao")
    assert "mailto:marco.aurelio-silva@gestao.gov.br" in texto
    assert "tel:+5524988493257" in texto
    assert "https://wa.me/5524988493257" in texto
    assert "(24) 98849-3257" in texto
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -k mais_de_um_caminho -q
```

Esperado: **1 failed**, em `assert "tel:+5524988493257" in texto`.

- [ ] **Step 3: O bloco `.fecho`**

Troque o bloco inteiro:

```html
      <p class="endereco"><a class="link-neutro" href="mailto:marco.aurelio-silva@gestao.gov.br?subject=INTEGRA%20%E2%80%94%20conversa%20de%20diagn%C3%B3stico">marco.aurelio-silva@gestao.gov.br</a></p>
      <div class="acoes">
        <a class="btn btn-p" href="mailto:marco.aurelio-silva@gestao.gov.br?subject=INTEGRA%20%E2%80%94%20conversa%20de%20diagn%C3%B3stico">Escrever o e-mail</a>
        <a class="btn btn-s" href="https://github.com/MarcoAShanon/integra-gov">Abrir o repositório</a>
      </div>
      <p class="fuga">O endereço acima e o botão abrem o seu programa de e-mail com o assunto preenchido; acrescente nele a sigla do seu órgão. E se você prefere não escrever para ninguém, o caminho não depende disso: o núcleo está no GitHub sob licença MIT, com documentação e exemplos — clonar, ler e testar não passa por conversa nenhuma.</p>
```

por:

```html
      <p class="endereco"><a class="link-neutro" href="mailto:marco.aurelio-silva@gestao.gov.br?subject=INTEGRA%20%E2%80%94%20conversa%20de%20diagn%C3%B3stico">marco.aurelio-silva@gestao.gov.br</a></p>
      <p class="endereco"><a class="link-neutro" href="tel:+5524988493257">(24) 98849-3257</a></p>
      <div class="acoes">
        <a class="btn btn-p" href="mailto:marco.aurelio-silva@gestao.gov.br?subject=INTEGRA%20%E2%80%94%20conversa%20de%20diagn%C3%B3stico">Escrever o e-mail</a>
        <a class="btn btn-s" href="https://wa.me/5524988493257">Chamar no WhatsApp</a>
        <a class="btn btn-s" href="https://github.com/MarcoAShanon/integra-gov">Abrir o repositório</a>
      </div>
      <p class="fuga">O endereço abre o seu programa de e-mail com o assunto preenchido; acrescente nele a sigla do seu órgão. O número atende no WhatsApp e por ligação, no horário de trabalho. E se você prefere não falar com ninguém agora, o caminho não depende disso: o núcleo está no GitHub sob licença MIT, com documentação e exemplos — clonar, ler e testar não passa por conversa nenhuma.</p>
```

Três pontos que **não** precisam de CSS novo, e por quê:

1. **O terceiro botão.** `.acoes` já vira coluna com `width:100%` e
   `align-self:stretch` abaixo de 768px, independentemente do alinhamento do pai
   (contrato § 8.3-e). Não escreva regra nenhuma para ele.
2. **O alvo de toque do telefone.** `#conversao .endereco a` já carrega
   `min-height:44px` (`05-conversao.css:144`), e a segunda `<p class="endereco">`
   entra na mesma regra.
3. **O mono do número.** `#conversao .endereco` já é `var(--font-mono)`
   (`05-conversao.css:136`); o telefone herda, e por isso **não** leva `.num`
   ali — pelo mesmo motivo que o e-mail ao lado dele não leva.

- [ ] **Step 4: A linha do rodapé**

No `<div class="contato">`, **depois** da linha do e-mail, acrescente:

```html
        <p><span class="rot">telefone</span><a class="link-neutro" href="tel:+5524988493257">(24) 98849-3257</a></p>
```

Verifique o tipográfico deste bloco antes de fechar a tarefa: se
`#conversao .rodape .contato a` **não** resolver para `var(--font-mono)`, o
número precisa de `.num` para cumprir o contrato § 5.4. Meça o **computado**, não
a regra:

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -c "import re,pathlib; css=pathlib.Path('site/parts/05-conversao.css').read_text(encoding='utf-8'); print([b for b in re.findall(r'[^{}]+\{[^{}]*\}', css) if 'contato' in b])"
```

- [ ] **Step 5: O comentário de projeto no topo do arquivo**

O comentário da 05 afirma hoje, por escrito, o contrário do que a seção passou a
fazer. Troque:

```
     A PROMESSA: conversa inicial e orientacao pontual. O h2 define
     "assistido" e limita o escopo na primeira frase, e o cartao "O que
     acontece depois do e-mail" fecha a porta por escrito. Nao ha
     formulario, newsletter, WhatsApp, prazo, fila nem acompanhamento. -->
```

por:

```
     A PROMESSA: conversa inicial e orientacao pontual. O h2 define
     "assistido" e limita o escopo na primeira frase, e o cartao "O que
     acontece depois que voce chama" diz onde a ajuda daqui termina — como
     divisao de trabalho, nao como porta batendo.

     DOIS CANAIS, desde 26/08/2026 (D3: "nao quero limitar no texto que
     estamos limitados a contato por e-mail e nada mais"). O e-mail
     institucional continua e continua primario; ao lado dele entra o
     (24) 98849-3257, no WhatsApp e por ligacao. O custo de publicar numero em
     pagina aberta — raspagem, spam permanente, cache e indice que nao se
     desfazem — foi posto ao usuario antes, e a decisao e dele. O numero foi
     conferido contra o portao de privacidade: 24988493257 nao passa no digito
     verificador do modulo 11, entao nao e falso positivo de CPF.

     CONTINUA NAO HAVENDO formulario, newsletter, prazo nem fila — o que mudou
     nao foi o fato, foi a pagina parar de NEGA-LOS por escrito, que e gesto de
     quem fecha porta (D4). Ha portao para os dois lados disso:
     tests/test_site.py::test_o_convite_nao_nega_o_formulario_nem_termina_ai e
     ::test_o_convite_oferece_mais_de_um_caminho. -->
```

Preserve intactos os parágrafos anteriores do comentário — a nota da **faixa de
tinta** (contrato § 4.2) e a de **sem dependência de JavaScript**, que continuam
valendo palavra por palavra.

- [ ] **Step 6: Rodar os testes e o portão da fatia**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q
```

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/montar.py --so 05-conversao
```

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/verificar.py site/preview-05-conversao.html
```

Esperado: todos passam. Em particular o portão de privacidade **não** pode
acusar CPF — se acusar, pare e reporte: significa que o número foi escrito em
formato diferente do previsto.

- [ ] **Step 7: Commit**

```bash
git add tests/test_site.py site/parts/05-conversao.html
git commit -m "feat(site): o convite ganha um segundo caminho, alem do e-mail"
```

---

### Task 5: A página inteira — os quatro portões, a leitura em sequência e o registro

**Files:**
- Modify: `site/index.html` (**gerado** por `montar.py` — não editar à mão)
- Modify: `CHANGELOG.md:97` (a primeira seção `### Alterado` de `[Não publicado]`)

**Interfaces:**
- Consumes: as quatro fatias das Tasks 1–4.

Sem teste novo: os portões de regressão do texto já estão nas Tasks 1–4, e o que
falta aqui é o que **nenhum portão automático faz** — ler a página como o leitor
lê, e conferir que os links funcionam.

- [ ] **Step 1: Remontar a página inteira**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/montar.py
```

Esperado: `site/index.html` regenerado com as seis fatias.

- [ ] **Step 2: Os quatro portões, na ordem do `site/README.md`**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/verificar.py
```

Esperado: `verificar: sem achados (index.html)`, código 0.

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/auditar_contrato.py
```

Esperado: aprovado. (Nenhuma cor foi tocada, então este portão é confirmação de
que nada vazou — se ele acusar, alguma tarefa mexeu em CSS sem dizer.)

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q
```

Esperado: todos passam.

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest -q
```

Esperado: a suíte inteira passa (**742 + os 7 testes novos = 749**).

- [ ] **Step 3: A leitura em sequência — checagem humana**

Abra `site/index.html` no navegador e **leia a 01b e depois a 05 seguidas**,
como faz quem clica no botão "Ver como a conversa funciona".

Cobre-se uma coisa só, e ela não tem portão: **nenhuma exigência da 05 pode
contradizer o que a 01b acabou de dispensar.** Se a 01b diz que basta uma pessoa
da própria área e a 05 pede outra coisa do leitor, a correção falhou — reporte
em vez de remendar.

Verifique também que o `#oferta` continua dizendo "biblioteca Python" e
"extra · Windows": isso é **esperado** (Global Constraint 7), é catálogo, não
exigência.

- [ ] **Step 4: Os três links novos — checagem humana**

O portão vê que o `href` existe; ele **não** vê se está correto. Confira os três
no navegador:

| link | esperado |
|---|---|
| `mailto:` (endereço e botão primário) | abre o programa de e-mail com o assunto preenchido |
| `tel:+5524988493257` | oferece discar `(24) 98849-3257` |
| `https://wa.me/5524988493257` | abre a conversa do WhatsApp com o número certo |

- [ ] **Step 5: O registro no CHANGELOG**

Em `CHANGELOG.md`, na **primeira** seção `### Alterado` de `[Não publicado]`
(linha 97), acrescente:

```markdown
- **A landing para de barrar o gestor não-técnico na porta.** A fatia do gestor
  existia para derrubar "isso é coisa de TI, eu não tenho equipe" e, no mesmo
  bloco, reintroduzia a objeção como requisito: exigia alguém que lesse Python e
  uma máquina Windows, e mandava o leitor para uma seção que pedia a versão do
  SEI e se havia quem programasse. A página se desmentia no clique que ela mesma
  pedia.
  - **Sai a exigência técnica das três fatias que o leitor percorre** (`01b`,
    `03` e `05`). O custo continua dito — a automação exige alguém por perto, e
    o roteiro quebra se a tela mudar —, mas como preço à vista, não como
    condição de entrada. A `04-oferta` não muda: lá é catálogo técnico.
  - **O contato deixa de ser só o e-mail.** Entra `(24) 98849-3257`, no WhatsApp
    e por ligação, ao lado do endereço institucional. O número foi conferido
    contra o portão de privacidade antes de entrar.
  - **O limite continua dito, sem fechar a porta.** Some o "Termina aí" e a
    negação em série; fica a divisão de trabalho — quem implanta e opera é a
    equipe do órgão — e a conversa segue se fizer sentido para os dois lados.
  - **Sete testes novos em `tests/test_site.py`** cobram cada uma dessas
    decisões no texto publicado, lendo a fatia sem os comentários de projeto.
```

- [ ] **Step 6: Commit**

```bash
git add site/index.html CHANGELOG.md
git commit -m "docs(site): remonta a pagina e registra a porta do gestor"
```

- [ ] **Step 7: Reportar o que ficou de fora**

**Não publique.** O redeploy é ordem explícita do usuário e não foi dada
(Global Constraint 8). Ao fechar, reporte:

1. a página montada **não está no ar** — o que está publicado ainda é a versão
   sem a fatia 01b;
2. a 01b **continua sem crítico cego e sem sessão de revisão**, e agora a 05 tem
   texto novo na mesma situação;
3. a lacuna do § 4.1 do contrato (a alternância de fundos fixada em cinco
   fatias, sem linha para a sexta) **continua aberta**;
4. o `CHANGELOG.md` tem **duas** seções `### Alterado` seguidas dentro de
   `[Não publicado]` (linhas 97 e 103) — defeito preexistente, fora do escopo
   deste plano, mas registrado para não se perder.
