# Dados pessoais do pensionista no e-SIAPE (CDCOPSBENE) — design

**Data:** 2026-09-16
**Módulo alvo:** `integra_gov/esiape/dados_pensionista.py`
**Estratégia:** porte guiado do módulo privado `DadosPessoaisPensionista`
(CDCOPSBENE, validado em produção), com a impressão trocada pela mecânica
já estabilizada da lib. Nenhum dado pessoal ou órgão real embutido.

## Contexto

O módulo `esiape.dados_pessoais` (CDCOINDPES, mergeado em 16/09) cobre
servidor, aposentado e instituidor. **Pensionista não tem equivalente**: o
SIAPE 3270 só oferece a ficha financeira (`siape.ficha_pensionista`), e o
cadastro de pensionista só existe no e-SIAPE, na transação CDCOPSBENE.

As duas telas são de naturezas diferentes, e isso governa o desenho:

| | CDCOINDPES (servidor) | CDCOPSBENE (pensionista) |
|---|---|---|
| tela | relatório impresso | formulário com campos de entrada |
| origem dos campos | camada de texto do PDF | valores no DOM, por `data-testtoolid` |
| tela intermediária | nenhuma | procuração, quando há procurador |
| conferência de identidade | matrícula impressa no PDF | eco do campo de busca (mais fraca, ver §Identidade) |

Ler o formulário pelo DOM é o que o privado faz em produção. Ler pelo PDF
seria apostar que o impresso tem camada de texto e carrega os valores
digitados, o que ninguém mediu. A lib passa a ter duas mecânicas de leitura,
uma por tela, e isso é deliberado.

Consumidores previstos: a fatia B-5 do `integra-flow` e processos de pensão
que hoje dependem de consulta manual.

## Escopo

**Entra:** o módulo, o arquivo compartilhado de máscara, testes mockados,
README + CHANGELOG + uso-basico no mesmo commit, gate ao vivo.

**Fica fora:**
- Dados do **benefício** (instituidor, tipo e início da pensão): o privado
  tem isso em módulo à parte, provavelmente outra transação. Fatia própria.
- Nome do procurador: o resultado diz apenas que **existe** procuração. Ler
  quem é acrescenta dado pessoal de terceiro sem finalidade declarada.
- Leitura pura de um PDF de pensionista já no disco: não se sabe se o
  impresso carrega os campos. O gate mede; se carregar, vira fatia futura.
- Lote, checkpoint e "só faltantes" → orquestrador (B-5 do flow).

## API pública

```python
from pathlib import Path
from integra_gov.esiape import DadosPessoaisPensionista

cad = DadosPessoaisPensionista(driver, pasta_saida=Path("cadastrais/"))
dados = cad.consultar("0000000")          # matrícula fictícia
dados.nome, dados.cep, dados.com_procuracao, dados.pdf
```

### `DadosPensionista` (dataclass)

| campo | origem (`data-testtoolid`) | normalização |
|---|---|---|
| `matricula` | a pedida, normalizada | só dígitos |
| `nome` | `w_tl_no_benef` | `strip` |
| `cpf` | `w_tl_nu_cpf` | `strip` |
| `data_nascimento` | `w_da_nascimento` | ver abaixo |
| `email` | `w_tl_ed_correio_eletronico` | minúsculas |
| `logradouro` | `w_tl_no_logradouro` | `strip` |
| `numero` | `w_nu_end` | `strip` |
| `complemento` | `w_tl_complemento_endereco` | `strip` |
| `bairro` | `w_tl_no_bairro_novo` | `strip` |
| `municipio` | `w_tl_no_municipio` | maiúsculas iniciais |
| `uf` | `w_tl_uf_end` | `strip` |
| `cep` | `w_co_cep` | `strip` |
| `com_procuracao` | tela intermediária | `bool`, default `False` |
| `pdf` | — | caminho do PDF renomeado |

Campo vazio vira `None`, sem levantar: ausência é informação, não falha
(mesma regra do módulo de servidor). O valor de cada campo sai de
`get_attribute("value")` do elemento de entrada.

**Data de nascimento, formato a confirmar no gate.** A leitura aceita
`DDMMMAAAA` (padrão SIAPE, convertido para `dd/mm/aaaa`) **e** `dd/mm/aaaa`
(mantido); qualquer outra forma vira `None`. Depois do gate, a forma que não
ocorrer sai do código, com o registro do que foi medido.

**Privacidade.** `repr(DadosPensionista)` omite nome, CPF, nascimento,
e-mail e o endereço inteiro; mostra município, UF, `com_procuracao` e a
matrícula mascarada. Logs trazem só os dois últimos dígitos da matrícula.

### `DadosPessoaisPensionista(driver, pasta_saida, pasta_download=None)`

Mesma assinatura e mesmos defaults de `DadosPessoaisServidor`
(`pasta_download` = `pasta_saida / "_download_esiape"`, ambas criadas). A
pasta de download DEVE ser dedicada: a impressão apaga todos os PDFs dela.

`consultar(matricula) -> DadosPensionista`, sequência:

1. `matricula` normalizada a dígitos; vazia → `ValueError`.
2. `fechar_janelas_extras`, `fechar_popups_cis`, `limpar_overlay`.
3. `navegar_para_transacao(driver, "CDCOPSBENE", SEL_MATRICULA)`, com **uma**
   repetição quando falha e `relogin_pendente` (limpa a flag antes). Falha de
   novo → `TransacaoNaoAbriu`.
4. Matrícula no campo de busca + ENTER, que envia a consulta sozinho.

   *(Medido no gate ao vivo de 16/09: as duas matrículas falharam com "o
   botão Consultar não apareceu em 30s" depois de a tela já ter aberto — a
   CDCOPSBENE não tem botão Consultar, diferente da tela de servidor, de
   onde o passo veio por engano. O módulo privado, validado em produção,
   declara o seletor `onClickbtnConsulta` no seu dicionário de seletores mas
   nunca o clica; o envio é só o ENTER.)*
5. **Tela de procuração** (§ própria abaixo): se presente, atravessa e marca
   `com_procuracao = True`.
6. Lê os 11 campos do formulário.
7. Conferência de identidade (§ própria abaixo).
8. Se **todos** os 11 campos vierem vazios → `DadosPessoaisIndisponiveis`
   com motivo "a consulta não trouxe dados".
9. `imprimir_via_popup` com um único clique em `onPrintPDF` como
   `clicar_imprimir`; guarda de camada de texto; renomeia para
   `pasta_saida / f"dados_pensionista_{matricula}.pdf"`, sobrescrevendo.

   *(Medição do gate ao vivo de 16/09, terceira rodada: a primeira impressão
   real da sessão excedeu os 60s default de `imprimir_via_popup` — a
   segunda e a terceira, na mesma sessão, não excederam. A causa não foi
   estabelecida; o orçamento de download subiu para 120s
   (`TIMEOUT_DOWNLOAD`), e a falha por timeout passou a listar quantos
   arquivos há na pasta de download e de que extensões, sem nome nenhum,
   para o próximo estouro vir com diagnóstico em vez de só um timeout mudo.)*

   *(Medição do gate ao vivo de 16/09, quarta rodada: as duas matrículas
   reais falharam com a pasta de download VAZIA — não por tempo, o
   orçamento de 120s não mudou nada. O PDF desta transação chega como
   DOWNLOAD disparado a partir de uma janela popup, diferente do módulo de
   servidor, que imprime um relatório HTML via kiosk printing; um
   screenshot da rodada anterior mostra o popup exibindo o placeholder do
   próprio Chrome para `StartDynamicContent.pdf` com um botão "Abrir" —
   isso é UI do Chrome, não DOM da página, e uma janela popup não respeita
   de forma confiável `download.default_directory` do perfil. O módulo
   passa a fixar a pasta de download via `Browser.setDownloadBehavior` do
   CDP, em melhor esforço, imediatamente antes de cada impressão
   (`_forcar_pasta_de_download`, chamada de `_imprimir`).)*

   *(Medição do gate ao vivo de 16/09, quinta rodada: as duas matrículas
   reais falharam de novo, e da mesma forma — popup aberto (2 janelas), pasta
   de download vazia depois de 120s — e fixar a pasta via CDP não mudou
   NADA. A causa não era a pasta: é o cartão "Abrir" do próprio Chrome para
   `StartDynamicContent.pdf`, que é interface do navegador, não DOM da
   página, e espera um clique humano que o Selenium não pode dar. A máquina
   de downloads é a estrada errada para esta transação. Como o popup
   NAVEGA para uma URL que DEVOLVE o PDF, o módulo passa a buscar esse
   arquivo pela própria sessão — `baixar_pdf_do_popup`, em
   `integra_gov.esiape.impressao`, com o mesmo mecanismo que
   `integra_gov.sei.download_documento` já usa para documentos do SEI:
   `fetch` com `credentials: 'include'`, checando que os bytes começam em
   `%PDF` antes de gravar. `imprimir_via_popup` continua intacta para as
   telas de RELATÓRIO, que dependem de verdade da máquina de downloads.)*

   *(Medido no gate ao vivo de 16/09: as duas matrículas reais chegaram até
   aqui com sucesso — leitura dos campos ok — e falharam esperando o botão
   `w_report.onGeneratePrintVersion`, que nunca aparece nesta tela. O clique
   em `onPrintPDF` já abre a janela que carrega o PDF; a prova é que a
   consulta SEGUINTE, ao limpar janelas extras, fechou "1 janela(s) extra(s)
   fechada(s)". Esse botão de "gerar versão para impressão" é das telas de
   RELATÓRIO (CDCOINDPES, FPEMFICHAF); a CDCOPSBENE é formulário e não o
   tem. Consistente com o módulo privado, validado em produção, que também
   clica só `onPrintPDF`.)*
10. Botão Sair, falha ignorada com `warning`.
11. Em falha dentro da transação (passos 4 a 9): `_recuperar_tela` (fechar
    popups, limpar cortina, Sair), best effort, que **nunca** mascara a
    exceção original.

*(Limitação declarada, apontada na review final de 16/09: o código recupera a
tela apenas para `DadosPessoaisIndisponiveis` e `PdfImpressoIlegivel`, não
para qualquer falha. Uma exceção crua do Selenium no meio da transação escapa
sem limpeza, e a consulta seguinte começa numa tela suja. O módulo irmão de
servidor tem exatamente a mesma cláusula estreita; os dois se corrigem juntos
ou nenhum, para não divergirem. Fica para depois do gate.)*

Seletores (do privado, validados em produção): `w_matr_infor_alfa`,
`onPrintPDF`, `onClickBtnSair`, todos por `data-testtoolid`.

**A impressão NÃO é portada do privado.** O privado envia dez tabulações e um
ENTER, depois procura `StartDynamicContent.pdf` em três pastas (temporária,
Downloads e Área de Trabalho). Isso é anterior a `esiape.impressao`, que
estabilizou a sequência e já rendeu quatro defeitos de gate até ficar assim.

## Tela de procuração

Aparece entre a consulta e os dados quando o pensionista tem procurador.
Vive num iframe cujo `id` contém `SUBPAGE`, e traz o texto
`BENEFICIARIO COM PROCURACAO`. É fechada enviando ENTER ao `body` desse
iframe (mecânica do privado).

Detecção e travessia são best effort com limite de tempo curto: a tela é
opcional, então **não encontrá-la é o caso normal**, não erro. Se o texto
aparecer e o ENTER não a dissolver, os campos seguintes não vão preencher e
o passo 8 levanta `DadosPessoaisIndisponiveis`, com o motivo dizendo que a
tela de procuração pode ter ficado presa.

## Identidade: a conferência é mais fraca que no servidor

No módulo de servidor a matrícula é lida do PDF e comparada com a pedida.
A tela do pensionista **não devolve a matrícula junto dos dados**, então essa
comparação não existe aqui. As proteções são:

1. **Estrutural:** cada `consultar` navega para a transação do zero, então o
   formulário chega em branco. Não há reaproveitamento de tela entre pessoas.
2. **Eco do campo de busca:** depois da consulta, o módulo lê o valor de
   `w_matr_infor_alfa`. Se vier preenchido, tem de bater com a pedida
   (senão `DadosPessoaisIndisponiveis`). Se vier vazio, um `warning` registra
   que a conferência não foi possível e a consulta segue.

O gate mede qual dos dois casos é o real. Se o eco existir sempre, a
tolerância do caso vazio sai do código na sequência, e a spec registra a
medição. Enquanto a medição não existe, o comportamento tolerante fica
declarado aqui e na documentação, em vez de prometido como conferência.

### Medição do gate de 16/09: o campo não ecoa, ele SOME

*Nas duas matrículas reais, depois da consulta, `w_matr_infor_alfa` não
estava em nenhum frame visível — não em alguns casos, nos dois. A pergunta
2 do gate está respondida: não há eco a conferir nesta tela, então a
conferência por eco é estruturalmente impossível aqui, não apenas
eventualmente vazia. A única proteção hoje é a estrutural (item 1 acima:
cada `consultar` navega para a transação do zero). Por isso os logs dos
caminhos "impossível" (campo ausente dos frames; campo vazio) passam de
`warning` para `debug` — uma condição que ocorre em toda consulta não pode
soar como alerta em toda consulta. O caminho de eco DIVERGENTE continua
levantando `DadosPessoaisIndisponiveis`, sem mudança: se o campo vier
preenchido com outra matrícula, é sinal forte de erro. Uma conferência real
pode voltar a existir se o PDF impresso carregar a matrícula — o que a
pergunta 4 do gate mede à parte.*

## Erros

`ValueError` é da linguagem; as demais são filhas de `EsiapeError`:

| exceção | quando |
|---|---|
| `ValueError` | matrícula vazia depois de normalizada |
| `TransacaoNaoAbriu` (existente) | a tela não montou, mesmo após a repetição por relogin |
| `DadosPessoaisIndisponiveis` (existente, reaproveitada) | nenhum campo preenchido; eco de matrícula divergente; a impressão não produziu PDF |
| `PdfImpressoIlegivel` (existente) | o impresso saiu sem camada de texto; o arquivo fica na pasta de download, com o nome bruto, até a próxima impressão |

`DadosPessoaisIndisponiveis` é reaproveitada de propósito: o significado é o
mesmo e quem consome trata servidor e pensionista com um `except` só.

## Mudança pontual no código existente

Três helpers vivem hoje dentro de `dados_pessoais.py` e passam a ser usados
pelos dois módulos: `_mascarar` (matrícula), `_mascarar_digitos` (qualquer
número longo) e `_data_siape` (conversão `DDMMMAAAA`). Saem para
`integra_gov/esiape/_campos.py` como `mascarar_matricula`,
`mascarar_digitos` e `data_siape`, junto com a tabela `MESES_SIAPE`, e os
testes que os cobriam vão para `tests/test_esiape_campos.py`.
`dados_pessoais.py` importa de lá.

*(Ajuste feito ao escrever o plano: a spec previa mover só a máscara, mas o
módulo de pensionista também precisa da conversão de data, e duplicar a
tabela de meses mais o regex seria duplicar lógica. O nome `_campos` cobre
as duas famílias; `_mascara` cobriria só uma.)*

Sem mudança de comportamento: os corpos são os mesmos e a suíte existente é
a prova.

## Testes (`tests/test_esiape_dados_pensionista.py`)

Sem navegador real. Driver falso que devolve elementos de entrada por
`data-testtoolid`, com valores fictícios (matrícula `0000000`, CPF
`000.000.000-00`, e-mail `fulano@exemplo.gov.br`).

- Os 12 campos do resultado (11 lidos do formulário, mais a matrícula pedida)
  a partir de um formulário completo; campo vazio vira `None`;
  e-mail em minúsculas; município em maiúsculas iniciais.
- Data: `15AGO1960` → `15/08/1960`; `15/08/1960` mantido; `1960-08-15` e
  lixo → `None`.
- Procuração: tela presente → atravessada, ENTER enviado ao `body` do iframe
  e `com_procuracao is True`; tela ausente → `False` e nenhum ENTER.
- Todos os campos vazios → `DadosPessoaisIndisponiveis`, e **nenhum PDF é
  impresso** (a impressão só acontece depois da checagem).
- Eco divergente → levanta, com as duas matrículas mascaradas na mensagem;
  eco vazio → segue e registra `warning`.
- Relogin atravessado → exatamente uma repetição; persistindo →
  `TransacaoNaoAbriu`.
- Impressão levantando → `DadosPessoaisIndisponiveis`; PDF sem camada de
  texto → `PdfImpressoIlegivel` com o arquivo mantido.
- Recuperação de tela roda nas falhas e nunca mascara a exceção original
  (inclusive quando a própria recuperação levanta).
- `repr` não expõe nome, CPF, e-mail, endereço nem a matrícula inteira.
- Ordem dos cliques e chamadas de limpeza conferidas por contador.
- Exportação dos nomes em `integra_gov.esiape`.

## Verificação ao vivo (gate antes do merge)

Script em `dados_reais/` (gitignored), nos moldes do gate do módulo de
servidor: saída mascarada, verificação por **forma** e não por valor, código
de saída 1 só em falha real. Duas matrículas de pensionista reais e uma
inexistente por último.

Perguntas que o gate responde, e que entram nesta spec como medição:

1. formato da data de nascimento no formulário — **respondida** (quarta
   rodada, 16/09): as duas matrículas reais logaram `data de nascimento na
   forma DDMMMAAAA` (o instrumento passou a viver dentro do módulo,
   `ler_campos`, em DEBUG, desde a wave anterior). O ramo `dd/mm/aaaa` que
   `_data_nascimento` aceitava por precaução nunca ocorreu nas duas
   medições e saiu do código; `forma_da_data` continua classificando-o de
   propósito — é o instrumento que revelaria uma mudança futura da tela.
2. se `w_matr_infor_alfa` ecoa a matrícula depois da consulta —
   **respondida**: não ecoa, o campo SOME de todos os frames visíveis
   depois da consulta, nas duas matrículas reais (ver §Identidade).
3. o que a tela faz com matrícula inexistente (campos vazios? popup? outra
   coisa?) — **respondida**: os campos do formulário simplesmente não
   aparecem; a sonda de popup do CIS (`[id^='IPO_']`) não capturou nenhum
   popup.
4. se o PDF impresso tem camada de texto e carrega os mesmos campos, o que
   decide se vale uma leitura pura numa fatia futura — **respondida** (gate
   de 16/09, terceira rodada): o impresso da matrícula que passou inteira
   tem camada de texto, e `nome`, `cpf`, `logradouro`, `bairro` e `uf`
   apareceram verbatim na extração da camada. Uma fatia futura de leitura
   offline **pode** avançar, com parser próprio sobre as formas cruas do
   PDF. Os campos que a sonda reportou como não encontrados
   (`data_nascimento`, `email`, `municipio`, `cep`, `numero`,
   `complemento`) não são evidência de ausência no PDF: a sonda compara o
   valor já NORMALIZADO pelo módulo (e-mail em minúsculas, município com
   maiúsculas iniciais, data convertida) contra o texto bruto do PDF, e
   `numero`/`complemento` estavam ausentes da própria tela, então não
   tinham como aparecer em lugar nenhum. A conclusão honesta é que o PDF
   carrega os dados e o método de comparação da sonda produziu os `False`,
   não a ausência no PDF.

Se uma das matrículas reais for de pessoa **com procurador**, a tela
intermediária é exercitada ao vivo. Se não houver uma à mão, esse caminho
fica coberto só pelo teste mockado, e a documentação diz isso em vez de
prometer verificação que não houve.

## Documentação (junto com o módulo)

README: linha na tabela do e-SIAPE + exemplo curto. CHANGELOG: "Adicionado",
com a nota de verificação ao vivo preenchida só depois do gate.
`docs/uso-basico.md`: seção do módulo com a pasta de download dedicada, a
lista dos 12 campos, a semântica de `com_procuracao` e as duas limitações
declaradas (conferência de identidade mais fraca; sem releitura offline).

## Riscos e mitigação

- **Seletor de campo muda no e-SIAPE** → o campo vira `None`; se todos
  virarem, a consulta levanta em vez de devolver resultado vazio como se
  fosse bom.
- **Tela de procuração presa** → os campos não preenchem e o passo 8 levanta,
  com o motivo apontando essa hipótese.
- **Dados da pessoa anterior** → navegação nova por consulta, mais o eco do
  campo de busca quando existir.
- **Pasta de download compartilhada** → a impressão apagaria PDFs alheios;
  default dedicado e aviso na documentação.
- **Formato de data desconhecido** → duas formas aceitas, resto `None`, e a
  medição do gate reduz o código depois.
