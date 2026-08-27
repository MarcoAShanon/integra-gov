# Sessão caída fora do funil — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a lib `integra_gov.sei` reclassificar sessão caída nos dois pontos que faltam (`barra_icones` e `iniciar_processo`), limitando a reclassificação do `iniciar_processo` à fronteira do efeito, e remover os três invólucros repetidos do `integra-flow`.

**Architecture:** Nenhuma abstração nova. Chama-se `levantar_se_sessao_expirada(driver, exc)` no ponto de falha, imediatamente antes de levantar o erro tipado — o mesmo padrão que `iframes.py` e `processo.py` já usam. No `iniciar_processo`, a fase pré-efeito é extraída para um método próprio que termina em *localizar* o botão Salvar; o `click()` e tudo depois dele ficam fora da proteção.

**Tech Stack:** Python 3.13, Selenium, pytest, ruff. Dois repositórios irmãos; o `integra-flow` instala a lib em modo editable.

**Spec:** `docs/superpowers/specs/2026-08-27-sessao-caida-fora-do-funil-design.md`

## Global Constraints

- Venvs por repo, caminho absoluto sempre:
  - lib: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe`
  - flow: `C:\Users\Thelemarco\PycharmProjects\integra-flow\.venv\Scripts\python.exe`
- Baseline verde antes de começar: **747** testes na lib, **334** no flow, `ruff check .` limpo nos dois.
- `SessaoExpiradaError` é irmã de `SeiNavegacaoError`, **não** filha. `pytest.raises(SeiNavegacaoError)` não a captura — é isso que separa os testes em pares.
- Mensagens de erro existentes são **preservadas** para o caso de a sessão estar viva. Nenhuma mudança de texto.
- Docstrings em português; `Raises:` atualizado junto com o comportamento, no mesmo commit.
- PowerShell quebra com aspas em mensagem de commit: usar `git commit -F <arquivo>`.
- **Contraprova por mutação só DEPOIS do commit** — `git checkout -- <arquivo>` em arquivo não commitado apaga, não restaura.

---

## Armadilha que atinge duas tarefas — leia antes da Task 2

Os drivers falsos dos testes são `MagicMock()`. Um `MagicMock` devolve um objeto
**verdadeiro** para qualquer chamada não configurada:

```
>>> MagicMock().find_elements("id", "x")
<MagicMock ...>          # bool() == True
```

`sessao_expirada(driver)` decide pela presença de `txtUsuario` **e** `pwdSenha`
em `find_elements`. Num driver falso não configurado, os dois "existem" — então
**todo** teste de falha passaria a ver `SessaoExpiradaError`.

Por isso cada driver falso tocado por este plano recebe um `find_elements`
explícito, com sessão **viva** por padrão. Isso está nos passos, não é opcional.

---

### Task 1: `barra_icones` — os dois resíduos

**Files:**
- Modify: `integra_gov/sei/barra_icones.py`
- Create: `tests/test_barra_icones.py`

**Interfaces:**
- Consumes: `levantar_se_sessao_expirada(driver, causa)` de `integra_gov/sei/sessao.py` (já existe e é público).
- Produces: `clicar_icone_barra(...)` passa a levantar `SessaoExpiradaError` quando o nó ou o ícone falta **e** a página atual é a de login. Assinatura inalterada.

- [ ] **Step 1: Escrever o arquivo de teste, que hoje falha**

Não existe `tests/test_barra_icones.py` — os quatro módulos que consomem o funil
neutralizam `clicar_icone_barra` nos testes deles. Este arquivo é novo e exercita
a função de verdade.

Criar `tests/test_barra_icones.py`:

```python
"""Testes de ``integra_gov.sei.barra_icones`` — sem navegador real.

``IframesSei`` é neutralizado (a navegação de frame tem testes próprios em
``test_iframes``) e ``WebDriverWait``/``EC`` viram fakes: ``until(cond)`` chama
``cond(driver)`` e as condições resolvem via ``driver.find_element``. O que
interessa aqui é a TIPIFICAÇÃO da falha: nó ou ícone ausente com a página de
login na tela é sessão caída, não erro de navegação.
"""

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from integra_gov.sei import barra_icones as bi
from integra_gov.sei.barra_icones import clicar_icone_barra
from integra_gov.sei.exceptions import SeiNavegacaoError, SessaoExpiradaError

IDS_LOGIN = ("txtUsuario", "pwdSenha")
XPATH_ICONE = '//img[@title="Enviar Processo"]'


class _FakeWait:
    def __init__(self, driver, timeout):
        self.driver = driver

    def until(self, cond):
        try:
            res = cond(self.driver)
        except NoSuchElementException:
            res = False
        if res:
            return res
        raise TimeoutException("condição não satisfeita")


def _driver(*, ausentes=(), na_pagina_de_login=False):
    """Driver fake.

    ``ausentes`` = seletores cuja busca levanta ``NoSuchElement``;
    ``na_pagina_de_login`` faz ``find_elements`` devolver os campos do SIP.

    O ``find_elements`` explícito é OBRIGATÓRIO: sem ele o MagicMock devolveria
    um objeto verdadeiro e ``sessao_expirada()`` leria QUALQUER driver como
    página de login.
    """
    driver = MagicMock()
    els: dict[str, MagicMock] = {}

    def _find(by, value):
        if value in ausentes:
            raise NoSuchElementException(value)
        if value not in els:
            els[value] = MagicMock(name=value)
        return els[value]

    driver.find_element.side_effect = _find
    driver.find_elements.side_effect = lambda by, value: (
        ["el"] if na_pagina_de_login and value in IDS_LOGIN else []
    )
    driver.els = els
    return driver


@pytest.fixture
def selenium(monkeypatch):
    monkeypatch.setattr(bi, "WebDriverWait", _FakeWait)
    monkeypatch.setattr(bi, "IframesSei", MagicMock())
    monkeypatch.setattr(bi.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        bi.EC,
        "element_to_be_clickable",
        lambda locator: (lambda d: d.find_element(*locator)),
    )
    # O frame aninhado é fallback defensivo; aqui nunca está disponível.
    monkeypatch.setattr(
        bi.EC,
        "frame_to_be_available_and_switch_to_it",
        lambda locator: (lambda d: False),
    )
    return monkeypatch


def test_caminho_feliz_clica_o_icone(selenium):
    driver = _driver()
    clicar_icone_barra(driver, "Enviar Processo")
    assert driver.els[XPATH_ICONE].click.called


def test_no_ausente_com_sessao_viva_e_erro_de_navegacao(selenium):
    driver = _driver(ausentes={bi.CSS_NO_SELECIONADO})
    with pytest.raises(SeiNavegacaoError, match="nenhum nó selecionado"):
        clicar_icone_barra(driver, "Enviar Processo")


def test_no_ausente_na_pagina_de_login_e_sessao_expirada(selenium):
    driver = _driver(ausentes={bi.CSS_NO_SELECIONADO}, na_pagina_de_login=True)
    with pytest.raises(SessaoExpiradaError):
        clicar_icone_barra(driver, "Enviar Processo")


def test_icone_ausente_com_sessao_viva_e_erro_de_navegacao(selenium):
    driver = _driver(ausentes={XPATH_ICONE})
    with pytest.raises(SeiNavegacaoError, match="não encontrado ou não clicável"):
        clicar_icone_barra(driver, "Enviar Processo")


def test_icone_ausente_na_pagina_de_login_e_sessao_expirada(selenium):
    driver = _driver(ausentes={XPATH_ICONE}, na_pagina_de_login=True)
    with pytest.raises(SessaoExpiradaError):
        clicar_icone_barra(driver, "Enviar Processo")


def test_a_causa_original_e_encadeada(selenium):
    driver = _driver(ausentes={XPATH_ICONE}, na_pagina_de_login=True)
    with pytest.raises(SessaoExpiradaError) as excinfo:
        clicar_icone_barra(driver, "Enviar Processo")
    assert isinstance(excinfo.value.__cause__, TimeoutException)
```

- [ ] **Step 2: Rodar e confirmar que os dois testes de login falham**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_barra_icones.py -v
```

Esperado: `test_caminho_feliz_clica_o_icone` e os dois "sessao_viva" **passam**;
`test_no_ausente_na_pagina_de_login_e_sessao_expirada`,
`test_icone_ausente_na_pagina_de_login_e_sessao_expirada` e
`test_a_causa_original_e_encadeada` **falham** com
`SeiNavegacaoError` no lugar de `SessaoExpiradaError`.

- [ ] **Step 3: Implementar — import**

Em `integra_gov/sei/barra_icones.py`, junto dos imports relativos existentes
(`from .exceptions import SeiNavegacaoError` / `from .iframes import IframesSei`),
acrescentar:

```python
from .sessao import levantar_se_sessao_expirada
```

(Não há ciclo: `sessao` importa `login`, e `iframes` — que este módulo já
importa — já importa `sessao`.)

- [ ] **Step 4: Implementar — sítio 1, o nó da árvore**

Em `_selecionar_no_arvore`, no `except` da espera pelo nó:

```python
    try:
        no = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, CSS_NO_SELECIONADO))
        )
    except TimeoutException as exc:
        levantar_se_sessao_expirada(driver, exc)
        raise SeiNavegacaoError(
            "nenhum nó selecionado na árvore — abra/selecione um processo antes"
        ) from exc
```

**Não tocar em `_ir_para_visualizacao`** — ele delega a `IframesSei.navegar`, que
já reclassifica (spec §3.1).

- [ ] **Step 5: Implementar — sítio 2, o ícone**

Em `_clicar_icone`, no `except` final:

```python
    except TimeoutException as exc:
        levantar_se_sessao_expirada(driver, exc)
        raise SeiNavegacaoError(
            f"ícone {titulo!r} não encontrado ou não clicável na barra"
        ) from exc
```

- [ ] **Step 6: Implementar — o contrato na docstring**

Na docstring de `clicar_icone_barra`, substituir a seção `Raises:` por:

```python
    Raises:
        SessaoExpiradaError: se a árvore/o ícone faltar E a página atual for a
            de login — a sessão caiu (a requisição foi redirecionada, ou seja,
            NÃO foi executada pelo SEI).
        SeiNavegacaoError: se a árvore, o nó ou o ícone não forem encontrados
            com a sessão viva.
```

- [ ] **Step 7: Rodar o arquivo novo e a suíte inteira**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_barra_icones.py -v
```

Esperado: 6 passed.

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest -q
```

Esperado: **753 passed** (747 + 6). Nenhum teste existente muda de resultado —
os quatro módulos que consomem o funil neutralizam `clicar_icone_barra`.

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m ruff check .
```

Esperado: `All checks passed!`

- [ ] **Step 8: Commit**

Mensagem em arquivo (PowerShell quebra com aspas):

```bash
git add integra_gov/sei/barra_icones.py tests/test_barra_icones.py
git commit -F docs/superpowers/plans/.msg-task1.txt
```

Conteúdo de `.msg-task1.txt` (apagar o arquivo depois do commit):

```
fix(sei): barra_icones tipifica sessao caida no no e no icone

Os dois pontos onde o frame ja abriu mas o conteudo nao e o esperado
levantavam SeiNavegacaoError mesmo quando a pagina era a de login. Agora
reclassificam, cobrindo de uma vez os 13 modulos que consomem o funil.

_ir_para_visualizacao fica intocado: delega ao IframesSei.navegar, que ja
reclassifica.

Primeiro teste direto do barra_icones (os consumidores o neutralizam).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

### Task 2: `iniciar_processo` — a fronteira do efeito

**Files:**
- Modify: `integra_gov/sei/iniciar_processo.py`
- Modify: `tests/test_iniciar_processo.py`

**Interfaces:**
- Consumes: `levantar_se_sessao_expirada(driver, causa)`; `SeiError` e `SessaoExpiradaError` de `integra_gov/sei/exceptions.py`.
- Produces: `IniciarProcesso.iniciar()` levanta `SessaoExpiradaError` **apenas** para falhas anteriores ao clique em Salvar. Novos métodos privados `_preparar_formulario()` (devolve o WebElement do botão Salvar) e `_localizar_botao_salvar()`; o método `_salvar()` deixa de existir. `ID_SALVAR` e o retorno `str` (NUP) permanecem.

- [ ] **Step 1: Consertar o driver falso e escrever os três testes novos**

Em `tests/test_iniciar_processo.py`, substituir `_make_driver` por:

```python
IDS_LOGIN = ("txtUsuario", "pwdSenha")


def _make_driver(missing=(), *, na_pagina_de_login=False):
    """Driver fake: ``find_element(by, value)`` devolve um mock por ``value``
    (memorizado em ``driver.els``); ``value`` em ``missing`` levanta NoSuchElement.

    ``find_elements`` é explícito e devolve ``[]`` por padrão — sessão VIVA. Sem
    essa linha o MagicMock devolveria um objeto verdadeiro e ``sessao_expirada()``
    leria todo driver como página de login, virando os testes de falha do avesso.
    """
    driver = MagicMock()
    driver.title = "SEI - 19975.014466/2026-41"  # NUP do processo criado
    els: dict[str, MagicMock] = {}

    def _find(by, value):
        if value in missing:
            raise NoSuchElementException(value)
        if value not in els:
            els[value] = MagicMock(name=value)
        return els[value]

    driver.find_element.side_effect = _find
    driver.find_elements.side_effect = lambda by, value: (
        ["el"] if na_pagina_de_login and value in IDS_LOGIN else []
    )
    driver.els = els
    return driver
```

Acrescentar `SessaoExpiradaError` ao import de exceções, que passa a ser:

```python
from integra_gov.sei.exceptions import (
    IniciarProcessoError,
    NivelAcessoError,
    SessaoExpiradaError,
)
```

E acrescentar ao fim do arquivo:

```python
# ----- fronteira do efeito (spec 2026-08-27, §3.2) -----


def test_salvar_ausente_na_pagina_de_login_e_sessao_expirada(selenium):
    """Falha ANTES do clique: nada tocou o SEI, reclassificar é seguro."""
    driver = _make_driver(
        missing={IniciarProcesso.ID_SALVAR}, na_pagina_de_login=True
    )
    with pytest.raises(SessaoExpiradaError):
        IniciarProcesso(driver, "Tipo X").iniciar()


def test_nivel_acesso_falhando_na_pagina_de_login_e_sessao_expirada(selenium):
    """O `except SeiError` cobre o NivelAcessoError, que também é pré-efeito."""
    driver = _make_driver(na_pagina_de_login=True)
    mod.configurar_nivel_acesso.side_effect = NivelAcessoError("falhou")
    with pytest.raises(SessaoExpiradaError):
        IniciarProcesso(driver, "Tipo X").iniciar()


def test_falha_apos_salvar_na_pagina_de_login_continua_ambigua(selenium):
    """NÃO SIMPLIFIQUE ISTO envolvendo o iniciar() inteiro.

    Depois do clique em Salvar o processo PODE existir. Se esta falha virasse
    SessaoExpiradaError, o Executor do integra-flow reabriria a etapa
    (excecoes_sessao → PENDENTE) e, após o relogin, o processo seria criado uma
    SEGUNDA vez. Ambígua é o comportamento correto: vai para quarentena, onde
    uma pessoa confere. Spec 2026-08-27 §3.2.
    """
    driver = _make_driver(na_pagina_de_login=True)
    driver.title = "SEI"  # sem NUP → _capturar_numero falha
    with pytest.raises(IniciarProcessoError, match="criação não confirmada"):
        IniciarProcesso(driver, "Tipo X").iniciar()
```

- [ ] **Step 2: Rodar e confirmar que os três novos falham**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_iniciar_processo.py -v
```

Esperado: os testes existentes **continuam passando** (é o que prova que o
conserto do `find_elements` funcionou); os dois primeiros novos falham com
`IniciarProcessoError`/`NivelAcessoError` em vez de `SessaoExpiradaError`. O
terceiro (`..._continua_ambigua`) **já passa** — é um teste de regressão que
trava o comportamento atual para que o passo seguinte não o quebre.

- [ ] **Step 3: Implementar — imports**

Em `integra_gov/sei/iniciar_processo.py`, trocar

```python
from .exceptions import IniciarProcessoError
```

por

```python
from .exceptions import IniciarProcessoError, SeiError, SessaoExpiradaError
from .sessao import levantar_se_sessao_expirada
```

(mantendo `from .nivel_acesso import configurar_nivel_acesso, validar_nivel_acesso`
na ordem alfabética que o ruff exige: `.exceptions`, `.nivel_acesso`, `.sessao`.)

- [ ] **Step 4: Implementar — partir `iniciar()` na fronteira**

Substituir o corpo de `iniciar()` (tudo depois da docstring) por:

```python
        botao_salvar = self._preparar_formulario()
        botao_salvar.click()
        self._confirmar_sem_alerta_de_validacao()
        _log.info("Processo salvo")
        numero = self._capturar_numero()
        _log.info("Processo iniciado: %s (tipo %r)", numero, self.tipo)
        return numero
```

E acrescentar à docstring de `iniciar()`, na seção `Raises:`, antes da linha de
`IniciarProcessoError`:

```python
            SessaoExpiradaError: se a sessão cair em qualquer passo ANTERIOR ao
                clique em "Salvar" — aí a requisição foi redirecionada ao login
                e o processo NÃO foi criado. Depois do clique a falha continua
                ``IniciarProcessoError``, deliberadamente ambígua: o processo
                pode existir, e reabrir a etapa o criaria duas vezes.
```

- [ ] **Step 5: Implementar — `_preparar_formulario` e `_localizar_botao_salvar`**

Remover o método `_salvar` e pôr, no lugar dele:

> `grep -rn "\._salvar(" integra_gov/` devolve **três** resultados. Só o de
> `iniciar_processo.py` é este; `editar_conteudo.py` e
> `inserir_documento_externo.py` têm métodos privados homônimos, de classes
> diferentes. **Não tocar nesses dois.** O `_salvar` daqui é chamado apenas por
> `iniciar()`.

```python
    def _preparar_formulario(self):
        """Executa tudo o que ANTECEDE o efeito e devolve o botão "Salvar".

        A fronteira do efeito é o clique em Salvar, feito pelo chamador. Até
        aqui nada foi persistido no SEI, então uma sessão caída significa
        "requisição redirecionada ao login = não executada" e pode ser
        reclassificada com segurança. Depois do clique, não pode (spec
        2026-08-27, §3.2).

        Captura ``SeiError`` (e não só ``IniciarProcessoError``) para que o
        ``NivelAcessoError`` de ``configurar_nivel_acesso`` — também pré-efeito
        — entre na mesma proteção sem repetir a regra.
        """
        try:
            self._clicar_menu_iniciar()
            self._selecionar_tipo()
            if self.especificacao:
                self._preencher_especificacao()
            if self.assunto:
                self._configurar_assunto()
            if self.interessado:
                self._adicionar_interessado()
            if self.observacao:
                self._adicionar_observacao()
            configurar_nivel_acesso(
                self.driver,
                self.nivel_acesso,
                hipotese_legal=self.hipotese_legal,
                timeout=self.timeout,
            )
            return self._localizar_botao_salvar()
        except SessaoExpiradaError:
            raise  # já tipada — não re-embrulhar
        except SeiError as exc:
            levantar_se_sessao_expirada(self.driver, exc)
            raise

    def _localizar_botao_salvar(self):
        """Localiza o botão "Salvar" — ainda PRÉ-efeito (não clica)."""
        try:
            return WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.ID, self.ID_SALVAR))
            )
        except TimeoutException as exc:
            raise IniciarProcessoError("botão Salvar não encontrado") from exc
```

- [ ] **Step 6: Rodar os testes do módulo**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_iniciar_processo.py -v
```

Esperado: todos passam, incluindo os três novos. Conferir em especial que
`test_salvar_ausente_levanta_erro` (o antigo, com sessão viva) continua
esperando `IniciarProcessoError` — a mensagem "botão Salvar não encontrado" não
mudou de lugar.

- [ ] **Step 7: Suíte inteira + ruff**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest -q
```

Esperado: **756 passed** (753 + 3).

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m ruff check .
```

Esperado: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add integra_gov/sei/iniciar_processo.py tests/test_iniciar_processo.py
git commit -F docs/superpowers/plans/.msg-task2.txt
```

Conteúdo de `.msg-task2.txt`:

```
fix(sei): iniciar_processo reclassifica sessao caida ate a fronteira do efeito

O iniciar() nao passa pelo funil de iframes, entao a expiracao chegava como
IniciarProcessoError ambigua e quem reclassificava era o integra-flow — para
o metodo INTEIRO, inclusive depois do clique em Salvar.

Isso e um defeito: com o processo ja criado, o Executor lia SessaoExpiradaError,
reabria a etapa e, apos o relogin, criava o processo uma segunda vez.

Agora a fase pre-efeito e explicita (_preparar_formulario, que termina em
localizar o botao) e so ela reclassifica. Depois do clique a falha continua
ambigua e vai para quarentena, onde uma pessoa confere.

Os drivers falsos do teste ganharam find_elements explicito: MagicMock nao
configurado devolve objeto verdadeiro e faria sessao_expirada() ler qualquer
driver como pagina de login.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

### Task 3: documentação da lib

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `README.md:389-410`
- Modify: `docs/uso-basico.md:614-646`
- Modify: `integra_gov/sei/sessao.py` (docstring do módulo)

**Interfaces:**
- Consumes: o comportamento entregue nas Tasks 1 e 2.
- Produces: nada de código. Nenhum teste novo; `tests/test_site.py` e os demais não olham estes arquivos.

- [ ] **Step 1: `CHANGELOG.md` — entrada em "Não publicado"**

Inserir como **primeiro item** da seção `### Alterado` já existente (antes do
item do `ficha_anual`):

```markdown
- **A lib passou a tipificar sessão caída em dois pontos que faltavam.**
  `clicar_icone_barra` (nó da árvore e ícone da barra) e `IniciarProcesso`
  agora levantam **`SessaoExpiradaError`** quando a falha coincide com a página
  de login, em vez de `SeiNavegacaoError`/`IniciarProcessoError` genéricos. O
  primeiro cobre de uma vez os 13 módulos que consomem a barra de ícones.

  É **mudança de comportamento**: quem captura os tipos estreitos passa a ver a
  nova exceção escapar (ela é irmã de `SeiNavegacaoError`, não filha). Quem
  captura `SeiError` não sente diferença.

  Com isso, orquestradores não precisam mais reclassificar por fora — o
  `integra-flow` removeu os três invólucros que repetiam essa lógica.
```

E criar uma seção `### Corrigido` (se ainda não houver) logo após `### Alterado`:

```markdown
### Corrigido
- **Risco de processo criado duas vezes quando a sessão caía durante a criação.**
  A reclassificação de sessão no `IniciarProcesso` agora vale **somente até a
  fronteira do efeito** — o clique em "Salvar". Uma falha posterior (o NUP não
  aparece no título) permanece `IniciarProcessoError` **deliberadamente
  ambígua**, porque o processo pode ter sido criado.

  Antes, o orquestrador reclassificava o método inteiro; ao ler "sessão caiu =
  requisição não executada", ele reabria a etapa e, depois do relogin, criava o
  processo de novo. Agora essa falha vai para quarentena, para conferência
  humana.
```

- [ ] **Step 2: `README.md` — a seção "Sessão expirada no meio do fluxo"**

Substituir o parágrafo de abertura (hoje: *"Quando a sessão do SEI cai (expirou
por inatividade ou foi derrubada por outro acesso), …"*) por:

```markdown
Quando a sessão do SEI cai (por inatividade, ou porque alguém saiu do sistema),
a página vira a de login e a operação seguinte falha com `SessaoExpiradaError` —
em vez de um erro genérico de navegação. A lib só detecta e tipifica;
relogar/pausar é decisão sua:
```

> **Por que a troca:** o SEI do colaboragov/MGI **não** derruba sessão em
> múltiplos logins — isso foi verificado, e está na memória
> `sei-sessoes-concorrentes.md`. A frase antiga afirmava o contrário.

E, ao final da seção, substituir o parágrafo sobre os helpers por:

```markdown
A detecção acontece nos pontos centrais: navegação de iframes, acesso a processo,
a barra de ícones do documento e a criação de processo. No `IniciarProcesso` ela
vale **até o clique em "Salvar"**; uma falha posterior continua
`IniciarProcessoError` de propósito, porque o processo pode já existir e repetir
a etapa o criaria duas vezes.

Para reclassificar uma falha em código próprio, os helpers públicos continuam
disponíveis: `sessao_expirada(driver)` responde se a página atual é a de login, e
`levantar_se_sessao_expirada(driver, causa)` levanta o erro tipado se for.
```

- [ ] **Step 3: `docs/uso-basico.md` — seção 6**

Substituir a frase de abertura (hoje: *"O SEI derruba a sessão por inatividade (e
também quando o mesmo usuário loga em outro lugar)."*) por:

```markdown
O SEI derruba a sessão por inatividade, ou quando alguém sai do sistema
explicitamente — **não** por login simultâneo em outro lugar. Quando isso
acontece no meio de uma automação, a página atual vira a de login.
```

E substituir o parágrafo "Pontos que detectam: …" por:

```markdown
Pontos que detectam: a navegação de iframes (`IframesSei` /
`switch_to_iframe_visualizacao`), o acesso a processo (`ProcessoSei.acessar` e a
confirmação do acesso), a barra de ícones (`clicar_icone_barra`) e a criação de
processo (`IniciarProcesso`).

**Uma exceção deliberada:** no `IniciarProcesso` a detecção vale só **até o
clique em "Salvar"**. Depois dele o processo pode existir, e dizer "a requisição
não foi executada" faria um orquestrador repetir a etapa e criar o processo duas
vezes — então a falha continua `IniciarProcessoError`, para conferência humana.
```

- [ ] **Step 4: `integra_gov/sei/sessao.py` — a docstring do módulo**

No primeiro parágrafo, trocar

```
(expirou por inatividade, foi derrubada por acesso concorrente, ou nunca houve
login)
```

por

```
(expirou por inatividade, alguém saiu do sistema, ou nunca houve login)
```

E, em `_MSG_SESSAO_EXPIRADA`, trocar `"expirou, foi encerrada em outro acesso, ou
não houve login"` por `"expirou, foi encerrada, ou não houve login"`.

> Atenção: `tests/test_sessao.py::test_levantar_se_expirada_levanta_com_causa`
> casa com `match="login do SEI"`, trecho que **não** muda. Rodar o arquivo para
> confirmar.

- [ ] **Step 5: Suíte + ruff**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest -q
```

Esperado: **756 passed** (a doc não acrescenta testes).

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m ruff check .
```

Esperado: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md README.md docs/uso-basico.md integra_gov/sei/sessao.py
git commit -F docs/superpowers/plans/.msg-task3.txt
```

Conteúdo de `.msg-task3.txt`:

```
docs: a deteccao de sessao caida ganha dois pontos, e um limite

CHANGELOG (Alterado + Corrigido), README e uso-basico passam a listar a barra
de icones e o iniciar_processo entre os pontos que detectam — e a dizer, nos
tres, que no iniciar_processo a deteccao para no clique em Salvar, com o motivo.

De quebra, sai a afirmacao de que a sessao cai por login em outro lugar. Isso
foi verificado e e falso no SEI do colaboragov/MGI (memoria
sei-sessoes-concorrentes.md); a frase estava no README, no uso-basico e na
docstring do proprio modulo sessao.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

### Task 4: `integra-flow` — remover os três invólucros

**Files:**
- Modify: `C:\Users\Thelemarco\PycharmProjects\integra-flow\integra_flow\execucao\catalogo_real.py`
- Modify: `C:\Users\Thelemarco\PycharmProjects\integra-flow\tests\test_catalogo_real.py`

**Interfaces:**
- Consumes: o comportamento das Tasks 1 e 2 (a lib está instalada em modo editable — as mudanças já valem sem reinstalar).
- Produces: as três fábricas (`_fabrica_iniciar_processo`, `_fabrica_inserir_documento_externo`, `_fabrica_enviar_processo`) deixam de capturar e reclassificar. Assinaturas e retornos inalterados.

- [ ] **Step 1: Reescrever os testes que exercitam o invólucro**

São **seis** pontos. Três testes afirmam que a *fábrica* reclassifica — deixam
de fazer sentido, porque quem reclassifica agora é a lib. Trocar cada um por um
teste de que a fábrica **não engole** a `SessaoExpiradaError` vinda da lib. A
classe local `_Tipada` (um `Exception` vazio, redefinido dentro de cada um dos
três testes) sai: o que se quer afirmar agora é a exceção real.

Acrescentar ao bloco de imports do topo de `tests/test_catalogo_real.py`:

```python
from integra_gov.sei import SessaoExpiradaError
```

Substituir o teste do `iniciar` (a classe `_Tipada` está na linha 82; o teste
inteiro vai até a linha 95) por:

```python
def test_fabrica_propaga_sessao_expirada_da_lib(monkeypatch):
    """A lib reclassifica (spec 2026-08-27); a fábrica só não pode engolir."""
    iniciar = MagicMock()
    iniciar.return_value.iniciar.side_effect = SessaoExpiradaError(
        "página de login"
    )
    monkeypatch.setattr(mod, "IniciarProcesso", iniciar)
    with pytest.raises(SessaoExpiradaError):
        _descritor().fabrica(MagicMock(), {"tipo": "X"}, {})
```

Fazer o equivalente nos dois irmãos (`_Tipada` nas linhas 240 e 404): a classe
`ProcessoQueFalha` passa a levantar `SessaoExpiradaError` direto, e saem a
classe `_Tipada`, a função `_levantar` e a linha
`monkeypatch.setattr(mod, "levantar_se_sessao_expirada", _levantar)`.

Nos outros três testes (`..._com_sessao_viva_propaga_o_erro_original`), remover
apenas a linha

```python
    monkeypatch.setattr(mod, "levantar_se_sessao_expirada", lambda d, c=None: None)
```

A asserção (o erro original propaga) continua válida e é o que trava a
regressão.

- [ ] **Step 2: Rodar e ver falhar — e ler o vermelho certo**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-flow\.venv\Scripts\python.exe -m pytest tests/test_catalogo_real.py -v
```

**Três falham, três passam — e os três que passam, passam por acidente.**

O motivo é um só. Com o invólucro ainda no lugar e o helper não mais
neutralizado pelo `monkeypatch`, o helper **real** roda contra um driver
`MagicMock`, cujo `find_elements` não configurado devolve um objeto verdadeiro
(ver a nota "Armadilha" no topo deste plano). `sessao_expirada()` lê "página de
login" para qualquer driver, e o invólucro levanta uma `SessaoExpiradaError`
**nova**, encobrindo o que quer que tenha vindo de baixo.

- Os três reescritos esperam `SessaoExpiradaError` e a recebem — **mas a do
  invólucro, não a da lib**. Verde enganoso; não tire conclusão deles agora.
- Os três `..._com_sessao_viva_propaga_o_erro_original` esperam o `RuntimeError`
  original e recebem `SessaoExpiradaError`. **É este o vermelho que importa** —
  são eles que só ficam verdes depois do Step 3.

Conferir com `-v` que a falha dos três é exatamente essa troca de exceção.

- [ ] **Step 3: Remover os três invólucros**

Em `integra_flow/execucao/catalogo_real.py`, nas três fábricas, substituir

```python
    try:
        <corpo>
    except Exception as exc:
        levantar_se_sessao_expirada(driver, exc)  # página de login → tipada
        raise
```

pelo `<corpo>` sem o `try`. E remover `levantar_se_sessao_expirada` da lista de
imports de `integra_gov.sei` no topo do arquivo.

- [ ] **Step 4: Atualizar as docstrings das três fábricas**

Em `_fabrica_iniciar_processo`, substituir o parágrafo que começa com
"Reclassificação de sessão caída: …" por:

```python
    """``params`` validados → kwargs da lib (None filtrado: defaults da lib).

    Sessão caída é tipificada **pela lib** (spec 2026-08-27) e só até a
    fronteira do efeito: falha ANTES do clique em "Salvar" chega como
    ``SessaoExpiradaError`` — é o que autoriza o Executor a reabrir a etapa —, e
    falha depois dele continua ``IniciarProcessoError`` ambígua, indo para
    quarentena. Não reintroduza um ``except`` aqui: envolver o método inteiro
    faria o processo ser criado duas vezes."""
```

Em `_fabrica_inserir_documento_externo`, trocar o item 4 da lista por:

```python
    4. ``inserir()`` — ``DocumentoExternoError`` daqui é ambígua → quarentena.
       Sessão caída vem tipificada da própria lib (barra de ícones e funil de
       iframes), sem invólucro aqui.
```

Em `_fabrica_enviar_processo`, acrescentar ao final da docstring, antes do
parágrafo do retorno:

```python
    Sessão caída vem tipificada da lib (barra de ícones / funil de iframes);
    não há invólucro de reclassificação nesta fábrica.
```

E, no cabeçalho do módulo, trocar a última linha
(``SessaoExpiradaError`` é tratada por fora (``excecoes_sessao`` do Executor).``)
por:

```python
``SessaoExpiradaError`` vem tipificada da lib e é tratada pelo Executor
(``excecoes_sessao``) — as fábricas não a produzem nem a capturam."""
```

- [ ] **Step 5: Rodar os dois níveis**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-flow\.venv\Scripts\python.exe -m pytest tests/test_catalogo_real.py -v
```

Esperado: todos passam.

```bash
C:\Users\Thelemarco\PycharmProjects\integra-flow\.venv\Scripts\python.exe -m pytest -q
```

Esperado: **334 passed** (o número não muda — testes foram reescritos, não
acrescentados).

```bash
C:\Users\Thelemarco\PycharmProjects\integra-flow\.venv\Scripts\python.exe -m ruff check .
```

Esperado: `All checks passed!`

- [ ] **Step 6: Contraprova por mutação — SÓ depois do commit**

Commitar primeiro (Step 7), e então: reintroduzir o `try/except` numa fábrica e
confirmar que nenhum teste quebra (ele é redundante, não errado); depois
`git checkout -- <arquivo>` — que agora **restaura**, porque o arquivo está
commitado.

- [ ] **Step 7: Commit**

```bash
git add integra_flow/execucao/catalogo_real.py tests/test_catalogo_real.py
git commit -F .msg-task4.txt
```

Conteúdo de `.msg-task4.txt` (na raiz do integra-flow; apagar depois):

```
refactor(catalogo): a lib tipifica sessao caida, saem os tres involucros

As tres fabricas repetiam try/except -> levantar_se_sessao_expirada -> raise.
A lib passou a reclassificar nos pontos que faltavam (integra-gov <SHA-DA-LIB>),
entao o involucro virou repeticao sem funcao.

No iniciar_processo ha uma diferenca que NAO e cosmetica: a lib reclassifica
so ate a fronteira do efeito. Falha depois do clique em Salvar continua
ambigua e vai para quarentena, em vez de reabrir a etapa e criar o processo
uma segunda vez. A docstring da fabrica registra isso.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

Substituir `<SHA-DA-LIB>` pelo sha do commit da Task 2.

---

### Task 5: gate ao vivo

**Files:**
- Create: `dados_reais/gate_sessao_caida.py` (gitignored — não entra no commit)
- Modify: `docs/superpowers/specs/2026-08-27-sessao-caida-fora-do-funil-design.md` (registro do gate)

**Interfaces:**
- Consumes: tudo das Tasks 1–4.
- Produces: nenhum código de produção. Um registro na spec dizendo o que foi observado — e o que **não** foi.

- [ ] **Step 1: Escrever o script**

Criar `dados_reais/gate_sessao_caida.py`:

```python
"""Gate ao vivo da tipificação de sessão caída (spec 2026-08-27).

Roteiro: o script loga, abre um processo e PARA, pedindo que você saia do SEI
em outra aba. Ao continuar, dispara uma operação que passa pela barra de ícones
e reporta qual exceção veio.

Unidade obrigatória: MGI-SGP-DECIPEX-CGPAG-NUTEC (memória unidade-de-testes-sei).
"""

import getpass

from integra_gov.sei import (
    LoginSei,
    ProcessoSei,
    SeiNavegacaoError,
    SessaoExpiradaError,
    criar_driver_chrome,
)
from integra_gov.sei.barra_icones import clicar_icone_barra

BASE_URL = input("URL base do SEI: ").strip()
ORGAO = input("Órgão: ").strip()
UNIDADE = "MGI-SGP-DECIPEX-CGPAG-NUTEC"
NUP = input("NUP de um processo já existente nessa unidade: ").strip()

driver = criar_driver_chrome()
try:
    LoginSei(
        driver, BASE_URL, ORGAO, input("Usuário: "), getpass.getpass("Senha: ")
    ).logar()
    ProcessoSei(driver, NUP).acessar()
    print(f"\nProcesso {NUP} aberto.")
    input(
        "AGORA: abra outra aba, entre no SEI e clique em Sair. "
        "Depois volte aqui e tecle Enter. "
    )
    try:
        clicar_icone_barra(driver, "Enviar Processo")
    except SessaoExpiradaError as exc:
        print(f"\nOK — SessaoExpiradaError: {exc}")
    except SeiNavegacaoError as exc:
        print(f"\nFALHOU — veio SeiNavegacaoError, não a tipada: {exc}")
    else:
        print("\nINCONCLUSIVO — a operação passou; a sessão não caiu.")
finally:
    driver.quit()
```

- [ ] **Step 2: Pedir ao usuário que rode**

Entregar o comando completo, com caminhos absolutos (o `integra` de trabalho
está global — o venv do repo é obrigatório):

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe C:\Users\Thelemarco\PycharmProjects\integra-publico\dados_reais\gate_sessao_caida.py
```

**O usuário digita a senha.** Não pedir a senha, não a registrar em lugar nenhum.

- [ ] **Step 3: Registrar o gate na spec — inclusive o que não foi visto**

Acrescentar uma seção `## 11. Registro do gate ao vivo` ao fim da spec, com a
data, o que foi observado e a exceção recebida.

**Obrigatório:** o caso pós-Salvar do §3.2 exige o logout na janela entre o
clique e a leitura do título, e provavelmente **não** será reproduzível. Se não
for, escrever que ele **não foi observado ao vivo** — e que a garantia se apoia
no teste `test_falha_apos_salvar_na_pagina_de_login_continua_ambigua`. Não
escrever "verificado" para o que não foi.

- [ ] **Step 4: Commit do registro**

```bash
git add docs/superpowers/specs/2026-08-27-sessao-caida-fora-do-funil-design.md
git commit -F docs/superpowers/plans/.msg-task5.txt
```

Conteúdo de `.msg-task5.txt`:

```
docs(spec): registro do gate ao vivo da sessao caida

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

---

## Checagem final da fatia

- [ ] Lib: `pytest -q` → **756 passed**; `ruff check .` limpo.
- [ ] Flow: `pytest -q` → **334 passed**; `ruff check .` limpo.
- [ ] `git status` limpo nos dois repos (os `.msg-task*.txt` foram apagados).
- [ ] Nenhuma menção sobrevivente a `levantar_se_sessao_expirada` em
      `integra_flow/` fora dos testes:
      `grep -rn "levantar_se_sessao_expirada" integra_flow/` → sem resultados.
- [ ] O gate está registrado na spec, com o que **não** foi observado dito
      explicitamente.
