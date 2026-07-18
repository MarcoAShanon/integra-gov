# SessaoExpiradaError — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detectar e tipificar a sessão do SEI caída no meio de um fluxo: novo
`SessaoExpiradaError` + helper público `sessao_expirada(driver)`, disparados no
funil central de navegação (iframes + acesso ao processo).

**Architecture:** Novo módulo `integra_gov/sei/sessao.py` (detecção pela
presença dos campos `txtUsuario`+`pwdSenha` do login SIP, sem espera); exceção
`SessaoExpiradaError(SeiError)` — subclasse DIRETA de `SeiError`, irmã de
`SeiNavegacaoError` (os módulos capturam `SeiNavegacaoError` para embrulhar no
erro próprio; a irmã atravessa TODOS eles intocada — verificado por grep: nenhum
módulo captura `SeiError` largo, e o único `except Exception` do pacote,
`editar_conteudo.py`, re-levanta após cleanup). Fiação em 3 pontos de falha:
`_retry_iframe`, loop de candidatos do `switch_to_iframe_visualizacao`, e
`ProcessoSei.acessar`.

**Tech Stack:** Python ≥3.9 (`target-version = "py39"`), Selenium, pytest
(Selenium mockado — sem navegador), ruff.

**Spec:** `docs/superpowers/specs/2026-07-18-sessao-expirada-design.md`
(aprovada; leia antes de executar).

## Global Constraints

- Branch de trabalho: `feat/sessao-expirada` (criada na Task 1; merge ff na Task 5).
- Baseline: 273 testes verdes, ruff limpo. NENHUM teste existente pode quebrar
  — exceto os 4 listados nas Tasks 2–3, cujo ajuste (driver com "sessão viva")
  faz parte da mudança de comportamento planejada.
- Suíte/lint: `.venv/Scripts/python.exe -m pytest -q` e
  `.venv/Scripts/python.exe -m ruff check .` (rodar da raiz do repo).
- TDD estrito: escrever o teste, VER falhar (pelo motivo certo), implementar,
  ver passar, commitar.
- Sem dados reais em código/teste versionado (números de processo fictícios).
- Docstrings e mensagens em português, no estilo dos módulos vizinhos.
- NÃO commitar `body.txt` (arquivo solto na raiz, alheio a este trabalho) nem
  `dados_reais/` (está no `.gitignore`).
- Mensagem padrão do erro (única no pacote, definida UMA vez em `sessao.py`):
  `"a página atual é a de login do SEI — a sessão não está mais autenticada (expirou, foi encerrada em outro acesso, ou não houve login)"`.

---

### Task 1: Exceção + módulo `sessao.py` + exports

**Files:**
- Modify: `integra_gov/sei/exceptions.py` (adicionar ao FINAL do arquivo)
- Create: `integra_gov/sei/sessao.py`
- Modify: `integra_gov/sei/__init__.py`
- Create: `tests/test_sessao.py`

**Interfaces:**
- Consumes: `LoginSei.TXT_USUARIO` / `LoginSei.PWD_SENHA` (constantes `"txtUsuario"`/`"pwdSenha"` em `integra_gov/sei/login.py`); `SeiError` de `integra_gov/sei/exceptions.py`.
- Produces (Tasks 2–3 dependem): `sessao_expirada(driver) -> bool` e `levantar_se_sessao_expirada(driver, causa: BaseException | None = None) -> None` em `integra_gov.sei.sessao`; `SessaoExpiradaError` em `integra_gov.sei.exceptions`. Sem ciclo de import: `iframes` → `sessao` → `login` → `tela_aviso` (nada nessa cadeia importa `iframes`).

- [ ] **Step 1: Criar a branch**

```bash
git checkout -b feat/sessao-expirada
```

- [ ] **Step 2: Escrever os testes que falham**

Criar `tests/test_sessao.py`:

```python
"""Testes de ``integra_gov.sei.sessao`` — sem navegador real (Selenium mockado).

O driver fake devolve listas em ``find_elements`` conforme os IDs configurados;
a detecção exige os DOIS campos do formulário de login do SIP."""

from unittest.mock import MagicMock

import pytest
from selenium.common.exceptions import WebDriverException

from integra_gov.sei.exceptions import SeiError, SessaoExpiradaError
from integra_gov.sei.sessao import levantar_se_sessao_expirada, sessao_expirada


def _driver(ids_presentes=(), erro=None):
    """Driver fake: ``find_elements(By.ID, x)`` → [elemento] se x configurado."""
    driver = MagicMock()
    if erro is not None:
        driver.find_elements.side_effect = erro
    else:
        presentes = set(ids_presentes)
        driver.find_elements.side_effect = (
            lambda by, valor: ["el"] if valor in presentes else []
        )
    return driver


def test_pagina_de_login_detectada():
    driver = _driver({"txtUsuario", "pwdSenha"})
    assert sessao_expirada(driver) is True
    driver.switch_to.default_content.assert_called()  # parte do topo


def test_so_um_campo_nao_e_login():
    assert sessao_expirada(_driver({"txtUsuario"})) is False
    assert sessao_expirada(_driver({"pwdSenha"})) is False


def test_pagina_normal_do_sei_nao_e_login():
    assert sessao_expirada(_driver(set())) is False


def test_driver_morto_devolve_false():
    # Na dúvida o erro original prevalece: o helper nunca vira a causa da falha.
    assert sessao_expirada(_driver(erro=WebDriverException("morto"))) is False


def test_default_content_falhando_devolve_false():
    driver = _driver({"txtUsuario", "pwdSenha"})
    driver.switch_to.default_content.side_effect = WebDriverException("morto")
    assert sessao_expirada(driver) is False


def test_levantar_se_expirada_levanta_com_causa():
    causa = TimeoutError("timeout original")
    with pytest.raises(SessaoExpiradaError, match="login do SEI") as excinfo:
        levantar_se_sessao_expirada(_driver({"txtUsuario", "pwdSenha"}), causa)
    assert excinfo.value.__cause__ is causa
    assert isinstance(excinfo.value, SeiError)  # herda da base do pacote


def test_levantar_se_expirada_noop_com_sessao_viva():
    levantar_se_sessao_expirada(_driver(set()))  # não deve levantar


def test_sessao_expirada_nao_e_navegacao_error():
    # Deliberado (spec): irmã de SeiNavegacaoError, não filha — módulos que
    # capturam SeiNavegacaoError para embrulhar não podem engoli-la.
    from integra_gov.sei.exceptions import SeiNavegacaoError

    assert not issubclass(SessaoExpiradaError, SeiNavegacaoError)


def test_exports_publicos():
    import integra_gov.sei as sei

    assert sei.SessaoExpiradaError is SessaoExpiradaError
    assert sei.sessao_expirada is sessao_expirada
    assert sei.levantar_se_sessao_expirada is levantar_se_sessao_expirada
    assert "SessaoExpiradaError" in sei.__all__
    assert "sessao_expirada" in sei.__all__
    assert "levantar_se_sessao_expirada" in sei.__all__
```

- [ ] **Step 3: Ver os testes falharem pelo motivo certo**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sessao.py -q`
Expected: erro de import (`ImportError`/`ModuleNotFoundError`: `SessaoExpiradaError` / `integra_gov.sei.sessao` não existem).

- [ ] **Step 4: Implementar a exceção**

Adicionar ao FINAL de `integra_gov/sei/exceptions.py`:

```python
class SessaoExpiradaError(SeiError):
    """A página atual é a de login do SEI — a sessão não está mais autenticada
    (expirou por inatividade, foi encerrada em outro acesso, ou não houve
    login). A requisição que falhou foi redirecionada ao login, ou seja, **não
    foi executada** pelo SEI.

    Subclasse direta de :class:`SeiError` — deliberadamente NÃO de
    :class:`SeiNavegacaoError`: expiração é estado de sessão, não defeito de
    navegação, e quem captura ``SeiNavegacaoError`` para retry não deve engolir
    uma sessão caída (retry ali é inútil).

    A política de reação (relogar, pausar o lote, abortar) é do chamador.
    Caso-limite teórico para orquestradores: uma sessão derrubada por login
    concorrente IMEDIATAMENTE após um POST bem-sucedido pode classificar como
    expirada uma ação que ocorreu — ao automatizar retry, avalie por operação."""
```

- [ ] **Step 5: Implementar o módulo `sessao.py`**

Criar `integra_gov/sei/sessao.py`:

```python
"""Detecção de sessão do SEI caída (página de login no meio do fluxo).

Quando a sessão deixa de estar autenticada (expirou por inatividade, foi
derrubada por acesso concorrente, ou nunca houve login), o SIP redireciona
qualquer requisição para a página de login — e a próxima operação da automação
falha. Este módulo detecta essa condição e a tipifica como
:class:`~integra_gov.sei.exceptions.SessaoExpiradaError`.

Mecanismo, não política: a lib detecta e levanta; relogar/pausar/abortar é
decisão de quem chama."""

from __future__ import annotations

import logging

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from .exceptions import SessaoExpiradaError
from .login import LoginSei

_log = logging.getLogger(__name__)

#: Mensagem padrão do pacote para sessão caída (única fonte).
_MSG_SESSAO_EXPIRADA = (
    "a página atual é a de login do SEI — a sessão não está mais autenticada "
    "(expirou, foi encerrada em outro acesso, ou não houve login)"
)


def sessao_expirada(driver) -> bool:
    """``True`` se a página atual é a de login do SEI (sessão não autenticada).

    Detecta pela presença SIMULTÂNEA dos campos ``txtUsuario`` e ``pwdSenha``
    do formulário do SIP (IDs de :class:`~integra_gov.sei.login.LoginSei` —
    estáveis entre instâncias, ao contrário da URL, que varia por órgão). A
    checagem é imediata (``find_elements``, sem espera) — roda em caminhos de
    falha e não pode custar timeout. Não distingue *por que* a sessão não está
    autenticada (expirou / derrubada / nunca logou).

    Em qualquer ``WebDriverException`` devolve ``False``: na dúvida, o erro
    original prevalece — este helper nunca vira a causa da falha.

    Efeito colateral: deixa o driver posicionado no ``default_content`` (a
    página de login não tem os iframes do SEI; a checagem parte do topo). Quem
    a chamar avulso deve re-navegar depois.
    """
    try:
        driver.switch_to.default_content()
        usuario = driver.find_elements(By.ID, LoginSei.TXT_USUARIO)
        senha = driver.find_elements(By.ID, LoginSei.PWD_SENHA)
    except WebDriverException:
        return False
    caiu = bool(usuario) and bool(senha)
    if caiu:
        _log.debug("Página de login do SEI detectada — sessão não autenticada")
    return caiu


def levantar_se_sessao_expirada(
    driver, causa: BaseException | None = None
) -> None:
    """Levanta :class:`SessaoExpiradaError` se a sessão caiu; senão, no-op.

    Companheiro de :func:`sessao_expirada` para caminhos de falha: encadeia o
    erro original em ``causa`` (``raise ... from causa``). Útil também a
    orquestradores, para reclassificar uma falha qualquer::

        try:
            operacao(driver)
        except SeiError as exc:
            levantar_se_sessao_expirada(driver, exc)  # reclassifica se caiu
            raise
    """
    if sessao_expirada(driver):
        raise SessaoExpiradaError(_MSG_SESSAO_EXPIRADA) from causa
```

- [ ] **Step 6: Exports no `integra_gov/sei/__init__.py`**

Três edições (manter ordem alfabética):

1. Na lista de módulos da docstring, após a linha do ``processo``:

```python
  - ``sessao``            : detecção de sessão caída (login no meio do fluxo) ✅
```

2. No bloco de imports: adicionar ``SessaoExpiradaError`` ao import de
   ``.exceptions`` (após ``SeiNavegacaoError``, antes de ``SelecaoDocumentoError``
   — ordem alfabética: ``SeiNavegacaoError``, ``SelecaoDocumentoError``, …,
   ``SessaoExpiradaError`` entra após ``SelecaoDocumentoError``); e, após a linha
   ``from .selecao_unidade import ...``:

```python
from .sessao import levantar_se_sessao_expirada, sessao_expirada
```

3. No ``__all__`` (ordem alfabética): ``"SessaoExpiradaError"`` após
   ``"SelecaoUnidade"``; ``"levantar_se_sessao_expirada"`` após
   ``"fechar_tela_aviso"``; ``"sessao_expirada"`` após ``"montar_url_login"``.

- [ ] **Step 7: Ver os testes passarem + suíte + ruff**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sessao.py -q`
Expected: 9 passed.
Run: `.venv/Scripts/python.exe -m pytest -q` → 282 passed (273 + 9).
Run: `.venv/Scripts/python.exe -m ruff check .` → All checks passed!

- [ ] **Step 8: Commit**

```bash
git add integra_gov/sei/exceptions.py integra_gov/sei/sessao.py integra_gov/sei/__init__.py tests/test_sessao.py
git commit -m "feat(sei): SessaoExpiradaError + sessao_expirada (deteccao de sessao caida)"
```

---

### Task 2: Funil em `iframes.py` (fail-fast)

**Files:**
- Modify: `integra_gov/sei/iframes.py`
- Modify: `tests/test_iframes.py`

**Interfaces:**
- Consumes: `levantar_se_sessao_expirada(driver, causa)` de `integra_gov.sei.sessao` (Task 1).
- Produces: `IframesSei.navegar()` e `switch_to_iframe_visualizacao()` levantam `SessaoExpiradaError` (em vez de `TimeoutException`) quando a página é a de login — na PRIMEIRA falha, sem esgotar retries/candidatos.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `tests/test_iframes.py` (os imports novos vão junto aos
existentes no topo: `from integra_gov.sei.exceptions import SessaoExpiradaError`):

```python
def _driver_sessao_caida():
    """Driver fake numa página de login: find_elements devolve elemento p/
    txtUsuario e pwdSenha."""
    driver = MagicMock()
    driver.find_elements.side_effect = (
        lambda by, valor: ["el"] if valor in {"txtUsuario", "pwdSenha"} else []
    )
    return driver


def _driver_sessao_viva():
    """Driver fake numa página do SEI: find_elements devolve lista vazia
    (MagicMock cru devolveria um mock truthy — falso positivo de login)."""
    driver = MagicMock()
    driver.find_elements.return_value = []
    return driver


def test_switch_visualizacao_sessao_caida_levanta_sessao_expirada(selenium):
    selenium(set())  # nenhum iframe: é a página de login
    with pytest.raises(SessaoExpiradaError):
        iframes.switch_to_iframe_visualizacao(_driver_sessao_caida())


def test_switch_visualizacao_fail_fast_no_primeiro_candidato(selenium):
    """Com a sessão caída, não queima o timeout do 2º candidato: a checagem
    dispara na falha do 1º."""
    tentados = []

    class _WaitContando:
        def __init__(self, driver, timeout):
            pass

        def until(self, cond):
            tentados.append(cond[1])
            raise TimeoutException("página de login não tem iframes")

    import unittest.mock

    with unittest.mock.patch.object(iframes, "WebDriverWait", _WaitContando):
        with pytest.raises(SessaoExpiradaError):
            iframes.switch_to_iframe_visualizacao(_driver_sessao_caida())
    assert tentados == ["ifrConteudoVisualizacao"]  # NÃO tentou o 2º


def test_navegar_sessao_caida_fail_fast_sem_retries(monkeypatch):
    """`_retry_iframe` não repete contra uma página de login: 1 tentativa."""
    monkeypatch.setattr(
        iframes.EC, "frame_to_be_available_and_switch_to_it", lambda loc: loc
    )
    monkeypatch.setattr(iframes.time, "sleep", lambda _s: None)
    chamadas = {"n": 0}

    class _WaitSempreFalha:
        def __init__(self, driver, timeout):
            pass

        def until(self, cond):
            chamadas["n"] += 1
            raise TimeoutException("página de login")

    monkeypatch.setattr(iframes, "WebDriverWait", _WaitSempreFalha)
    with pytest.raises(SessaoExpiradaError):
        IframesSei(_driver_sessao_caida(), IframesSei.ARVORE).navegar()
    assert chamadas["n"] == 1  # fail-fast: sem as 3 tentativas


def test_navegar_sessao_viva_mantem_retry_e_timeout(selenium):
    """Regressão: com sessão viva, o comportamento atual fica intacto
    (retry + TimeoutException no esgotamento)."""
    selenium(set())
    with pytest.raises(TimeoutException):
        iframes.switch_to_iframe_visualizacao(_driver_sessao_viva())
```

- [ ] **Step 2: Ajustar 3 testes existentes para "sessão viva"**

Os testes abaixo exercitam caminhos de falha com `driver = MagicMock()` cru —
cujo `find_elements` devolve mock *truthy* e, com a fiação nova, viraria falso
positivo de página de login. Trocar `driver = MagicMock()` por
`driver = _driver_sessao_viva()` em:

1. `test_switch_visualizacao_sei3_cai_para_ifrvisualizacao` (o 1º candidato falha);
2. `test_switch_visualizacao_sem_nenhum_levanta_timeout`;
3. `test_navegar_retry_em_falha_transitoria` (a 1ª tentativa falha).

(Como `_driver_sessao_viva` ficará definido abaixo desses testes, mover as duas
funções helper `_driver_sessao_caida`/`_driver_sessao_viva` para logo após a
fixture `selenium`, antes do primeiro teste.)

- [ ] **Step 3: Ver os testes novos falharem pelo motivo certo**

Run: `.venv/Scripts/python.exe -m pytest tests/test_iframes.py -q`
Expected: os 4 testes novos FALHAM (`TimeoutException` levantada em vez de
`SessaoExpiradaError`; contagens erradas); os demais passam.

- [ ] **Step 4: Implementar a fiação em `iframes.py`**

1. Adicionar o import (junto aos imports relativos):

```python
from .sessao import levantar_se_sessao_expirada
```

2. Em `switch_to_iframe_visualizacao`, no `except` do loop de candidatos —
   inserir a checagem após registrar o erro (fail-fast: falhou o 1º candidato
   numa página de login → nem tenta o 2º):

```python
        except _EXCECOES_IFRAME as exc:
            erros.append(f"{nome}={type(exc).__name__}")
            _log.debug("iframe '%s' indisponível: %s", nome, type(exc).__name__)
            levantar_se_sessao_expirada(driver, exc)
```

3. Em `_retry_iframe`, no `except` do loop de tentativas — inserir a checagem
   ANTES de agendar a próxima tentativa:

```python
                except (TimeoutException, StaleElementReferenceException) as exc:
                    levantar_se_sessao_expirada(self.driver, exc)
                    ultima_exc = exc
```

   (o restante do bloco — log, `default_content`, `sleep` — fica como está).

4. Atualizar a docstring do módulo (bloco "API:") com uma linha:

```
    - Sessão caída: nos caminhos de falha, uma página de login detectada vira
      :class:`~integra_gov.sei.exceptions.SessaoExpiradaError` imediatamente
      (fail-fast — sem esgotar retries/candidatos contra a página de login).
```

Docstrings de `switch_to_iframe_visualizacao` e `IframesSei.navegar`: adicionar
`SessaoExpiradaError: se a página atual é a de login (sessão caída).` na seção
`Raises:`.

- [ ] **Step 5: Ver tudo passar + ruff**

Run: `.venv/Scripts/python.exe -m pytest tests/test_iframes.py tests/test_sessao.py -q`
Expected: todos passam (14 + 9).
Run: `.venv/Scripts/python.exe -m pytest -q` → 286 passed (282 + 4).
Run: `.venv/Scripts/python.exe -m ruff check .` → All checks passed!

- [ ] **Step 6: Commit**

```bash
git add integra_gov/sei/iframes.py tests/test_iframes.py
git commit -m "feat(sei): funil de iframes levanta SessaoExpiradaError (fail-fast na pagina de login)"
```

---

### Task 3: Funil em `processo.py` + prova de propagação

**Files:**
- Modify: `integra_gov/sei/processo.py`
- Modify: `tests/test_processo.py`

**Interfaces:**
- Consumes: `levantar_se_sessao_expirada(driver, causa)` (Task 1); `IframesSei.navegar()` levantando `SessaoExpiradaError` (Task 2).
- Produces: `ProcessoSei.acessar()` levanta `SessaoExpiradaError` quando o campo de pesquisa falta E a página é a de login; `ProcessoSei.ir_para_raiz()` a PROPAGA (não embrulha em `SeiNavegacaoError`) — a prova de que a exceção-irmã atravessa os módulos.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `tests/test_processo.py` (import novo no topo:
`from integra_gov.sei.exceptions import SessaoExpiradaError`):

```python
def _driver_login(ids_presentes):
    """Driver fake com find_element falhando (campo ausente) e find_elements
    configurado (página de login ou não)."""
    driver = MagicMock()
    driver.find_element.side_effect = NoSuchElementException("sem campo")
    presentes = set(ids_presentes)
    driver.find_elements.side_effect = (
        lambda by, valor: ["el"] if valor in presentes else []
    )
    return driver


def test_acessar_sessao_caida_levanta_sessao_expirada(selenium):
    driver = _driver_login({"txtUsuario", "pwdSenha"})
    with pytest.raises(SessaoExpiradaError):
        ProcessoSei(driver, "19975.120202/2023-82").acessar()


def test_acessar_sessao_viva_mantem_navegacao_error(selenium):
    """Regressão: campo ausente SEM página de login segue SeiNavegacaoError."""
    driver = _driver_login(set())
    with pytest.raises(SeiNavegacaoError):
        ProcessoSei(driver, "19975.120202/2023-82").acessar()


def test_ir_para_raiz_propaga_sessao_expirada(selenium):
    """Prova de propagação fim-a-fim: SessaoExpiradaError vinda do funil de
    iframes ATRAVESSA o módulo (o `except TimeoutException` do ir_para_raiz não
    a captura — ela não é TimeoutException nem SeiNavegacaoError)."""
    driver = MagicMock()
    fake_iframes = MagicMock()
    fake_iframes.ARVORE = "arvore"
    fake_iframes.return_value.navegar.side_effect = SessaoExpiradaError("caiu")
    selenium.setattr(mod, "IframesSei", fake_iframes)
    with pytest.raises(SessaoExpiradaError):
        ProcessoSei(driver, "19975.120202/2023-82").ir_para_raiz()
```

- [ ] **Step 2: Ajustar 1 teste existente para "sessão viva"**

`test_acessar_campo_pesquisa_ausente_levanta_navegacao` usa `MagicMock()` cru
(`find_elements` truthy → falso positivo de login com a fiação nova). Adicionar
uma linha após criar o driver:

```python
    driver.find_elements.return_value = []
```

- [ ] **Step 3: Ver os testes novos falharem pelo motivo certo**

Run: `.venv/Scripts/python.exe -m pytest tests/test_processo.py -q`
Expected: `test_acessar_sessao_caida_levanta_sessao_expirada` FALHA
(`SeiNavegacaoError` em vez de `SessaoExpiradaError`);
`test_ir_para_raiz_propaga_sessao_expirada` deve JÁ PASSAR (a propagação é
consequência da hierarquia da Task 1 — rodar para confirmar, é a prova);
os demais passam.

- [ ] **Step 4: Implementar a fiação em `processo.py`**

1. Import (junto aos relativos):

```python
from .sessao import levantar_se_sessao_expirada
```

2. Em `ProcessoSei.acessar`, no `except TimeoutException` do campo de pesquisa
   — checar ANTES de embrulhar (mensagem existente preservada):

```python
        except TimeoutException as exc:
            levantar_se_sessao_expirada(self.driver, exc)
            raise SeiNavegacaoError(
                "campo de pesquisa rápida não encontrado — a sessão do SEI "
                "está autenticada?"
            ) from exc
```

3. Docstring de `acessar`, seção `Raises:` — adicionar:
   `SessaoExpiradaError: se a página atual é a de login (sessão caída).`

- [ ] **Step 5: Ver tudo passar + ruff**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 289 passed (286 + 3).
Run: `.venv/Scripts/python.exe -m ruff check .` → All checks passed!

- [ ] **Step 6: Commit**

```bash
git add integra_gov/sei/processo.py tests/test_processo.py
git commit -m "feat(sei): ProcessoSei.acessar tipifica sessao caida; propagacao provada por teste"
```

---

### Task 4: Documentação (README + uso-basico + CHANGELOG)

**Files:**
- Modify: `README.md` (tabela de módulos + seção de uso)
- Modify: `docs/uso-basico.md` (nova seção "## 6." inserida antes de "## Exemplo completo" — que não é numerado, então nada a renumerar)
- Modify: `CHANGELOG.md` (seção "Não publicado" → "### Adicionado")

**Interfaces:**
- Consumes: API pública das Tasks 1–3 (nomes exatos: `SessaoExpiradaError`, `sessao_expirada`, `levantar_se_sessao_expirada`).
- Produces: docs completas ANTES do merge (convenção do projeto: feature não chega à main sem README+CHANGELOG+uso-basico).

- [ ] **Step 1: README — linha na tabela de módulos**

Em `## Módulos` → `### SEI — multiplataforma (núcleo)`, após a linha de
`integra_gov.sei.login`:

```markdown
| `integra_gov.sei.sessao` | Detecção de sessão caída (página de login no meio do fluxo) | ✅ |
```

- [ ] **Step 2: README — seção de uso**

Após a seção `### Enviar o processo a outra unidade` (antes de
`### SIAPE (terminal 3270)`):

```markdown
### Sessão expirada no meio do fluxo

Quando a sessão do SEI cai (expirou por inatividade ou foi derrubada por outro
acesso), a página vira a de login e a operação seguinte falha com
`SessaoExpiradaError` — em vez de um erro genérico de navegação. A lib só
detecta e tipifica; relogar/pausar é decisão sua:

```python
from integra_gov.sei import SessaoExpiradaError

try:
    processo.acessar()
except SessaoExpiradaError:
    # a sessão caiu: logue de novo e repita a operação
    LoginSei(driver, BASE_URL, ORGAO, usuario, senha).logar()
    processo.acessar()
```

Para reclassificar uma falha qualquer (útil em orquestradores), o helper
`sessao_expirada(driver)` responde se a página atual é a de login; e
`levantar_se_sessao_expirada(driver, causa)` levanta o erro tipado se for.
```

(Atenção ao fechar o bloco de código aninhado — seguir o padrão das seções
vizinhas do README.)

- [ ] **Step 3: uso-basico — nova seção**

Em `docs/uso-basico.md`, antes de `## Exemplo completo (do zero ao processo
aberto)`:

```markdown
## 6. Sessão expirada no meio do fluxo

O SEI derruba a sessão por inatividade (e também quando o mesmo usuário loga em
outro lugar). Quando isso acontece no meio de uma automação, a página atual
vira a de login — e a próxima operação falharia com um erro genérico. A lib
detecta essa condição nos pontos centrais de navegação e levanta
`SessaoExpiradaError`:

```python
from integra_gov.sei import SessaoExpiradaError

try:
    processo.acessar("00000.000000/0000-00")
except SessaoExpiradaError:
    # A sessão caiu. A operação NÃO foi executada pelo SEI (a requisição foi
    # redirecionada ao login). Logue de novo e repita:
    LoginSei(driver, BASE_URL, ORGAO, usuario, senha).logar()
    processo.acessar("00000.000000/0000-00")
```

Pontos que detectam: a navegação de iframes (`IframesSei` /
`switch_to_iframe_visualizacao`) e o acesso a processo (`ProcessoSei.acessar`).
Qualquer outra falha pode ser reclassificada com os helpers públicos:

```python
from integra_gov.sei import SeiError, levantar_se_sessao_expirada

try:
    operacao(driver)
except SeiError as exc:
    levantar_se_sessao_expirada(driver, exc)  # vira SessaoExpiradaError se caiu
    raise
```
```

- [ ] **Step 4: CHANGELOG — entrada em "Não publicado" → "### Adicionado"**

No topo da lista de "### Adicionado" (padrão: mais recente primeiro):

```markdown
- `integra_gov.sei.sessao`: **detecção de sessão caída** (página de login no
  meio do fluxo) — `sessao_expirada(driver)` (a página atual é a de login?) e
  `levantar_se_sessao_expirada(driver, causa)`; nova exceção
  `SessaoExpiradaError` (subclasse direta de `SeiError` — deliberadamente NÃO
  de `SeiNavegacaoError`, para atravessar os módulos sem ser embrulhada).
  **Comportamento novo no funil de navegação:** falhas em
  `IframesSei.navegar`/`switch_to_iframe_visualizacao` e em
  `ProcessoSei.acessar` com a página de login presente levantam
  `SessaoExpiradaError` (fail-fast, sem esgotar retries contra a página de
  login) em vez de `TimeoutException`/`SeiNavegacaoError`. Quem captura
  `SeiError` não sente diferença. Motivação: orquestradores (integra-flow)
  distinguirem "sessão caiu" (recuperável: logar de novo) de falha ambígua.
```

- [ ] **Step 5: Conferir e commitar**

Run: `.venv/Scripts/python.exe -m pytest -q` → 289 passed (docs não quebram nada).

```bash
git add README.md docs/uso-basico.md CHANGELOG.md
git commit -m "docs: sessao expirada no README, uso-basico e CHANGELOG"
```

---

### Task 5: Verificação ao vivo + merge

**Files:**
- Create: `dados_reais/teste_real_sessao_expirada.py` (NÃO versionado — `dados_reais/` está no `.gitignore`)
- Modify: `CHANGELOG.md` (nota "Verificado ao vivo" após passar)

**Interfaces:**
- Consumes: toda a API das Tasks 1–3.
- Produces: feature verificada contra o SEI real; branch mesclada na main.

**NOTA:** esta task exige o OPERADOR (login real). Executor agêntico: prepare o
script, rode a suíte, e PARE — peça ao usuário para rodar o teste ao vivo e
reporte o resultado antes do merge.

- [ ] **Step 1: Criar o script ao vivo**

Criar `dados_reais/teste_real_sessao_expirada.py` (padrão dos vizinhos:
constantes editáveis + `getpass`):

```python
"""Teste REAL de `sessao` (SessaoExpiradaError) contra o SEI.

Fluxo: login → sanidade (acessar processo com sessão viva) →
`driver.delete_all_cookies()` (simula a expiração: sem o cookie de sessão o SIP
redireciona ao login) → tentar acessar de novo → esperar `SessaoExpiradaError`.

VOCÊ digita a senha (via getpass) — ela não é salva nem versionada.

Como rodar (com o venv do integra-gov ativo):
    python dados_reais/teste_real_sessao_expirada.py

Esta pasta (dados_reais/) está no .gitignore — não vai para o GitHub.
"""

import logging
from getpass import getpass

from integra_gov.sei import (
    LoginSei,
    ProcessoSei,
    SessaoExpiradaError,
    criar_driver_chrome,
    sessao_expirada,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# ===== EDITE AQUI =====
BASE_URL = "https://colaboragov.sei.gov.br"
ORGAO = "MGI"
USUARIO = "seu.usuario"           # << TROQUE pelo seu usuário do SEI
PROCESSO = "00000.000000/0000-00"  # << TROQUE por um processo SEU (qualquer um)
# ======================


def main() -> None:
    if USUARIO == "seu.usuario" or PROCESSO == "00000.000000/0000-00":
        print("⚠️  Edite USUARIO e PROCESSO no topo do arquivo antes de rodar.")
        return

    driver = criar_driver_chrome()
    try:
        LoginSei(driver, BASE_URL, ORGAO, USUARIO, getpass("Senha do SEI: ")).logar()

        # 1) Controle (sem falso positivo): sessão viva opera normalmente.
        assert not sessao_expirada(driver), "falso positivo com sessão viva!"
        ProcessoSei(driver, PROCESSO).acessar()
        print("✅ 1/3 Sessão viva: processo acessado, sem falso positivo.")

        # 2) Derruba a sessão (simulação fiel: cookie de sessão removido).
        driver.delete_all_cookies()

        # 3) A próxima operação deve virar SessaoExpiradaError.
        try:
            ProcessoSei(driver, PROCESSO).acessar()
        except SessaoExpiradaError as exc:
            print(f"✅ 2/3 SessaoExpiradaError tipificada: {exc}")
        else:
            print("❌ 2/3 acessar() não levantou SessaoExpiradaError!")
            return

        assert sessao_expirada(driver), "helper deveria confirmar a página de login"
        print("✅ 3/3 sessao_expirada(driver) confirma a página de login.")
        print("🏁 Verificação ao vivo COMPLETA.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: PARAR e pedir a execução ao vivo ao usuário**

Pedir: rodar `python dados_reais/teste_real_sessao_expirada.py` (editando as
constantes) e reportar a saída. NÃO prosseguir sem os 3 ✅.

Se a realidade divergir (ex.: o SEI redireciona para uma URL/tela diferente e a
detecção não dispara): investigar com o usuário, corrigir o detector
(`sessao.py`), re-rodar a suíte offline E o teste ao vivo, e só então seguir.

- [ ] **Step 3: Registrar a verificação no CHANGELOG**

Ao final da entrada da Task 4, acrescentar (ajustar versão/órgão ao reportado):

```markdown
  **Verificado ao vivo** no SEI 4.1.5 (MGI): sem falso positivo com sessão
  viva; após `delete_all_cookies()`, `ProcessoSei.acessar` levantou
  `SessaoExpiradaError` e `sessao_expirada(driver)` confirmou a página de login.
```

```bash
git add CHANGELOG.md
git commit -m "docs: registra verificacao ao vivo da deteccao de sessao caida"
```

- [ ] **Step 4: Merge na main (ff, convenção do repo) e suíte final**

```bash
git checkout main
git merge --ff-only feat/sessao-expirada
```

Run: `.venv/Scripts/python.exe -m pytest -q` → 289 passed.
Run: `.venv/Scripts/python.exe -m ruff check .` → All checks passed!

```bash
git branch -d feat/sessao-expirada
```
