# Contrato de design — landing do Projeto INTEGRA

Fatia 0. Este documento é lei para as fatias 01 a 05. Ele foi escrito para
alguém competente que **não pode perguntar nada a ninguém**: se você está em
dúvida sobre algo que não está aqui, a resposta é "não faça".

Arquivos que compõem a fatia 0:

| arquivo | papel |
|---|---|
| `contrato.md` | este documento — a lei em prosa |
| `00-sistema.css` | os tokens e as primitivas (o CSS da lei) |
| `head.html` | o conteúdo do `<head>`, incluindo o `<link>` das fontes |
| `script.js` | o JavaScript da página inteira |

---

## 1. O que cada fatia pode e não pode fazer

**Pode:** escrever o HTML da sua seção; escrever um `NN-nome.css` cujos
seletores começam **todos** pelo `#id` da própria seção; usar qualquer token e
qualquer primitiva deste contrato.

**Não pode:**

1. Declarar bloco `:root` — nem para criar token novo, nem para redefinir.
   `site/verificar.py` reprova. Precisa de um valor local? Declare a custom
   property dentro do seu próprio prefixo: `#prova .grafico{--altura:200px}` —
   e nunca com um nome que já exista no sistema.
2. Declarar `padding-block`, `padding-top`, `padding-bottom` ou `background`
   na própria `<section>`. Isso é da `.faixa` (§4).
3. Usar `@media` de largura fora dos dois valores fechados (§3).
4. Declarar `font-family` crua. Só `var(--font-display)`, `var(--font-corpo)`
   ou `var(--font-mono)`.
5. Redefinir uma primitiva (`.card`, `.btn`, `.pill`…) globalmente. Ajustar
   **dentro do seu prefixo** é permitido e esperado:
   `#oferta .card{padding:var(--e-4)}`.
6. Pôr texto sobre gradiente (§6.4).
7. Escrever a marca de outro jeito que não a primitiva `.marca` (§8.10).
8. Escrever a marcação do lightbox. O `script.js` a cria (§9.3).
9. Escrever `href="#"` ou `href=""`. O verificador reprova. Toda âncora aponta
   para um `id` que existe.
10. Escrever atributo `style` inline. **Nenhum**, em nenhuma circunstância — o
    `verificar.py` não olha `style`, então isso não seria pego por máquina, e um
    valor cravado no HTML é exatamente o que escapa de toda regra deste
    contrato. Tudo vai para o seu `NN-nome.css` prefixado. A única coisa que um
    elemento carrega no HTML são os ganchos `data-*` documentados no § 9.
11. Escrever `z-index` cru. A escala é `--z-topo` (100), `--z-lightbox` (200) e
    `--z-skip` (999), e ela cobre a página inteira.

O montador (`site/montar.py`) já emite, sozinho, o `<!doctype>`, o `<html>`, o
`<head>`, o skip link `<a class="skip" href="#conteudo">` e o
`<main id="conteudo">`. **Nenhuma fatia escreve isso.** O id `conteudo` e o id
`lightbox-video` são reservados.

---

## 2. A direção estética, em uma frase

**Rigor técnico quente.** A estrutura é de engenharia — grade de 12 colunas em
custom properties, fio de cabelo no lugar de sombra, densidade controlada, todo
número em monoespaçada. A base cromática é quente — ecru, âmbar, tinta marrom
escura. O resultado tem que parecer um instrumento de precisão feito por gente
competente: nem startup fria, nem portal de governo.

Três consequências práticas, que valem como regra:

- **Sombra é proibida.** Nenhuma `box-shadow` de elevação em nenhuma fatia. O
  que separa um bloco do fundo é o fio de 1px (`--border`) e o espaço. A única
  `box-shadow` autorizada na página é a do foco, que já vem no sistema.
- **Densidade é uma escolha, não um acidente.** Prefira mais informação por
  bloco com espaçamento firme, a menos informação com espaçamento inflado.
- **Todo número em mono** (§5.4). Sem exceção.

---

## 3. Regra de coerência 1 — breakpoints fechados

Existem **dois** valores de `@media` de largura na página inteira, os dois na
forma `max-width`, sempre nesta ordem dentro do arquivo:

```css
@media (max-width:1080px){ /* ... */ }
@media (max-width:768px){ /* ... */ }
```

Qualquer outro valor é achado de revisão. Não invente 900px, 620px, 480px.
Não use `min-width`. O CSS base é a versão **desktop**; os dois blocos são
reduções sucessivas.

O que o sistema já faz em cada um:

| breakpoint | o que muda no sistema |
|---|---|
| `1080px` | `.wrap` reduz o respiro lateral para `--e-4`; `.faixa` reduz o passo vertical para `clamp(--e-6, 7vw, --e-7)` |
| `768px` | `--calha` cai para 16px; `.faixa` fixa em `--e-6`; `.grid` colapsa para uma coluna e **força** todo filho a `grid-column:1 / -1`; `.marca-cubo` cai para 36px; `.btn` ocupa a linha inteira |

Consequência importante: como o sistema força o colapso da `.grid` com
`!important`, você **não precisa** escrever nada para o seu `grid-column:span N`
sobreviver ao celular. Em compensação, se a sua seção precisa de duas colunas no
celular, **não use `.grid`** — monte um grid próprio dentro do seu prefixo.

---

## 4. Regra de coerência 2 — o ritmo vertical e o fundo não são seus

A `<section>` de cada fatia é uma `.faixa`. A primitiva define o padding
vertical e o fundo. A fatia não define nenhum dos dois.

Sem isso, a junção entre duas seções soma dois paddings, e duas faixas de mesma
cor coladas viram uma faixa só.

### 4.1 A sequência de fundos, fixada

| fatia | `id` | classe da section | fundo |
|---|---|---|---|
| 01 hero | `hero` | `class="faixa"` | `--bg` (ecru claro) |
| 02 prova | `prova` | `class="faixa alt"` | `--fundo-alt` (ecru fundo) |
| 03 contexto | `contexto` | `class="faixa"` | `--bg` |
| 04 oferta | `oferta` | `class="faixa alt"` | `--fundo-alt` |
| 05 conversão | `conversao` | `class="faixa tinta"` | `--fundo-tinta` (tinta escura) |

Isto não se renegocia. A alternância ecru claro / ecru fundo dá o pulso, e a
faixa de tinta fecha a página com a única inversão de valor do documento — é
ela que faz o olho parar no CTA.

A alternância é **de valor e de temperatura**: no claro, `--bg` → `--fundo-alt`
desloca ΔL\*=3,10 e ainda derruba o canal azul cerca do dobro do vermelho, então
a faixa par lê como "papel mais quente", não só como "papel mais escuro". Isso é
intencional. No escuro o deslocamento é só de valor (ΔL\*=4,89), e por isso ele
é maior — no pé da curva tonal um painel barato come a diferença.

### 4.1-b A navegação e o rodapé

Nenhuma das duas tinha lei aqui, e o agente do hero construiria a primeira no
escuro. Agora tem:

- **O topo é `.topo`**, primeiro filho do `.wrap` da faixa 01: `.marca` à
  esquerda, `.nav` à direita. **Não é grudento** (`position:sticky` está
  proibido): a página é curta, tem um CTA só, e uma barra fixa teria de negociar
  fundo com cada faixa — inclusive com a de tinta — o que é justamente o tipo de
  costura que este contrato existe para evitar.
- **`.nav`** é uma fileira de links de texto para âncoras internas
  (`#prova`, `#contexto`, `#oferta`, `#conversao`). Sem menu sanfonado, sem
  submenu, sem ícone de hambúrguer: abaixo de 768px o `.topo` vira coluna e os
  links quebram em linha. Quatro links cabem.
- **O rodapé é `.rodape`**, último bloco **dentro da faixa 05**. Não é uma sexta
  faixa. É onde vive o bloco institucional que a página no ar tem — CGPAG, a
  revista, licença MIT, contato.

> **Pendência estrutural, registrada e não resolvida por mim.** O `montar.py`
> envolve as cinco fatias em `<main id="conteudo">`, então a `<nav>` fica dentro
> de `<main>`: a página não tem landmark `banner`, e o skip link — que aterrissa
> em `#conteudo` — cai **antes** da navegação, sem pular nada, que é o seu único
> propósito. Isso não se conserta dentro de uma fatia. A emenda mínima está
> proposta no § 12; até ela existir, monte o `.topo` como descrito acima, que é
> o que funciona hoje.

### 4.2 A faixa de tinta troca a escala inteira

`.faixa.tinta` redefine, **localmente**, `--bg`, `--fundo-alt`, `--surface`,
`--text`, `--text-soft`, `--border`, `--acento`, `--acento-ink`, `--acento-soft`,
`--on-acento`, `--ok`, `--ok-soft`, `--dado`, `--dado-fraco` e `--dado-neutro`
para a escala escura — **quinze tokens**. Portanto:
dentro da faixa 05 você continua escrevendo `var(--text)`, `var(--bg)`,
`.card`, `.btn-p` e `.pill` normalmente, e tudo se inverte sozinho. **Nunca
escreva um hex** para "fazer o texto ficar claro no fundo escuro" — o token já é
claro lá dentro.

**A única exceção, e ela importa:** `--fundo-tinta` **não** se inverte. Ele é o
fundo *da própria faixa*, e é a `.faixa.tinta` que o pinta. Você nunca precisa
dele, e usá-lo como fundo de um painel interno pinta um retângulo da mesma cor
da faixa. Para um painel dentro da faixa 05, use `.card` (que é `--surface`, já
invertido) ou `var(--bg)`.

### 4.3 O esqueleto de uma fatia

```html
<section id="prova" class="faixa alt">
  <div class="wrap">
    <!-- ... -->
  </div>
</section>
```

Uma `.faixa`, uma `.wrap` dentro dela. Sempre. O `.wrap` é quem centraliza em
`--maxw` (1120px) e dá o respiro lateral; sem ele o conteúdo cola na borda da
janela.

O fio de 1px entre faixas vizinhas é emitido pelo sistema
(`.faixa + .faixa{border-top}`), e é suprimido automaticamente nas duas
junções que envolvem a faixa de tinta. Você não escreve isso.

---

## 5. Tipografia

### 5.1 As três famílias

| token | família | papel |
|---|---|---|
| `--font-display` | **Bricolage Grotesque** | h1–h4, `.marca-nome`, números de destaque quando forem título |
| `--font-corpo` | **Archivo** | corpo, lede, botão, legenda, tabela |
| `--font-mono` | **IBM Plex Mono** | **todo número**, micro-rótulos (`.pill`), eixos de gráfico, `.marca-desc`, trechos de terminal |

As três estão no Google Fonts e foram batidas ao vivo na API em 20/08/2026: a
URL exata que está em `head.html` responde 200 e devolve as três `@font-face`
com `font-display: swap`.

### 5.2 Por que esse par

**Bricolage Grotesque** é um grotesco de eixo variável desenhado com
irregularidades deliberadas — terminais assimétricos, aberturas fechadas,
proporção estreita. Ele parece *fabricado para uma função*, não *desenhado para
uma marca*: é a voz certa para um projeto que se apresenta como ferramenta de
trabalho de servidor público, e tem caráter suficiente para carregar o wordmark
sem apoio de imagem. **IBM Plex Mono** é a contraparte: uma monoespaçada
desenhada dentro do sistema tipográfico de uma empresa de engenharia, com
algarismos inequívocos (zero cortado, 1 e 7 distintos) e um calor humanista que
impede a tabela de números de ficar clínica. Foi escolhida em cima de
alternativas mais chamativas (Azeret Mono, Martian Mono) por um motivo
específico deste projeto: aqui o mesmo mono precisa servir a três tamanhos
muito diferentes — o indicador gigante (`−90%`), o rótulo de eixo de 11px e a
pílula em caixa alta — e as mais largas quebram no segundo caso. **Archivo**
entra como voz neutra do corpo, porque nem Bricolage nem Plex Mono aguentam
parágrafos de 60 caracteres sem cansar.

### 5.3 Pilhas de queda

```
--font-display: "Bricolage Grotesque", "Segoe UI", "Helvetica Neue", Arial, sans-serif
--font-corpo:   "Archivo", "Segoe UI", "Helvetica Neue", Arial, sans-serif
--font-mono:    "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, "Liberation Mono", monospace
```

A queda foi escolhida olhando o **wordmark**, não a página — e a ordem foi
**medida**, não suposta. Altura-de-x renderizada a 100px no peso 800:

| família | altura-de-x | contra o Bricolage |
|---|---|---|
| Bricolage Grotesque | 53 | — |
| Segoe UI | 50 | −6% |
| Arial | 52 | −2% (mas grotesco de desenho bem mais frio) |
| Helvetica Neue | 45 | **−15%** |

Por isso **Segoe UI vem primeiro** na pilha do display, e não Helvetica Neue: é
a queda que menos desfigura o wordmark e, em Windows — o parque das máquinas
deste público —, é a que de fato renderiza. Sem o Google Fonts,
`PROJETO INTEGRA` continua legível em vez de virar imagem quebrada. `font-display:swap` está na URL: a piscada do primeiro carregamento é
aceitável; texto invisível não é.

### 5.4 A regra do mono — leia com atenção

**Todo número visível da página vai em `--font-mono`**, dentro de um elemento
com classe `.num` (ou `.num-g`, para número de destaque). Isso inclui:
percentuais, quantidades, anos, valores em reais, notas, versões, posições de
ranking, datas e intervalos. Inclui o número dentro de uma frase.

```html
<p>de <span class="num">~32 min</span> para <span class="num">~3,5 min</span></p>
<span class="num-g">−90%</span>
```

**Exceção, e é uma só: número dentro de uma `.pill`.** A pílula já é mono
inteira, e aninhar `.num` nela faria o `letter-spacing:-.02em` do número vencer
o `.11em` da pílula **só nos dígitos** — uma quebra de tracking visível no meio
de um rótulo em caixa alta. Dentro de `.pill`, o número não recebe `.num`.

Não há segunda exceção. Em particular, versão e nome próprio com número —
`SEI 4.1.5`, `vol. 3`, `4ª Região` — **levam `.num` normalmente**, inclusive
dentro de um `<h2>`. Na dúvida: mono.

`.num` e `.num-g` já trazem `font-variant-numeric:tabular-nums` e o zero
cortado. Não redeclare.

### 5.5 A escala tipográfica — oito degraus

| token | valor | uso |
|---|---|---|
| `--t-1` | `.72rem` | micro-rótulo em caixa alta: `.pill`, `.marca-desc`, eixo de gráfico |
| `--t-2` | `.82rem` | legenda, nota de rodapé, fonte da informação |
| `--t-3` | `.94rem` | texto secundário, texto de botão, célula de tabela |
| `--t-4` | `1.0625rem` (17px) | **corpo** — é o `font-size` do `body` |
| `--t-5` | `1.3rem` | lede (o parágrafo de abertura de cada seção) e `h4` |
| `--t-6` | `clamp(1.4rem, 1.22rem + .7vw, 1.7rem)` | `h3` |
| `--t-7` | `clamp(1.85rem, 1.3rem + 2.4vw, 2.7rem)` | `h2` e `.num-g` |
| `--t-8` | `clamp(2.35rem, 1.5rem + 3.8vw, 3.85rem)` | `h1` — existe **um** na página, no hero |

Nenhum `font-size` fora desta escala. Se você precisa de um tamanho que não
está aqui, o layout está errado, não a escala.

O degrau `--t-4` → `--t-5` foi aberto de propósito, de 1,111 (≈2px) para 1,224
(≈4px). No valor antigo o `.lede` se distinguia do corpo quase só pela cor, e o
parágrafo mais importante da página — a proposição em uma frase do hero, logo
abaixo de um `<h1>` de até 62px — lia como *mais apagado* em vez de *maior*. Um
lede é texto de corpo promovido; a promoção precisa ser de tamanho, não só de
tom.

Alturas de linha: `--lh-corpo` (1.62) para texto corrido, `--lh-titulo` (1.12)
para h1–h4, `--lh-marca` (1.02) para o wordmark. Os títulos já vêm com
`text-wrap:balance`.

### 5.6 Hierarquia de títulos

Um `<h1>` na página inteira, no hero. **As faixas 02 a 05 abrem com um `<h2>`;
o hero abre com o `<h1>` e não usa `.abertura`** (ver § 8.3-b). Dentro de cada
faixa, `<h3>` e depois `<h4>`. **Nunca pule degrau** — `verificar.py` reprova
`h2` seguido de `h4`. Um rótulo visualmente pequeno que não é título de seção
não é `<h5>`: é um `<span class="pill">` ou um `<p class="num">`.

---

## 6. Cor

### 6.1 A paleta e o papel de cada cor

Tema claro (o padrão):

| token | valor | papel |
|---|---|---|
| `--bg` | `#FBFAF7` | ecru claro — fundo da página e das faixas 01 e 03 |
| `--fundo-alt` | `#F4F1E9` | ecru fundo — faixas 02 e 04 |
| `--fundo-tinta` | `#14110D` | tinta — faixa 05 |
| `--surface` | `#FFFFFF` (e `#F8F6F1` em faixa par) | papel do `.card`, sempre um passo acima da faixa |
| `--text` | `#1C1917` | texto principal |
| `--text-soft` | `#6A6055` | texto secundário, legenda, borda de `.btn-s` |
| `--border` | `#DED7C9` | fio de cabelo — **decorativo** (ver 6.3) |
| `--acento` | `#E7920D` | âmbar de **preenchimento**: fundo do `.btn-p` |
| `--acento-ink` | `#96570A` | âmbar de **texto e contorno**: link em destaque, número grande, anel de foco |
| `--acento-soft` | `#F7EBD2` | tinta clara de âmbar: fundo de `.pill`, realce de linha |
| `--on-acento` | `#20160A` | texto sobre `--acento` |
| `--ok` | `#0A7355` | esmeralda — **sinal de estado positivo**, ver 6.5 |
| `--ok-soft` | `#E3F1EA` | fundo do sinal de estado |
| `--dado` | `#563506` | série cheia do gráfico — o degrau mais escuro |
| `--dado-neutro` | `#695E54` | referência / cenário manual — degrau do meio, dessaturado |
| `--dado-fraco` | `#AA8046` | período parcial — o degrau mais claro |

Tema escuro (`@media (prefers-color-scheme: dark)`), e **os mesmos valores**
valem dentro de `.faixa.tinta` no tema claro:

| token | escuro | dentro da faixa de tinta, no escuro |
|---|---|---|
| `--bg` | `#14110D` | — |
| `--fundo-alt` | `#201B14` | — |
| `--fundo-tinta` | `#2A2318` | — |
| `--surface` | `#241D15` (e `#2D2720` em faixa par) | `#352C1F` |
| `--text` | `#F3EEE5` | igual |
| `--text-soft` | `#B3A99B` | igual |
| `--border` | `#3A3227` | `#4A4030` |
| `--acento` | `#F0AE3E` | igual |
| `--acento-ink` | `#F0AE3E` | igual |
| `--acento-soft` | `#2C2214` | igual |
| `--ok-soft` | `#10271E` | igual |
| `--on-acento` | `#1A1206` | igual |
| `--ok` | `#45CBA0` | igual |
| `--dado` | `#EFD7AF` | igual |
| `--dado-neutro` | `#ABA69C` | igual |
| `--dado-fraco` | `#92764F` | igual |

Todo token tem definição no tema claro. Nenhum nasce dentro do bloco escuro.

### 6.2 Contraste medido, não estimado

Calculado pela fórmula WCAG 2 de luminância relativa
(`L = 0.2126R + 0.7152G + 0.0722B` linearizados; razão
`(L_claro + 0.05) / (L_escuro + 0.05)`). Mínimo 4,5:1 para texto, 3:1 para
objeto gráfico (barra de gráfico, contorno de controle).

**Tema claro**

| par | sobre `--bg` | sobre `--fundo-alt` | sobre `--surface` |
|---|---|---|---|
| `--text` | 16,75:1 | 15,49:1 | 17,49:1 |
| `--text-soft` | 5,89:1 | 5,44:1 | 6,15:1 |
| `--acento-ink` | 5,49:1 | 5,08:1 | 5,73:1 |
| `--ok` | 5,59:1 | 5,17:1 | 5,84:1 |
| `--dado` (3:1) | 10,55:1 | 9,75:1 | 11,01:1 |
| `--dado-neutro` (3:1) | 6,04:1 | 5,59:1 | 6,31:1 |
| `--dado-fraco` (3:1) | 3,42:1 | 3,16:1 | 3,57:1 |

Mais: `--text` sobre `--acento-soft` 14,80:1 · `--text-soft` sobre
`--acento-soft` 5,20:1 · `--acento-ink` sobre `--acento-soft` 4,85:1 · `--ok`
sobre `--ok-soft` 5,02:1 · `--on-acento` sobre `--acento` **7,21:1**.

**Tema escuro** (e faixa de tinta no tema claro)

| par | sobre `--bg` | sobre `--fundo-alt` | sobre `--surface` |
|---|---|---|---|
| `--text` | 16,29:1 | 14,79:1 | 14,40:1 |
| `--text-soft` | 8,12:1 | 7,38:1 | 7,19:1 |
| `--acento-ink` | 9,71:1 | 8,82:1 | 8,58:1 |
| `--ok` | 9,23:1 | 8,39:1 | 8,17:1 |
| `--dado` (3:1) | 13,45:1 | 12,22:1 | 11,90:1 |
| `--dado-neutro` (3:1) | 7,77:1 | 7,06:1 | 6,87:1 |
| `--dado-fraco` (3:1) | 4,42:1 | 4,01:1 | 3,90:1 |

Mais: `--text` sobre `--acento-soft` 13,50:1 · `--text-soft` sobre
`--acento-soft` 6,73:1 · `--acento-ink` sobre `--acento-soft` 8,05:1 · `--ok`
sobre `--ok-soft` 7,74:1 · `--on-acento` sobre `--acento` **9,56:1**.

**Faixa de tinta dentro do tema escuro** (fundo `#2A2318`, cartão `#352C1F`) —
o caso mais apertado da página: `--text` 13,44:1 / 11,87:1 · `--text-soft`
6,70:1 / 5,92:1 · `--acento-ink` 8,01:1 / 7,07:1 · `--ok` 7,62:1 / 6,73:1 ·
`--dado-fraco` 3,64:1 / 3,22:1 — o piso da rampa de dados.

**O `--surface` de faixa par** (`#F8F6F1` no claro, `#2D2720` no escuro) também
foi medido: pior caso 3,30:1 (`--dado-fraco` no claro) e 3,46:1 (`--dado-fraco`
no escuro); todo texto acima de 5,3:1.

Nenhum par abaixo do mínimo, em nenhum dos contextos. São **99 razões**,
recalculadas a partir dos tokens do próprio `00-sistema.css`.

**Se você combinar duas cores que não estão nesta tabela, você quebrou o
contrato.** Não existe combinação nova sem recalcular, e recalcular não é
tarefa de fatia.

### 6.3 O fio de cabelo é decorativo

`--border` mede de 1,27:1 (sobre `--fundo-alt`) a 1,43:1 (sobre `--surface`) contra o fundo. Isso é **de propósito**: é um fio de
separação, não um contorno de controle. Por isso a regra:

- `--border` pode desenhar: borda de `.card`, régua entre linhas de tabela,
  moldura de imagem, `.hairline`.
- `--border` **não** pode ser a única coisa que identifica um controle
  interativo. Botão secundário usa `--text-soft` na borda (5,89:1); anel de
  foco usa `--acento-ink` (5,49:1). Ambos já vêm assim no sistema — não mexa.

### 6.4 Fundo sólido atrás de texto — regra dura

Nenhum texto legível da página fica sobre gradiente, sobre imagem, ou sobre
`background-clip:text`.

O motivo é concreto: a página que está no ar hoje tem **18 elementos de texto
sobre gradiente** — medido em 20/08/2026. O contraste desses 18 não é
verificável por máquina, só por opinião, e por isso ninguém consegue afirmar
que a página passa AA. O redesenho existe em parte para acabar com isso.

Gradiente continua permitido como **ornamento**: um véu atrás de um bloco que
não contém texto, uma faixa decorativa, o preenchimento de uma barra de
gráfico. Se houver uma palavra em cima, o fundo imediato daquela palavra é uma
cor sólida da tabela de 6.2.

Isso vale também para a foto: legenda de imagem vai **fora** da imagem, num
bloco de `--surface`, nunca sobreposta.

### 6.5 O destino da esmeralda — decidido

O `#10A87E` **sai da paleta de acento** e sobrevive apenas como **sinal de
estado positivo**, nos tokens `--ok` / `--ok-soft` (recalibrados para
`#0A7355` / `#E3F1EA` no claro e `#45CBA0` / `#10271E` no escuro).

A recalibração não é gosto: o `#10A87E` original **reprova como texto sobre os
três fundos claros da página**, medido pela mesma fórmula do resto da tabela —
**2,91:1** sobre `--bg` (`#FBFAF7`), 3,03:1 sobre `--surface` (`#FFFFFF`) e
2,69:1 sobre `--fundo-alt` (`#F4F1E9`), contra o mínimo de 4,5:1. O número de
referência desta página é o **2,91:1 sobre `--bg`**, que é o fundo em que a
esmeralda de fato aparecia. O `#0A7355` que entra no lugar mede 5,59:1 sobre o
mesmo ecru.

Motivo: "âmbar como acento único" é a regra da direção estética, e um segundo
acento de mesma força faz a página perder o eixo — foi o que aconteceu com a
versão no ar, em que âmbar e esmeralda disputam a atenção em pílula, chip,
badge, gráfico e checkmark, e nenhum dos dois significa nada. Mas apagar o
verde de vez custaria caro em outro lugar: o argumento central desta página é
"verificado ao vivo em produção", e um estado precisa ser distinguível da
marca — se o ✓ tem a mesma cor do botão, todo selo de verificação passa a ler
como material de propaganda.

Onde `--ok` pode aparecer, e em nenhum outro lugar:

1. `.pill.ok` — um selo de estado, tipo "em produção" ou "verificado ao vivo".
2. O glifo `✓` de uma lista de garantias.
3. O `.ponto` de status dentro de uma `.pill.ok`.

(O `.ponto` em si não é exclusivo da `.pill.ok` — ele existe em qualquer `.pill`
e herda a cor dela via `currentColor`. O que é exclusivo do estado positivo é a
**cor** `--ok`, não a bolinha.)

Onde **não** pode: botão, título, link, série de gráfico, fundo de faixa,
borda de cartão, ícone decorativo. E o estado nunca é comunicado **só** pela
cor: a `.pill.ok` sempre traz a palavra escrita.

O `--data-blue` (`#3B7DE0`) da paleta antiga **sai da página**. Não há azul.

### 6.6 A paleta de dados — uma rampa de intensidade, com o alvo escrito

Os gráficos são monocromáticos no matiz âmbar e os três níveis se separam por
**intensidade** — luminância —, não por matiz. Isso é uma afirmação verificável,
e os números do alvo estão aqui para que ela possa ser conferida:

| nível | papel | claro | escuro / tinta |
|---|---|---|---|
| `--dado` | série cheia | `#563506` | `#EFD7AF` |
| `--dado-neutro` | referência / cenário manual | `#695E54` | `#ABA69C` |
| `--dado-fraco` | período parcial | `#AA8046` | `#92764F` |

**O alvo de separação, como número:**

- **`--dado` × `--dado-fraco` ≥ 3:1.** É o par que aparece lado a lado no mesmo
  gráfico (os anos cheios e o `2026*`), e 3:1 é o mesmo mínimo que a WCAG exige
  entre objetos gráficos adjacentes. Medido: **3,09:1** no claro, **3,05:1** no
  escuro.
- **Qualquer par vizinho da rampa ≥ 1,7:1.** Medido: 1,75:1 e 1,77:1 no claro,
  1,73:1 e 1,76:1 no escuro.
- **Cada nível ≥ 3:1 contra todos os fundos** em que pode ser desenhado. Pior
  caso: 3,16:1 (`--dado-fraco` sobre `--fundo-alt`) e 3,22:1 (`--dado-fraco`
  sobre o cartão da faixa de tinta no escuro).

**Por que 3:1 entre os três pares é impossível, e por que o contrato não promete
isso.** O nível mais claro está preso em L ≤ 0,2601 pelo piso de 3:1 contra o
`--fundo-alt`. Do teto até o preto puro cabem no máximo `(0,2601+0,05)/0,05` =
**6,20:1** de rampa inteira, o que dá `√6,20` = **2,49:1** entre vizinhos em dois
degraus — e isso usando preto, que não é âmbar. Um contrato que prometesse 3:1
nos três pares estaria mentindo. O que dá para garantir com honestidade é 3:1 no
par que divide um gráfico e 1,7:1 no resto, e é isso que está escrito acima.

E é por isso que **`--acento` não pode ser barra**: o âmbar da marca (`#E7920D`)
mede 2,47:1 sobre o papel, abaixo do mínimo de 3:1 para objeto gráfico. A marca
vive no botão e na pílula; o dado vive na rampa.

**A prova de que a rampa é de intensidade e não de matiz** é o que sobra ao tirar
a cor. Convertidos para cinza (mesma luminância relativa):

| | `--dado` | `--dado-neutro` | `--dado-fraco` |
|---|---|---|---|
| claro | `#3C3C3C` (60) | `#606060` (96) | `#888888` (136) |
| escuro | `#DADADA` (218) | `#A7A7A7` (167) | `#7A7A7A` (122) |

Três degraus de 36 a 51 unidades. Consequência prática: **quem tem daltonismo
separa os três, e impressa em preto e branco a distinção sobrevive.**

`--dado-neutro` carrega ainda um segundo sinal, além da posição na rampa: é
dessaturado. É assim que o cenário de referência se distingue da série mesmo
quando cai no meio dela.

**Onde a rampa não vale:** gráfico não vai dentro da `.faixa.tinta`. Os tokens
existem lá e foram calibrados contra os fundos de lá, mas a faixa 05 é conversão,
não dado.

E a regra que fecha, que nenhuma calibragem substitui: **nenhuma informação de
gráfico é transmitida só por cor.** Toda barra tem o seu valor escrito ao lado,
em `.num`, e todo período parcial tem asterisco e nota de rodapé.

## 7. Grade e espaçamento

### 7.1 A grade de 12 colunas

`--maxw` = 1120px, `--calha` = 24px (16px abaixo de 768px).

Duas formas de usar, ambas legítimas:

**(a) `.grid` + span** — para layout. O `span` vai no **seu CSS prefixado**;
atributo `style` é proibido (§ 1, item 10):

```html
<div class="grid">
  <div class="painel">…</div>
  <aside class="lateral">…</aside>
</div>
```
```css
#contexto .painel{grid-column:span 7}
#contexto .lateral{grid-column:span 5}
```

**(b) `--col-N`** — para largura de medida de leitura e para `flex-basis`:

```css
#contexto .lede{max-width:var(--col-7)}
```

`--col-N` é a largura de N colunas **mais** as calhas entre elas — mas o `100%`
de dentro dele resolve contra o **bloco contenedor do elemento**, não contra o
`.wrap`. Por isso a regra é mais estreita do que parece:

> **`--col-N` só vale como filho DIRETO do `.wrap`.**

Dentro de uma célula de grade, `var(--col-7)` significa "7 colunas de uma grade
do tamanho da célula" — numa célula de `span 8` isso dá ≈38% do `.wrap`, e o
título é esmagado sem que nada acuse erro. Foi por isso que `.abertura` e
`.lede` **deixaram de usar `--col-N`**: a medida delas é `52rem` e `62ch`, que
não dependem de onde o bloco foi parar.

Medida de leitura: use `ch` (`60ch`–`70ch`) para texto corrido em qualquer lugar,
e `--col-N` só para dividir o `.wrap` no primeiro nível. Nunca deixe um
parágrafo com a largura inteira.

### 7.2 A escala de espaçamento — Fibonacci a partir de 4px

| token | valor | uso típico |
|---|---|---|
| `--e-1` | `4px` | folga entre glifo e texto |
| `--e-2` | `8px` | gap dentro de uma pílula, entre ícone e rótulo |
| `--e-3` | `12px` | gap entre itens irmãos curtos; padding vertical de botão |
| `--e-4` | `20px` | padding de cartão pequeno; respiro lateral no celular |
| `--e-5` | `32px` | padding de `.card`; respiro lateral do `.wrap` |
| `--e-6` | `52px` | distância entre blocos dentro de uma seção |
| `--e-7` | `84px` | passo vertical da faixa em tela média |
| `--e-8` | `136px` | passo vertical da faixa em tela grande |

Todo `margin`, `padding` e `gap` sai desta escala. `0` e `auto` continuam
válidos, claro. Valores em `%`, `ch` e `fr` são para largura, não para respiro.

### 7.3 Raios

`--raio` (10px) para cartão, imagem, painel. `--raio-s` (6px) para botão,
campo, chip. Pílula usa `999px` — já está dentro da primitiva. Não existe
terceiro raio.

---

## 8. As primitivas

O que cada uma faz, e **quando não usá-la**.

### 8.1 `.wrap`
Container: `max-width:--maxw`, centrado, com respiro lateral.
**Não use** aninhado dentro de outro `.wrap`. Uma faixa, um `.wrap`.

### 8.2 `.faixa` (+ `.alt`, `.tinta`)
Fundo e ritmo vertical da seção (§4).
**Não use** em nada que não seja a `<section>` de topo da fatia. Não é
container de cartão nem de bloco interno.

### 8.3 `.grid`
Grade de 12 colunas com calha.
**Não use** quando a sua seção precisa manter mais de uma coluna abaixo de
768px — o sistema colapsa `.grid` à força. Nesse caso monte um grid próprio no
seu prefixo.

### 8.3-b `.abertura` e `.lede`
`.abertura` é o bloco que abre **toda** faixa: `.pill`, depois `<h2>`, depois
`<p class="lede">`, empilhados com `--e-4` de respiro e largura máxima
`--col-7`. `.lede` é o parágrafo de abertura: `--t-5`, cor `--text-soft`.

```html
<div class="abertura rise">
  <span class="pill"><span class="ponto"></span>Resultados · medidos</span>
  <h2>O que a automação entregou na ponta.</h2>
  <p class="lede">Números aferidos pelo próprio histórico…</p>
</div>
```

Estão no sistema, e não em cada fatia, porque as faixas abrem do mesmo jeito —
se cada uma compusesse o próprio cabeçalho, a costura apareceria na montagem.

**O hero (fatia 01) NÃO usa `.abertura`.** Ele monta o próprio topo. Duas razões,
e as duas são concretas: a medida de `52rem` da `.abertura` é calibrada para um
`<h2>`, e um `<h1>` de até 62px dentro dela quebraria em quatro ou cinco linhas;
e o § 8.9 proíbe `.rise` acima da dobra e **nunca** no `<h1>`, enquanto o exemplo
acima — que é o que se copia — traz `.abertura rise`. `.abertura` é das faixas
02 a 05.

**Não use** `.abertura` para um bloco no meio da seção; ela é o topo. **Não
use** `.lede` para parágrafo comum — corpo é `--t-4` e cor `--text`.

### 8.3-c `.link`
Link dentro de texto corrido: `--acento-ink`, sublinhado com offset, sublinhado
engrossa no hover.
**Não use** para uma ação principal — isso é `.btn-p`. **Não use** em cima de
um `.card` inteiro que já é `<a class="card">`.

### 8.3-d `.topo` e `.nav`
A barra do alto da faixa 01: `.marca` à esquerda, `.nav` à direita. Não é
grudenta (§ 4.1-b). `.nav` é uma fileira de links de texto; abaixo de 768px o
`.topo` vira coluna.
**Não use** `.topo` em nenhuma outra faixa — há um só.

### 8.3-e `.acoes`
O grupo de botões. **Use sempre que houver mais de um `.btn` lado a lado**, e
não um `<div>` seu: abaixo de 768px o sistema faz `.btn{width:100%}`, e isso só
fica certo se o contêiner virar coluna — o que `.acoes` faz e um `<div>` avulso
não faria. Dois agentes com dois wrappers diferentes produziriam duas linhas de
botão diferentes no celular.

### 8.3-f `.tabela`
Tabela de dados: cabeçalho em mono/caixa alta, régua de 1px entre linhas, sem
régua na última. O ranking do prêmio é uma `.tabela`.
**Não use** para layout. **Não use** para uma lista de dois campos — isso é um
parágrafo.

### 8.3-g `.figura`
`<figure>` com a legenda **fora** da imagem, num bloco de `--surface` separado
por fio — que é o que o § 6.4 exige.
**Não use** legenda sobreposta à imagem, nunca; é exatamente o caso que a regra
do fundo sólido proíbe.

### 8.3-h `.lista-ok`
A lista de garantias, com `✓` em `--ok` gerado pelo CSS. É o segundo dos três
lugares onde a esmeralda pode aparecer (§ 6.5).
**Não use** para lista comum — `<ul>` simples já tem reset e marcador.

### 8.3-i `.rodape`
O bloco institucional, último dentro da faixa 05 (§ 4.1-b). Fio no topo, texto
em `--t-2` e `--text-soft`.
**Não use** como faixa própria; não existe fatia 06.

### 8.3-j `.trilha`
A pista de altura definida onde a `.col` de um gráfico cresce (§ 9.2). Altura
188px por padrão, ajustável no seu prefixo.
**Não use** para nada além de barra de gráfico, e nunca ponha rótulo dentro
dela — é isso que quebraria a conta da porcentagem.

### 8.4 `.card`
Painel: `--surface`, fio de 1px, `--raio`, padding `--e-5`.

**O que define o cartão é o fio, não o preenchimento.** Isso não é estilo de
escrita, é uma consequência aritmética que você precisa conhecer: com um único
`--surface` é impossível o cartão subir o mesmo tanto sobre duas faixas de tons
diferentes — a diferença entre os dois levantes é, exatamente, a diferença entre
as duas faixas. Por isso `.faixa.alt` **redefine `--surface`**, e o levante fica
uniforme dentro de cada tema:

| contexto | faixa | `--surface` | ΔL\* |
|---|---|---|---|
| claro, faixas 01/03 | `#FBFAF7` | `#FFFFFF` | 1,73 |
| claro, faixas 02/04 | `#F4F1E9` | `#F8F6F1` | 1,74 |
| escuro, faixas 01/03 | `#14110D` | `#241D15` | 6,10 |
| escuro, faixas 02/04 | `#201B14` | `#2D2720` | 5,95 |

O levante é deliberadamente discreto no claro (o branco é o teto: sobre um papel
ecru não há para onde subir) e franco no escuro. Em ambos, **todo `.card` carrega
o seu fio de 1px** — nenhuma fatia pode delimitar um cartão só pelo
preenchimento, porque no tema claro não há preenchimento suficiente para
delimitar nada.
**Não use** como decoração de um parágrafo solto, nem aninhado dentro de outro
`.card` (dois fios concêntricos é ruído). Se o cartão for um link inteiro, use
`<a class="card">` — o sistema dá o hover de borda âmbar.

### 8.5 `.btn`, `.btn-p`, `.btn-s`
Sempre `.btn` mais **uma** das duas variantes. `.btn-p` (âmbar preenchido) é a
ação principal; existe **no máximo uma por faixa**. `.btn-s` é a alternativa,
contorno em `--text-soft`.
**Não use** `.btn` para um link de texto dentro de um parágrafo — link inline é
`<a>` com `color:var(--acento-ink)` e sublinhado.

### 8.6 `.pill` (+ `.ok`)
Micro-rótulo em mono, caixa alta, tracking largo. Abre a seção, antes do `<h2>`.
`.pill.ok` é o selo de estado positivo (§6.5).
**Não use** mais de uma `.pill` como abertura de seção, nem como botão, nem
como tag de lista longa — para lista de termos, use texto em `--t-3`.
Ponto de status opcional: `<span class="ponto"></span>` dentro dela.

### 8.7 `.hairline`
Fio de 1px isolado, para separar blocos dentro de uma seção.
**Não use** entre faixas — o sistema já emite esse fio.

### 8.8 `.skip`
O skip link. **Já é emitido pelo montador.** Nenhuma fatia escreve. Está
listado aqui só para você saber que ele existe e que fica invisível
(`top:-136px`) até receber foco, quando aparece a 20px da borda.

### 8.9 `.rise` (+ `.in`, `data-atraso`)
Entrada por rolagem (§10). A regra que esconde o bloco é `.js .rise` — só existe
se o `head.html` tiver conseguido marcar `<html class="js">`. Sem JavaScript,
`.rise` não esconde nada (§ 9.1).
**Não use** em elemento que precisa estar visível de saída — nada acima da
dobra do hero, nada que seja o único conteúdo de uma faixa curta, e nunca no
`<h1>`.

### 8.10 `.num` e `.num-g`
`.num` = todo número (§5.4). `.num-g` = número de destaque, em `--t-7`, peso
600, cor `--acento-ink`.
**Não use** `.num-g` mais de quatro ou cinco vezes numa mesma faixa: se tudo é
destaque, nada é.

### 8.11 `.marca` — a marca do cabeçalho
Composição única: cubo em imagem + wordmark em texto. Só o hero usa hoje, mas a
definição mora no sistema porque cinco fatias não podem compor a marca cada uma
do seu jeito.

Marcação **exata**:

```html
<span class="marca">
  <img class="marca-cubo" src="assets/cubo-integra.png"
       alt="" aria-hidden="true" width="283" height="268">
  <span class="marca-texto">
    <b class="marca-nome">Projeto INTEGRA</b>
    <span class="marca-desc">I.A. &amp; Automação</span>
  </span>
</span>
```

Quatro coisas não negociáveis:

1. **O cubo é decorativo**: `alt=""` **e** `aria-hidden="true"`, sempre. O nome
   acessível vem do texto ao lado. A armadilha é pôr `alt="INTEGRA"` no cubo e
   fazer o leitor de tela anunciar "INTEGRA INTEGRA".
2. **A marca não leva `aria-label`.** Nem no `<span>`, nem num futuro `<a>`.
   Medido na página no ar: o `aria-label="INTEGRA"` que está lá hoje
   **sobrescreve** o conteúdo interno, então o leitor de tela anuncia só
   "INTEGRA" e o usuário de leitor perde o "I.A. & Automação" que o vidente lê.
   O `alt=""` no cubo mais o texto visível já produzem o nome acessível certo e
   **completo** — qualquer `aria-label` aqui só pode empobrecê-lo.
3. **A marca não é link.** O `href="#"` que o `verificar.py` vinha acusando na
   página no ar é justamente o link do logo: um link que não navega para lugar
   nenhum é pior que um logo que não é link. Se um dia virar link, terá que
   apontar para um `id` que existe ou para fora do site — nunca `href="#"`.
4. `assets/cubo-integra.png` (283×268) é **o** asset da marca.
   `logo-integra-claro.png` e `img-09-…png` **não entram na página**: o
   wordmark embutido neles tem luminância medida de ~242/255 — é branco, e
   some no ecru.

O `.marca-nome` já traz `text-transform:uppercase`, peso 800 e
`letter-spacing:.055em` fixados; o `.marca-desc` já traz mono, `--t-1` e
`letter-spacing:.16em`. **Não sobrescreva nenhum dos dois.**

Registro, para ninguém descrever isto como novidade: a página no ar **já**
compõe o cabeçalho como cubo-imagem mais wordmark em texto. O comentário "LOGO
PROVISÓRIA" que está no HTML dela é sobre o cubo do CGPAG ser provisório
enquanto marca, não sobre o wordmark ser imagem. O que muda aqui é o cubo
(passa a ser o `cubo-integra.png`, 283×268, quase o dobro da resolução) e a
tipografia do wordmark — não a técnica.

> **Divergência consciente, registrada para ninguém "consertar" depois:** a
> marca desta landing fica **tipograficamente diferente** do lockup oficial
> usado na revista e no painelsei. A decisão é do usuário, tomada em
> 20/08/2026, porque o wordmark oficial é branco e desaparece no fundo claro.
> Compor o wordmark em texto resolve o contraste, fica nítido em qualquer tela
> e faz o nome do projeto herdar a tipografia do redesenho.

### 8.12 `.lightbox` (e `.lightbox-video`, `.lightbox-fechar`)
Estilo do diálogo de vídeo, que o `script.js` cria. **Nenhuma fatia escreve
essa marcação nem esses seletores** (§9.3).

---

## 9. A API do `script.js`

Um único arquivo, sem dependência, inlinado pelo montador no fim do `<body>`.
Três comportamentos, três ganchos. **Se a sua fatia precisa de um deles, use o
gancho exatamente como está aqui — o script não vai ser alterado por você.**

### 9.1 Entrada por rolagem — `.rise` → `.in`

Ponha `class="rise"` no bloco que deve entrar. Um `IntersectionObserver`
(threshold 0.15) adiciona `.in` quando ele aparece e para de observar.

Escalonamento opcional, para uma fileira de cartões:

```html
<div class="card rise" data-atraso="1">…</div>
<div class="card rise" data-atraso="2">…</div>
```

`data-atraso` vai de `1` a `5` (80ms cada). Valor fora dessa faixa não faz nada.

**Degradação, nos três casos — e o terceiro é o que quase passou batido:**

1. `prefers-reduced-motion: reduce`: o script adiciona `.in` a tudo de uma vez,
   no carregamento.
2. Navegador sem `IntersectionObserver`: idem.
3. **JavaScript não roda** — filtro corporativo de órgão (e este é um público de
   órgão público), erro em qualquer ponto do script, robô de prévia de link que
   não executa script. Aqui os dois casos acima não ajudam, porque quem
   adicionaria `.in` é justamente o script que não rodou.

O caso 3 se resolve no CSS, não no JS: a regra que esconde é **`.js .rise`**, e a
classe `js` entra no `<html>` por um script inline e síncrono no `head.html`. Se
esse script não rodar, a regra de esconder não casa com nada e a página inteira
nasce visível. **É por isso que nenhuma fatia pode escrever `.rise{opacity:0}`
por conta própria** — seria reintroduzir o defeito para todo mundo.

Vale para as barras também: sem JS, `.col` fica com altura zero e o gráfico
some. Isso é aceitável e é a razão de o § 9.2 exigir o valor escrito ao lado de
cada barra em `.num`: sem script, o gráfico degrada para uma lista de números
legível, que é honesta. O que **não** se pode fazer é dar altura fixa à `.col`
no CSS para "consertar" — isso desenharia barras todas do mesmo tamanho, ou
seja, um gráfico que mente.

### 9.2 Gráfico de barras — `.bars[data-max]` e `.col[data-h]`

```html
<div class="bars" data-max="8000">
  <div class="barra">
    <span class="num valor">7.139</span>
    <div class="trilha"><div class="col" data-h="7139"></div></div>
    <span class="num eixo">2023</span>
  </div>
  <!-- ... -->
</div>
```

O script lê `data-max` da caixa e, para cada `.col[data-h]` dentro dela, define
`style.height` = `max(2, (h / max) * 100)` por cento. Portanto:

- **A mãe DIRETA da `.col` precisa ser a `.trilha`** — uma pista de altura
  definida (188px no sistema), sem rótulo nenhum dentro. Essa é a armadilha
  clássica deste gancho: o `height:%` que o script escreve resolve contra o pai
  imediato, então se a `.col` for filha da `.barra` a porcentagem passa a contar
  a linha do valor e a do eixo, e a barra de valor máximo transborda. `.trilha`
  existe exatamente para isolar a pista dos rótulos. Se precisar de outra
  altura, mude-a no seu prefixo: `#prova .trilha{height:220px}`.
- `.col` começa com altura zero no seu CSS e ganha a altura via JS. Anime com
  `transition:height` — o `@media (prefers-reduced-motion)` do sistema já
  neutraliza isso sozinho.
- `data-h` aceita decimal com ponto (`3.88`). O texto visível ao lado é que usa
  vírgula (`3,88`), e vai em `.num`.
- `data-max` inválido ou `<= 0` faz o script ignorar a caixa em silêncio, em
  vez de quebrar a página.
- A caixa recebe `data-cheia="1"` depois de preenchida — não use esse atributo
  para outra coisa.
- As cores das barras são `--dado`, `--dado-fraco` e `--dado-neutro` (§6.6), e
  **você** as aplica no seu CSS.
- O preenchimento acontece quando a `.bars` entra na viewport (ela é observada
  mesmo sem `.rise`), e imediatamente no modo de movimento reduzido.

### 9.3 Lightbox de vídeo — `.proj[data-video]` e `#lightbox-video`

```html
<article class="proj" data-video="/media/exante.mp4">
  <div class="poster">
    <img src="assets/img-08-6ad7082f.jpg" alt="…" loading="lazy">
    <button type="button" class="play" aria-label="Assistir à execução">▶</button>
  </div>
  <!-- ... -->
</article>
```

Contrato do gancho:

- O elemento com `data-video` tem que ter a classe `.proj`.
- Ele **precisa conter exatamente um `<button>`** — é o que dá acesso pelo
  teclado, e é para onde o foco volta quando o diálogo fecha. **Sem `<button>`,
  o script ignora o cartão inteiro**, de propósito: assim a falta aparece na sua
  prévia, em vez de virar um defeito silencioso de acessibilidade em produção.
- `data-video-titulo="INTEGRA Exante"` nomeia o diálogo daquele vídeo. É
  opcional com um vídeo só, e **obrigatório a partir do segundo** — sem ele
  todos os diálogos se anunciam "Vídeo de execução" e o leitor de tela não os
  distingue.
- Se houver um `.poster`, ele também abre no clique (mouse), sem duplicar o
  evento do botão.
- O id `lightbox-video` é **reservado**. O elemento é criado pelo script no
  `<body>`, com `role="dialog"`, `aria-modal="true"` e `aria-label`. Se não
  existir nenhum `.proj[data-video]` na página, o diálogo nem é criado.

Acessibilidade que o script garante (e que você não precisa reimplementar):
foco vai para o botão de fechar ao abrir; `Tab` e `Shift+Tab` circulam apenas
entre fechar e o vídeo; `Escape` fecha; clique fora fecha; ao fechar, o foco
**volta ao botão que abriu**; o `src` do vídeo é removido para o download
parar; a rolagem do documento é travada enquanto o diálogo está aberto; e o
resto da página recebe `inert` + `aria-hidden` enquanto ele está aberto — a
armadilha de `Tab` sozinha prende o foco, mas não impede o rotor de um leitor de
tela de passear pela página atrás do diálogo.

---

## 10. Movimento

Regras, todas fixadas no sistema:

- **Duração**: `--tempo` (0,22s) para micro-interação, `--tempo-lento` (0,6s)
  para entrada por rolagem. Curva única: `--curva`
  (`cubic-bezier(.2,.7,.2,1)`).
- **Entrada**: só `.rise` — opacidade 0→1 e 14px de deslocamento vertical.
  Nada de escala, nada de rotação, nada de entrada lateral.
- **Hover**: no máximo 1px de deslocamento vertical, e apenas em `.btn`. Cartão
  **não** levanta; cartão-link muda a cor da borda para `--acento-ink`.
- **Foco**: contorno de 2px em `--acento-ink`, offset 3px. Único na página.
  **Nunca declare `outline` em lugar nenhum** — nem para pôr, nem para tirar. A
  regra do sistema usa `:where(...)`, que tem especificidade zero de propósito
  (para você poder estilizar os elementos livremente); o efeito colateral é que
  *qualquer* regra sua prefixada a vence. `#oferta .btn{outline:none}` apaga o
  indicador de foco da página sem aviso nenhum.
- **Movimento reduzido**: o sistema tem um bloco final
  `@media (prefers-reduced-motion: reduce)` que zera duração de transição e de
  animação de **tudo**, com `!important`, e revela os `.rise`. É rede de
  segurança: mesmo assim, escreva a sua animação de forma que a ausência dela
  não esconda informação.
- Nada pisca, nada roda em laço infinito, nada toca sozinho.

---

## 11. Verificação antes de entregar a sua fatia

```
C:/Users/Thelemarco/PycharmProjects/integra-publico/.venv/Scripts/python.exe site/montar.py --so 0N-nome
C:/Users/Thelemarco/PycharmProjects/integra-publico/.venv/Scripts/python.exe site/verificar.py site/preview-0N-nome.html
```

E confira à mão, item por item:

- [ ] a `<section>` tem `id` e `class="faixa"` (mais `alt`/`tinta` conforme §4.1)
- [ ] existe exatamente um `.wrap` dentro dela
- [ ] a fatia não declara padding vertical nem background na `<section>`
- [ ] todo número visível está em `.num` ou `.num-g`
- [ ] todo `@media` de largura é 768px ou 1080px, em `max-width`
- [ ] nenhum seletor do seu CSS começa fora do `#id` da sua seção
- [ ] nenhum bloco `:root`, nenhum token novo com nome do sistema
- [ ] nenhuma `box-shadow` de elevação
- [ ] nenhum texto sobre gradiente ou sobre imagem
- [ ] toda `<img>` tem `alt` (vazio **e** `aria-hidden` se for decorativa)
- [ ] a marca, se a sua fatia a usa, não tem `aria-label` (§8.11)
- [ ] nenhum atributo `style` inline, nenhum `z-index` cru, nenhum `outline`
- [ ] você não escreveu `.rise{opacity:0}` nem altura fixa em `.col`
- [ ] **você abriu a prévia com o JavaScript desligado** e a seção continua
      inteira, legível, com os números dos gráficos visíveis
- [ ] toda `.col` é filha direta de uma `.trilha`
- [ ] nenhum `--col-N` fora de um filho direto do `.wrap`
- [ ] nenhum `href="#"`; toda âncora aponta para um `id` existente
- [ ] a hierarquia de títulos não pula degrau
- [ ] você olhou a seção nos dois temas, claro e escuro

---

## 12. Pendência que não é de fatia: a emenda do `montar.py`

Registrada aqui porque é o único defeito estrutural que este contrato não
consegue corrigir sozinho, e porque quem for consertá-lo precisa saber o que se
espera.

**O problema.** `montar.py` emite `<main id="conteudo">` envolvendo as cinco
fatias. Logo a `<nav>` do hero fica dentro de `<main>`, e daí decorrem duas
coisas erradas: a página não tem landmark `banner`, e o skip link — que aponta
para `#conteudo` — aterrissa **antes** da navegação. Pular a navegação é o único
propósito de um skip link; este não pula nada.

**A emenda mínima que eu recomendo.** Fazer o montador ler uma parte opcional
`site/parts/topo.html` e emiti-la dentro de um `<header class="topo-fixo">`
entre o skip link e o `<main>`:

```python
partes_topo = PARTS / "topo.html"
...
'<a class="skip" href="#conteudo">Pular para o conteúdo</a>',
*( [f'<header>{_ler("topo.html")}</header>'] if partes_topo.exists() else [] ),
'<main id="conteudo">',
```

Com isso: `<header>` vira landmark `banner`; a `<nav>` sai de dentro de
`<main>`; e o skip link passa a pular de fato a navegação. A fatia 01 deixa de
escrever o `.topo` dentro do hero e passa a escrever `topo.html`, sem que
nenhuma outra fatia mude.

**Por que eu não fiz:** mexer no montador durante a construção das cinco fatias
troca o contrato de saída no meio do caminho. Enquanto a emenda não existir,
monte o `.topo` como o § 4.1-b descreve — funciona, só não produz o landmark.

**O que NÃO recomendo:** envolver a fatia 01 inteira em `<header>` e deixar as
outras quatro em `<main>`. Isso põe o `<h1>` fora do `<main>` e faz o skip link
pular a proposta de valor inteira, não só a navegação.
