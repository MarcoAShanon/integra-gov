# Dados pessoais do servidor no e-SIAPE (CDCOINDPES) — design

**Data:** 2026-09-16
**Módulo alvo:** `integra_gov/esiape/dados_pessoais.py`
**Estratégia:** porte do script da apresentação de 11/09/2026
(`dados_reais/apresentacao/extrair_cadastral.py`, gitignored), que rodou
ao vivo em 5 matrículas com 9/9 campos lidos, sem falha. Nenhum dado
pessoal ou órgão real embutido: tudo que varia é parâmetro.

## Contexto

A tela CDCOINDPES ("dados individuais pessoais") mostra o cadastro de uma
matrícula e imprime um PDF com camada de texto cujos rótulos são estáveis
(`MATRICULA`, `NOME`, `SIT.SER.`, `NUMERO DO CPF`, `DATA NASCIMENTO`,
`E-MAIL PESSOAL`, `MUNICIPIO`, `UF`, `ORGAO SOLICITADO`). O PDF serve como
documento a anexar em processo e como fonte dos campos: a decisão tomada no
gate de 11/09 foi **ler do PDF, não da tela**, porque o texto dos frames CIS
é menos estável e o PDF é necessário de qualquer forma.

Consumidores previstos: a fatia B-5 do `integra-flow` (e-SIAPE como etapa
antes do lote do SEI) e a fatia 1 do `integra-exante-novo`. Ambos precisam
reler PDFs já no disco sem abrir o navegador — daí as duas camadas.

## Escopo

**Entra:** o módulo, a exceção `DadosPessoaisIndisponiveis`, testes
mockados, README + CHANGELOG + uso-basico no mesmo commit, gate ao vivo.

**Fica fora:**
- Lote, checkpoint e "só faltantes" → orquestrador (B-5 do flow).
- Campos além dos 9 (sexo, estado civil, endereço, telefone…): o campo
  `texto` entrega o PDF inteiro para quem precisar; um campo novo entra com
  teste e rótulo confirmado em PDF real, não por suposição.
- Pensionista (CDCOPSBENE) e ficha mensal (FPCOFICHAF): ciclos próprios.
- Leitura pela tela (como faz `dados_funcionais`): duas fontes para os
  mesmos dados seria manutenção em dobro.

## API pública

```python
from pathlib import Path
from integra_gov.esiape import DadosPessoaisServidor, ler_dados_pessoais

# com navegador (sessão do e-SIAPE já autenticada)
dados = DadosPessoaisServidor(driver, pasta_saida=Path("cadastrais/")).consultar("0000000")
dados.nome, dados.cpf, dados.pdf        # pdf = cadastrais/dados_pessoais_0000000.pdf

# sem navegador: PDF já no disco
dados = ler_dados_pessoais(Path("cadastrais/dados_pessoais_0000000.pdf"))
```

### `DadosPessoais` (dataclass)

| campo | origem (rótulo) | normalização |
|---|---|---|
| `matricula` | `MATRICULA` | só dígitos |
| `nome` | `NOME` | como está |
| `situacao` | `SIT.SER.` | remove o código numérico inicial (`02 APOSENTADO` → `APOSENTADO`) |
| `cpf` | `NUMERO DO CPF` | como está |
| `data_nascimento` | `DATA NASCIMENTO` | `15AGO1960` → `15/08/1960`; se não casar, `None` |
| `email` | `E-MAIL PESSOAL` | minúsculas |
| `municipio` | `MUNICIPIO` | Title Case |
| `uf` | `UF` | como está |
| `orgao` | `ORGAO SOLICITADO` | remove `código - ` inicial (`40806 - DECIP/SGP` → `DECIP/SGP`) |
| `texto` | — | a camada de texto inteira do PDF (`extraction_mode="layout"`) |
| `pdf` | — | caminho do PDF: o recebido, em `ler_dados_pessoais`; o renomeado, em `consultar` |

Campo cujo rótulo não aparece no texto fica `None`, sem levantar: campo
ausente é informação, não falha. O valor de cada rótulo vai até o próximo
rótulo **conhecido** na mesma linha (um ou mais espaços seguidos de um dos
nove rótulos e `:`) ou o fim da linha. *(Revisão final de 16/09: o script
cortava em "2+ espaços + maiúsculas + `:`", o que truncava valores com dois
espaços internos e engolia o rótulo seguinte quando o modo layout separava
duas colunas por um espaço só; a regra por rótulos conhecidos cobre os dois
casos.)* O `repr` de `DadosPessoais` omite nome, CPF, nascimento, e-mail e
`texto`, e mostra a matrícula mascarada. Cada normalização é uma função
pequena do módulo (`_situacao`, `_data_siape`, `_orgao`), testável isolada.

### `ler_dados_pessoais(pdf: Path) -> DadosPessoais`

Pura: abre com `pypdf`, exige camada de texto via
`integra_gov.ficha_financeira.tem_camada_de_texto` (senão
`PdfIlegivelError`, a mesma de `ficha_financeira`), extrai e monta o
dataclass. Não confere matrícula: quem lê um PDF do disco pode não saber
qual matrícula esperar.

### `DadosPessoaisServidor(driver, pasta_saida, pasta_download=None)`

Mesma assinatura e mesmos defaults de `FichaAnualServidor`
(`pasta_download` = `pasta_saida / "_download_esiape"`). A pasta de download
DEVE ser dedicada: `imprimir_via_popup` apaga os PDFs órfãos dela.

`consultar(matricula) -> DadosPessoais`, sequência:

1. `str(matricula).strip()`; vazia → `ValueError`.
2. `fechar_janelas_extras`, `limpar_overlay`.
3. `navegar_para_transacao(driver, "CDCOINDPES", SEL_MATRICULA)`. Se falhar
   e `relogin_pendente(driver)`: `limpar_flag_relogin` e **uma** repetição
   (a CDCOINDPES é por matrícula; não depende da habilitação que o relogin
   devolve ao padrão). Falha de novo → `TransacaoNaoAbriu`.
4. Matrícula + ENTER, botão Consultar, botão Imprimir (cada botão esperado
   com `esperar_seletor`, `TIMEOUT_TELA = 30`).
5. `imprimir_via_popup(driver, clicar_gerar_pdf, pasta_download)` → PDF
   bruto na pasta de download.
6. `ler_dados_pessoais(bruto)` **ainda na pasta de download**; se
   `dados.matricula != matricula` → `DadosPessoaisIndisponiveis`, e o PDF
   fica lá com o nome bruto. *(Revisão final de 16/09: conferir ANTES de
   renomear, senão o PDF de outra pessoa recebia o nome da matrícula pedida
   e apagava o PDF anterior dela.)*
7. Só então renomeado para `pasta_saida / f"dados_pessoais_{matricula}.pdf"`,
   sobrescrevendo o anterior; `dados.pdf` aponta para o destino.
8. Botão Sair, falha ignorada com `warning` (a transação seguinte começa
   pelo menu de qualquer forma).

A matrícula de entrada é normalizada a dígitos (`000.000-0` → `0000000`)
antes de tudo.

Seletores (fatos da tela, confirmados ao vivo em 11/09):
`w_matr_infor_alfa`, `onClickbtnConsulta`, `onClickbtnImprimir`,
`w_report.onGeneratePrintVersion`, `onClickBtnSair`, todos por
`data-testtoolid`.

## Erros

Todas filhas de `EsiapeError`:

| exceção | quando |
|---|---|
| `TransacaoNaoAbriu` (existente) | a tela não montou, mesmo após a repetição por relogin |
| `DadosPessoaisIndisponiveis(matricula, motivo)` (nova) | Consultar ou Imprimir não apareceram no prazo; o PDF não veio (`imprimir_via_popup` levantou); a matrícula lida do PDF difere da pedida |
| `PdfImpressoIlegivel` (existente, agora aceita `bloco=None`) | o PDF veio sem camada de texto (impressora errada); `consultar` converte o `PdfIlegivelError` de `ler_dados_pessoais` nela; o arquivo fica na pasta de download, com o nome bruto, até a próxima impressão (que limpa a pasta) |

**Pendência declarada no código:** o sinal da CDCOINDPES para matrícula
inexistente ou de outro órgão não é conhecido. Até o gate, ele se manifesta
como Imprimir ausente (timeout) e cai em `DadosPessoaisIndisponiveis`. O
gate testa uma matrícula inexistente e a mensagem real, se houver, entra
como `MSG_NAO_ENCONTRADA` com detecção antes do timeout.

Logs: só os dois últimos dígitos da matrícula (`*****NN`); nunca nome, CPF
ou e-mail. O `texto` do PDF nunca é logado.

## Testes (`tests/test_esiape_dados_pessoais.py`)

Sem navegador real. Texto sintético com os rótulos reais e valores
fictícios (matrícula `0000000`, CPF `000.000.000-00`, e-mail
`fulano@exemplo.gov.br`).

- Parsing: os 9 campos lidos de um texto completo; cada normalização
  (`_situacao`, `_data_siape` válida/inválida, `_orgao`, e-mail minúsculo,
  município Title Case); rótulo ausente → `None`; rótulo colado ao próximo
  (2+ espaços) corta no lugar certo; matrícula com caracteres não numéricos
  vira só dígitos.
- `ler_dados_pessoais`: PDF sintético gerado com `pypdf` (mesma técnica de
  `test_esiape_ficha_anual`) devolve os campos e `pdf` = caminho; PDF sem
  texto → `PdfIlegivelError`.
- `consultar` com driver falso: sequência de seletores clicados na ordem;
  `navegar_para_transacao` falhando com `relogin_pendente` → exatamente uma
  repetição e `limpar_flag_relogin` chamado; falhando sem relogin → sem
  repetição, `TransacaoNaoAbriu`; matrícula divergente no PDF →
  `DadosPessoaisIndisponiveis`; Sair levantando → resultado normal + warning;
  `imprimir_via_popup` levantando → `DadosPessoaisIndisponiveis`; PDF sem
  texto → `PdfImpressoIlegivel` e arquivo mantido; matrícula vazia →
  `ValueError`.
- Export: `DadosPessoaisServidor`, `DadosPessoais`, `ler_dados_pessoais`,
  `DadosPessoaisIndisponiveis` em `integra_gov.esiape.__all__`.

## Verificação ao vivo (gate antes do merge)

Script em `dados_reais/` (gitignored), Chrome com as prefs de impressão de
`docs/uso-basico.md`, SERPRO ID confirmado pelo usuário:

1. Duas matrículas reais em sequência na mesma sessão: 9/9 campos, PDFs com
   o nome esperado, matrícula conferida.
2. Uma matrícula inexistente: registrar o que a tela faz e a exceção que
   saiu; ajustar `MSG_NAO_ENCONTRADA` se houver mensagem.
3. Se um relogin do SERPRO atravessar entre as pessoas, a repetição deve
   absorvê-lo; se não atravessar, o caminho fica coberto só pelo teste
   mockado, e a doc diz isso.

Resultado registrado nesta spec (§ "Verificado ao vivo") e a nota no
CHANGELOG. Depois do gate, `extrair_cadastral.py` passa a importar a lib.

## Documentação (junto com o módulo)

README: linha na tabela do e-SIAPE + exemplo curto. CHANGELOG: "Adicionado".
`docs/uso-basico.md`: seção do módulo com o aviso da pasta de download
dedicada e a lista dos 9 campos.

## Riscos e mitigação

- **Rótulo muda no e-SIAPE** → campo vira `None`, não exceção; o consumidor
  (flow) acusa campo vazio. `texto` permite diagnóstico sem nova impressão.
- **PDF de outra pessoa** (tela anterior ainda carregada) → conferência
  matrícula-do-PDF == pedida, obrigatória em `consultar`.
- **Pasta de download compartilhada** → `imprimir_via_popup` apagaria PDFs
  alheios; doc e default (subpasta dedicada) mitigam.
- **Relogin atravessado** → uma repetição; mais que isso é problema de
  sessão e deve subir.
