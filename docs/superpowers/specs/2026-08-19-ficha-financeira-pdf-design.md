# Design — `integra_gov.ficha_financeira`: leitura de ficha financeira em PDF

*Rev. 3 — 19/08/2026. Incorpora as revisões cegas das rodadas 1 e 2.*
*Rev. 5 — todos os 6 módulos implementados e validados contra PDFs reais dos
dois formatos, inclusive o round-trip da impressão do e-SIAPE.*

## 1. Objetivo

Receber um **PDF de ficha financeira** (servidor, aposentado, pensionista ou
instituidor) e devolver os lançamentos como **dados neutros**: rubrica,
descrição, competência (mês/ano), valor e natureza (R = rendimento /
D = desconto).

A biblioteca **não decide nada de negócio**. Ela devolve a ficha estruturada;
qualquer script consumidor escolhe o que fazer (filtrar rubrica, somar
período, comparar exercícios, exportar planilha).

Fora de escopo: baixar o PDF do e-SIAPE/SIAPE (já existe em
`integra_gov.esiape` e `integra_gov.siape`), OCR, cálculo de erário, relatório.

## 2. Os dois formatos de origem

Três PDFs reais foram analisados localmente (`fichas/`, **gitignorado** —
dados pessoais, e o rodapé da impressão web ainda vaza `SESSIONID`).

### Formato A — relatório do SIAPE mainframe (`pensionista.pdf`)

Cabeçalho `L.A54120.DE`, monoespaçado, camada de texto presente e **fiel**:
cada linha vem do PDF como uma única string, com os espaços reais (verificado
com `visitor_text`, todos os runs em `x=0`). Não é reconstrução do extrator,
então recorte por posição é confiável **neste formato**.

```
   R U B R I C A                R/D SEQ           JUL            AGO   ...
--------------------------------------------------------------------------------
00597 PENSAO COMPLEMENTAR - CIVI R  0           1.931,56       1.931,56 ...
**** T O T A L   B R U T O          ****        1.931,56       1.931,56 ...
```

**Geometria — slices Python (`inicio:fim`, fim exclusivo).** Toda a tabela é
expressa na mesma convenção, de propósito: misturar intervalo inclusivo com
exclusivo é a origem clássica de off-by-one na implementação.

| Campo | Slice | Verificado |
|---|---|---|
| código da rubrica | `linha[0:5]` | `"00597"` |
| descrição | `linha[6:32]` | 26 chars, truncada pelo SIAPE |
| **marcador R/D** | `linha[33:34]` | ver nota abaixo |
| SEQ | `linha[36:39]` | `"0  "` |
| valor do mês 1..6 | `[41:56] [56:71] [71:86] [86:101] [101:116] [116:131]` | 15 chars, alinhado à direita |

> **O marcador R/D está na coluna 33, não na 32.** O rótulo `R/D` do cabeçalho
> começa em 32, mas o caractere de dado alinha com o **meio** do rótulo:
> `linha[32]` é espaço em *todas* as linhas e `linha[33]` traz `R`/`D`/espaço.
> Ler a coluna 32 devolveria branco em toda linha e faria a herança de grupo
> (§ 3) atribuir tudo ao primeiro grupo — erro silencioso, com totais que não
> fecham como único sintoma.

As mesmas colunas de valor servem para as linhas `TOTAL BRUTO`,
`TOTAL DESCONTOS` e `TOTAL LIQUIDO`.

Uma página cobre **6 meses**. O exercício está no título (`REFERENTE A 2024`),
**não** no `MES PAGAMENTO`, que é a competência de emissão do relatório.

### Formato B — impressão web do e-SIAPE (`instituidor.pdf`, `aposentado.pdf`)

Tabela com separadores `|`, dois blocos por página (1º e 2º semestre), colunas
`Rubrica | Nome Rubrica | R/D | Seq. | JAN … JUN` e as mesmas três linhas de
total.

> ⚠️ **Bloqueio nos exemplos atuais:** esses dois PDFs **não têm camada de
> texto**. `/Resources` da página é `{}` (nenhum `/Font`) e o content stream
> não contém nenhum operador de texto (`BT`/`Tj`/`TJ`) — cada glifo é curva
> vetorial (3,5 MB e 4,2 MB de bezier). `Producer = "Microsoft: Print To PDF"`:
> a impressão saiu pela impressora padrão do Windows, não pelo destino
> *Salvar como PDF* do Chrome que `docs/uso-basico.md` § "Configuração do
> Chrome (obrigatória)" exige. Reexportar é pré-requisito do M5.

**Ruído previsto no formato B** (a descartar no parser, não a interpretar):
cabeçalho de data/hora do navegador, título com placeholder não resolvido
`$11/default/titlePrintVersionOutput$`, rodapé com a URL contendo `SESSIONID`
e contador de página.

## 3. A regra do marcador R/D: herança de grupo

O marcador **não** é impresso em toda linha. Ele aparece na linha em que o
grupo começa e as linhas seguintes **herdam o último marcador explícito**, na
ordem impressa.

Evidência (formato A, verificada diretamente no texto extraído):

| PDF / página | Linhas | Conferência |
|---|---|---|
| A p1 | `00597 R` → `00599` em branco herda **R** | JUN: bruto `2.897,34` = `1.931,56 + 965,78` ✔ |
| A p2 | `00597 R` → `00600` em branco herda **R**; `00599 D` abre o grupo de descontos | NOV: bruto `3.863,12` ✔, descontos `965,78` ✔, líquido `2.897,34` ✔ |

Evidência (formato B, obtida por rasterização a 4× — ver § 8):

| PDF | Linhas | Conferência |
|---|---|---|
| B aposentado | `00005 R` → `00182`, `10289`, `82881` herdam **R**; `34113 D` → `34334`, `34855` herdam **D** | JAN: bruto `3.600,36` ✔, descontos `1.319,52` ✔, líquido `2.280,84` ✔ |
| B instituidor | `00001 R` → 4 linhas em branco herdam **R** | JAN: bruto `8.066,40` ✔, sem descontos |

O caso decisivo é o do aposentado: uma linha em branco herdando **D**. É ele
que distingue "herança de grupo" de "branco significa R" — no formato A,
sozinho, as duas regras são indistinguíveis. O caso mais difícil é o de JUN no
mesmo PDF: `00182` em branco **intercalada** entre o grupo `R` e o grupo `D`,
e ainda assim somando no bruto (`5.606,40`).

**Consequências de projeto:**

1. A inferência é **determinística** — varredura na ordem impressa, carregando
   o último marcador. Não é busca de subconjunto que some ao total, que seria
   ambígua sempre que dois lançamentos do mesmo valor tivessem naturezas
   opostas (exatamente o caso da rubrica 00599, aliás).
2. A conciliação contra os totais é **validação, não motor de inferência**.
   Se a herança estiver errada, os totais não fecham e a ficha volta marcada —
   em vez de devolver um número silenciosamente trocado.
3. `Natureza.INDEFINIDA` fica reservada a dois casos: linha em branco **sem**
   marcador anterior no bloco, e herança que a conciliação reprovou.

A mesma rubrica pode ter naturezas opostas em meses diferentes — 00599
(adiantamento da gratificação natalina) é crédito em junho e débito em
novembro. A natureza é do **lançamento**, nunca da rubrica.

## 4. Um PDF pode conter várias fichas

Os extratores do próprio pacote produzem PDFs **mesclados**, e eles são o
input nº 1 deste leitor:

- `esiape.ficha_anual.FichaAnualServidor` divide a faixa em blocos de até 15
  anos (`MAX_ANOS_POR_CONSULTA = 15`) e **mescla** tudo em
  `ficha_<matricula>_<ano_ini>_<ano_fim>.pdf`;
- `esiape.ficha_multi_orgao.FichaMultiOrgao` percorre órgãos para trás e
  mescla em `..._multiorgao.pdf` — com **órgão e matrícula mudando** entre
  páginas (o módulo rastreia pares `(orgao, matricula)`).

Ler esse arquivo como "uma ficha" misturaria identidades diferentes.

**Unidade de retorno: uma identidade em um exercício.** A leitura segmenta o
PDF sempre que muda a chave `(tipo, matrícula, órgão)` ou o exercício.

```python
ler_fichas_financeiras(pdf) -> tuple[FichaFinanceira, ...]   # principal
ler_ficha_financeira(pdf)  -> FichaFinanceira                # a única, ou erro honesto
```

> Optei por **segmentar** em vez de trocar `exercicio: int` por
> `exercicios: tuple[int, ...]`. Segmentando, `exercicio: int` volta a ser
> correto *por ficha*, e o consumidor que quer a série histórica agrupa as
> fichas devolvidas. Ter os dois seria redundante.

## 5. Decomposição em módulos

O M3 (identificação) da rev. 1 **foi absorvido**: detectar formato é um
dispatcher barato, e extrair cabeçalho é intrinsecamente por-formato (os
cabeçalhos A e B não compartilham um único campo). Módulo separado espalharia
conhecimento de layout por dois lugares. Ficam 6.

| # | Módulo | Entrega | Estado |
|---|---|---|---|
| **M1** | `modelo.py` + `exceptions.py` | Contrato de dados (cru e final) e árvore de exceções. Sem I/O. | ✅ 47 testes |
| **M2** | `leitura.py` | PDF → páginas de texto + `tem_camada_de_texto()`. Falha com orientação quando não há texto. | ✅ 20 testes |
| **M3** | `_layout_siape.py` | Parser do formato A → `BlocoCru`. | ✅ 38 testes |
| **M4** | `_layout_esiape.py` | Parser do formato B → `BlocoCru`. | |
| **M5** | `conciliacao.py` | `BlocoCru → FichaFinanceira`: herança de grupo + validação contra os totais. Função pura. | ✅ 27 testes |
| **M6** | `api.py` | `ler_fichas_financeiras()` + `ler_ficha_financeira()`, despacho de layout, páginas órfãs. | ✅ 17 testes (doc pendente) |

**Testes de cada módulo entram no commit do próprio módulo**, não acumulados
no fim (regra do projeto). O M6 fica com integração e documentação.

## 6. Contrato de dados (M1 — implementado)

Dois níveis, e a separação resolve o acoplamento entre parsers e conciliação:

**Cru** — o que os parsers emitem, sem interpretar nada:

```python
LinhaCrua(rubrica, descricao, natureza_declarada, sequencia,
          valores: tuple[tuple[Competencia, Decimal], ...])
BlocoCru(identificacao, exercicio, competencias, linhas, totais_lidos,
         emitido_em, paginas)
```

**Final** — o que a conciliação produz:

```python
Competencia(ano, mes)          # frozen, ordenável, hasheável; de_texto("JUN", 2024)
Lancamento(rubrica, descricao, competencia, valor, natureza,
           natureza_declarada, sequencia)
    .natureza_inferida         # PROPERTY derivada, não campo armazenado
TotaisMes(competencia, bruto, descontos, liquido, confere)
Identificacao(tipo, matricula, nome, situacao, orgao_*, upag_*,
              instituidor_*, banco, agencia, conta)
    .chave                     # (tipo, matricula, orgao) — segmenta o PDF mesclado
Aviso(codigo, mensagem, competencia)   # código estável, p/ gate programático
FichaFinanceira(identificacao, exercicio, lancamentos, totais,
                emitido_em, origem, avisos)
    .consistente               # gate de uma checagem só
```

Decisões e o porquê:

- **`Decimal`, nunca `float`** — são centavos; o erro de arredondamento
  binário quebraria a conferência contra os totais.
- **Valor sempre positivo**, sinal na `Natureza` — guardar desconto como
  negativo embutiria uma convenção contábil que é do consumidor.
- **`natureza_inferida` é property**, não campo: campo armazenado poderia
  divergir do resto do estado (`inferida=True` com `declarada="R"`).
- **`Aviso` com código estável**, não string solta: o consumidor testa
  `a.codigo == "MES_NAO_CONFERE"` em vez de casar substring, que quebra a
  cada ajuste de texto.
- **`None` ≠ zero** em `TotaisMes`: mês sem desconto imprime a linha vazia.
- **`situacao` guarda o literal** (`"02 - APOSENTADO"`) além do enum `tipo`:
  é a fonte da derivação no formato B e não se perde na tradução.
- **`emitido_em`**: quem confere pagamento precisa saber de quando é a foto.

### Exceções — e a distinção que define o modo estrito

```
FichaFinanceiraError                 (base)
├── PdfIlegivelError                 arquivo não abre / corrompido
├── PdfSemTextoError                 sem camada de texto — instrui reexportar
├── LayoutNaoReconhecidoError        tem texto, mas não bate com A nem B
├── LinhaNaoReconhecidaError         PERDA DE DADO — sempre levanta
└── FichaInconsistenteError          totais não fecham — só com strict=True
```

`PdfSemTextoError` e `PdfIlegivelError` dividem o caso "nenhuma página tem
texto" por **causa**, não por sintoma: se alguma página falhou na extração, o
PDF pode perfeitamente ter camada de texto, e o erro sai como `PdfIlegivelError`
carregando as falhas de cada página — sem a orientação de reexportar, que
pertence à outra causa. Afirmar um diagnóstico que os dados em mãos desmentem é
a mesma falta que a distinção abaixo evita, um nível acima.

As duas últimas são tratadas de forma **diferente** de propósito:

- **Total que não fecha** é divergência *visível*: vira `Aviso`,
  `TotaisMes.confere=False` e `ficha.consistente=False`. O dado degradado
  fica à vista e o consumidor decide. `strict=True` transforma em exceção.
- **Linha não reconhecida** é *perda de dado*: some sem rastro, e a ficha
  resultante parece íntegra estando incompleta. Levanta **sempre**,
  independente de `strict`. Descartar linha em silêncio é a violação real de
  "mensagens honestas"; total que não fecha é honesto por construção.

Quando `LinhaNaoReconhecidaError` for levantada pela primeira vez (M3/M4), ela
deve carregar **payload estruturado** — a linha ofensora e o número da página —
e não só uma mensagem. É o padrão das exceções tipadas do pacote (cf.
`ExtracaoFichaEsiapeInterrompida`, que carrega `blocos_processados` e `causa`).
Os campos não existem ainda porque não há quem os preencha.

## 7. Pins de robustez (viram teste)

- **P1 — meses sempre do cabeçalho do bloco**, nunca do índice da página. Os
  dois formatos imprimem `JAN FEV …` no cabeçalho. Isso resolve por
  construção o caso "formato A com mais de uma página por semestre", para o
  qual não há amostra. O pareamento mês↔coluna é **por posição**: colunas sem
  mês entram como `None` em vez de serem descartadas. Compactar faria os pares
  deslizarem se uma coluna não-final viesse vazia — e deslizariam igual nas
  linhas de total, de modo que a conferência fecharia com todos os rótulos de
  mês trocados. Valor numa coluna sem mês levanta. O ponto geral: **corrupção
  coerente consigo mesma é pior que incoerente** — a autoverificação por
  construção (§ 3) passaria batido, porque os dois lados da conta estariam
  errados do mesmo jeito.
- **P6 — REFUTADO: o grupo R/D atravessa a quebra de tabela.** A versão
  anterior deste pin dizia o contrário, inferido de o relatório do mainframe
  reimprimir `00597 R` na página 2. A ficha do e-SIAPE derrubou a inferência: o
  bloco do 2º semestre abre com `00001 VENCIMENTO BASICO` **em branco**, e a
  aritmética exige que seja rendimento (`2.825,50 + 282,55 + 1.477,50 =
  4.585,55`, o `TOTAL BRUTO` de julho). A regra que explica os dois formatos é
  uma só: **o marcador é impresso quando o grupo muda**, não a cada página ou
  tabela; reimprimi-lo na virada é redundância, não reabertura.

  A outra metade da prova está no **aposentado**, e é ela que testa a regra
  contra um grupo `D` aberto: o 1º semestre dele *termina* em descontos
  (`34855`) e o 2º semestre abre com `00005 PROVENTO BASICO | R` **explícito**
  — o sistema imprimiu o marcador exatamente onde o grupo mudou (D→R),
  atravessando a fronteira de tabela. É uma predição afirmativa da regra, não
  redundância: se aquele `00005` viesse em branco, a regra nova quebraria
  naquele arquivo. Ele vem com `R`.

  O grupo começa indefinido a cada `BlocoCru` — e como a conciliação roda uma
  vez por bloco, isso basta. Se a herança atravessar um limite onde não devia,
  os totais não fecham e a ficha volta marcada.
- **P2 — linhas curtas.** O formato A trima a linha no último não-espaço:
  `TOTAL DESCONTOS` da p1 tem `len=40`, sem nenhum valor; uma linha sem valor
  em dezembro tem `len=116`. Os slices degradam para `''`, que o parser mapeia
  para célula vazia. Semântica na conciliação: `descontos=None` equivale a
  `0,00` quando `bruto − 0 = líquido` fecha (é o caso real da p1).
- **P8 — anonimizar na fonte, nunca depois.** A fixture do formato B foi
  gerada com o *scrub* rodando **dentro do navegador**, sobre a página aberta:
  o texto que saiu de lá já vinha com nome, matrícula, órgão e conta trocados
  por strings de mesmo comprimento. Assim o dado real nunca entrou no contexto
  do agente nem em arquivo nenhum — e não há uma cópia intermediária para
  esquecer de apagar. É o padrão a repetir para qualquer amostra futura num
  repositório público.
- **P3 — fixtures por *scrub*, não escritas do zero.** Anonimizar o texto real
  substituindo nome/matrícula/órgão por strings **do mesmo comprimento**,
  preservando a geometria. Fixture escrita à mão pode codificar uma coluna que
  não existe e testar o parser contra um layout imaginário. Cobrir: herança de
  grupo (os 4 casos do § 3), linha curta, `TOTAL DESCONTOS` ausente, PDF sem
  texto, PDF mesclado com duas identidades, e o **ruído de impressão do
  formato B** — cabeçalho de data/hora do navegador, título com o placeholder
  `$11/default/titlePrintVersionOutput$`, rodapé com URL/`SESSIONID` e
  contador de página. O parser B tem de descartar essas linhas sem confundi-las
  com linha de tabela não reconhecida (que levanta `LinhaNaoReconhecidaError`);
  é justamente o par de casos que pode se atropelar.
- **P5 — página ilegível vira aviso, não silêncio.** Página cuja extração
  falha não derruba o documento: vem com `PaginaTexto.erro` preenchido. No M6,
  toda ficha cujo intervalo de páginas contenha uma página com erro sai com
  `Aviso(CodigoAviso.PAGINA_ILEGIVEL, ..., competencia=None)` e portanto
  `consistente=False`. No layout do e-SIAPE uma ficha inteira cabe em uma
  página — perder uma em silêncio faria uma ficha sumir do retorno sem rastro,
  e log não é contrato.
- **P7 — páginas ilegíveis fora de qualquer bloco são do despachante.** A
  conciliação só enxerga o intervalo do bloco que recebeu, e uma página
  ilegível **nunca** aparece em `BlocoCru.paginas` (sem texto ela não é
  reconhecida como do layout e o parser não a vê). Por isso a interseção lá é
  com `range(min, max+1)` — o que captura a página quebrada *entre* páginas do
  mesmo bloco. As que caem entre blocos, ou nas bordas do PDF, só o M6 enxerga:
  no formato B elas podem ser uma **ficha inteira desaparecida**. O M6 anexa
  `PAGINA_ILEGIVEL` às fichas adjacentes (a de antes e a de depois) — é
  conservador e visível — e isso vira teste lá.
- **P4 — locale pt-BR.** `"1.931,56"` → `Decimal("1931.56")`: ponto é
  separador de milhar, vírgula é decimal. Valor impresso negativo
  **levanta** `LinhaNaoReconhecidaError`: o sinal nesta ficha é a coluna R/D,
  então um menos impresso é semântica que o parser não conhece — é da classe
  perda-de-dado, não da classe divergência. Zero é valor legítimo.

## 8. Pendências

**Para o usuário:**

~~1. Obter `instituidor.pdf` e `aposentado.pdf` **com camada de texto**.~~
   **RESOLVIDO** — o usuário gerou `instituidor_salvo_pdf.pdf` pelo destino
   nativo do Chrome (`Producer = Skia/PDF m151`, 95 KB contra 372 KB do
   vetorizado). O round-trip foi validado: a estrutura por `|` sobrevive à
   extração intacta, o ruído de impressão aparece onde previsto e é
   descartado, e a ficha fecha 7/7 meses. A fixture do formato B foi
   **regenerada a partir desse PDF**, e não mais da tela.

   O round-trip revelou um campo que a tela não mostra —
   `Banco/Agência/C. Corrente:`, emendado à direita do `Nome:` — que sem
   tratamento era arrastado para dentro do nome do titular. É a justificativa
   empírica de validar contra o artefato real em vez de confiar na fonte:
   duas renderizações do mesmo relatório não trazem os mesmos campos.

2. Obter os PDFs restantes **com camada de texto**. A
   biblioteca aceita qualquer PDF que a preserve — a origem é indiferente. Em
   ordem de preferência: (a) *download direto* do arquivo, se o e-SIAPE
   oferecer, que é a via mais segura porque o PDF vem pronto do servidor e não
   passa por driver de impressão; (b) impressão por um destino que não vetorize
   as fontes (o *Salvar como PDF* nativo do navegador). O que **não** serve é a
   impressora virtual `Microsoft Print to PDF`, que converte as fontes em
   contorno — foi ela que produziu os dois exemplos atuais. O M4 depende disso.
2. Existe ficha de **servidor ativo**? Em qual formato? O tipo está previsto,
   mas não há amostra.

**Técnica — evidência reconfirmada por segunda fonte, ainda não por texto:**
a linha do § 3 que distingue herança de grupo de "branco = R" é a do aposentado
(linha em branco herdando **D**). Não consegui reproduzi-la nesta máquina (sem
rasterizador disponível; `pdftotext` não serve num PDF sem camada de texto),
mas o revisor a reconfirmou de forma independente: rasterização da p. 1 a **4×**
com `pypdfium2` (instalado fora do venv do projeto — nenhuma dependência nova),
recorte da faixa da tabela do 1º semestre, leitura caractere a caractere. O
marcador `R` aparece só em `00005` e o `D` só em `34113`; `00182`, `10289`,
`82881`, `34334` e `34855` vêm em branco. A aritmética fecha: JAN bruto
`3.600,36` = `1.536,79 + 867,26 + 1.196,31`, descontos `1.319,52` =
`1.260,12 + 30,60 + 28,80`, líquido `2.280,84`. JUN ainda exercita o caso mais
difícil — `00182` em branco **intercalada** entre o `R` e o `D`, entrando no
bruto `5.606,40`.

Continua pendente a confirmação por **texto extraível**, que só vem com a
reexportação. Enquanto isso a regra está protegida pela conciliação: se
estiver errada, os totais não fecham e a ficha volta marcada, em vez de
silenciosamente errada.

## 9. Sinergia com o extrator e-SIAPE

`tem_camada_de_texto(pdf) -> bool` (M2) é exatamente o guard que falta em
`esiape.ficha_anual._aguardar_pdf_estavel`, que hoje aceita qualquer PDF que
apareça na pasta de download — foi assim que os dois exemplos vetorizados
passaram sem ninguém notar. Expor como helper público e o `esiape` importar:
uma implementação, dois usos, e o `PdfSemTextoError` já nasce com a orientação
certa. **Depende de decisão do usuário** — o guard no `esiape` é escopo de
outro ciclo.

## 10. O defeito que este ciclo achou seis vezes

Seis achados da revisão eram **o mesmo defeito em alturas diferentes**: um
valor que afirma mais do que se verificou.

| Onde | O que afirmava sem ter verificado |
|---|---|
| `TotaisMes.confere=True` por default | mês validado, sem validação nenhuma |
| Página que estourava virava vazia com log | retorno completo, com uma ficha a menos |
| `PdfSemTextoError` com todas as páginas falhando | uma causa que os próprios erros em mãos desmentiam |
| Página do layout sem título, descartada com log | ficha íntegra, faltando as rubricas daquela página |
| Nome de campo cortado no primeiro bloco de espaços | nome completo, com o sufixo de UF descartado |
| Mensagem prescrevendo "imprima pelo Chrome" | um requisito mais forte que o que a biblioteca impõe |

A correção foi sempre da mesma família: **tornar o estado não-verificado
representável e visível** — `confere` obrigatório, `PaginaTexto.erro`,
diagnóstico dividido por causa, exceção em vez de log, corte por rótulo,
mensagem que nomeia a causa e não a ferramenta.

Duas formulações que valem como regra geral, e que saíram deste ciclo:

- **Corrupção coerente consigo mesma é pior que incoerente.** Se os dois lados
  da conta erram do mesmo jeito, a autoverificação por construção (§ 3) passa
  batido. Foi o caso do pareamento mês↔coluna, em que os totais deslizariam
  junto com os lançamentos.
- **Teste que fabrica um estado inatingível é pior que teste ausente.** A
  ausência de teste é visível; a falsa cobertura dá confiança onde não há
  nenhuma. Foi o caso do guard de página ilegível, cujo teste positivo montava
  à mão um `BlocoCru` que o fluxo real nunca produz.

E uma que vale para o processo, não para o código. A regra "o grupo `R/D` não
atravessa a página" **sobreviveu porque só havia evidência que ela explicava**.
Ela caiu quando apareceu um caso que ela não explicava, e a regra que a
substituiu só ficou de pé porque alguém foi atrás de um caso que poderia
derrubá-la — e não derrubou. Confirmação passiva mantém regras erradas vivas;
o que separa uma hipótese sobrevivente de uma hipótese testada é ter procurado
o contraexemplo.

O mesmo se repetiu no artefato: o formato B foi levantado do texto da tela e
parecia completo, até a validação contra o PDF impresso revelar um campo que a
tela não mostra (`Banco/Agência/C. Corrente:`). Duas renderizações do mesmo
relatório não trazem os mesmos campos — validar contra a fonte não substitui
validar contra o artefato que a biblioteca de fato recebe.

## 11. Alinhamento com os princípios do pacote

1. **Headless** — devolve dados; nenhuma GUI, nenhum formato de saída imposto.
2. **Sem dados pessoais embutidos** — os PDFs de referência ficam fora do
   repositório; as fixtures são anonimizadas.
3. **Mensagens honestas** — nunca reporta sucesso sem conciliação; PDF sem
   texto falha explicando o que fazer, em vez de devolver ficha vazia; perda
   de dado levanta sempre.
4. **Sem dependência nova** — `pypdf>=3.0` já é dependência do pacote.
