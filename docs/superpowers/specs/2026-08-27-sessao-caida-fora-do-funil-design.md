# Design — sessão caída fora do funil: `iniciar_processo` e `barra_icones`

*27/08/2026. Escopo: caminhos de FALHA da lib `integra_gov.sei` + remoção do
invólucro repetido no `integra-flow`.*

*Emenda a `2026-07-18-sessao-expirada-design.md`, que criou o funil. Nada do que
está lá é revogado: esta spec fecha as saídas que sobraram e, com isso, aposenta
a reclassificação que aquela spec delegou ao consumidor.*

## 1. Objetivo

Fazer a lib reclassificar sessão caída **em todos os pontos onde ela é a causa
provável**, para que o `integra-flow` pare de repetir o invólucro
`try/except → levantar_se_sessao_expirada → raise` em cada descritor (hoje, três
vezes idênticas em `catalogo_real.py`).

E, no caminho, **fechar um defeito real de produção** descoberto ao medir o
código para esta spec (§3.2).

**Fora de escopo:** o sinal positivo pós-envio do `enviar_processo` (o outro item
do backlog, fatia própria); o `TODO` gêmeo no `concluir_processo`; instrumentar
os campos de formulário dentro de cada módulo (§9).

## 2. O que já existe — medido, não suposto

O item do backlog dizia "mover `levantar_se_sessao_expirada` para dentro da lib",
o que sugere que nada existisse. **Existe, e cobre a maior parte.** A tabela
abaixo foi levantada lendo o código em 27/08:

| Ponto | Reclassifica hoje? | Onde |
|---|---|---|
| `IframesSei.navegar` (todos os destinos) | **sim** | decorador `_retry_iframe`, `iframes.py:151` |
| `switch_to_iframe_visualizacao` | **sim** | laço de candidatos, `iframes.py:103` |
| `ProcessoSei.acessar` (campo de pesquisa) | **sim** | `processo.py:89` |
| `ProcessoSei._validar_acesso` | **sim** | `processo.py:148` — onde a expiração real aparece |
| `IniciarProcesso.iniciar` | **NÃO** | não usa o funil — lacuna estrutural |
| `barra_icones` — nó não encontrado | **NÃO** | resíduo, depois de o frame abrir |
| `barra_icones` — ícone não encontrado | **NÃO** | idem |

**Consequência:** o trabalho desta fatia é bem menor do que o item sugeria. Uma
lacuna estrutural e dois resíduos.

## 3. As lacunas

### 3.1 Os resíduos do `barra_icones`

`_ir_para_visualizacao` **já está coberto** — delega a `IframesSei.navegar`, que
reclassifica; e como `SessaoExpiradaError` não é `TimeoutException`, ela
atravessa o `except` que a converteria para `SeiNavegacaoError`. **Não mexer
nele.**

Sobram os dois pontos onde o frame abriu mas o conteúdo não é o esperado: o nó
selecionado da árvore e o ícone da barra. São resíduo (para chegar ali, a
navegação de frame já passou), mas é onde uma sessão que cai **entre** o switch
do frame e a busca do elemento se manifesta. Fechá-los cobre os 13 módulos que
consomem o funil de uma só vez.

### 3.2 `iniciar_processo` — a lacuna que é um defeito de produção

`IniciarProcesso` não usa iframes nem `ProcessoSei`: opera no contexto principal.
Nenhum ponto seu reclassifica. Hoje quem faz isso é o invólucro do flow — **e o
faz para o método inteiro**, inclusive depois do efeito.

A fronteira do efeito é o `botao.click()` dentro de `_salvar`
(`iniciar_processo.py:317`). Depois dele o processo **pode existir**.

O que acontece hoje, seguindo o código:

1. a sessão cai logo após o clique em Salvar — o processo **foi criado**;
2. `_capturar_numero` não acha o NUP no título → `IniciarProcessoError`;
3. o invólucro do flow chama `levantar_se_sessao_expirada` → vira
   `SessaoExpiradaError`;
4. `Executor._executar_etapa` a captura em `excecoes_sessao`, **reabre a etapa** e
   põe o item em `PENDENTE` (`executor.py:491`);
5. depois do relogin, a etapa roda de novo → **o processo é criado uma segunda
   vez**.

O comentário no próprio executor afirma: *"A lib garante: requisição redirecionada
ao login = NÃO executada"*. **Para o `iniciar_processo` pós-Salvar, essa garantia
não é verdadeira hoje.** A docstring de `SessaoExpiradaError` chama isso de
"caso-limite teórico"; a leitura do executor mostra que é o caminho normal do
código, não um limite.

Esta spec fecha isso: a lib passa a reclassificar **só até a fronteira do
efeito**, e a garantia que o executor afirma passa a ser verdadeira.

## 4. Decisão de arquitetura

**Nenhuma abstração nova.** Mesmo padrão que `iframes.py` e `processo.py` já
usam: chamar `levantar_se_sessao_expirada(driver, exc)` no ponto de falha,
imediatamente antes de levantar o erro tipado. Sem decorador novo, sem context
manager, sem helper novo.

Foi considerado e **recusado**: (a) envolver cada operação pública dos 13
módulos — move a duplicação do flow para a lib em vez de eliminá-la; (b) exportar
um context manager reutilizável — encurta o invólucro do flow de 4 linhas para 1,
mas quem usa a lib direto continua recebendo erro ambíguo.

## 5. Mudanças, por arquivo

### 5.1 `integra_gov/sei/barra_icones.py` — dois sítios

Em `_selecionar_no_arvore` (nó não encontrado) e em `_clicar_icone` (ícone não
encontrado): `levantar_se_sessao_expirada(driver, exc)` antes do
`raise SeiNavegacaoError`. Mensagens atuais preservadas para o caso de não ser
sessão.

`_ir_para_visualizacao` fica intocado (§3.1).

### 5.2 `integra_gov/sei/iniciar_processo.py` — a fronteira explícita

`_salvar` se parte em duas: **localizar** o botão (pré-efeito) e **acionar**
(efeito). `iniciar()` passa a ter a forma:

```
botao = self._preparar_formulario()   # menu, tipo, campos, nível, localizar Salvar
botao.click()                         # ← FRONTEIRA DO EFEITO
self._confirmar_sem_alerta_de_validacao()
numero = self._capturar_numero()
```

A reclassificação vive **dentro** de `_preparar_formulario`, e só ali:

```
except SessaoExpiradaError:
    raise                                    # já tipada, não re-embrulha
except SeiError as exc:
    levantar_se_sessao_expirada(self.driver, exc)
    raise
```

Capturar `SeiError` (e não só `IniciarProcessoError`) faz o `NivelAcessoError` de
`configurar_nivel_acesso` — que também é pré-efeito — entrar na mesma proteção sem
escrever a regra duas vezes.

**Depois do clique, nada é reclassificado.** Falha em
`_confirmar_sem_alerta_de_validacao` ou `_capturar_numero` continua
`IniciarProcessoError` ambígua → o flow a manda para **quarentena**, onde uma
pessoa confere se o processo existe. É o comportamento correto: na dúvida sobre
um efeito irreversível, não rearmar.

### 5.3 `integra-flow` — `integra_flow/execucao/catalogo_real.py`

Saem os três `try/except Exception → levantar_se_sessao_expirada → raise` e o
import do helper. As docstrings das três fábricas, que hoje explicam *por que o
invólucro existe*, passam a registrar que a lib reclassifica sozinha — e a do
`_fabrica_iniciar_processo` registra a fronteira do efeito, porque é ela que
sustenta o `PENDENTE` do executor.

Seis pontos em `tests/test_catalogo_real.py` fazem `monkeypatch` do helper no
módulo do catálogo; passam a exercitar a lib real ou a mockar no ponto novo.

## 6. Contrato e compatibilidade

`Raises:` ganha `SessaoExpiradaError` em `clicar_icone_barra` e em
`IniciarProcesso.iniciar` — neste, **com a fronteira dita em palavras**: só para
falhas anteriores ao clique em Salvar.

Mudança observável: falhas nesses pontos com página de login presente passam de
`SeiNavegacaoError`/`IniciarProcessoError` para `SessaoExpiradaError`. Quem captura
`SeiError` não sente nada; quem captura os tipos estreitos passa a ver a nova
exceção escapar — é o comportamento desejado, e é o mesmo trade-off que a spec de
julho já documentou.

A guarda de propagação de julho foi **reverificada** em 27/08 para os módulos do
funil: todos os `except` largos são `except WebDriverException` (que não captura
`SessaoExpiradaError`, uma `SeiError`), e o único `except Exception`
(`editar_conteudo.py:249`) re-levanta. **Nenhum módulo a engole.**

## 7. Testes (mockados, TDD)

| # | Teste | Trava o quê |
|---|---|---|
| 1 | nó não encontrado + página de login → `SessaoExpiradaError` | §5.1 |
| 2 | nó não encontrado, **sem** login → `SeiNavegacaoError` (mensagem atual) | não regredir |
| 3 | ícone não encontrado + login → `SessaoExpiradaError` | §5.1 |
| 4 | ícone não encontrado, sem login → `SeiNavegacaoError` | não regredir |
| 5 | falha **antes** de Salvar + login → `SessaoExpiradaError` | §5.2 |
| 6 | `NivelAcessoError` + login → `SessaoExpiradaError` | o `except SeiError` |
| 7 | **`_capturar_numero` falha + login → continua `IniciarProcessoError`** | §3.2 |
| 8 | caminho feliz do `iniciar()` intacto após a refatoração de `_salvar` | não regredir |

O **teste 7 é o mais importante da fatia**. Ele é o que impede alguém de
"simplificar" isto no futuro envolvendo o `iniciar()` inteiro, reabrindo o
processo duplicado. Seu comentário deve dizer isso.

Nos dois repos: suítes completas (747 / 334 + os novos) e `ruff check .`.

## 8. Gate ao vivo

Necessário. A mudança inteira vive em caminho de falha, e caminho de falha que
nunca foi visto de verdade é suposição.

Reprodutível de forma barata: o SEI só derruba sessão por inatividade ou **logout
explícito** (memória `sei-sessoes-concorrentes.md`). Roteiro: logar, abrir um
processo na `MGI-SGP-DECIPEX-CGPAG-NUTEC`, sair do SEI em outra aba, e disparar
uma operação. Esperado: `SessaoExpiradaError`, não `SeiNavegacaoError`.

O caso pós-Salvar (§3.2) é o difícil: exige o logout na janela entre o clique e a
leitura do título. Se não for possível provocá-lo, **registrar no gate que ele não
foi observado ao vivo** — e não dizer que foi.

Script em `dados_reais/` (gitignored); o usuário digita a senha.

## 9. Fora de escopo, deliberado

**Não** instrumentar os campos de formulário dentro de cada módulo. O funil pega o
caso dominante — quando a sessão cai, a página vira a de login e o *frame* é a
primeira coisa a faltar. Instrumentar cada campo seria a duplicação que esta spec
existe para eliminar, agora dentro da lib.

**Não** mexer no `concluir_processo` nem no sinal positivo do `enviar_processo` —
fatia (a), própria.

## 10. Convenções do commit

Doc no MESMO commit (memória `doc-ao-adicionar-modulo.md`): `CHANGELOG.md`
(*Alterado* — mudança de comportamento; *Corrigido* — o duplicado do §3.2), README
onde descreve as exceções, e `docs/uso-basico.md` se citar o invólucro.

O commit da lib e o do flow são **separados** (repos distintos), mas da mesma
fatia; o do flow referencia o `sha` da lib.
