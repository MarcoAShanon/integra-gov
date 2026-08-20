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

### 4.2 A faixa de tinta troca a escala inteira

`.faixa.tinta` redefine, **localmente**, `--surface`, `--text`, `--text-soft`,
`--border`, `--acento`, `--acento-ink`, `--acento-soft`, `--on-acento`, `--ok`,
`--dado`, `--dado-fraco` e `--dado-neutro` para a escala escura. Portanto:
dentro da faixa 05 você continua escrevendo `var(--text)`, `.card`, `.btn-p` e
`.pill` normalmente, e tudo se inverte sozinho. **Nunca escreva um hex** para
"fazer o texto ficar claro no fundo escuro" — o token já é claro lá dentro.

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
--font-display: "Bricolage Grotesque", "Helvetica Neue", "Segoe UI", Arial, sans-serif
--font-corpo:   "Archivo", "Segoe UI", "Helvetica Neue", Arial, sans-serif
--font-mono:    "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, "Liberation Mono", monospace
```

A queda foi escolhida olhando o **wordmark**, não a página: se o Google Fonts
não carregar, `PROJETO INTEGRA` cai em Helvetica Neue / Segoe UI — grotescos de
altura-de-x alta e peso comparáveis ao Bricolage em 800, o que mantém a marca
legível e clicável em vez de desfigurada. É estritamente melhor que uma imagem
quebrada. `font-display:swap` está na URL: a piscada do primeiro carregamento é
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

Exceções, e são só estas duas: (a) número que faz parte de um nome próprio
escrito por extenso no meio de um título (`SEI 4.1.5` num `<h2>` fica em mono
mesmo assim — na dúvida, mono); (b) numeral ordinal colado a palavra em um
rótulo curto de `.pill`, que já é mono inteira.

`.num` e `.num-g` já trazem `font-variant-numeric:tabular-nums` e o zero
cortado. Não redeclare.

### 5.5 A escala tipográfica — oito degraus

| token | valor | uso |
|---|---|---|
| `--t-1` | `.72rem` | micro-rótulo em caixa alta: `.pill`, `.marca-desc`, eixo de gráfico |
| `--t-2` | `.82rem` | legenda, nota de rodapé, fonte da informação |
| `--t-3` | `.94rem` | texto secundário, texto de botão, célula de tabela |
| `--t-4` | `1.0625rem` (17px) | **corpo** — é o `font-size` do `body` |
| `--t-5` | `1.18rem` | lede (o parágrafo de abertura de cada seção) e `h4` |
| `--t-6` | `clamp(1.2rem, 1.1rem + .5vw, 1.45rem)` | `h3` |
| `--t-7` | `clamp(1.85rem, 1.3rem + 2.4vw, 2.7rem)` | `h2` e `.num-g` |
| `--t-8` | `clamp(2.35rem, 1.5rem + 3.8vw, 3.85rem)` | `h1` — existe **um** na página, no hero |

Nenhum `font-size` fora desta escala. Se você precisa de um tamanho que não
está aqui, o layout está errado, não a escala.

Alturas de linha: `--lh-corpo` (1.62) para texto corrido, `--lh-titulo` (1.12)
para h1–h4, `--lh-marca` (1.02) para o wordmark. Os títulos já vêm com
`text-wrap:balance`.

### 5.6 Hierarquia de títulos

Um `<h1>` na página inteira, no hero. Cada faixa abre com um `<h2>`. Dentro
dela, `<h3>` e depois `<h4>`. **Nunca pule degrau** — `verificar.py` reprova
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
| `--surface` | `#FFFFFF` | papel do `.card`, sempre um passo acima da faixa |
| `--text` | `#1C1917` | texto principal |
| `--text-soft` | `#6A6055` | texto secundário, legenda, borda de `.btn-s` |
| `--border` | `#DED7C9` | fio de cabelo — **decorativo** (ver 6.3) |
| `--acento` | `#E7920D` | âmbar de **preenchimento**: fundo do `.btn-p` |
| `--acento-ink` | `#96570A` | âmbar de **texto e contorno**: link em destaque, número grande, anel de foco |
| `--acento-soft` | `#F7EBD2` | tinta clara de âmbar: fundo de `.pill`, realce de linha |
| `--on-acento` | `#20160A` | texto sobre `--acento` |
| `--ok` | `#0A7355` | esmeralda — **sinal de estado positivo**, ver 6.5 |
| `--ok-soft` | `#E3F1EA` | fundo do sinal de estado |
| `--dado` | `#C0770B` | série cheia do gráfico |
| `--dado-fraco` | `#9C8256` | série de período parcial |
| `--dado-neutro` | `#8C8377` | série de referência / cenário manual |

Tema escuro (`@media (prefers-color-scheme: dark)`), e **os mesmos valores**
valem dentro de `.faixa.tinta` no tema claro:

| token | escuro | dentro da faixa de tinta, no escuro |
|---|---|---|
| `--bg` | `#14110D` | — |
| `--fundo-alt` | `#1B1711` | — |
| `--fundo-tinta` | `#2A2318` | — |
| `--surface` | `#241D15` | `#352C1F` |
| `--text` | `#F3EEE5` | igual |
| `--text-soft` | `#B3A99B` | igual |
| `--border` | `#3A3227` | `#4A4030` |
| `--acento` | `#F0AE3E` | igual |
| `--acento-ink` | `#F0AE3E` | igual |
| `--acento-soft` | `#2C2214` | igual |
| `--on-acento` | `#1A1206` | igual |
| `--ok` | `#45CBA0` | igual |
| `--dado` | `#F0AE3E` | igual |
| `--dado-fraco` | `#A98F62` | igual |
| `--dado-neutro` | `#8A8070` | igual |

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
| `--dado` (3:1) | 3,42:1 | 3,16:1 | 3,57:1 |
| `--dado-fraco` (3:1) | 3,50:1 | 3,24:1 | 3,66:1 |
| `--dado-neutro` (3:1) | 3,57:1 | 3,31:1 | 3,73:1 |

Mais: `--text` sobre `--acento-soft` 14,80:1 · `--text-soft` sobre
`--acento-soft` 5,20:1 · `--acento-ink` sobre `--acento-soft` 4,85:1 · `--ok`
sobre `--ok-soft` 5,02:1 · `--on-acento` sobre `--acento` **7,21:1**.

**Tema escuro** (e faixa de tinta no tema claro)

| par | sobre `--bg` | sobre `--fundo-alt` | sobre `--surface` |
|---|---|---|---|
| `--text` | 16,29:1 | 15,44:1 | 14,40:1 |
| `--text-soft` | 8,12:1 | 7,70:1 | 7,19:1 |
| `--acento-ink` | 9,71:1 | 9,20:1 | 8,58:1 |
| `--ok` | 9,23:1 | 8,75:1 | 8,17:1 |
| `--dado` (3:1) | 9,71:1 | 9,20:1 | 8,58:1 |
| `--dado-fraco` (3:1) | 6,09:1 | 5,77:1 | 5,38:1 |
| `--dado-neutro` (3:1) | 4,84:1 | 4,59:1 | 4,28:1 |

Mais: `--text` sobre `--acento-soft` 13,50:1 · `--text-soft` sobre
`--acento-soft` 6,73:1 · `--acento-ink` sobre `--acento-soft` 8,05:1 · `--ok`
sobre `--ok-soft` 7,74:1 · `--on-acento` sobre `--acento` **9,56:1**.

**Faixa de tinta dentro do tema escuro** (fundo `#2A2318`, cartão `#352C1F`) —
o caso mais apertado da página: `--text` 13,44:1 / 11,87:1 · `--text-soft`
6,70:1 / 5,92:1 · `--acento-ink` 8,01:1 / 7,07:1 · `--ok` 7,62:1 / 6,73:1 ·
`--dado-neutro` 4,00:1 / 3,53:1.

Nenhum par abaixo do mínimo, em nenhum dos quatro contextos.

**Se você combinar duas cores que não estão nesta tabela, você quebrou o
contrato.** Não existe combinação nova sem recalcular, e recalcular não é
tarefa de fatia.

### 6.3 O fio de cabelo é decorativo

`--border` mede ~1,4:1 contra o fundo. Isso é **de propósito**: é um fio de
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
`#0A7355` / `#E3F1EA` no claro e `#45CBA0` / `#10271E` no escuro, porque o
`#10A87E` original media 3,3:1 sobre o ecru e reprovava em texto).

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

Onde **não** pode: botão, título, link, série de gráfico, fundo de faixa,
borda de cartão, ícone decorativo. E o estado nunca é comunicado **só** pela
cor: a `.pill.ok` sempre traz a palavra escrita.

O `--data-blue` (`#3B7DE0`) da paleta antiga **sai da página**. Não há azul.

### 6.6 A paleta de dados

Os gráficos são monocromáticos em âmbar, distinguidos por **intensidade**, não
por matiz — é o que preserva o acento único:

- `--dado` — período/série cheia.
- `--dado-fraco` — período parcial (o `2026*`, o `jun/26*`).
- `--dado-neutro` — série de referência ou o cenário "à mão".

`--dado` é um passo mais escuro que `--acento` de propósito: `--acento` sobre
papel mede 2,47:1 e reprovaria como objeto gráfico; `--dado` mede 3,42:1 a
3,57:1 e passa sem precisar de contorno.

E a regra que fecha: **nenhuma informação de gráfico é transmitida só por
cor.** Toda barra tem o seu valor escrito ao lado, em `.num`, e todo período
parcial tem asterisco e nota de rodapé — exatamente como na página atual.

---

## 7. Grade e espaçamento

### 7.1 A grade de 12 colunas

`--maxw` = 1120px, `--calha` = 24px (16px abaixo de 768px).

Duas formas de usar, ambas legítimas:

**(a) `.grid` + span** — para layout:

```html
<div class="grid">
  <div style="grid-column:span 7">…</div>
  <div style="grid-column:span 5">…</div>
</div>
```
(na prática o `span` vai no seu CSS prefixado, não em `style`.)

**(b) `--col-N`** — para largura de medida de leitura e para `flex-basis`:

```css
#contexto .lede{max-width:var(--col-7)}
```

`--col-N` é a largura de N colunas **mais** as calhas entre elas, em % do
`.wrap`. Só faz sentido dentro de um `.wrap`.

Medida de leitura recomendada: `--col-7` para lede e parágrafo longo,
`--col-6` para texto dentro de cartão largo. Nunca deixe um parágrafo com
`--col-12` de largura.

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

Estão no sistema, e não em cada fatia, porque as cinco abrem do mesmo jeito —
se cada uma compusesse o próprio cabeçalho, a costura apareceria na montagem.
**Não use** `.abertura` para um bloco no meio da seção; ela é o topo. **Não
use** `.lede` para parágrafo comum — corpo é `--t-4` e cor `--text`.

### 8.3-c `.link`
Link dentro de texto corrido: `--acento-ink`, sublinhado com offset, sublinhado
engrossa no hover.
**Não use** para uma ação principal — isso é `.btn-p`. **Não use** em cima de
um `.card` inteiro que já é `<a class="card">`.

### 8.4 `.card`
Painel: `--surface`, fio de 1px, `--raio`, padding `--e-5`.
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
Entrada por rolagem (§10).
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

Três coisas não negociáveis:

1. **O cubo é decorativo**: `alt=""` **e** `aria-hidden="true"`, sempre. O nome
   acessível vem do texto ao lado. A armadilha é pôr `alt="INTEGRA"` no cubo e
   fazer o leitor de tela anunciar "INTEGRA INTEGRA".
2. **A marca não é link.** `href="#"` é reprovado pelo verificador e um link
   para o topo da própria página não serve para nada. Se um dia virar link, terá
   que apontar para um `id` real ou para fora.
3. `assets/cubo-integra.png` (283×268) é **o** asset da marca.
   `logo-integra-claro.png` e `img-09-…png` **não entram na página**: o
   wordmark embutido neles tem luminância medida de ~242/255 — é branco, e
   some no ecru.

O `.marca-nome` já traz `text-transform:uppercase`, peso 800 e
`letter-spacing:.055em` fixados; o `.marca-desc` já traz mono, `--t-1` e
`letter-spacing:.16em`. **Não sobrescreva nenhum dos dois.**

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

**Degradação:** com `prefers-reduced-motion: reduce`, ou em navegador sem
`IntersectionObserver`, o script adiciona `.in` a tudo de uma vez, no
carregamento. Nenhum conteúdo depende de animação para existir.

### 9.2 Gráfico de barras — `.bars[data-max]` e `.col[data-h]`

```html
<div class="bars" data-max="8000">
  <div class="barra">
    <span class="num valor">7.139</span>
    <div class="col" data-h="7139"></div>
    <span class="num eixo">2023</span>
  </div>
  <!-- ... -->
</div>
```

O script lê `data-max` da caixa e, para cada `.col[data-h]` dentro dela, define
`style.height` = `max(2, (h / max) * 100)` por cento. Portanto:

- A caixa `.bars` **precisa ter altura própria no seu CSS**
  (ex.: `#prova .bars{height:188px}`), e `.col` precisa ser filho de um
  container de altura conhecida — senão `height:%` não resolve.
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
  teclado. O script liga o clique nesse botão.
- Se houver um `.poster`, ele também abre no clique (mouse), sem duplicar o
  evento do botão.
- O id `lightbox-video` é **reservado**. O elemento é criado pelo script no
  `<body>`, com `role="dialog"`, `aria-modal="true"` e `aria-label`. Se não
  existir nenhum `.proj[data-video]` na página, o diálogo nem é criado.

Acessibilidade que o script garante (e que você não precisa reimplementar):
foco vai para o botão de fechar ao abrir; `Tab` e `Shift+Tab` circulam apenas
entre fechar e o vídeo; `Escape` fecha; clique fora fecha; ao fechar, o foco
**volta ao botão que abriu**; o `src` do vídeo é removido para o download
parar; a rolagem do documento é travada enquanto o diálogo está aberto.

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
  Nunca remova `:focus-visible`.
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
- [ ] nenhum `href="#"`; toda âncora aponta para um `id` existente
- [ ] a hierarquia de títulos não pula degrau
- [ ] você olhou a seção nos dois temas, claro e escuro
