# Fundação e-SIAPE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subpacote `integra_gov.esiape` — navegação CIS (frames visíveis, popups modais, relogin), acesso SERPRO ID e troca de habilitação web, tornando qualquer transação e-SIAPE automatizável.

**Architecture:** `navegacao.py` = funções módulo-nível com o driver como 1º argumento (sem estado de classe; a flag de relogin vive no driver). `acesso.py` e `habilitacao.py` = classes finas sobre a navegação. Testes com um `DriverFake` próprio (árvore de frames + elementos roteirizados) — sem Selenium real, CI multiplataforma.

**Tech Stack:** Python 3.10+, Selenium (dependência do núcleo, já usada pelo `sei`), pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-08-05-esiape-fundacao-design.md`

## Global Constraints

- Padrões da lib: logging stdlib (`_log = logging.getLogger(__name__)`), exceções tipadas filhas de `EsiapeError`, type hints, docstrings PT, nenhum dado pessoal/órgão embutido, mensagens honestas (nunca declarar sucesso sem confirmação).
- Mecânicas CIS vêm dos módulos privados VALIDADOS AO VIVO (03-04/08/2026) — não "melhorar" sequências sem verificação ao vivo.
- Venv do repo SEMPRE: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe`; suíte (`-m pytest -q`) e `-m ruff check .` verdes ao final de cada task.
- Flag de relogin: atributo `_esiape_relogin_pendente` no driver; SÓ é setada quando `garantir_menu` clica AVANÇAR; SÓ é limpa por `limpar_flag_relogin` (chamada por `TrocaHabilitacaoEsiape.trocar` ao confirmar).
- Seletores exatos (constantes de `navegacao.py`): `SELETOR_LUPA='[data-testtoolid="onMenuClickPesqTrans"]'`, `SELETOR_CAMPO_TRANSACAO='[data-testtoolid="w_transacao"]'`, `SELETOR_BTN_IR='[data-testtoolid="onMenuClickBtnIr"]'`, `SELETOR_HOME='[data-testtoolid="onMenuClickHome"]'`, `SELETOR_OVERLAY="#OPA, .FLASHPageSwitch"`, `SELETOR_BTN_AVANCAR='[data-testtoolid="meucert.onCheck"]'`, `SELETOR_BTN_PULAR='[data-testtoolid="onClickBtnPular"]'`, `SELETOR_POPUP_FECHAR="td[id^='TITLEBAR'][id$='CLOSE']"`.
- Commits em PT no padrão do repo (`feat(esiape): ...`).

## File Structure

- Create: `integra_gov/esiape/__init__.py` — exports.
- Create: `integra_gov/esiape/exceptions.py` — `EsiapeError` + 4 filhas.
- Create: `integra_gov/esiape/navegacao.py` — alicerce CIS (Tasks 2-5).
- Create: `integra_gov/esiape/habilitacao.py` — `TrocaHabilitacaoEsiape`.
- Create: `integra_gov/esiape/acesso.py` — `AcessoEsiape`.
- Create: `tests/test_esiape_navegacao.py` — `DriverFake` + testes da navegação.
- Create: `tests/test_esiape_habilitacao.py`, `tests/test_esiape_acesso.py`.
- Modify: `README.md`, `docs/uso-basico.md`, `CHANGELOG.md`.

---

### Task 1: Subpacote + exceções

**Files:**
- Create: `integra_gov/esiape/__init__.py`
- Create: `integra_gov/esiape/exceptions.py`
- Test: `tests/test_esiape_navegacao.py` (criado aqui; recebe os demais testes depois)

**Interfaces:**
- Produces: `EsiapeError`; `MenuInacessivel`; `AutenticacaoNaoConfirmada`; `TransacaoNaoAbriu(transacao: str, seletor_confirmacao: str)` com atributos homônimos; `HabilitacaoNaoEncontrada(orgao: str, codigos_visiveis: list[str])` com atributos homônimos. Tasks 4-7 usam esses nomes.

- [ ] **Step 1: Write the failing tests** — criar `tests/test_esiape_navegacao.py`:

```python
"""Testes de ``integra_gov.esiape`` — navegação CIS com DriverFake."""

from __future__ import annotations

from integra_gov.esiape.exceptions import (
    AutenticacaoNaoConfirmada,
    EsiapeError,
    HabilitacaoNaoEncontrada,
    MenuInacessivel,
    TransacaoNaoAbriu,
)


def test_excecoes_sao_esiape_error():
    for exc in (MenuInacessivel, AutenticacaoNaoConfirmada,
                TransacaoNaoAbriu, HabilitacaoNaoEncontrada):
        assert issubclass(exc, EsiapeError)


def test_transacao_nao_abriu_carrega_contexto():
    exc = TransacaoNaoAbriu("TROCAHAB", '[data-testtoolid="x"]')
    assert exc.transacao == "TROCAHAB"
    assert exc.seletor_confirmacao == '[data-testtoolid="x"]'
    assert "TROCAHAB" in str(exc)


def test_habilitacao_nao_encontrada_lista_codigos():
    exc = HabilitacaoNaoEncontrada("00000", ["11111", "22222"])
    assert exc.orgao == "00000"
    assert exc.codigos_visiveis == ["11111", "22222"]
    assert "11111" in str(exc)
```

- [ ] **Step 2: Run to verify FAIL** — `<venv> -m pytest tests/test_esiape_navegacao.py -v` → `ModuleNotFoundError: integra_gov.esiape`

- [ ] **Step 3: Implement** — `integra_gov/esiape/exceptions.py`:

```python
"""Exceções tipadas do subpacote e-SIAPE."""

from __future__ import annotations


class EsiapeError(Exception):
    """Base de todos os erros do e-SIAPE."""


class MenuInacessivel(EsiapeError):
    """O menu (lupa de transações) não ficou acessível nem após a máquina de
    estados de recuperação. Se a sessão renasceu, o PIN do certificado pode
    estar sendo pedido numa janela do Windows (fora do alcance do Selenium)."""


class AutenticacaoNaoConfirmada(EsiapeError):
    """A confirmação no app SERPRO ID não chegou dentro do timeout."""


class TransacaoNaoAbriu(EsiapeError):
    """A tela da transação não confirmou (o seletor exclusivo não apareceu).

    Attributes:
        transacao: código da transação pedida.
        seletor_confirmacao: seletor CSS que deveria ter aparecido.
    """

    def __init__(self, transacao: str, seletor_confirmacao: str):
        self.transacao = transacao
        self.seletor_confirmacao = seletor_confirmacao
        super().__init__(
            f"a tela da transação {transacao} não abriu "
            f"(sem {seletor_confirmacao} em nenhum frame visível)"
        )


class HabilitacaoNaoEncontrada(EsiapeError):
    """O órgão pedido não está na grade de habilitações do usuário.

    Attributes:
        orgao: órgão pedido.
        codigos_visiveis: códigos que a grade mostrou.
    """

    def __init__(self, orgao: str, codigos_visiveis: list[str]):
        self.orgao = orgao
        self.codigos_visiveis = list(codigos_visiveis)
        super().__init__(
            f"habilitação para o órgão {orgao} não encontrada na grade "
            f"(códigos visíveis: {', '.join(self.codigos_visiveis) or 'nenhum'})"
        )
```

`integra_gov/esiape/__init__.py` (por ora só exceções; cresce nas tasks seguintes):

```python
"""Automação do e-SIAPE web (CIS/Software AG) — fundação.

Navegação por frames visíveis, travessia de popups/relogin do SERPRO,
acesso via SERPRO ID (você autentica) e troca de habilitação (TROCAHAB).
"""

from .exceptions import (
    AutenticacaoNaoConfirmada,
    EsiapeError,
    HabilitacaoNaoEncontrada,
    MenuInacessivel,
    TransacaoNaoAbriu,
)

__all__ = [
    "AutenticacaoNaoConfirmada",
    "EsiapeError",
    "HabilitacaoNaoEncontrada",
    "MenuInacessivel",
    "TransacaoNaoAbriu",
]
```

- [ ] **Step 4: Run to verify PASS** — 3 passed.
- [ ] **Step 5: Suite + ruff + commit**

```bash
git add integra_gov/esiape tests/test_esiape_navegacao.py
git commit -m "feat(esiape): subpacote novo com excecoes tipadas"
```

---

### Task 2: `DriverFake` + busca em frames visíveis

**Files:**
- Create: `integra_gov/esiape/navegacao.py`
- Test: `tests/test_esiape_navegacao.py` (append)

**Interfaces:**
- Produces (módulo `navegacao`): constantes de seletor (ver Global Constraints); `frames_visiveis(driver, ...)`, `ir_para_frame(driver, caminho) -> bool`, `procurar_em_frames(driver, seletor) -> tuple | None`, `esperar_seletor(driver, seletor, timeout=20, intervalo=0.5) -> tuple | None`.
- Produces (teste): `ElementoFake`, `FrameFake`, `DriverFake` — TODOS os testes esiape usam estes fakes; Tasks 3-7 os reutilizam sem redefinir.

- [ ] **Step 1: Write the failing tests** (append; inclui os fakes completos):

```python
import pytest

from integra_gov.esiape import navegacao as nav


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)


class ElementoFake:
    """Elemento DOM roteirizado (visibilidade, atributos, texto, cliques)."""

    def __init__(self, visivel=True, atributos=None, texto=""):
        self.visivel = visivel
        self.atributos = atributos or {}
        self.text = texto
        self.cliques = 0
        self.teclas = []

    def is_displayed(self):
        return self.visivel

    def get_attribute(self, nome):
        return self.atributos.get(nome)

    def click(self):
        self.cliques += 1

    def clear(self):
        pass

    def send_keys(self, *teclas):
        self.teclas.extend(teclas)


class FrameFake:
    """Nó da árvore de frames: filhos (iframes) + elementos por seletor."""

    def __init__(self, nome="", visivel=True):
        self.nome = nome
        self.visivel = visivel
        self.filhos: list[FrameFake] = []
        self.elementos: dict[str, list[ElementoFake]] = {}


class _SwitchToFake:
    def __init__(self, driver):
        self._d = driver

    def default_content(self):
        self._d._caminho = []

    def parent_frame(self):
        if self._d._caminho:
            self._d._caminho.pop()

    def frame(self, ref):
        atual = self._d._frame_atual()
        if isinstance(ref, ElementoFake):
            self._d._caminho.append(self._d._indice_do_iframe[id(ref)])
            return
        for i, filho in enumerate(atual.filhos):
            if ref in (filho.nome, i):
                self._d._caminho.append(i)
                return
        raise Exception(f"no such frame: {ref}")

    def window(self, handle):
        self._d.janela_atual = handle


class DriverFake:
    """Driver Selenium roteirizado sobre uma árvore de FrameFake."""

    def __init__(self, raiz: FrameFake):
        self.raiz = raiz
        self._caminho: list[int] = []
        self._indice_do_iframe: dict[int, int] = {}
        self.switch_to = _SwitchToFake(self)
        self.window_handles = ["principal"]
        self.janela_atual = "principal"
        self.fechadas: list[str] = []
        self.scripts: list[str] = []
        self.resultado_script = None  # valor fixo OU callable(script, *args)
        self.url = ""

    # -- infraestrutura --
    def _frame_atual(self) -> FrameFake:
        frame = self.raiz
        for i in self._caminho:
            frame = frame.filhos[i]
        return frame

    # -- API Selenium usada pela navegação --
    def find_elements(self, by, valor):
        atual = self._frame_atual()
        if valor == "iframe":
            saida = []
            for i, filho in enumerate(atual.filhos):
                el = ElementoFake(visivel=filho.visivel,
                                  atributos={"name": filho.nome, "id": filho.nome})
                self._indice_do_iframe[id(el)] = i
                saida.append(el)
            return saida
        return atual.elementos.get(valor, [])

    def find_element(self, by, valor):
        els = self.find_elements(by, valor)
        if not els:
            raise Exception(f"no such element: {valor}")
        return els[0]

    def execute_script(self, script, *args):
        self.scripts.append(script)
        if callable(self.resultado_script):
            return self.resultado_script(script, *args)
        return self.resultado_script

    @property
    def current_window_handle(self):
        return self.janela_atual

    def close(self):
        self.fechadas.append(self.janela_atual)
        self.window_handles = [h for h in self.window_handles
                               if h != self.janela_atual]

    def get(self, url):
        self.url = url


def _arvore_menu(com_lupa=True):
    """Raiz com WA0 oculto (tela velha COM lupa) e WA1 visível."""
    raiz = FrameFake()
    wa0 = FrameFake("WA0", visivel=False)
    wa0.elementos[nav.SELETOR_LUPA] = [ElementoFake()]  # tela morta!
    wa1 = FrameFake("WA1", visivel=True)
    if com_lupa:
        wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]
    raiz.filhos = [wa0, wa1]
    return raiz


def test_procurar_ignora_frame_oculto_com_o_seletor():
    driver = DriverFake(_arvore_menu(com_lupa=True))
    caminho = nav.procurar_em_frames(driver, nav.SELETOR_LUPA)
    assert caminho == ("WA1",)  # achou no visível, NUNCA no WA0 oculto


def test_procurar_devolve_none_sem_seletor_visivel():
    driver = DriverFake(_arvore_menu(com_lupa=False))
    assert nav.procurar_em_frames(driver, nav.SELETOR_LUPA) is None


def test_esperar_seletor_timeout_devolve_none():
    driver = DriverFake(_arvore_menu(com_lupa=False))
    assert nav.esperar_seletor(driver, nav.SELETOR_LUPA, timeout=0.05) is None
```

- [ ] **Step 2: Run to verify FAIL** — `ModuleNotFoundError`/`AttributeError` em `navegacao`.

- [ ] **Step 3: Implement** — `integra_gov/esiape/navegacao.py`:

```python
"""Navegação nas telas CIS do e-SIAPE (frames, popups, relogin, transações).

Mecânicas validadas ao vivo (03-04/08/2026):
- os iframes WA0/WA1/WA2 se REVEZAM e o CIS mantém as telas anteriores vivas
  nos ocultos — só o frame VISÍVEL é a tela atual;
- popups modais (ex.: aviso "UORG DO CORREIO...") fecham pelo X da barra de
  título, que fica no documento do TOPO — esconder via CSS não libera;
- a tela de relogin do SERPRO (AVANÇAR) significa sessão nova: a habilitação
  volta ao padrão do usuário e fica PENDENTE de re-troca (flag no driver).
"""

from __future__ import annotations

import logging
import time

from selenium.webdriver.common.by import By

_log = logging.getLogger(__name__)

SELETOR_LUPA = '[data-testtoolid="onMenuClickPesqTrans"]'
SELETOR_CAMPO_TRANSACAO = '[data-testtoolid="w_transacao"]'
SELETOR_BTN_IR = '[data-testtoolid="onMenuClickBtnIr"]'
SELETOR_HOME = '[data-testtoolid="onMenuClickHome"]'
SELETOR_OVERLAY = "#OPA, .FLASHPageSwitch"
SELETOR_BTN_AVANCAR = '[data-testtoolid="meucert.onCheck"]'
SELETOR_BTN_PULAR = '[data-testtoolid="onClickBtnPular"]'
SELETOR_POPUP_FECHAR = "td[id^='TITLEBAR'][id$='CLOSE']"

_PROFUNDIDADE_MAXIMA = 4


def frames_visiveis(driver, caminho=(), saida=None, prof=0):
    """Caminhos (tuplas de nomes) de todos os frames VISÍVEIS, em profundidade.

    Frames ocultos guardam telas ANTIGAS com dados velhos — são ignorados.
    """
    saida = saida if saida is not None else []
    saida.append(caminho)
    if prof > _PROFUNDIDADE_MAXIMA:
        return saida
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
    except Exception:
        return saida
    for i, frame in enumerate(iframes):
        try:
            if not frame.is_displayed():
                continue
            nome = (frame.get_attribute("name")
                    or frame.get_attribute("id") or f"idx{i}")
            driver.switch_to.frame(frame)
            frames_visiveis(driver, caminho + (nome,), saida, prof + 1)
            driver.switch_to.parent_frame()
        except Exception:
            try:
                driver.switch_to.parent_frame()
            except Exception:
                pass
    return saida


def ir_para_frame(driver, caminho) -> bool:
    """Posiciona o driver no frame do ``caminho``; ``False`` se ele sumiu."""
    driver.switch_to.default_content()
    for nome in caminho:
        try:
            driver.switch_to.frame(nome)
        except Exception:
            achou = False
            for el in driver.find_elements(By.TAG_NAME, "iframe"):
                if (el.get_attribute("name") or el.get_attribute("id")) == nome:
                    driver.switch_to.frame(el)
                    achou = True
                    break
            if not achou:
                return False
    return True


def procurar_em_frames(driver, seletor_css: str):
    """1º frame VISÍVEL contendo o seletor (deixa o driver NELE) ou ``None``.

    Sempre re-enumera do topo: uma busca anterior deixa o driver dentro de um
    frame, e enumerar dali produziria caminhos relativos inválidos.
    """
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    for caminho in frames_visiveis(driver):
        if not ir_para_frame(driver, caminho):
            continue
        try:
            if driver.find_elements(By.CSS_SELECTOR, seletor_css):
                return caminho
        except Exception:
            continue
    return None


def esperar_seletor(driver, seletor_css: str, timeout: float = 20,
                    intervalo: float = 0.5):
    """Espera o seletor aparecer em algum frame visível; caminho ou ``None``."""
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        caminho = procurar_em_frames(driver, seletor_css)
        if caminho is not None:
            return caminho
        time.sleep(intervalo)
    return None
```

- [ ] **Step 4: Run to verify PASS** — 6 passed no arquivo.
- [ ] **Step 5: Suite + ruff + commit**

```bash
git add integra_gov/esiape/navegacao.py tests/test_esiape_navegacao.py
git commit -m "feat(esiape): busca de elementos restrita a frames visiveis (telas mortas ignoradas)"
```

---

### Task 3: Overlay, janelas extras e popups modais

**Files:**
- Modify: `integra_gov/esiape/navegacao.py`
- Test: `tests/test_esiape_navegacao.py` (append)

**Interfaces:**
- Produces: `overlay_presente(driver) -> bool`, `limpar_overlay(driver, timeout=10) -> bool`, `fechar_janelas_extras(driver, handle_principal=None) -> str | None`, `fechar_popups_cis(driver) -> int`. Task 4 usa `fechar_popups_cis`; Task 5 usa `limpar_overlay`.

- [ ] **Step 1: Write the failing tests** (append):

```python
def test_limpar_overlay_esconde_cortina_presa():
    driver = DriverFake(FrameFake())
    # 1ª consulta: cortina presente; após o JS de esconder: ausente
    respostas = iter([True, True, 0, False])  # presente, presente, esconde, sumiu

    def roteiro(script, *args):
        return next(respostas)

    driver.resultado_script = roteiro
    assert nav.limpar_overlay(driver, timeout=0.05) is True


def test_limpar_overlay_sem_cortina_retorna_imediato():
    driver = DriverFake(FrameFake())
    driver.resultado_script = False  # overlay_presente() -> False
    assert nav.limpar_overlay(driver, timeout=0.05) is True
    assert len(driver.scripts) == 1  # não tentou esconder


def test_fechar_janelas_extras_fecha_e_volta_ao_principal():
    driver = DriverFake(FrameFake())
    driver.window_handles = ["principal", "popup1", "popup2"]
    principal = nav.fechar_janelas_extras(driver, "principal")
    assert principal == "principal"
    assert driver.fechadas == ["popup1", "popup2"]
    assert driver.janela_atual == "principal"


def test_fechar_popups_cis_clica_o_x_do_topo():
    raiz = FrameFake()
    x = ElementoFake(atributos={"id": "TITLEBAR0_2CLOSE"})
    raiz.elementos[nav.SELETOR_POPUP_FECHAR] = [x]
    driver = DriverFake(raiz)
    assert nav.fechar_popups_cis(driver) == 1
    assert x.cliques == 1


def test_fechar_popups_cis_ignora_x_invisivel():
    raiz = FrameFake()
    raiz.elementos[nav.SELETOR_POPUP_FECHAR] = [ElementoFake(visivel=False)]
    driver = DriverFake(raiz)
    assert nav.fechar_popups_cis(driver) == 0
```

- [ ] **Step 2: Run to verify FAIL** — `AttributeError: ... 'limpar_overlay'`.

- [ ] **Step 3: Implement** (adicionar a `navegacao.py`):

```python
def overlay_presente(driver) -> bool:
    """True se a cortina de transição do CIS está visível no topo."""
    try:
        driver.switch_to.default_content()
        return bool(driver.execute_script(
            """
            return [...document.querySelectorAll(arguments[0])].some(e => {
                const s = getComputedStyle(e);
                return s.display !== 'none' && s.visibility !== 'hidden' &&
                       e.offsetWidth > 0 && e.offsetHeight > 0;
            });
            """,
            SELETOR_OVERLAY,
        ))
    except Exception:
        return False


def limpar_overlay(driver, timeout: float = 10) -> bool:
    """Espera a cortina do CIS sumir; se ficar presa, esconde via JS.

    A cortina presa intercepta TODO clique ("element click intercepted") e
    derruba o lote inteiro; escondê-la é seguro — é decorativa.
    """
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if not overlay_presente(driver):
            return True
        time.sleep(0.3)
    try:
        driver.switch_to.default_content()
        escondidos = driver.execute_script(
            """
            const els = [...document.querySelectorAll(arguments[0])];
            els.forEach(e => { e.style.display = 'none'; });
            return els.length;
            """,
            SELETOR_OVERLAY,
        )
        _log.warning("Cortina de transição presa — escondida via JS "
                     "(%s elemento(s))", escondidos)
        return not overlay_presente(driver)
    except Exception as exc:
        _log.error("Falha ao limpar a cortina: %s", exc)
        return False


def fechar_janelas_extras(driver, handle_principal=None):
    """Fecha toda janela além da principal e devolve o foco a ela.

    Janelas de impressão órfãs acumulam e quebram a sessão ("Browser window
    not found" + cortina presa). Retorna o handle principal (ou ``None``).
    """
    try:
        handles = driver.window_handles
        if not handles:
            return None
        principal = (handle_principal if handle_principal in handles
                     else handles[0])
        extras = [h for h in handles if h != principal]
        for handle in extras:
            try:
                driver.switch_to.window(handle)
                driver.close()
            except Exception:
                pass
        driver.switch_to.window(principal)
        if extras:
            _log.warning("%d janela(s) extra(s) fechada(s)", len(extras))
        return principal
    except Exception as exc:
        _log.warning("Falha ao fechar janelas extras: %s", exc)
        return handle_principal


def fechar_popups_cis(driver) -> int:
    """Fecha page-popups modais do CIS pelo X da barra de título (no TOPO).

    O aviso "UORG DO CORREIO DO USUARIO DESATIVADA" (e afins) bloqueia a
    navegação até ser FECHADO — esconder via CSS não conta como lido.
    Retorna quantos popups foram fechados.
    """
    try:
        driver.switch_to.default_content()
        fechados = 0
        for el in driver.find_elements(By.CSS_SELECTOR, SELETOR_POPUP_FECHAR):
            try:
                if el.is_displayed():
                    el.click()
                    fechados += 1
                    time.sleep(0.5)
            except Exception:
                pass
        if fechados:
            _log.info("%d popup(s) modal(is) fechado(s) pelo X", fechados)
        return fechados
    except Exception:
        return 0
```

- [ ] **Step 4: Run to verify PASS** — 11 passed no arquivo.
- [ ] **Step 5: Suite + ruff + commit**

```bash
git add integra_gov/esiape/navegacao.py tests/test_esiape_navegacao.py
git commit -m "feat(esiape): overlay preso, janelas extras e popups modais do CIS"
```

---

### Task 4: `garantir_menu` + flag de relogin

**Files:**
- Modify: `integra_gov/esiape/navegacao.py`
- Test: `tests/test_esiape_navegacao.py` (append)

**Interfaces:**
- Produces: `garantir_menu(driver, timeout=60) -> bool`, `relogin_pendente(driver) -> bool`, `limpar_flag_relogin(driver) -> None`. Tasks 5-7 consomem os três.

- [ ] **Step 1: Write the failing tests** (append):

```python
def _com_elemento(seletor, *, frame="WA1"):
    """Raiz com um único frame visível contendo o seletor."""
    raiz = FrameFake()
    f = FrameFake(frame, visivel=True)
    el = ElementoFake()
    f.elementos[seletor] = [el]
    raiz.filhos = [f]
    return raiz, el


def test_garantir_menu_ja_no_menu_nao_seta_flag():
    raiz, _ = _com_elemento(nav.SELETOR_LUPA)
    driver = DriverFake(raiz)
    driver.resultado_script = False
    assert nav.garantir_menu(driver, timeout=0.5) is True
    assert nav.relogin_pendente(driver) is False


def test_garantir_menu_relogin_completo_seta_flag():
    """AVANÇAR → popup UORG (fechar pelo X) → Pular → lupa."""
    raiz = FrameFake()
    wa1 = FrameFake("WA1", visivel=True)
    avancar = ElementoFake()
    wa1.elementos[nav.SELETOR_BTN_AVANCAR] = [avancar]
    raiz.filhos = [wa1]
    driver = DriverFake(raiz)
    driver.resultado_script = False

    x_popup = ElementoFake(atributos={"id": "TITLEBAR0_2CLOSE"})
    pular = ElementoFake()
    lupa = ElementoFake()

    estado = {"passo": 0}
    _click_avancar = avancar.click

    def avancar_click():
        _click_avancar()
        # clicar AVANÇAR abre o popup modal no TOPO
        raiz.elementos[nav.SELETOR_POPUP_FECHAR] = [x_popup]
        estado["passo"] = 1

    avancar.click = avancar_click

    _click_x = x_popup.click

    def x_click():
        _click_x()
        # fechar o popup revela a tela do Pular
        raiz.elementos[nav.SELETOR_POPUP_FECHAR] = []
        del wa1.elementos[nav.SELETOR_BTN_AVANCAR]
        wa1.elementos[nav.SELETOR_BTN_PULAR] = [pular]

    x_popup.click = x_click

    _click_pular = pular.click

    def pular_click():
        _click_pular()
        del wa1.elementos[nav.SELETOR_BTN_PULAR]
        wa1.elementos[nav.SELETOR_LUPA] = [lupa]

    pular.click = pular_click

    assert nav.garantir_menu(driver, timeout=5) is True
    assert avancar.cliques == 1
    assert x_popup.cliques == 1
    assert pular.cliques == 1
    assert nav.relogin_pendente(driver) is True
    nav.limpar_flag_relogin(driver)
    assert nav.relogin_pendente(driver) is False


def test_garantir_menu_popup_perdido_sem_avancar_nao_seta_flag():
    raiz, lupa_el = _com_elemento(nav.SELETOR_LUPA)
    x_popup = ElementoFake(atributos={"id": "TITLEBAR0_4CLOSE"})
    raiz.elementos[nav.SELETOR_POPUP_FECHAR] = [x_popup]

    _click_x = x_popup.click

    def x_click():
        _click_x()
        raiz.elementos[nav.SELETOR_POPUP_FECHAR] = []

    x_popup.click = x_click
    driver = DriverFake(raiz)
    driver.resultado_script = False
    assert nav.garantir_menu(driver, timeout=5) is True
    assert x_popup.cliques == 1
    assert nav.relogin_pendente(driver) is False


def test_garantir_menu_popup_respawn_converge():
    """O popup reaparece 2x após fechado (visto ao vivo) — o laço converge."""
    raiz, _lupa = _com_elemento(nav.SELETOR_LUPA)
    x_popup = ElementoFake(atributos={"id": "TITLEBAR0_2CLOSE"})
    raiz.elementos[nav.SELETOR_POPUP_FECHAR] = [x_popup]

    _click_x = x_popup.click

    def x_click():
        _click_x()
        if x_popup.cliques >= 3:  # respawnou 2x; na 3ª fecha de vez
            raiz.elementos[nav.SELETOR_POPUP_FECHAR] = []

    x_popup.click = x_click
    driver = DriverFake(raiz)
    driver.resultado_script = False
    assert nav.garantir_menu(driver, timeout=5) is True
    assert x_popup.cliques == 3
    assert nav.relogin_pendente(driver) is False


def test_garantir_menu_timeout_devolve_false():
    driver = DriverFake(FrameFake())  # nada reconhecível
    driver.resultado_script = False
    assert nav.garantir_menu(driver, timeout=0.05) is False
```

- [ ] **Step 2: Run to verify FAIL** — `AttributeError: ... 'garantir_menu'`.

- [ ] **Step 3: Implement** (adicionar a `navegacao.py`):

```python
def relogin_pendente(driver) -> bool:
    """True se um relogin foi atravessado e a habilitação NÃO foi refeita.

    Sessão nova = habilitação de volta ao PADRÃO do usuário. Consultar outro
    órgão nesse estado devolve "sem dados" FALSO (lacuna silenciosa). Quem
    conhece o órgão em uso re-troca a habilitação e limpa a flag.
    """
    return bool(getattr(driver, "_esiape_relogin_pendente", False))


def limpar_flag_relogin(driver) -> None:
    """Marca a pendência de re-habilitação pós-relogin como sanada."""
    driver._esiape_relogin_pendente = False


def garantir_menu(driver, timeout: float = 60) -> bool:
    """Leva a sessão até o menu (lupa acessível), atravessando o que houver.

    Máquina de estados validada ao vivo: a cada passo fecha popup modal pelo
    X, OU clica Pular, OU clica AVANÇAR (tela de relogin do SERPRO — seta a
    flag de relogin), até a lupa reaparecer. ``False`` no timeout (se a
    sessão renasceu, o PIN do certificado pode estar sendo pedido em janela
    do Windows, fora do alcance do Selenium).
    """
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if fechar_popups_cis(driver):
            time.sleep(1.5)
            continue
        if procurar_em_frames(driver, SELETOR_LUPA) is not None:
            return True
        try:
            if procurar_em_frames(driver, SELETOR_BTN_PULAR) is not None:
                driver.find_element(By.CSS_SELECTOR, SELETOR_BTN_PULAR).click()
                _log.info("Botão 'Pular' clicado")
                time.sleep(2)
                continue
            if procurar_em_frames(driver, SELETOR_BTN_AVANCAR) is not None:
                driver.find_element(By.CSS_SELECTOR, SELETOR_BTN_AVANCAR).click()
                driver._esiape_relogin_pendente = True
                _log.warning("Tela de relogin atravessada (AVANÇAR) — "
                             "habilitação PENDENTE de re-troca")
                time.sleep(2)
                continue
        except Exception as exc:
            _log.warning("Clique falhou na travessia (%s) — tentando de novo",
                         exc)
        time.sleep(1.5)
    _log.error("Menu (lupa) não ficou acessível em %.0fs (PIN do certificado "
               "pode estar sendo pedido na janela do Windows)", timeout)
    return False
```

- [ ] **Step 4: Run to verify PASS** — 16 passed no arquivo.
- [ ] **Step 5: Suite + ruff + commit**

```bash
git add integra_gov/esiape/navegacao.py tests/test_esiape_navegacao.py
git commit -m "feat(esiape): garantir_menu atravessa popups/relogin e sinaliza habilitacao pendente"
```

---

### Task 5: `navegar_para_transacao`

**Files:**
- Modify: `integra_gov/esiape/navegacao.py`
- Test: `tests/test_esiape_navegacao.py` (append)

**Interfaces:**
- Produces: `navegar_para_transacao(driver, transacao, seletor_confirmacao, timeout=30) -> bool` — `True` SOMENTE se o seletor da tela-destino apareceu; sem lupa → `garantir_menu`; relogin pendente → falha a tentativa de propósito. Tasks 6-7 a consomem.

- [ ] **Step 1: Write the failing tests** (append):

```python
def _arvore_transacao(seletor_confirmacao):
    """Menu completo: lupa + campo + Ir; clicar Ir abre a tela-destino."""
    raiz = FrameFake()
    wa1 = FrameFake("WA1", visivel=True)
    lupa, campo, ir = ElementoFake(), ElementoFake(), ElementoFake()
    wa1.elementos[nav.SELETOR_LUPA] = [lupa]
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [campo]
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]
    raiz.filhos = [wa1]

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos[seletor_confirmacao] = [ElementoFake()]

    ir.click = ir_click
    return raiz, campo


SELETOR_TELA_X = '[data-testtoolid="telaX"]'


def test_navegar_confirma_pelo_seletor_da_tela():
    raiz, campo = _arvore_transacao(SELETOR_TELA_X)
    driver = DriverFake(raiz)
    driver.resultado_script = False
    assert nav.navegar_para_transacao(driver, "TRANSX", SELETOR_TELA_X,
                                      timeout=1) is True
    assert "TRANSX" in campo.teclas


def test_navegar_tela_nao_abriu_devolve_false():
    raiz = FrameFake()
    wa1 = FrameFake("WA1", visivel=True)
    wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_BTN_IR] = [ElementoFake()]  # Ir não abre nada
    raiz.filhos = [wa1]
    driver = DriverFake(raiz)
    driver.resultado_script = False
    assert nav.navegar_para_transacao(driver, "TRANSX", SELETOR_TELA_X,
                                      timeout=0.05) is False


def test_navegar_apos_relogin_falha_de_proposito_com_flag():
    """Sem lupa + tela de AVANÇAR: atravessa, mas FALHA a tentativa."""
    raiz = FrameFake()
    wa1 = FrameFake("WA1", visivel=True)
    avancar = ElementoFake()
    wa1.elementos[nav.SELETOR_BTN_AVANCAR] = [avancar]
    raiz.filhos = [wa1]
    driver = DriverFake(raiz)
    driver.resultado_script = False

    _click = avancar.click

    def avancar_click():
        _click()
        del wa1.elementos[nav.SELETOR_BTN_AVANCAR]
        wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]

    avancar.click = avancar_click

    assert nav.navegar_para_transacao(driver, "TRANSX", SELETOR_TELA_X,
                                      timeout=1) is False
    assert nav.relogin_pendente(driver) is True  # chamador deve re-habilitar


def test_navegar_popup_perdido_recupera_e_segue():
    raiz, _campo = _arvore_transacao(SELETOR_TELA_X)
    x_popup = ElementoFake(atributos={"id": "TITLEBAR0_9CLOSE"})
    raiz.elementos[nav.SELETOR_POPUP_FECHAR] = [x_popup]
    wa1 = raiz.filhos[0]
    lupa_backup = wa1.elementos.pop(nav.SELETOR_LUPA)  # popup "esconde" a lupa

    _click_x = x_popup.click

    def x_click():
        _click_x()
        raiz.elementos[nav.SELETOR_POPUP_FECHAR] = []
        wa1.elementos[nav.SELETOR_LUPA] = lupa_backup

    x_popup.click = x_click
    driver = DriverFake(raiz)
    driver.resultado_script = False
    assert nav.navegar_para_transacao(driver, "TRANSX", SELETOR_TELA_X,
                                      timeout=1) is True
    assert nav.relogin_pendente(driver) is False
```

- [ ] **Step 2: Run to verify FAIL** — `AttributeError: ... 'navegar_para_transacao'`.

- [ ] **Step 3: Implement** (adicionar a `navegacao.py`):

```python
def navegar_para_transacao(driver, transacao: str, seletor_confirmacao: str,
                           timeout: float = 30) -> bool:
    """Abre uma transação pelo atalho do cabeçalho: lupa → campo → Ir.

    ``True`` SOMENTE quando ``seletor_confirmacao`` (exclusivo da tela-
    destino) apareceu num frame visível — nunca falso positivo. Sem lupa,
    :func:`garantir_menu` atravessa popups/relogin; se um RELOGIN foi
    atravessado, esta tentativa FALHA de propósito (a habilitação voltou ao
    padrão; seguir consultaria o órgão errado — ver
    :func:`relogin_pendente`).
    """
    try:
        limpar_overlay(driver)
        if procurar_em_frames(driver, SELETOR_LUPA) is None:
            if not garantir_menu(driver):
                _log.error("Lupa de transação não encontrada")
                return False
            if relogin_pendente(driver):
                _log.warning("%s: tentativa abortada após relogin — refazer a "
                             "habilitação antes de repetir", transacao)
                return False
        driver.find_element(By.CSS_SELECTOR, SELETOR_LUPA).click()
        time.sleep(1.0)
        campo = driver.find_element(By.CSS_SELECTOR, SELETOR_CAMPO_TRANSACAO)
        campo.clear()
        campo.send_keys(transacao)
        botoes = driver.find_elements(By.CSS_SELECTOR, SELETOR_BTN_IR)
        (botoes[0] if botoes else campo).click()
        _log.info("Navegando para a transação %s...", transacao)
    except Exception as exc:
        _log.error("Falha ao navegar para %s: %s", transacao, exc)
        return False

    if esperar_seletor(driver, seletor_confirmacao, timeout=timeout) is None:
        _log.error("%s: a tela não abriu (sem %s em %.0fs)",
                   transacao, seletor_confirmacao, timeout)
        return False
    _log.info("Tela da transação %s aberta", transacao)
    return True
```

- [ ] **Step 4: Run to verify PASS** — 20 passed no arquivo.
- [ ] **Step 5: Suite + ruff + commit**

```bash
git add integra_gov/esiape/navegacao.py tests/test_esiape_navegacao.py
git commit -m "feat(esiape): navegar_para_transacao com confirmacao real e guarda de relogin"
```

---

### Task 6: `TrocaHabilitacaoEsiape`

**Files:**
- Create: `integra_gov/esiape/habilitacao.py`
- Test: `tests/test_esiape_habilitacao.py` (novo; importa os fakes de `test_esiape_navegacao`)

**Interfaces:**
- Consumes: `navegar_para_transacao`, `procurar_em_frames`, `esperar_seletor`, `limpar_flag_relogin` (navegacao); `TransacaoNaoAbriu`, `HabilitacaoNaoEncontrada`, `EsiapeError` (exceptions).
- Produces: `TrocaHabilitacaoEsiape(driver, orgao: str)` com `trocar() -> None`, `orgao_atual() -> str | None`; constantes `TRANSACAO="TROCAHAB"`, `SELETOR_GRADE_LINHAS="table.TEXTGRIDTable tr"`, `SELETOR_ORGAO_ATIVO='[data-testtoolid="w_menu_orgao_usu"]'`, `SELETOR_BTN_SIM='[data-testtoolid="onClickBtnSim"]'`.

- [ ] **Step 1: Write the failing tests** — criar `tests/test_esiape_habilitacao.py`:

```python
"""Testes de ``integra_gov.esiape.habilitacao`` — DriverFake roteirizado."""

from __future__ import annotations

import pytest

from integra_gov.esiape import navegacao as nav
from integra_gov.esiape import habilitacao as hab
from integra_gov.esiape.exceptions import (
    EsiapeError,
    HabilitacaoNaoEncontrada,
    TransacaoNaoAbriu,
)
from integra_gov.esiape.habilitacao import TrocaHabilitacaoEsiape
from tests.test_esiape_navegacao import DriverFake, ElementoFake, FrameFake


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(hab.time, "sleep", lambda *_a, **_k: None)


def _cabecalho(orgao_texto):
    return [ElementoFake(texto=orgao_texto)]


def _driver_menu_com_cabecalho(orgao_texto):
    raiz = FrameFake()
    wa1 = FrameFake("WA1", visivel=True)
    wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]
    wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_ORGAO_ATIVO] = \
        _cabecalho(orgao_texto)
    raiz.filhos = [wa1]
    driver = DriverFake(raiz)
    driver.resultado_script = False
    return driver, wa1


def test_idempotente_limpa_flag_e_nao_navega():
    driver, _ = _driver_menu_com_cabecalho("11111 - ORGAO DE TESTE")
    driver._esiape_relogin_pendente = True
    troca = TrocaHabilitacaoEsiape(driver, orgao="11111")
    troca.trocar()  # cabeçalho já no destino
    assert nav.relogin_pendente(driver) is False


def test_troca_completa_com_modal_e_confirmacao():
    driver, wa1 = _driver_menu_com_cabecalho("11111 - ORIGEM")
    troca = TrocaHabilitacaoEsiape(driver, orgao="22222")

    # tela TROCAHAB: grade com cabeçalho + 2 linhas
    linha_alvo = ElementoFake(texto="  22222  ORGAO  DESTINO")
    grade = [ElementoFake(texto="CABECALHO"),
             ElementoFake(texto="  11111  ORGAO  ORIGEM"), linha_alvo]
    sim = ElementoFake()
    home = ElementoFake()

    _click_alvo = linha_alvo.click

    def alvo_click():
        _click_alvo()
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_BTN_SIM] = [sim]

    linha_alvo.click = alvo_click

    _click_sim = sim.click

    def sim_click():
        _click_sim()
        # o CIS efetiva: cabeçalho passa a refletir o destino
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_ORGAO_ATIVO] = \
            _cabecalho("22222 - DESTINO")
        wa1.elementos[nav.SELETOR_HOME] = [home]

    sim.click = sim_click

    # navegar_para_transacao abre a grade (via clique no Ir)
    ir = ElementoFake()
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_GRADE_LINHAS] = grade

    ir.click = ir_click

    troca.trocar()
    assert linha_alvo.cliques == 1
    assert sim.cliques == 1
    assert troca.orgao_atual() == "22222"


def test_orgao_ausente_na_grade_levanta_com_codigos():
    driver, wa1 = _driver_menu_com_cabecalho("11111 - ORIGEM")
    grade = [ElementoFake(texto="CABECALHO"),
             ElementoFake(texto="  11111  ORGAO  ORIGEM")]
    ir = ElementoFake()
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_GRADE_LINHAS] = grade

    ir.click = ir_click

    with pytest.raises(HabilitacaoNaoEncontrada) as exc:
        TrocaHabilitacaoEsiape(driver, orgao="99999").trocar()
    assert "11111" in str(exc.value)


def test_transacao_nao_abriu_levanta():
    driver, wa1 = _driver_menu_com_cabecalho("11111 - ORIGEM")
    # sem campo/Ir: navegar_para_transacao devolve False
    with pytest.raises(TransacaoNaoAbriu):
        TrocaHabilitacaoEsiape(driver, orgao="22222").trocar()


def test_cabecalho_nao_refletiu_nao_declara_sucesso(monkeypatch):
    driver, wa1 = _driver_menu_com_cabecalho("11111 - ORIGEM")
    monkeypatch.setattr(TrocaHabilitacaoEsiape, "TIMEOUT_CONFIRMACAO", 0.05)
    troca = TrocaHabilitacaoEsiape(driver, orgao="22222")

    linha_alvo = ElementoFake(texto="  22222  ORGAO  DESTINO")
    grade = [ElementoFake(texto="CABECALHO"), linha_alvo]
    sim = ElementoFake()

    _click_alvo = linha_alvo.click

    def alvo_click():
        _click_alvo()
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_BTN_SIM] = [sim]

    linha_alvo.click = alvo_click
    # sim.click NÃO muda o cabeçalho — troca não efetivou

    ir = ElementoFake()
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos[TrocaHabilitacaoEsiape.SELETOR_GRADE_LINHAS] = grade

    ir.click = ir_click

    with pytest.raises(EsiapeError):
        troca.trocar()
```

- [ ] **Step 2: Run to verify FAIL** — `ModuleNotFoundError: ... habilitacao`.

- [ ] **Step 3: Implement** — `integra_gov/esiape/habilitacao.py`:

```python
"""Troca de habilitação (ÓRGÃO) no e-SIAPE web — transação TROCAHAB.

Mecânica validada ao vivo: a grade CIS lista as habilitações; selecionar a
linha abre o modal "Confirma ?" (frame próprio) e SÓ o "Sim" efetiva; a
troca só é declarada quando o CABEÇALHO reflete o novo órgão. Ao confirmar,
limpa a flag de relogin (ver ``navegacao.relogin_pendente``).
"""

from __future__ import annotations

import logging
import re
import time

from selenium.webdriver.common.by import By

from .exceptions import (
    EsiapeError,
    HabilitacaoNaoEncontrada,
    TransacaoNaoAbriu,
)
from .navegacao import (
    esperar_seletor,
    limpar_flag_relogin,
    navegar_para_transacao,
    procurar_em_frames,
)

_log = logging.getLogger(__name__)


class TrocaHabilitacaoEsiape:
    """Troca a habilitação de ÓRGÃO ativa na sessão do e-SIAPE web.

    Args:
        driver: WebDriver com a sessão do e-SIAPE autenticada.
        orgao: código do órgão de destino (ex.: ``"00000"``).
    """

    TRANSACAO = "TROCAHAB"
    SELETOR_GRADE_LINHAS = "table.TEXTGRIDTable tr"
    SELETOR_ORGAO_ATIVO = '[data-testtoolid="w_menu_orgao_usu"]'
    SELETOR_BTN_SIM = '[data-testtoolid="onClickBtnSim"]'
    SELETOR_HOME_MENU = '[data-testtoolid="onMenuClickHome"]'

    TIMEOUT_TELA = 20
    TIMEOUT_MODAL = 8
    TIMEOUT_CONFIRMACAO = 20
    INTERVALO_POLL = 0.25

    _PADRAO_CODIGO = re.compile(r"\b(\d{5})\b")

    def __init__(self, driver, orgao: str):
        self.driver = driver
        self.orgao = str(orgao).strip()
        if not self.orgao:
            raise ValueError("orgao é obrigatório")

    def orgao_atual(self) -> str | None:
        """Órgão ativo lido do cabeçalho (ex.: ``"99995"``); ``None`` se
        ilegível."""
        try:
            if procurar_em_frames(self.driver, self.SELETOR_ORGAO_ATIVO) is None:
                return None
            el = self.driver.find_element(By.CSS_SELECTOR,
                                          self.SELETOR_ORGAO_ATIVO)
            texto = (el.text or el.get_attribute("innerText") or "").strip()
            return texto.split("-")[0].strip() or None
        except Exception as exc:
            _log.warning("Não consegui ler o órgão ativo: %s", exc)
            return None

    def trocar(self) -> None:
        """Efetiva a troca (ou nada, se o cabeçalho já mostra o destino).

        Raises:
            TransacaoNaoAbriu: a tela TROCAHAB não confirmou.
            HabilitacaoNaoEncontrada: o órgão não está na grade.
            EsiapeError: o "Sim" não apareceu ou o cabeçalho não refletiu.
        """
        if self.orgao_atual() == self.orgao:
            _log.info("Habilitação já está no órgão %s", self.orgao)
            limpar_flag_relogin(self.driver)
            return

        if not navegar_para_transacao(self.driver, self.TRANSACAO,
                                      self.SELETOR_GRADE_LINHAS,
                                      timeout=self.TIMEOUT_TELA):
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SELETOR_GRADE_LINHAS)

        self._selecionar_linha_do_orgao()
        self._confirmar_modal()
        self._exigir_cabecalho_no_destino()
        self._voltar_ao_menu()
        limpar_flag_relogin(self.driver)
        _log.info("Habilitação trocada para o órgão %s", self.orgao)

    # ----- passos internos -----

    def _selecionar_linha_do_orgao(self) -> None:
        """Clica a linha da grade cujo código é o órgão (linha 0 = cabeçalho)."""
        linhas = self.driver.find_elements(By.CSS_SELECTOR,
                                           self.SELETOR_GRADE_LINHAS)
        codigos_vistos: list[str] = []
        for linha in linhas[1:]:
            codigos = self._PADRAO_CODIGO.findall(linha.text or "")
            if not codigos:
                continue
            if codigos[0] == self.orgao:
                linha.click()
                _log.info("Linha do órgão %s selecionada", self.orgao)
                return
            codigos_vistos.append(codigos[0])
        raise HabilitacaoNaoEncontrada(self.orgao, codigos_vistos)

    def _confirmar_modal(self) -> None:
        """O modal 'Confirma ?' (frame próprio) é quem efetiva — clica Sim."""
        if esperar_seletor(self.driver, self.SELETOR_BTN_SIM,
                           timeout=self.TIMEOUT_MODAL) is None:
            raise EsiapeError(
                "o modal 'Confirma ?' não apareceu após selecionar a linha — "
                "a troca NÃO foi efetivada"
            )
        self.driver.find_element(By.CSS_SELECTOR, self.SELETOR_BTN_SIM).click()
        time.sleep(0.5)

    def _exigir_cabecalho_no_destino(self) -> None:
        """Sucesso SÓ quando o cabeçalho reflete o novo órgão."""
        limite = time.monotonic() + self.TIMEOUT_CONFIRMACAO
        while time.monotonic() < limite:
            atual = self.orgao_atual()
            if atual == self.orgao:
                return
            time.sleep(self.INTERVALO_POLL)
        raise EsiapeError(
            f"cliquei 'Sim' mas o cabeçalho não refletiu o órgão "
            f"{self.orgao} em {self.TIMEOUT_CONFIRMACAO}s "
            f"(atual: {self.orgao_atual()!r}) — troca NÃO confirmada"
        )

    def _voltar_ao_menu(self) -> None:
        """Deixa a sessão no menu (best-effort; falha não mascara a troca)."""
        try:
            if procurar_em_frames(self.driver, self.SELETOR_HOME_MENU) is None:
                return
            self.driver.find_element(By.CSS_SELECTOR,
                                     self.SELETOR_HOME_MENU).click()
            time.sleep(1.2)
            self.driver.switch_to.default_content()
        except Exception as exc:
            _log.warning("Falha ao voltar ao menu (ignorada): %s", exc)
```

- [ ] **Step 4: Run to verify PASS** — 5 passed no arquivo novo.
- [ ] **Step 5: Suite + ruff + commit**

```bash
git add integra_gov/esiape/habilitacao.py tests/test_esiape_habilitacao.py
git commit -m "feat(esiape): TrocaHabilitacaoEsiape com modal Confirma e confirmacao pelo cabecalho"
```

---

### Task 7: `AcessoEsiape`

**Files:**
- Create: `integra_gov/esiape/acesso.py`
- Test: `tests/test_esiape_acesso.py` (novo)

**Interfaces:**
- Consumes: `garantir_menu`, `procurar_em_frames`, seletores (navegacao); `AutenticacaoNaoConfirmada`, `MenuInacessivel` (exceptions).
- Produces: `AcessoEsiape(driver, timeout_confirmacao=180)` com `executar() -> None`; constantes `URL_ESIAPE` e `XPATH_BOTAO_CERTIFICADO`.

- [ ] **Step 1: Write the failing tests** — criar `tests/test_esiape_acesso.py`:

```python
"""Testes de ``integra_gov.esiape.acesso`` — DriverFake roteirizado."""

from __future__ import annotations

import pytest

from integra_gov.esiape import acesso as ac
from integra_gov.esiape import navegacao as nav
from integra_gov.esiape.acesso import AcessoEsiape
from integra_gov.esiape.exceptions import (
    AutenticacaoNaoConfirmada,
    MenuInacessivel,
)
from tests.test_esiape_navegacao import DriverFake, ElementoFake, FrameFake


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(ac.time, "sleep", lambda *_a, **_k: None)


def _driver_pos_login():
    """Após a confirmação no app: tela de AVANÇAR presente; clicá-lo revela
    a lupa (menu)."""
    raiz = FrameFake()
    botao_cert = ElementoFake()
    raiz.elementos[AcessoEsiape.XPATH_BOTAO_CERTIFICADO] = [botao_cert]
    wa1 = FrameFake("WA1", visivel=True)
    avancar = ElementoFake()
    wa1.elementos[nav.SELETOR_BTN_AVANCAR] = [avancar]
    raiz.filhos = [wa1]

    _click = avancar.click

    def avancar_click():
        _click()
        del wa1.elementos[nav.SELETOR_BTN_AVANCAR]
        wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]

    avancar.click = avancar_click
    driver = DriverFake(raiz)
    driver.resultado_script = False
    return driver, botao_cert


def test_executar_aciona_certificado_e_chega_ao_menu():
    driver, botao_cert = _driver_pos_login()
    AcessoEsiape(driver, timeout_confirmacao=1).executar()
    assert driver.url == AcessoEsiape.URL_ESIAPE
    assert botao_cert.cliques == 1
    # o relogin de ENTRADA não deixa pendência: o acesso limpa a flag
    assert nav.relogin_pendente(driver) is False


def test_timeout_do_app_levanta_autenticacao_nao_confirmada():
    raiz = FrameFake()
    raiz.elementos[AcessoEsiape.XPATH_BOTAO_CERTIFICADO] = [ElementoFake()]
    driver = DriverFake(raiz)  # nenhuma tela pós-login jamais aparece
    driver.resultado_script = False
    with pytest.raises(AutenticacaoNaoConfirmada):
        AcessoEsiape(driver, timeout_confirmacao=0.05).executar()


def test_menu_inacessivel_apos_login_levanta(monkeypatch):
    raiz = FrameFake()
    raiz.elementos[AcessoEsiape.XPATH_BOTAO_CERTIFICADO] = [ElementoFake()]
    wa1 = FrameFake("WA1", visivel=True)
    wa1.elementos[nav.SELETOR_BTN_PULAR] = [ElementoFake()]  # detectado...
    raiz.filhos = [wa1]
    driver = DriverFake(raiz)
    driver.resultado_script = False
    # ...mas garantir_menu nunca converge (Pular não revela nada)
    monkeypatch.setattr(ac, "garantir_menu", lambda d, timeout=60: False)
    with pytest.raises(MenuInacessivel):
        AcessoEsiape(driver, timeout_confirmacao=1).executar()
```

- [ ] **Step 2: Run to verify FAIL** — `ModuleNotFoundError: ... acesso`.

- [ ] **Step 3: Implement** — `integra_gov/esiape/acesso.py`:

```python
"""Acesso ao e-SIAPE web via SERPRO ID — VOCÊ autentica (app no celular).

A lib navega, aciona o certificado e ESPERA a sua confirmação no app; nunca
digita PIN/senha e não registra credenciais em log.
"""

from __future__ import annotations

import logging
import time

from selenium.webdriver.common.by import By

from .exceptions import AutenticacaoNaoConfirmada, MenuInacessivel
from .navegacao import (
    SELETOR_BTN_AVANCAR,
    SELETOR_BTN_PULAR,
    SELETOR_LUPA,
    garantir_menu,
    limpar_flag_relogin,
    procurar_em_frames,
)

_log = logging.getLogger(__name__)


class AcessoEsiape:
    """Realiza o acesso ao e-SIAPE web (SERPRO ID + travessia de entrada).

    Args:
        driver: WebDriver (ex.: ``integra_gov.sei.criar_driver_chrome()``).
        timeout_confirmacao: segundos de espera pela confirmação no app.
    """

    URL_ESIAPE = ("https://esiape.sigepe.gov.br/modsiape/servlet/StartCISPage"
                  "?PAGEURL=/cisnatural/NatLogon.html"
                  "&xciParameters.natsession=modsiape")
    XPATH_BOTAO_CERTIFICADO = (
        "//*[self::button or self::a]"
        "[contains(translate(., 'certifcado', 'CERTIFCADO'), 'CERTIFICADO')]"
    )
    INTERVALO_POLL = 2.0

    def __init__(self, driver, timeout_confirmacao: float = 180):
        self.driver = driver
        self.timeout_confirmacao = timeout_confirmacao

    def executar(self) -> None:
        """Login completo: URL → certificado → confirmação no app → menu.

        Raises:
            AutenticacaoNaoConfirmada: confirmação não chegou no timeout.
            MenuInacessivel: autenticou mas o menu não ficou acessível.
        """
        _log.info("Acessando o e-SIAPE: %s", self.URL_ESIAPE)
        self.driver.get(self.URL_ESIAPE)
        time.sleep(2)
        self._acionar_certificado()
        self._esperar_confirmacao_no_app()
        if not garantir_menu(self.driver):
            raise MenuInacessivel(
                "autenticação confirmada, mas o menu de transações não ficou "
                "acessível (veja o log da travessia)"
            )
        # relogin de ENTRADA não é pendência: a sessão está no estado
        # padrão esperado e a primeira troca de habilitação é explícita.
        limpar_flag_relogin(self.driver)
        _log.info("Acesso ao e-SIAPE concluído — menu acessível")

    # ----- passos internos -----

    def _acionar_certificado(self) -> None:
        """Clica o botão de certificado se a página de login o mostrar."""
        try:
            botoes = self.driver.find_elements(By.XPATH,
                                               self.XPATH_BOTAO_CERTIFICADO)
            if botoes:
                botoes[0].click()
                _log.info("Botão de certificado acionado — CONFIRME no app "
                          "SERPRO ID")
        except Exception as exc:
            _log.warning("Botão de certificado não acionado (%s) — a página "
                         "pode já estar autenticada", exc)

    def _esperar_confirmacao_no_app(self) -> None:
        """Poll até uma tela pós-login aparecer (AVANÇAR/Pular/lupa)."""
        limite = time.monotonic() + self.timeout_confirmacao
        while time.monotonic() < limite:
            for seletor in (SELETOR_BTN_AVANCAR, SELETOR_BTN_PULAR,
                            SELETOR_LUPA):
                if procurar_em_frames(self.driver, seletor) is not None:
                    _log.info("Autenticação detectada")
                    return
            time.sleep(self.INTERVALO_POLL)
        raise AutenticacaoNaoConfirmada(
            f"a confirmação no app SERPRO ID não chegou em "
            f"{self.timeout_confirmacao:.0f}s"
        )
```

- [ ] **Step 4: Run to verify PASS** — 3 passed no arquivo novo.
- [ ] **Step 5: Suite + ruff + commit**

```bash
git add integra_gov/esiape/acesso.py tests/test_esiape_acesso.py
git commit -m "feat(esiape): AcessoEsiape — SERPRO ID com voce autenticando no app"
```

---

### Task 8: Exports + documentação

**Files:**
- Modify: `integra_gov/esiape/__init__.py`
- Modify: `README.md`, `docs/uso-basico.md`, `CHANGELOG.md`
- Test: `tests/test_esiape_navegacao.py` (append: teste de exports)

**Interfaces:**
- Produces: `from integra_gov.esiape import AcessoEsiape, TrocaHabilitacaoEsiape` + funções de `navegacao` re-exportadas (`garantir_menu`, `navegar_para_transacao`, `relogin_pendente`, `limpar_flag_relogin`, `fechar_janelas_extras`, `limpar_overlay`, `procurar_em_frames`, `esperar_seletor`).

- [ ] **Step 1: Teste de exports** (append em `tests/test_esiape_navegacao.py`):

```python
def test_exports_do_subpacote():
    import integra_gov.esiape as pacote

    for nome in ("AcessoEsiape", "TrocaHabilitacaoEsiape", "garantir_menu",
                 "navegar_para_transacao", "relogin_pendente",
                 "limpar_flag_relogin", "fechar_janelas_extras",
                 "limpar_overlay", "procurar_em_frames", "esperar_seletor"):
        assert hasattr(pacote, nome), nome
        assert nome in pacote.__all__
```

- [ ] **Step 2: FAIL** → **Step 3: Implement** — completar `__init__.py` com os imports/`__all__` (ordem alfabética) e docstring citando o exemplo:

```python
from .acesso import AcessoEsiape
from .habilitacao import TrocaHabilitacaoEsiape
from .navegacao import (
    esperar_seletor,
    fechar_janelas_extras,
    garantir_menu,
    limpar_flag_relogin,
    limpar_overlay,
    navegar_para_transacao,
    procurar_em_frames,
    relogin_pendente,
)
```

(mantendo os imports de `exceptions` da Task 1; `__all__` = tudo acima + exceções, alfabético.)

- [ ] **Step 4: Docs** — seguir o ESTILO EXISTENTE de cada arquivo:
  - README: seção `integra_gov.esiape` (tabela: navegacao/acesso/habilitacao/exceptions) + exemplo do spec (driver do `criar_driver_chrome`, `AcessoEsiape().executar()`, `TrocaHabilitacaoEsiape(driver, orgao="00000").trocar()`).
  - `docs/uso-basico.md`: seção nova com o fluxo, as 6 mecânicas CIS resumidas (frames ocultos; X do topo; relogin/flag; cortina; lupa; TROCAHAB efetiva no Sim + cabeçalho) e a semântica de `relogin_pendente`.
  - CHANGELOG `[Não publicado]`: subpacote novo, multiplataforma, mecânicas validadas ao vivo em lote real (14 extrações), "PENDENTE: verificação ao vivo do módulo público".
- [ ] **Step 5: Suite + ruff + commit**

```bash
git add integra_gov/esiape/__init__.py tests/test_esiape_navegacao.py README.md docs/uso-basico.md CHANGELOG.md
git commit -m "feat(esiape): exports do subpacote + docs (README, uso-basico, CHANGELOG)"
```

---

### Task 9 (gate final, manual): Verificação ao vivo

**NÃO automatizável** — requer o usuário (app SERPRO ID no celular).

- [ ] Script descartável `dados_reais/verifica_esiape_fundacao.py` (gitignored): `criar_driver_chrome()` → `AcessoEsiape(driver).executar()` (você confirma no app) → `orgao_atual()` → troca ida-e-volta entre dois órgãos que você possui → `navegar_para_transacao` numa transação de consulta inócua com `seletor_confirmacao` real → leitura final do cabeçalho.
- [ ] Conferir nos logs: travessia de entrada (Avançar/UORG/Pular), confirmação da troca pelo cabeçalho, tela da transação confirmada pelo seletor.
- [ ] Corrigir o que a verificação apontar (com teste de regressão mockado para cada correção).
- [ ] CHANGELOG: trocar "PENDENTE" por "Verificado ao vivo em AAAA-MM-DD" + o que corrigiu.
- [ ] Commit final e merge (squash se houver dado sensível em commit intermediário).
