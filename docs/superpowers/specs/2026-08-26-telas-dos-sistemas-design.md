# Design — as telas dos sistemas: cinco paradas e o vídeo

*26/08/2026. Escopo: um bloco novo na fatia `03-contexto` da landing, com as
capturas reais das telas por onde o trabalho manual passa, e o vídeo da
automação como fecho. Mais a troca da abertura da fatia.*

*As cinco capturas existem e foram auditadas — ver § 11.*

## 0. Enquadramento

Vale o § 0 da spec de 20/08 (`2026-08-20-landing-divulgacao-design.md`):
**parceria entre gestores, não relação comercial**, com o vocabulário de
transação vetado (`solução`, `cliente`, `atendimento`, `oferta`, `proposta de
valor`) e sem imperativo publicitário.

E vale um corolário específico deste trabalho, que **corrige um erro do
controlador**. Ao registrar a ideia pela primeira vez, o controlador propôs uma
**grade de quatro telas lado a lado**, argumentando que "a comparação simultânea
é o argumento". O usuário corrigiu:

> *"A questão aqui não é comparação e sim trazer a memória do gestor os sistemas
> com os quais ele tem que lidar."*

**O objetivo é RECONHECIMENTO, não comparação — e os dois pedem desenhos
opostos.** Comparação quer miniaturas alinhadas, para a diferença saltar.
Reconhecimento quer cada tela **grande o bastante para o gestor dizer "essa eu
conheço"**; miniatura a 25% da largura não dispara memória nenhuma.

Consequência que precisa ficar escrita, para ninguém "corrigir" isto no futuro:
o instinto original do usuário (uma tela por vez, grande) estava **mais próximo
do objetivo real** que a contraproposta do controlador. O que barrava o carrossel
— § 10 do contrato, "nada roda em laço infinito", e a exigência de que a ausência
da animação não esconda informação — continua valendo, mas o problema era o
**mecanismo**, não a intenção.

## 1. O problema

A fatia `03-contexto` **afirma** que os sistemas não se falam. A abertura diz
*"Dois sistemas que não se falam — e um deles nasceu em 1989"*, e a lede
completa: *"Entre os dois fica o servidor: copiando, digitando e conferindo
matrícula por matrícula."*

Afirmar é o que a página pode fazer com palavras. Mas o leitor-alvo — um gestor
que conhece esses sistemas **como usuário** — não precisa que lhe digam: ele
precisa **reconhecer**. Uma captura da tela verde do 3270 faz, num segundo, o que
o parágrafo tenta em três linhas.

## 2. As decisões do usuário — 26/08/2026, verbatim

> **U1.** *"nesta pasta salvei umas capturas de telas que podem ser interessantes
> para chamar a atenção sobre os sistemas que não se falam, talvez algum tipo de
> animação ou carrocel, principalmente para a parte dos leigos"*

> **U2.** *"A questão aqui não é comparação e sim trazer a memória do gestor os
> sistemas com os quais ele tem que lidar!"*

> **U3.** A sequência real, dada pelo usuário quando perguntado:
> *"Seria, SEI (verificar processo), eSIAPE emitir ficha, SEI novamente fazer a
> instrução processual, Terminal (lançamento), SEI para fechar."*

> **U4.** *"Em baixo pode ter um: Veja funcionando! com o link do vídeo com a
> automação completa."*

## 3. Decisões de desenho

| # | decisão | alternativa descartada |
|---|---|---|
| D1 | **Uma tela por vez, grande, na rolagem** — o leitor percorre as cinco paradas | grade simultânea (serve comparação, não reconhecimento); carrossel (§ 10 do contrato) |
| D2 | **O SEI aparece três vezes**, porque a sequência real volta a ele três vezes | mostrar cada sistema uma vez e dizer o vaivém por escrito |
| D3 | **O SIAPEnet fica de fora** | incluí-lo porque a captura existe |
| D4 | **O vídeo fecha o bloco**, ligado à cena que o leitor acabou de percorrer | manter o vídeo só na vitrine da fatia 04 |
| D5 | **A abertura passa a "Dois sistemas. Três telas. Cinco paradas."** | manter "Dois sistemas que não se falam", que o leitor contradiz contando as telas |
| D6 | **Sem exclamação em lugar nenhum** | "Veja funcionando!" como o usuário escreveu |

**Sobre D3:** o SIAPEnet não está na sequência do usuário. Entrar só porque a
captura existe seria decoração, e a página inteira é construída contra isso.

**Sobre D2 — e uma correção do controlador que precisa ficar registrada:** ao
propor o caminho, o controlador afirmou que repetir o SEI três vezes seria "de
graça", porque o navegador serviria a mesma imagem do cache. Isso vale para a
**mesma** imagem. Logo em seguida o próprio controlador recomendou três capturas
**diferentes** do SEI (árvore, instrução, fechamento), e as duas coisas não podem
ser verdade ao mesmo tempo. **São cinco arquivos, não três**, e o custo está no
§ 8.

**Sobre D6:** o texto visível da página inteira tem **zero** exclamações, e os
cinco `h2` são declarativos. Uma exclamação aqui seria a única da página. O
usuário escolheu o rótulo sem ela (§ 5).

## 4. As cinco paradas

Uma `<ol>` de cinco itens. Cada item traz uma captura e uma legenda que nomeia
**o que o gestor faz ali** — não o que a imagem mostra.

| # | tela | arquivo de origem | legenda (texto exato) |
|---|---|---|---|
| 1 | SEI — árvore do processo | `SEI.png` | "O processo chega. Você abre a árvore para ver o que ele pede." |
| 2 | e-SIAPE (Sigepe) — folha | `eSIAPE.png` | "Para responder, você emite a ficha financeira em outro sistema." |
| 3 | SEI — Registrar Documento Externo | `instrucao.png` | "Volta ao processo e redigita, à mão, o que leu na outra tela." |
| 4 | Terminal 3270 — menu | `SIAPE_TERMINAL.png` | "O lançamento é numa terceira tela, que não conversa com nenhuma das duas." |
| 5 | SEI — Conclusão de Processo | `conclusao.png` | "Volta de novo, para fechar." |

**A parada 3 e a sua legenda se sustentam uma na outra, e isso não é acaso.** A
captura é o formulário "Registrar Documento Externo" com **todos os campos
vazios** — Tipo do Documento, Nome na Árvore, Remetente, Interessados,
Classificação por Assuntos. O formulário em branco **é** a redigitação de que a
legenda fala. Uma captura anterior mostrava um visualizador de PDF com página em
branco ocupando ~70% da imagem; foi substituída pelo usuário em 26/08 porque a
legenda dizia uma coisa e a figura mostrava outra. **Não a restaure.**

E o fecho do bloco, **a única frase em que a página fala**, porque o leitor já
contou sozinho:

> **Três voltas ao mesmo lugar. Nenhum dado passou sozinho.**

**"Três" vai por extenso, e não leva `.num`.** O § 5.4 do contrato cobra
*número* — dígito —, e o portão do mono varre dígitos. Por extenso, em prosa
curta, a palavra lê melhor e não cria um número solto no meio de uma frase de
fecho. Já o `3270` das legendas e o `5 min 28 s` do vídeo são dígitos e **vão em
`.num`**.

## 5. O bloco do vídeo

Fecha a sequência. Rótulo escolhido pelo usuário entre três opções:

> **Veja o mesmo percurso, feito pela automação** · `5 min 28 s`

*"O mesmo percurso"* é o que amarra o vídeo à cena — e é o que faz o leitor
querer ver. A duração aparece ao lado, em `.num`.

**Por que a duração é obrigatória:** o crítico cego apontou, sobre a vitrine da
fatia 04, que *"o gestor decide clicar pelo tamanho; sem ele, não clica"*.
5min28s é um compromisso real para quem ainda está decidindo se escreve — dizer
o número é honesto, e a página não tem escolha quanto a dizer.

**Mecânica:** reusa o gancho do contrato § 9.3 — `.proj` + `data-video` +
`.poster` + **exatamente um** `<button>`. Sem o botão o script ignora o bloco.
Nenhuma linha de JavaScript nova.

**Sem JavaScript:** a regra do sistema esconde o botão
(`html:not(.js) .proj[data-video] button{display:none !important}`), porque sem
script ele ficaria desenhado e inerte. Mas o leitor com JS bloqueado é justamente
o servidor numa máquina de órgão com bloqueador corporativo. O bloco leva um
`.so-sem-js` com **link direto para `/media/exante.mp4`**, para que esse leitor
não perca o vídeo.

**O vídeo passa a ter duas portas** (aqui e na vitrine da fatia 04). Não é
repetição: ali ele é mostruário, aqui é a resposta à cena que o leitor acabou de
percorrer.

**Atenção ao testar:** `site/media/` é gitignored e o vídeo **vive só na VPS**.
Numa prévia local o `data-video` aponta para um arquivo que não existe — o botão
aparece e o lightbox abre vazio. Isso é esperado e **não é defeito**.

## 6. A abertura da fatia 03

De:

> `<h2>` Dois sistemas que não se falam — e um deles nasceu em `1989`.

Para:

> `<h2>` Dois sistemas. Três telas. Cinco paradas.

**O `1989` tem de MUDAR DE LUGAR, não sumir.** Verificado: ele aparece **uma
única vez** em toda a fatia, e é neste `h2` (linha 19). Trocar o título sem mais
nada **apagaria da página** o fato que dá o soco — um dos dois sistemas é mais
velho que a web. Ele passa para a lede, que fica:

> "O SEI tramita documentos na web desde `2009`. O SIAPE guarda os dados
> funcionais numa emulação de terminal de mainframe — a tela preta `3270`, que
> existe desde `1989`. Entre os dois fica o servidor: copiando, digitando e
> conferindo matrícula por matrícula."

(Os três números continuam em `.num`, como já estão.)

Não é contradição com "dois": e-SIAPE e terminal 3270 são o **mesmo SIAPE**, em
duas caras. O `h2` novo diz isso e prepara o que vem abaixo.

## 7. Estrutura e acessibilidade

- **`<ol>`**, não `<ul>` nem `<div>`: a ordem é semântica. Quem usa leitor de
  tela precisa saber que a parada 3 vem depois da 2.
- Cada item é uma **`.figura`** (contrato § 8.3-g): legenda **fora** da imagem,
  num bloco de `--surface` separado por fio. **Nunca** legenda sobreposta —
  é exatamente o caso que o § 6.4 proíbe.
- Cada `<img>` leva **`alt` descritivo da tela**, não do passo. O alt serve quem
  não vê a imagem; a legenda já diz o que se faz ali. Exemplo para a parada 4:
  *"Terminal 3270 do SIAPE: tela preta com texto verde e menu de opções em caixa
  alta — ADMINIST, CADSIAPE, CONSULTAS, FOLHA."*
- **`loading="lazy"`** e `width`/`height` explícitos em todas as cinco, como as
  outras nove imagens da página.
- **Sem dependência de JavaScript:** as figuras são estáticas e a seção nasce
  inteira. Só o botão do vídeo depende de script, e tem o fallback do § 5.

## 8. Os assets

**Origem:** `site/media/` (gitignored). Hoje contém `SEI.png`,
`SIAPE_TERMINAL.png`, `SIAPEnet.png`, `eSIAPE.png` e `exante.mp4`.

**Tratamento:** JPEG redimensionado, no padrão das existentes (a maior da página
é `img-08`, 1000×541, 117 KB). Nomeadas por **hash do conteúdo** e gravadas em
`site/assets/`, conforme a regra de cache do `site/README.md` — asset que muda de
conteúdo muda de nome, e o navegador nunca serve o antigo.

**O peso, medido:**

| | antes | depois |
|---|---|---|
| assets | 701 KB em 12 arquivos | ~1,3 MB em 17 |

É o dobro, numa página que se orgulha de ter saído de 648,7 KB para 125 KB.
Mitiga o `loading="lazy"`: as cinco só carregam quando o leitor chega ao bloco,
e nenhuma atrasa a primeira dobra. **O usuário aprovou este custo explicitamente.**

**Compressão — o limite que não se deve cruzar:** reconhecimento depende de
**fidelidade**. Comprimir até borrar o desenho dos menus, a cor da barra do SEI
ou a tipografia do 3270 destrói o objetivo do bloco. É o único lugar deste
trabalho onde economizar peso custa a função. Na dúvida, mais qualidade.

**Privacidade — auditado em 26/08/2026:**

- Nenhuma das quatro capturas tem CPF, matrícula, nome de servidor ou qualquer
  dado de terceiro.
- O que aparece é o nome do **próprio autor** (`MARCO` no terminal e no e-SIAPE;
  `MARCO AURELIO DA SILVA` no SIAPEnet, que fica de fora), já publicado no rodapé
  da página como contato. Decisão dele.
- Os números de processo na captura do SEI são **fictícios, de teste** —
  confirmado pelo usuário.
- **As duas capturas novas (§ 11) precisam da mesma auditoria antes de entrar**,
  e devem ser feitas na unidade de testes, com processos fictícios.

## 9. Restrições do contrato que este trabalho toca

1. **§ 8.3-g `.figura`** — legenda fora da imagem, em bloco de `--surface`
   separado por fio. Não sobrepor.
2. **§ 6.4** — fundo sólido atrás de texto: proíbe legenda sobre imagem.
3. **§ 5.4** — todo número visível em `.num`: o `três` do fecho, o `3270`, o
   `5 min 28 s`.
4. **§ 9.3** — o gancho do lightbox: `.proj` + `data-video` + `.poster` +
   exatamente um `<button>`.
5. **§ 10** — nada pisca, nada roda em laço, nada toca sozinho. As figuras são
   estáticas; o vídeo abre por clique e **mudo** (`video.muted = true` antes do
   `play()`, já garantido pelo `script.js`).
6. **§ 9.1** — os `.rise` só somem sob `.js`. Com script bloqueado o bloco nasce
   inteiro.
7. **§ 4.1** — a fatia 03 não muda de fundo; o bloco novo mora dentro dela.
8. **Nenhum token, primitiva ou breakpoint do sistema é criado ou alterado.** Se
   o bloco exigir CSS, ele mora em `03-contexto.css`, prefixado por `#contexto`.

## 10. Verificação

O ciclo do `site/README.md`, sem atalho — os quatro têm de passar:

1. `site/montar.py`
2. `site/verificar.py` — cobra `alt` em toda imagem e recurso externo por host
3. `site/auditar_contrato.py`
4. `pytest tests/test_site.py`

Além deles, três checagens que os portões não fazem:

- **O portão do mono** (`test_nenhum_numero_visivel_escapa_do_mono`) vai cobrar
  os números novos automaticamente — é o teste escrito nesta mesma data.
- **Olhar as cinco imagens no navegador, em tamanho real**, e responder: dá para
  reconhecer a tela? Se a compressão apagou o que faz o gestor reconhecê-la, o
  bloco falhou no seu único objetivo, e nenhum teste diz isso.
- **Testar com JavaScript desligado**: as cinco figuras têm de aparecer, e o link
  alternativo do vídeo tem de estar acessível.

**Publicação:** o redeploy do `site/README.md` (assets primeiro, página por
último) só com **ordem explícita do usuário**.

## 11. As capturas — resolvido em 26/08/2026

As cinco existem em `site/media/` e **todas foram auditadas**:

| parada | arquivo | o que mostra | privacidade |
|---|---|---|---|
| 1 | `SEI.png` | árvore do processo, três documentos "teste" | limpa |
| 2 | `eSIAPE.png` | menu da folha no Sigepe, "EMITE INFORMACOES FINANCEIRAS" | nome do autor |
| 3 | `instrucao.png` | "Registrar Documento Externo", campos vazios | limpa |
| 4 | `SIAPE_TERMINAL.png` | menu inicial do 3270, tela preta e verde | nome do autor |
| 5 | `conclusao.png` | "Conclusão de Processo", "Somente concluir" | limpa |

Nenhuma tem CPF, matrícula, nome de servidor ou dado de terceiro. As três do SEI
são da unidade de testes (`MGI-SGP-DECIPEX-CGPAG-NUTEC`), com processos que o
usuário confirmou serem fictícios. Nas duas do SIAPE aparece o primeiro nome do
próprio autor, já publicado no rodapé da página como contato — decisão dele.

**O `SIAPEnet.png` continua fora** (D3), e é a única das seis que traz o nome
completo do autor.

## 11-b. Ferramenta de preparo — precisa ser resolvida no plano

**Este repositório não tem hoje como redimensionar nem converter imagem.**
Verificado em 26/08: `Pillow` não está no venv, `ImageMagick` não está instalado.
O que existe no `PATH` como `convert` é
`C:\Windows\system32\convert.exe` — **o utilitário do Windows que converte
volume de FAT para NTFS**. Nunca o invoque para imagem.

Foi por essa ausência que o ciclo anterior escreveu `site/recortar_cubo.py`, um
decodificador de PNG em zlib puro. Aqui não serve: é preciso **codificar** JPEG,
não só decodificar PNG.

**Decisão para o plano:** instalar `Pillow` no venv do repo como ferramenta local
de preparo de asset. Não entra no `pyproject.toml` e não vira dependência do
pacote `integra-gov` — é o mesmo estatuto de `extrair_assets.py` e
`gerar_og.py`.

## 12. O que fica em aberto

1. **O vídeo não é versionado.** Vive na VPS, e `site/media/` é gitignored. Não
   há como um teste automático provar que o arquivo existe em produção.
2. **A duração `5 min 28 s` foi medida do arquivo local** (`mvhd` do MP4:
   328,1 s; 5,7 MB). Se o vídeo for reeditado, o número na página passa a mentir
   e nenhum portão avisa.
3. **O bloco cresce a fatia 03 em cerca de 2.000px no celular**, numa página que
   o crítico cego já apontou como densa (~2.640 palavras, 21.500px). Aprovado
   pelo usuário sabendo disso.
4. **O achado maior do crítico cego continua aberto** e este trabalho só o
   arranha: o vão entre o que a página **prova** (o Exante, marcado "interno") e
   o que ela **entrega** (os blocos públicos). O vídeo mostra a automação
   funcionando, o que ajuda — mas não responde *quem escreve o código* nem
   *em quanto tempo sai o primeiro fluxo*.
