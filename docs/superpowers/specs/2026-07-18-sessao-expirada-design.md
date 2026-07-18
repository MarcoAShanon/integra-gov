# Design — `SessaoExpiradaError` + detecção de sessão caída (SEI)

Data: 2026-07-18
Pacote: `integra-gov` (público, MIT)
Consumidor-motivador: motor do integra-flow (fase A, plano 4 — classificar
"sessão expirou" como condição recuperável distinta de falha ambígua)

## Objetivo

Quando a sessão do SEI deixa de estar autenticada no meio de um fluxo (expirou
por inatividade, foi derrubada por acesso concorrente, ou nunca houve login), a
página vira a de login do SIP e a próxima operação falha. Hoje essa falha se
disfarça de erro genérico (`TimeoutException` embrulhada em `SeiNavegacaoError`,
`ConcluirProcessoError`, …) — o chamador não consegue distinguir "sessão caiu"
(recuperável: basta logar de novo) de um defeito real de navegação.

Este design adiciona à lib a capacidade de **detectar e tipificar** essa
condição. Política de reação (pausar lote, pedir novo login, relogar) fica em
quem chama — a lib é mecanismo, não política (decisão aprovada).

Escopo: **somente `integra_gov.sei`** (aprovado). O subpacote `siape` fica de
fora — sessão 3270 expira de forma diferente e não tem consumidor imediato.

## Decisão de arquitetura (aprovada)

**Funil central + helper público.** A detecção dispara nos caminhos de falha da
camada comum de navegação (por onde quase toda operação passa), e a função de
checagem é pública para o chamador reclassificar qualquer outra falha que escape
do funil. ~3 arquivos tocados; cobre a imensa maioria dos casos; risco baixo.

Alternativas descartadas: gancho em todos os ~15 módulos (cobertura total, mas
mudança mecânica grande e mais superfície de regressão); só helper público sem a
lib levantar o erro (contradiz "detectar e tipificar na lib").

## Novo módulo `integra_gov/sei/sessao.py`

```python
def sessao_expirada(driver) -> bool
```

`True` se a página atual é a de login do SIP. Implementação:

1. `driver.switch_to.default_content()` (a página de login não tem os iframes
   do SEI; a checagem parte do topo).
2. Presença **simultânea** dos campos `txtUsuario` **e** `pwdSenha` via
   `find_elements` (imediato, sem espera — a checagem roda em caminhos de falha
   e não pode custar timeout). IDs reutilizados de `LoginSei.TXT_USUARIO` /
   `LoginSei.PWD_SENHA` (DRY; um único ponto de verdade com o módulo de login).
3. Qualquer `WebDriverException` na checagem → `False`. Na dúvida, o erro
   original prevalece; o helper **nunca** vira a causa da falha.

Efeito colateral documentado: a checagem deixa o driver posicionado no
`default_content` (irrelevante nos caminhos de falha, onde uma exceção vem a
seguir; quem a chamar avulso deve re-navegar depois).

Por que campos e não URL: a URL de login varia por órgão e aceita override
(`url_login` no `LoginSei`); os IDs do formulário SIP são estáveis entre
instâncias.

Limite documentado: a função detecta "página de login presente" — não distingue
*por que* a sessão não está autenticada (expirou / derrubada / nunca logou).

## Nova exceção em `integra_gov/sei/exceptions.py`

```python
class SessaoExpiradaError(SeiError)
```

Subclasse **direta** de `SeiError` — deliberadamente NÃO de `SeiNavegacaoError`:
expiração é estado de sessão, não defeito de navegação; código existente que
captura `SeiNavegacaoError` para retry não deve engolir uma sessão caída (retry
ali é inútil — a página de login não volta a ser o SEI sozinha).

Docstring documenta:

- o que significa (página de login presente = sessão não autenticada; causas
  possíveis);
- que a requisição que falhou foi **redirecionada ao login — não executada**
  pelo SEI;
- o caso-limite teórico (sessão derrubada por login concorrente imediatamente
  após um POST bem-sucedido) para o integrador decidir a política de retry por
  operação — no integra-flow, isso é a escolha de listar ou não a exceção nas
  `excecoes_pre_efeito` de cada descritor;
- que a política de reação (relogar, pausar, abortar) é do chamador.

## Pontos de detecção (o funil)

| Ponto | Onde | Comportamento novo |
|---|---|---|
| `_retry_iframe` | `iframes.py` (decorator de `IframesSei.navegar`) | Dentro do `except` do loop de retry: se `sessao_expirada(driver)` → `SessaoExpiradaError` **imediatamente** (fail-fast; não queima as 3 tentativas contra uma página de login). |
| `switch_to_iframe_visualizacao` | `iframes.py` (`except` do loop de candidatos) | Na falha de **cada candidato** (não só no raise final): se `sessao_expirada(driver)` → `SessaoExpiradaError` imediatamente — evita queimar o timeout do 2º candidato contra a página de login. Cobre módulos que chamam a função direto, fora do `IframesSei`. |
| `ProcessoSei.acessar` | `processo.py` (campo de pesquisa não encontrado) | Onde a mensagem atual já *suspeita* ("a sessão do SEI está autenticada?"): checar de verdade; expirou → `SessaoExpiradaError`; senão → `SeiNavegacaoError` atual (mensagem preservada). |

**Guarda de propagação:** varrer os módulos por `except` largos
(`WebDriverException`, `Exception`) que engoliriam ou re-embrulhariam
`SessaoExpiradaError` no caminho até o chamador; onde houver, deixá-la passar
(`except SessaoExpiradaError: raise` antes do handler largo, ou tupla explícita).
Os `except TimeoutException` existentes não a capturam (ela não é
`TimeoutException`), então a propagação natural já funciona na maioria dos
módulos.

**Export:** `SessaoExpiradaError` e `sessao_expirada` entram no
`integra_gov/sei/__init__.py` junto dos demais.

## Semântica para o consumidor (integra-flow)

- O motor lista `SessaoExpiradaError` nas `excecoes_pre_efeito` dos descritores
  (decisão por descritor, no plano 5 do integra-flow — não nesta lib) → item
  vira `erro` rearmável, sem quarentena.
- `sessao_expirada()` público permite ao motor **reclassificar** qualquer
  `SeiError` que escape do funil: capturou erro de módulo → checa a sessão →
  se caiu, trata como sessão expirada.

## Compatibilidade e release

Mudança de comportamento observável: falhas no funil com página de login
presente passam de `TimeoutException`/`SeiNavegacaoError` para
`SessaoExpiradaError`. Quem captura `SeiError` (ou `Exception`) não sente nada;
quem captura os tipos estreitos passa a ver a nova exceção escapar — é o
comportamento desejado e será documentado.

Convenções do projeto no MESMO commit: entrada no `CHANGELOG.md` (seção
"Não publicado": *Adicionado* para módulo/exceção, *Alterado* para a mudança de
comportamento no funil), README (tabela + exemplo) e `docs/uso-basico.md`.

## Testes

**Offline** (padrão atual: Selenium mockado):

- `sessao_expirada`: `True` com os dois campos; `False` com só um, nenhum, ou
  `WebDriverException` na checagem.
- Fail-fast: driver "sessão caída" em `IframesSei.navegar` → `SessaoExpiradaError`
  na primeira tentativa (sem as 3 do retry).
- `switch_to_iframe_visualizacao` com sessão caída → `SessaoExpiradaError`.
- `ProcessoSei.acessar` com sessão caída → `SessaoExpiradaError`.
- Regressão: com sessão viva, os erros originais continuam
  (`TimeoutException`/`SeiNavegacaoError`/erros de módulo), inclusive o retry
  de 3 tentativas do `_retry_iframe`.

**Ao vivo** (convenção da lib — script em `dados_reais/`):

- logar → `driver.delete_all_cookies()` (simula a expiração fielmente: sem o
  cookie de sessão, o SIP redireciona ao login) → tentar operação (ex.: acessar
  processo) → esperar `SessaoExpiradaError`.
- caminho feliz de controle: logar → operar normalmente → sem falso positivo.
