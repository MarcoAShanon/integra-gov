# Ficha financeira anual do pensionista (SIAPE 3270) — design

**Data:** 2026-08-05
**Módulo alvo:** `integra_gov/siape/ficha_pensionista.py`
**Estratégia:** reescrita guiada — módulo novo no padrão do integra-gov, usando o
extrator privado (validado em lote real: 649 fichas, ~253 s/pensionista) apenas
como referência de comportamento. Nenhum dado pessoal ou default de órgão
embutido.

## Contexto

O SIAPE 3270 tem a transação `>FPEMPSFICF` (ficha financeira anual do
pensionista): uma impressão por ano, muito mais rápida que a rota web mês a
mês. O `integra_gov.siape` já oferece toda a fundação pública — `LancadorHod`,
`ConexaoTerminal3270`, `ControleTerminal3270`, `TrocaHabilitacao` — mas não tem
o módulo de extração. Este design fecha essa lacuna.

## Escopo

**Entra:** a primitiva de extração — uma pensionista, uma faixa de anos, PDFs
por ano no disco, resultado tipado.

**Fica fora (decisões explícitas):**
- Lote, checkpoint, retomada, disjuntor de falhas, janela de horário —
  responsabilidade do orquestrador (integra-flow), como nas demais áreas.
- Mesclagem dos PDFs anuais em arquivo único — quem chama decide.
- Troca de habilitação — o chamador usa `TrocaHabilitacao` antes de extrair.
- Estimativa do primeiro ano com dados (semente estatística do pacote
  privado) — YAGNI; a faixa de anos é sempre explícita.

## API pública

```python
from integra_gov.siape import ControleTerminal3270, FichaAnualPensionista

ficha = FichaAnualPensionista(
    terminal,                             # ControleTerminal3270 conectado
    pasta_saida=Path("fichas/"),
    impressora="Microsoft Print to PDF",  # default; parametrizável
)
resultado = ficha.extrair(
    matricula_pensionista="0000000",
    ano_inicial=2008,
    ano_final=2026,
    matricula_instituidor=None,   # obrigatória APENAS em pensão múltipla
)
```

Retorno — dataclass `ResultadoFichaAnual`:

| campo | tipo | significado |
|---|---|---|
| `pdfs` | `list[Path]` | um PDF por ano com dados, `ficha_<matricula>_<ano>.pdf` |
| `anos_com_dados` | `list[int]` | anos cujo arquivo existe no disco com tamanho > 0 |
| `anos_sem_dados` | `list[int]` | anos que responderam `(0034)` NAO EXISTEM DADOS |
| `duracao_s` | `float` | tempo total da extração |

Sem dados **não é erro** — períodos de pensão variam; é informação do
resultado.

Dependências: `ControleTerminal3270` (público) + `pywinauto` para a janela
nativa de salvar (extra `[siape]`, import protegido como nos módulos irmãos).

## Fluxo do terminal (comportamento validado em produção)

1. **Posicionamento (1× por pensionista):** transação `>FPEMPSFICF` →
   matrícula da pensionista.
   - Pensão múltipla: o SIAPE abre a tela de seleção de instituidores. O
     módulo seleciona a linha do `matricula_instituidor` informado; se o
     parâmetro faltar ou não estiver na lista → `InstituidorObrigatorio`
     (nunca escolher sozinho). Instituidor único segue direto.
2. **Loop por ano** (`ano_inicial..ano_final`):
   - ano → `X` → ENTER (tela "CONFIRMA EMISSÃO? S/N") → `S` + ENTER →
     mensagem de impressão (aguarda ENTER) → 2º ENTER fecha a mensagem;
   - **decisão pelo que existe, não por timeout:** se a janela nativa
     "Salvar Saída de Impressão como" apareceu → há dados: salvar via
     `Edit.set_edit_text` (atômico) na `pasta_saida`; senão, esperar
     `ESPERA_POS_S` (~2,2 s) e ler o terminal atrás do `(0034)` → ano vazio;
   - após `(0034)`: enviar `{F2}` para reposicionar o cursor no campo
     EXERCÍCIO (a leitura de tela desalinha o cursor; sem o F2 os dígitos do
     próximo ano caem em campos errados).
3. **Finalização:** `F12` devolve o terminal ao prompt de matrícula — o
   chamador emenda a próxima pensionista sem redigitar a transação.

Constantes de tempo (espera pós-S, poll da janela de salvar, intervalo entre
anos) são atributos de classe documentados, com os valores otimizados como
default — máquinas lentas folgam sem tocar no código.

**Restrições de ambiente** (herdadas do 3270; documentar no módulo e no
`docs/uso-basico.md`): sessão Windows GUI interativa; impressora de PDF
instalada; clipboard e foco são globais → execução estritamente serial;
locale PT-BR.

## Erros e honestidade

Exceções novas em `exceptions.py`, filhas de `SiapeError`:

- `InstituidorObrigatorio` — tela de seleção apareceu sem
  `matricula_instituidor` (ou a matrícula não está na lista). A mensagem lista
  as matrículas encontradas na tela.
- `FichaIndisponivel` — o fluxo não chegou à confirmação de emissão
  (matrícula inexistente ou sem acesso na habilitação ativa). Distinta de
  "sem dados": aqui nada era extraível.

Reuso: `SessaoSiapePerdida` (terminal corrompido no meio — o chamador decide
reconectar) e `TransacaoError`.

Princípios de mensagem honesta:

1. **Ano vazio ≠ erro ≠ sucesso silencioso:** `(0034)` vira entrada em
   `anos_sem_dados`; exceção no meio do loop **aborta a pensionista inteira**
   (nunca devolve parcial como completo). Os PDFs já salvos ficam no disco e a
   exceção carrega `anos_processados` para diagnóstico.
2. **Confirmação antes de declarar:** um ano só entra em `anos_com_dados`
   depois de o arquivo existir no disco com tamanho > 0 — não quando a janela
   de salvar fecha.

## Testes

Mockados, no padrão da suíte: `TerminalFake` com telas roteirizadas
(confirmação de emissão, mensagem de impressão, `(0034)`, seleção de
instituidor) + janela de salvar fake. Cenários mínimos:

1. ano com dados (arquivo salvo e verificado);
2. ano vazio → `(0034)` → F2 enviado;
3. instituidor único (sem tela de seleção);
4. pensão múltipla com `matricula_instituidor` correto;
5. pensão múltipla sem o parâmetro → `InstituidorObrigatorio` com a lista;
6. sessão perdida no meio → exceção com `anos_processados`;
7. matrícula inexistente → `FichaIndisponivel`;
8. arquivo não apareceu no disco após salvar → ano NÃO entra em
   `anos_com_dados`.

## Verificação ao vivo (gate antes do merge)

1 pensionista real de faixa curta, usuário presente (PIN/OTP; dia útil
7h-22h), script em `dados_reais/` (gitignored). CHANGELOG registra
"Verificado ao vivo" incluindo o que a verificação corrigiu.

## Documentação (junto com o módulo)

- Linha na tabela do README + exemplo mínimo.
- Seção em `docs/uso-basico.md` com o fluxo e as restrições de ambiente.
- CHANGELOG.

## Riscos e mitigação

- **Variação de telas entre órgãos/versões do SIAPE:** os marcadores usados
  ("CONFIRMA EMISSÃO", `(0034)`, título da janela de salvar) são os
  observados em produção; ficam em constantes de classe para ajuste sem
  fork.
- **Timing em máquinas lentas:** constantes de espera parametrizáveis
  (default = valores otimizados validados).
- **pywinauto ausente/plataforma não-Windows:** import protegido +
  `PywinautoIndisponivel`, como nos módulos irmãos.
