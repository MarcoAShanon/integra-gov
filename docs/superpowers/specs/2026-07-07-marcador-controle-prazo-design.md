# Design — Módulos `marcador` e `controle_prazo` (SEI)

Data: 2026-07-07
Pacote: `integra-gov` (público, MIT)
Fonte: pacote privado `integra` (porte em sala limpa — ler, não modificar)

## Objetivo

Portar dois módulos do SEI do pacote privado para o público:

1. **Marcador** — trabalhar com os marcadores do SEI em dois contextos: filtrar a
   lista de processos por marcador (tela **Controle de Processos**) e
   incluir/remover marcador de um **processo aberto** (modal "Gerenciar
   Marcador").
2. **Controle de prazo** — definir/excluir o prazo (em dias) de um processo
   aberto (ícone "Controle de Prazo").

Ambos reusam a espinha de navegação que já existe no pacote público
(`iframes`, `barra_icones`) e seguem os princípios do pacote (headless, exceções
tipadas, sem dados/valores de órgão embutidos, testes com Selenium mockado).

## Decisão de arquitetura (aprovada)

Marcador vira **um módulo com duas classes**, separadas por **contexto/pré-condição**
(as operações vivem em duas telas diferentes do SEI). Coeso pelo conceito
("marcador" = um arquivo, uma exceção, uma seção de doc); isolado pela
pré-condição (cada classe tem um estado de entrada claro). Controle de prazo é um
módulo próprio (tela/ícone independente).

Alternativas descartadas: uma única classe com tudo (mistura pré-condições de
duas telas numa interface ambígua); dois módulos separados (quebra o conceito
"marcador" em dois arquivos).

## Módulo `integra_gov/sei/marcador.py`

### `Marcador` (dataclass, frozen)

```python
Marcador(id: int | None, nome: str, quantidade: int | None, cor: str | None)
```

Representa um marcador como **dado** (contexto lista). `id` = id interno usado no
`filtrarMarcador(id)`; `quantidade` = nº de processos; `cor` = nome da cor
(ex.: `"vermelho"`).

### `Marcadores(driver, *, timeout=10)` — contexto Controle de Processos

Pré-condição: driver na tela **Controle de Processos** (a lista). Opera no
`default_content` (a tela de lista não usa iframe de conteúdo).

| Método | Assinatura | Comportamento |
|---|---|---|
| `listar` | `() -> list[Marcador]` | Garante a visão "Ver por marcadores" (clica o link se `tblMarcadores` ausente) e lê a tabela linha a linha via Selenium + regex. |
| `selecionar` | `(marcador: str \| int) -> Marcador` | Filtra a lista pelos processos do marcador via JS `filtrarMarcador(id)`. Se `marcador` for nome, resolve id via `listar()`. `MarcadorError` se não existir. Devolve o `Marcador`. |
| `remover_filtro` | `() -> None` | `filtrarMarcador(null)` — volta à lista completa; espera `tblMarcadores`. |
| `filtro_ativo` | `() -> Marcador \| None` | Lê `divFiltroMarcador` (marcador em filtro agora), resolve no cache/`listar()`; `None` se sem filtro. |

Seletores (literais da fonte `seletor_marcadores.py`/`marcador.py`):
- Tabela de marcadores: `By.ID, "tblMarcadores"`
- Tabela de processos filtrados: `By.ID, "tblProcessosDetalhado"`
- Filtro ativo: `By.ID, "divFiltroMarcador"`
- Link "ver por marcadores": `By.LINK_TEXT, "Ver por marcadores"`
- Quantidade na linha: `<a class="ancoraPadraoAzul">` (texto)
- id no `onclick`: regex `r"filtrarMarcador\((\d+)\)"`
- cor no `src` da `<img>`: regex `r"marcador_(\w+)\.svg"`
- nome: texto da última `<td>` da linha
- JS: `filtrarMarcador({id})` / `filtrarMarcador(null)`

### `MarcadorProcesso(driver, *, timeout=10)` — contexto processo aberto

Pré-condição: processo aberto. Abre o modal "Gerenciar Marcador" via
`clicar_icone_barra`.

| Método | Assinatura | Comportamento |
|---|---|---|
| `incluir` | `(nome: str, mensagem: str = "") -> None` | Abre o modal, `btnAdicionar`, escolhe `nome` no dropdown, preenche a mensagem, salva, confirma pela `<img>` com `title` contendo `nome`. `ValueError` se `len(mensagem) > 250`. `MarcadorError` se o `nome` não estiver no dropdown (a mensagem lista as opções). |
| `remover` | `(nome: str) -> None` | Abre o modal, acha a linha cujo nome (`td[2]`) == `nome`, clica remover e aceita o alerta. `MarcadorError` se o processo não tiver esse marcador. |
| `listar` | `() -> list[str]` | Nomes dos marcadores **deste** processo (lê as linhas do modal). |

Seletores (literais da fonte `troca_marcador.py`):
- Ícone que abre o modal: `clicar_icone_barra(driver, "Gerenciar Marcador")`
- Adicionar: `//*[@id="btnAdicionar"]`
- Dropdown: `.dd-select` / opções `.dd-option-text` (compara `text == nome`)
- Mensagem: `//*[@id="txaTexto"]` (`.clear()`; **limite 250** → `ValueError`)
- Salvar: `//*[@id="sbmSalvar"]`
- Verificação pós-save: `//img[contains(@title, "{nome}")]`
- Remover (por linha da tabela do modal): nome em `td[2]`; link remover em
  `td[6]//a[img[@src='/infra_css/svg/remover.svg']]`; depois `alert.accept()`
- Voltar (opcional): `clicar_icone_barra(driver, "Controle de Processos")`

Nota de performance (da fonte): durante a varredura de remoção, zerar o implicit
wait e restaurar no `finally` (evita 15s por linha sem `td[2]`). Como o pacote
público não usa implicit wait, isso provavelmente é dispensável — confirmar ao
vivo.

### Exceção

`MarcadorError(SeiError)` em `exceptions.py`.

## Módulo `integra_gov/sei/controle_prazo.py`

### `ControlePrazo(driver, *, timeout=10)` — contexto processo aberto

| Método | Assinatura | Comportamento |
|---|---|---|
| `definir` | `(dias: int) -> None` | Define prazo de N dias. Valida **1 ≤ dias ≤ 9999** (`ValueError` fora). Abre "Controle de Prazo", seleciona a opção "dias", preenche `txtDias`, confirma. `ControlePrazoError` se a UI falhar. |
| `excluir` | `() -> None` | Remove o prazo: `btnExcluir` + aceita o alerta. `ControlePrazoError` se falhar. |

**Melhoria sobre a fonte:** a fonte usa `prazo="0"` (string) como "excluir" — um
valor mágico. A versão pública separa em `definir(dias)` e `excluir()`, sem valor
mágico, com `dias: int`.

Escopo: prazo por **dias** (como a fonte). "Data específica" fica anotado como
evolução futura (a fonte não a implementa).

Seletores (literais da fonte `controle_prazos.py`):
- Ícone: `clicar_icone_barra(driver, "Controle de Prazo")`
- Excluir: `//*[@id="btnExcluir"]` → `EC.alert_is_present()` → `alert.accept()`
- Opção dias: `//*[@id="divOptDias"]/div/label`
- Campo dias: `//*[@id="txtDias"]` (`.clear()` + `send_keys(dias)`)
- Confirmar: `//*[@id="sbmDefinirControlePrazo"]`

### Exceção

`ControlePrazoError(SeiError)` em `exceptions.py`.

## Transversais

### Tratamento de erro
Bools silenciosos da fonte → exceções tipadas (`MarcadorError`,
`ControlePrazoError`, filhas de `SeiError`). `ValueError` para entradas
inválidas (dias fora de 1–9999; mensagem > 250).

### Reúso
`barra_icones.clicar_icone_barra` ("Gerenciar Marcador", "Controle de Prazo") e
`iframes.IframesSei`. A lista opera no `default_content`; o processo usa os
frames de árvore/documento. **Risco a confirmar ao vivo:** onde o modal
"Gerenciar Marcador" / a tela "Controle de Prazo" aparecem (mesmo frame de
visualização vs. frame aninhado) — a fonte navegava `"Exibe frame documentos"`.

### O que descartamos da fonte (violam princípios do pacote)
- Conexão via DevTools `debuggerAddress` (`SeletorMarcadoresSEI.conectar`) — o
  pacote recebe o `driver` pronto.
- Menu interativo `input()` (`selecionar_marcador_interativo`) — GUI na lib.
- `imprimir_marcadores` (print) — não é responsabilidade de biblioteca.
- `PrimeiroPlanoNavegador` (traz janela ao 1º plano) — GUI/desktop.
- Dependências `bs4` (usar Selenium+regex) e `tenacity` (retry inline se
  necessário).
- Fluxo combinado `trocar_marcador` (remove+add numa tacada) → separado em
  `incluir`/`remover`.

### Testes (Selenium mockado, padrão dos `test_*` atuais)
Testes de lógica pura (sem WebDriver real), em `tests/test_marcador.py` e
`tests/test_controle_prazo.py`:
- `ControlePrazo`: validação de dias (aceita 1/30/9999; rejeita 0/-1/10000);
  `excluir()` não valida dias.
- `MarcadorProcesso`: `ValueError` para mensagem > 250; resolução do dropdown por
  nome exato.
- `Marcadores`: regex de id (`filtrarMarcador(\d+)`) e cor (`marcador_(\w+).svg`);
  resolução nome→id; `MarcadorError` quando o nome não existe.
- Padrão: funções `test_*`, `from __future__ import annotations`, import do
  submódulo (`from integra_gov.sei.marcador import ...`).

`pytest -q` + `ruff check .` verdes.

### Exports
`integra_gov/sei/__init__.py`: exportar `Marcador`, `Marcadores`,
`MarcadorProcesso`, `MarcadorError`, `ControlePrazo`, `ControlePrazoError`;
adicionar à tabela de módulos do `README` e ao `CHANGELOG`.

### Verificação ao vivo (segurar o commit até confirmar)
Scripts em `dados_reais/` (gitignored):
- `teste_real_controle_prazo.py`: `definir(dias)` → conferir na tela → `excluir()`
  (reversível).
- `teste_real_marcador.py`: `Marcadores.listar/selecionar/remover_filtro` (lista,
  não muta) e `MarcadorProcesso.incluir/remover` num processo de teste
  (reversível — remove o que incluiu).

### Implementação
Porte em paralelo (Workflow) seguido de **revisão adversarial de 3 lentes**
(fidelidade à fonte / princípios do pacote / cobertura de testes) antes da
verificação ao vivo. Segurar o commit até a confirmação ao vivo; depois
`README`/`CHANGELOG` + commit + push.

## Fora de escopo (agora)
- Escrita de marcador via tela de lista (a lista é read-only aqui).
- `marcador_arvore` (presença na árvore) e `gerenciador_marcadores` (histórico) —
  podem virar métodos/módulos futuros.
- Prazo por data específica.
