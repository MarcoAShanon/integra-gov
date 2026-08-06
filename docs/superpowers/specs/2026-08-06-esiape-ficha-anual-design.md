# Ficha anual e-SIAPE + multi-órgão (ciclo E2) — design

**Data:** 2026-08-06
**Módulos alvo:** `integra_gov/esiape/ficha_anual.py`, `dados_funcionais.py`,
`ficha_multi_orgao.py` (sobre a fundação do ciclo E1)
**Estratégia:** reescrita guiada — comportamento dos módulos privados
validados em produção (lote de 14 extrações multi-órgão sem falha,
03-08/2026). Nenhum dado pessoal ou órgão real embutido.

## Contexto

A ficha financeira anual do servidor/aposentado/instituidor (transação
FPEMFICHAF) só enxerga o **órgão ativo** da habilitação. Quem migrou de
órgão perde os anos anteriores **silenciosamente** — a ficha sai "com cara
de completa". A solução validada: descobrir o órgão anterior via CDCOINDFUN,
trocar a habilitação e extrair a faixa de cada órgão, mesclando tudo — com
as lacunas SEMPRE declaradas.

## Escopo

**Entra:** os 3 módulos abaixo + `pypdf>=3.0` no núcleo (mesclagem).

**Fica fora:**
- Lote/checkpoint/disjuntor → orquestrador (integra-flow).
- Ficha MENSAL do servidor (FPCOFICHAF) e do pensionista web (FPCOPSFICF) —
  ciclos futuros se houver demanda.
- Download via fetch→base64 — nunca funcionou no popup do FPEMFICHAF
  (pendência conhecida do privado); o download do Chrome foi 100% no lote.
- Auditoria de conteúdo do PDF (contagem de meses por ano) — ferramenta de
  QA do projeto privado; o público declara cobertura por FAIXAS extraídas.

## API pública

```python
from integra_gov.esiape import FichaAnualServidor, FichaMultiOrgao

resultado = FichaAnualServidor(driver, pasta_saida=Path("fichas/")).extrair(
    matricula="0000000", ano_inicial=2008, ano_final=2026)

multi = FichaMultiOrgao(driver, orgao_inicial="00000", pasta_saida=Path("fichas/"))
resultado = multi.extrair("0000000", 2008, 2026)
```

### `ficha_anual.py` — `FichaAnualServidor`

`FichaAnualServidor(driver, pasta_saida, pasta_download=None)`:
- `pasta_download`: onde o Chrome baixa (default: subpasta `_download_esiape`
  de `pasta_saida`; deve coincidir com a configuração do driver — documentado;
  o `criar_driver_chrome` aceita pasta de download).
- `extrair(matricula, ano_inicial, ano_final) -> ResultadoFichaEsiape`:
  1. divide a faixa em **blocos de ≤15 anos** (`MAX_ANOS_POR_CONSULTA=15` —
     o e-SIAPE recusa faixas maiores);
  2. por bloco: `navegar_para_transacao("FPEMFICHAF", ...)` → Consulta
     Online → matrícula → período → consulta → **sem dados?** (mensagem
     "NAO HOUVE DADOS PARA CRITERIO SOLICITADO") registra e segue → senão
     Gerar Relatório → **impressão** (ver mecânica abaixo) → PDF do bloco
     **renomeado** (`ficha_<matricula>_<ano_de>_<ano_ate>.pdf`) antes do
     bloco seguinte (sem renomear, o seguinte SOBRESCREVE — bug real do
     piloto);
  3. mescla os blocos em ordem cronológica (pypdf) →
     `ficha_<matricula>_<ano_inicial>_<ano_final>.pdf`.
- `ResultadoFichaEsiape`: `pdf: Path | None` (mesclado; `None` se nenhum
  bloco teve dados), `pdfs_blocos: list[Path]`, `blocos_com_dados` e
  `blocos_sem_dados` (listas de `(ano_de, ano_ate)`), `duracao_s`.
- **Bloco com ERRO aborta a pessoa** (`ExtracaoFichaEsiapeInterrompida` com
  `blocos_processados` e `causa`); sem dados NÃO é erro. A distinção usa a
  mensagem do CIS após a consulta — nunca "sem dados" por timeout.

Mecânica da impressão (sequência ESTABILIZADA em produção — a origem
histórica da degradação de sessão):
1. `fechar_janelas_extras` + `limpar_overlay` antes;
2. clicar Imprimir → esperar popup por `window_handles`;
3. o popup dispara o download do Chrome; esperar o PDF **estável no disco**
   (tamanho constante em 2 leituras consecutivas) na `pasta_download`;
4. fechar o popup **por handle Selenium** (`driver.close()` com retry e
   verificação; `window.close()` JS só como fallback);
5. retornar à janela principal + refresh + reposicionamento;
6. mover/renomear o PDF para `pasta_saida`.
Antes de cada impressão, limpar PDFs órfãos da `pasta_download` (o fallback
de "mais recente" confundiria resto de bloco anterior com o atual).

Seletores (constantes de classe, observados ao vivo):
`ID_CONSULTA_ONLINE="onClickBtnConsultaOnline"`,
`ID_MATRICULA="w_matr_infor_alfa"`, `ID_ANO_INICIO="w_ano_inicio"`,
`SELETOR_ANO_FIM='[data-testtoolid="w_ano_fim"]'`,
`ID_GERAR_RELATORIO="onClickBtnGerarTodosSemestres"`,
`ID_IMPRIMIR="w_report.onGeneratePrintVersion"`,
`SELETOR_SAIR='[data-testtoolid="onClickBtnSair"]'`,
`MSG_SEM_DADOS="NAO HOUVE DADOS PARA CRITERIO SOLICITADO"` (todos os `ID_*`
são `data-testtoolid`; busca via fundação, só frames visíveis).

### `dados_funcionais.py` — `DadosFuncionaisOrgao` (CDCOINDFUN)

`DadosFuncionaisOrgao(driver).consultar(matricula, orgao) -> DadosFuncionais`:
- 3 telas: (1) órgão **explícito** + matrícula → Pesquisar (nunca confiar no
  órgão default do formulário ao encadear trocas); (2) checkboxes ÓRGÃO
  ATUAL/ANTERIOR + ÓRGÃO ORIGEM/REQUIS. + INGRESSO NO ÓRGÃO → Pesquisar;
  (3) resultado lido por TEXTO.
- **Marcador da tela 3 = "Cadastramento no SIAPE"** — "INGRESSO NO ÓRGÃO"
  também é rótulo de checkbox da tela 2 e faz parsear a tela errada
  (armadilha real documentada).
- `DadosFuncionais` (dataclass): `orgao_anterior: str | None`,
  `matricula_anterior: str | None`, `ano_ingresso: int | None`,
  `cadastramento_siape: str | None`. Campos ilegíveis → `None` (nunca
  inventar); consulta que não abre → `TransacaoNaoAbriu`.

### `ficha_multi_orgao.py` — `FichaMultiOrgao`

`FichaMultiOrgao(driver, orgao_inicial, pasta_saida, max_saltos=5)`:
- `extrair(matricula, ano_inicial, ano_final) -> ResultadoMultiOrgao`, laço
  validado em produção:
  1. início de pessoa: `fechar_janelas_extras` + `limpar_overlay`; se
     `relogin_pendente` → re-trocar habilitação para o órgão corrente ANTES
     de qualquer consulta (sem isso, "sem dados" FALSO = lacuna silenciosa);
  2. por órgão (do mais recente ao mais antigo): CDCOINDFUN → faixa deste
     órgão = `max(ano_inicial, ano_ingresso)..pendente_ate` →
     `FichaAnualServidor.extrair` → **o ano da VIRADA pertence aos DOIS
     órgãos** (`pendente_ate = ano_de`, não `ano_de - 1` — JAN-NOV do ano de
     migração ficam no órgão anterior; foi a lacuna invisível do piloto);
  3. parar quando: cobertura alcançou `ano_inicial`; sem órgão anterior
     (lacuna declarada); sem habilitação no anterior
     (`HabilitacaoNaoEncontrada` → lacuna declarada, ENTREGA o que tem);
     ciclo detectado (visitados por `(orgao, matricula)`); `max_saltos`;
  4. retry: `TENTATIVAS_POR_FAIXA=2` por faixa (falha intermitente de popup
     não pode custar a pessoa inteira), com re-habilitação se relogin no
     meio;
  5. fim: mescla cronológica (pypdf) + **retorna a habilitação ao
     `orgao_inicial`** (com retentativas; se não conseguir, sinaliza —
     próxima pessoa do chamador falharia).
- `ResultadoMultiOrgao`: `pdf: Path | None`, `trilha:
  list[tuple[str, str, int, int]]` (órgão, matrícula, ano_de, ano_ate),
  `lacunas: list[str]`, `falhas_tecnicas: list[str]` (subconjunto
  retentável), `voltou_ao_orgao_inicial: bool`, `duracao_s`.
- **Nunca lança por lacuna legítima** — entrega o que cobriu com as lacunas
  declaradas. Só propaga exceção se NADA foi extraível.

### Exceções novas (`exceptions.py`)

- `ExtracaoFichaEsiapeInterrompida(blocos_processados: list[tuple[int, int]],
  causa)` — bloco com erro; parciais ficam no disco.
- `FichaEsiapeIndisponivel` — matrícula não encontrada na habilitação ativa
  (mensagem com o que o CIS mostrou).

## Testes

`DriverFake` da fundação estendido no arquivo de teste novo: janelas
(`window_handles` mutáveis, popup de impressão roteirizado) e download fake
(callback que escreve o arquivo na pasta). PDFs mínimos gerados com pypdf no
próprio teste para a mesclagem real. Cenários mínimos:

1. bloco único com dados (fluxo completo até o PDF renomeado);
2. 2008-2026 → blocos 2008-2022 + 2023-2026, cada um renomeado, mesclagem
   cronológica com pypdf real;
3. bloco sem dados (mensagem do CIS) → registrado, segue, não aborta;
4. bloco com erro → `ExtracaoFichaEsiapeInterrompida` com
   `blocos_processados`; parciais permanecem no disco;
5. popup que resiste ao fechamento → fallback JS → janela órfã não derruba o
   fluxo (fechar_janelas_extras na próxima iteração);
6. CDCOINDFUN: 3 telas felizes; campos ilegíveis → `None`; marcador correto
   (tela 2 com o rótulo-armadilha não é confundida com a 3);
7. multi-órgão 1 salto: faixas corretas com o ano da virada nos DOIS órgãos;
8. multi-órgão sem órgão anterior → lacuna declarada, entrega parcial;
9. multi-órgão sem habilitação no anterior → lacuna declarada;
10. ciclo detectado → para;
11. relogin no meio → re-habilitação antes da faixa (flag consumida);
12. retorno ao órgão inicial ao final (e sinalização quando falha).

## Verificação ao vivo (gate antes do merge)

Emitir a ficha REAL de um reformado **multi-órgão** (matrícula em runtime,
nada em arquivo): `AcessoEsiape` → `FichaMultiOrgao.extrair` na faixa
completa → conferir o PDF mesclado (abre, páginas plausíveis, faixa coberta
na trilha), `lacunas` vazias (ou justificadas), cabeçalho de volta ao órgão
inicial. Script em `dados_reais/` (gitignored).

## Documentação (junto com o módulo)

README (tabela + exemplo dos dois caminhos), `docs/uso-basico.md` (fluxo,
blocos de 15 anos, semântica de lacunas/falhas_tecnicas, requisito da pasta
de download do driver), CHANGELOG.

## Riscos e mitigação

- **Popup de impressão intermitente** ("Browser window not found"): retry por
  faixa + fechamento Selenium-first + janelas extras varridas — o pacote de
  mitigação que zerou as falhas no lote real.
- **pasta_download divergente da configuração do driver:** documentado no
  README/uso-basico; erro honesto quando o PDF não aparece (cita a pasta e a
  hipótese de configuração).
- **Layout do CDCOINDFUN variar:** leitura por texto com marcadores em
  constantes; campos ilegíveis viram `None` e o multi-órgão declara lacuna
  em vez de inventar.
