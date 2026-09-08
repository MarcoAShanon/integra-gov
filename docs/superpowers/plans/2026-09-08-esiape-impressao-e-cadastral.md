# Plano A — Impressão do e-SIAPE como auxiliar público + extração cadastral (fase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extrair de `ficha_anual` a mecânica "clicar imprimir → popup → PDF estável → fechar → voltar" para `integra_gov/esiape/impressao.py`, sem mudar comportamento, e usar essas funções num script ao vivo que gera `cadastral_<matricula>.pdf` (CDCOINDPES) para cada linha da planilha da apresentação e grava a cópia da planilha com a coluna `arquivo`.

**Architecture:** Refatoração de **mover**: cinco métodos privados viram funções puras de módulo, com os mesmos nomes sem o `_`, os mesmos timeouts passados por parâmetro, e `ficha_anual` passa a chamá-las na mesma ordem. O script da fase 1 (gitignored, em `dados_reais/apresentacao/`) só faz o que é da tela CDCOINDPES; tudo o que é impressão vem do módulo novo.

**Tech Stack:** Python 3.14 (venv da lib), Selenium, pypdf (já dependência), openpyxl **só no venv, como ferramenta local** (não entra no `pyproject.toml`, mesmo precedente do Pillow).

**Spec:** `C:\Users\Thelemarco\PycharmProjects\integra-flow\docs\superpowers\specs\2026-09-08-instrucao-completa-apresentacao-design.md`, §4 e §10 (itens 1 e 2).

## Global Constraints

- Sem mudança de comportamento em `ficha_anual`: a suíte inteira continua verde e `test_imprimir_bloco_popup_download_e_renomeio` passa **sem alteração** (só o teste de órfãos muda de alvo, porque o método deixa de existir).
- Nenhum código copiado do pacote privado. Os seletores `data-testtoolid` são fatos da tela.
- O script vive em `dados_reais/` (gitignored). Não entra `import` dele em teste nenhum. Matrículas e nomes ficam na planilha, nunca no script.
- Comandos com caminho absoluto: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe`.
- Commit com `git commit -F <arquivo>`; mensagens em português no padrão `tipo(escopo): frase`.
- Módulo novo entra com README (tabela) + CHANGELOG + `uso-basico.md` **no mesmo commit** (regra do projeto).
- Contraprova por mutação só depois do commit.

---

## Mapa de arquivos

| arquivo | responsabilidade |
|---|---|
| `integra_gov/esiape/impressao.py` (novo) | `aguardar_popup`, `aguardar_pdf_estavel`, `fechar_popup`, `retornar_apos_impressao`, `limpar_downloads_orfaos`, e a composição `imprimir_via_popup` |
| `integra_gov/esiape/ficha_anual.py` (modificar) | `_imprimir_bloco` chama as funções; os cinco métodos privados são removidos |
| `integra_gov/esiape/__init__.py` (modificar) | exporta `imprimir_via_popup` |
| `tests/test_esiape_impressao.py` (novo) | as cinco funções + a composição, com um driver falso mínimo |
| `tests/test_esiape_ficha_anual.py` (modificar) | só o teste de órfãos muda de alvo |
| `README.md`, `CHANGELOG.md`, `docs/uso-basico.md` | a entrada do módulo |
| `dados_reais/apresentacao/extrair_cadastral.py` (novo, gitignored) | a fase 1 |

---

### Task A1: `esiape/impressao.py` — mover a impressão para funções públicas

**Files:**
- Create: `integra_gov/esiape/impressao.py`
- Modify: `integra_gov/esiape/ficha_anual.py` (método `_imprimir_bloco`, linhas 282–322; remover `_aguardar_popup`, `_aguardar_pdf_estavel`, `_fechar_popup`, `_retornar_apos_impressao`, `_limpar_downloads_orfaos`)
- Modify: `integra_gov/esiape/__init__.py`
- Modify: `tests/test_esiape_ficha_anual.py:277-281`
- Test: `tests/test_esiape_impressao.py`
- Modify: `README.md`, `CHANGELOG.md`, `docs/uso-basico.md`

**Interfaces:**
- Produces (todas em `integra_gov.esiape.impressao`):
  - `aguardar_popup(driver, handles_antes: list[str], *, timeout: float = 20, intervalo: float = 0.3) -> str | None`
  - `aguardar_pdf_estavel(pasta_download: Path, *, timeout: float = 60, intervalo: float = 0.3) -> Path` (levanta `TimeoutError`)
  - `fechar_popup(driver, popup_handle: str, *, intervalo: float = 0.3) -> None`
  - `retornar_apos_impressao(driver, handle_principal: str, *, delay: float = 1.0) -> None`
  - `limpar_downloads_orfaos(pasta_download: Path) -> None`
  - `imprimir_via_popup(driver, clicar_imprimir: Callable[[], None], pasta_download: Path, *, timeout_popup: float = 20, timeout_download: float = 60, delay: float = 1.0) -> Path` — limpa órfãos, guarda handles, chama `clicar_imprimir()`, espera popup e PDF, fecha o popup, volta com refresh e devolve o PDF **bruto** (quem chama renomeia).

- [ ] **Step 1: Escrever os testes do módulo novo**

`tests/test_esiape_impressao.py`:

```python
"""``integra_gov.esiape.impressao`` — a mecânica de imprimir via popup, movida
de ``ficha_anual`` sem mudar comportamento."""

from __future__ import annotations

from pathlib import Path

import pytest

from integra_gov.esiape import impressao as mod
from integra_gov.esiape.impressao import (
    aguardar_pdf_estavel,
    aguardar_popup,
    fechar_popup,
    imprimir_via_popup,
    limpar_downloads_orfaos,
    retornar_apos_impressao,
)


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)


class _SwitchTo:
    def __init__(self, d):
        self._d = d

    def window(self, handle):
        self._d.janela_atual = handle

    def default_content(self):
        self._d.default_content_chamado += 1


class DriverImpressao:
    """Só o que a impressão usa: handles, close, refresh, execute_script."""

    def __init__(self):
        self.window_handles = ["principal"]
        self.janela_atual = "principal"
        self.current_window_handle = "principal"
        self.fechadas: list[str] = []
        self.refreshes = 0
        self.scripts: list[str] = []
        self.default_content_chamado = 0
        self.switch_to = _SwitchTo(self)
        self.close_falha = 0  # nº de vezes que close() deve falhar

    def close(self):
        if self.close_falha > 0:
            self.close_falha -= 1
            raise RuntimeError("close recusado")
        self.fechadas.append(self.janela_atual)
        self.window_handles = [h for h in self.window_handles if h != self.janela_atual]

    def refresh(self):
        self.refreshes += 1

    def execute_script(self, script, *args):
        self.scripts.append(script)
        if script == "window.close();":
            self.window_handles = [h for h in self.window_handles if h != self.janela_atual]


def _pdf(caminho: Path, tamanho: int = 10) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"%PDF-" + b"x" * tamanho)
    return caminho


# ------------------------------------------------------------ popup
def test_aguardar_popup_devolve_o_handle_novo():
    d = DriverImpressao()
    d.window_handles = ["principal", "popup"]
    assert aguardar_popup(d, ["principal"], timeout=0.05) == "popup"


def test_aguardar_popup_sem_popup_devolve_none_no_timeout():
    d = DriverImpressao()
    assert aguardar_popup(d, ["principal"], timeout=0.01) is None


# -------------------------------------------------------------- pdf
def test_aguardar_pdf_estavel_devolve_o_mais_recente_estavel(tmp_path):
    _pdf(tmp_path / "a.pdf")
    assert aguardar_pdf_estavel(tmp_path, timeout=1, intervalo=0) == tmp_path / "a.pdf"


def test_aguardar_pdf_estavel_ignora_arquivo_vazio_ate_ter_conteudo(tmp_path, monkeypatch):
    caminho = tmp_path / "a.pdf"
    caminho.write_bytes(b"")
    leituras = {"n": 0}
    original = Path.stat

    def _stat(self, *a, **k):
        if self == caminho:
            leituras["n"] += 1
            if leituras["n"] >= 3:
                caminho.write_bytes(b"%PDF-xxxx")
        return original(self, *a, **k)

    monkeypatch.setattr(Path, "stat", _stat)
    assert aguardar_pdf_estavel(tmp_path, timeout=2, intervalo=0) == caminho


def test_aguardar_pdf_estavel_timeout_honesto_cita_a_pasta(tmp_path):
    with pytest.raises(TimeoutError, match=str(tmp_path).replace("\\", "\\\\")):
        aguardar_pdf_estavel(tmp_path, timeout=0.01, intervalo=0)


# ------------------------------------------------------------ fechar
def test_fechar_popup_por_selenium():
    d = DriverImpressao()
    d.window_handles = ["principal", "popup"]
    fechar_popup(d, "popup")
    assert d.fechadas == ["popup"] and "popup" not in d.window_handles


def test_fechar_popup_cai_para_js_quando_close_resiste():
    d = DriverImpressao()
    d.window_handles = ["principal", "popup"]
    d.close_falha = 2
    fechar_popup(d, "popup")
    assert "window.close();" in d.scripts and "popup" not in d.window_handles


def test_fechar_popup_inexistente_e_inofensivo():
    d = DriverImpressao()
    fechar_popup(d, "sumiu")
    assert d.fechadas == [] and d.scripts == []


# ------------------------------------------------------------ voltar
def test_retornar_volta_a_principal_com_refresh_e_raiz():
    d = DriverImpressao()
    d.window_handles = ["principal"]
    d.janela_atual = "outra"
    retornar_apos_impressao(d, "principal")
    assert d.janela_atual == "principal" and d.refreshes == 1
    assert d.default_content_chamado == 1


def test_retornar_usa_a_primeira_janela_se_a_principal_sumiu():
    d = DriverImpressao()
    d.window_handles = ["sobrevivente"]
    retornar_apos_impressao(d, "principal")
    assert d.janela_atual == "sobrevivente"


# ------------------------------------------------------------ órfãos
def test_limpar_downloads_orfaos_remove_pdfs(tmp_path):
    a = _pdf(tmp_path / "a.pdf")
    (tmp_path / "nao_pdf.txt").write_text("x")
    limpar_downloads_orfaos(tmp_path)
    assert not a.exists() and (tmp_path / "nao_pdf.txt").exists()


# -------------------------------------------------------- composição
def test_imprimir_via_popup_faz_a_sequencia_inteira(tmp_path):
    d = DriverImpressao()
    _pdf(tmp_path / "resto_antigo.pdf")  # órfão: deve sumir antes do clique

    def clicar():
        d.window_handles = ["principal", "popup"]
        _pdf(tmp_path / "StartDynamicContent.pdf")

    pdf = imprimir_via_popup(d, clicar, tmp_path, timeout_popup=0.5, timeout_download=1)
    assert pdf == tmp_path / "StartDynamicContent.pdf"
    assert not (tmp_path / "resto_antigo.pdf").exists()
    assert d.fechadas == ["popup"]
    assert d.janela_atual == "principal" and d.refreshes == 1


def test_imprimir_via_popup_sem_popup_ainda_devolve_o_pdf(tmp_path):
    """O download pode disparar sem janela nova; quem decide é o PDF no disco."""
    d = DriverImpressao()

    def clicar():
        _pdf(tmp_path / "StartDynamicContent.pdf")

    pdf = imprimir_via_popup(d, clicar, tmp_path, timeout_popup=0.01, timeout_download=1)
    assert pdf.exists() and d.fechadas == [] and d.refreshes == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_impressao.py -v`
Expected: `ModuleNotFoundError: integra_gov.esiape.impressao`.

- [ ] **Step 3: Criar o módulo**

`integra_gov/esiape/impressao.py`:

```python
"""Impressão via popup no e-SIAPE: a sequência estabilizada em produção.

O CIS imprime abrindo um popup que dispara um download (com o Chrome
configurado para "Save as PDF", ver ``docs/uso-basico.md``). A sequência
que funciona, e que já rendeu quatro defeitos só no gate ao vivo até ficar
assim, é:

1. limpar PDFs órfãos da pasta de download (o "mais recente" confundiria);
2. guardar os handles de janela ANTES do clique;
3. clicar em imprimir;
4. esperar o popup (pode não abrir; o download dispara mesmo assim);
5. esperar UM PDF aparecer e ficar estável (tamanho constante em 2 leituras);
6. fechar o popup por handle Selenium, com JS como fallback;
7. voltar à janela principal com ``refresh`` (sem ele a página fica em
   carregamento eterno) e ``default_content``.

Nasceu como cinco métodos privados de :mod:`ficha_anual`; virou módulo para
que a extração de dados cadastrais (e qualquer outra tela que imprime) não
duplique um trecho tão sensível. :func:`imprimir_via_popup` é a composição;
as funções soltas ficam para quem precisa intercalar algo (a ficha anual
confere a camada de texto ANTES de fechar o popup).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

_log = logging.getLogger(__name__)


def aguardar_popup(driver, handles_antes: list[str], *, timeout: float = 20,
                   intervalo: float = 0.3) -> str | None:
    """Handle da janela nova (``None`` se não abriu — o download pode
    disparar mesmo assim; quem decide é o PDF no disco)."""
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        novos = [h for h in driver.window_handles if h not in handles_antes]
        if novos:
            return novos[0]
        time.sleep(intervalo)
    _log.warning("Popup de impressão não detectado em %.0fs", timeout)
    return None


def aguardar_pdf_estavel(pasta_download: Path, *, timeout: float = 60,
                         intervalo: float = 0.3) -> Path:
    """Espera UM PDF aparecer em ``pasta_download`` e ficar estável (tamanho
    constante em 2 leituras). Erro honesto no timeout."""
    pasta_download = Path(pasta_download)
    limite = time.monotonic() + timeout
    tamanho_anterior: dict[Path, int] = {}
    while time.monotonic() < limite:
        pdfs = sorted(pasta_download.glob("*.pdf"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        if pdfs:
            atual = pdfs[0]
            tamanho = atual.stat().st_size
            if tamanho > 0 and tamanho_anterior.get(atual) == tamanho:
                return atual
            tamanho_anterior[atual] = tamanho
        time.sleep(intervalo)
    raise TimeoutError(
        f"o PDF não apareceu em {pasta_download} em {timeout}s — a pasta de "
        f"download do driver coincide com pasta_download?")


def fechar_popup(driver, popup_handle: str, *, intervalo: float = 0.3) -> None:
    """Fecha o popup por handle Selenium (retry); JS como fallback."""
    for _tentativa in range(2):
        try:
            if popup_handle not in driver.window_handles:
                return
            driver.switch_to.window(popup_handle)
            driver.close()
            time.sleep(intervalo)
            if popup_handle not in driver.window_handles:
                return
        except Exception:
            pass
    try:  # fallback JS
        if popup_handle in driver.window_handles:
            driver.switch_to.window(popup_handle)
            driver.execute_script("window.close();")
    except Exception:
        pass
    if popup_handle in driver.window_handles:
        _log.warning("Popup de impressão resistiu — janela órfã será "
                     "varrida por fechar_janelas_extras")


def retornar_apos_impressao(driver, handle_principal: str, *, delay: float = 1.0) -> None:
    """Volta à janela principal, refresh e contexto raiz (a página fica em
    carregamento eterno sem o refresh — comportamento real do CIS)."""
    try:
        if handle_principal in driver.window_handles:
            driver.switch_to.window(handle_principal)
        elif driver.window_handles:
            driver.switch_to.window(driver.window_handles[0])
        driver.refresh()
        driver.switch_to.default_content()
        time.sleep(delay)
    except Exception as exc:
        _log.warning("Retorno pós-impressão com falha (%s)", exc)


def limpar_downloads_orfaos(pasta_download: Path) -> None:
    """Remove PDFs de tentativas anteriores da pasta de download."""
    for pdf in Path(pasta_download).glob("*.pdf"):
        try:
            pdf.unlink()
            _log.debug("Órfão removido: %s", pdf.name)
        except OSError:
            pass


def imprimir_via_popup(driver, clicar_imprimir: Callable[[], None],
                       pasta_download: Path, *, timeout_popup: float = 20,
                       timeout_download: float = 60, delay: float = 1.0) -> Path:
    """A sequência inteira. Devolve o PDF BRUTO na pasta de download; quem
    chama renomeia (e, se quiser conferir o conteúdo antes de fechar o popup,
    use as funções soltas, como ``ficha_anual`` faz)."""
    limpar_downloads_orfaos(pasta_download)
    handle_principal = driver.current_window_handle
    handles_antes = list(driver.window_handles)
    clicar_imprimir()
    popup = aguardar_popup(driver, handles_antes, timeout=timeout_popup)
    pdf = aguardar_pdf_estavel(pasta_download, timeout=timeout_download)
    if popup is not None:
        fechar_popup(driver, popup)
    retornar_apos_impressao(driver, handle_principal, delay=delay)
    return pdf
```

Em `integra_gov/esiape/__init__.py`, acrescente ao bloco de imports e ao `__all__`:

```python
from .impressao import imprimir_via_popup
```

- [ ] **Step 4: Rodar e ver passar** — `13 passed`.

- [ ] **Step 5: Fazer `ficha_anual` chamar as funções e remover os métodos**

No topo de `integra_gov/esiape/ficha_anual.py`, junto dos outros imports relativos:

```python
from .impressao import (
    aguardar_pdf_estavel,
    aguardar_popup,
    fechar_popup,
    limpar_downloads_orfaos,
    retornar_apos_impressao,
)
```

Substitua o corpo de `_imprimir_bloco` (mantendo a assinatura e a docstring) por:

```python
        limpar_downloads_orfaos(self.pasta_download)
        fechar_janelas_extras(self.driver)
        limpar_overlay(self.driver)
        handle_principal = self.driver.current_window_handle
        handles_antes = list(self.driver.window_handles)

        if esperar_seletor(self.driver, self.SEL_GERAR_RELATORIO,
                           timeout=self.TIMEOUT_TELA) is None:
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SEL_GERAR_RELATORIO)
        self.driver.find_element(By.CSS_SELECTOR,
                                 self.SEL_GERAR_RELATORIO).click()
        time.sleep(self.DELAY_PADRAO)

        if esperar_seletor(self.driver, self.SEL_IMPRIMIR,
                           timeout=self.TIMEOUT_TELA) is None:
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SEL_IMPRIMIR)
        self.driver.find_element(By.CSS_SELECTOR, self.SEL_IMPRIMIR).click()

        popup = aguardar_popup(self.driver, handles_antes,
                               timeout=self.TIMEOUT_POPUP, intervalo=self.DELAY_CURTO)
        pdf_bruto = aguardar_pdf_estavel(self.pasta_download,
                                         timeout=self.TIMEOUT_DOWNLOAD,
                                         intervalo=self.DELAY_CURTO)
        self._exigir_camada_de_texto(pdf_bruto, (ano_de, ano_ate))
        if popup is not None:
            fechar_popup(self.driver, popup, intervalo=self.DELAY_CURTO)
        retornar_apos_impressao(self.driver, handle_principal,
                                delay=self.DELAY_PADRAO)

        destino = (self.pasta_saida
                   / f"ficha_{matricula}_{ano_de}_{ano_ate}.pdf")
        if destino.exists():
            destino.unlink()
        pdf_bruto.rename(destino)
        _log.info("Bloco %d-%d salvo em %s", ano_de, ano_ate, destino)
        return destino
```

Apague os métodos `_aguardar_popup`, `_aguardar_pdf_estavel`, `_fechar_popup`, `_retornar_apos_impressao` e `_limpar_downloads_orfaos` da classe (mantenha `_exigir_camada_de_texto`, que é específico da ficha). Os atributos `TIMEOUT_POPUP`, `TIMEOUT_DOWNLOAD`, `DELAY_CURTO`, `DELAY_PADRAO` ficam.

Em `tests/test_esiape_ficha_anual.py`, o teste de órfãos passa a ser:

```python
def test_limpar_downloads_orfaos_remove_pdfs_antigos(tmp_path):
    from integra_gov.esiape.impressao import limpar_downloads_orfaos

    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)
    orfao = pdf_minimo(ficha.pasta_download / "resto_antigo.pdf")
    limpar_downloads_orfaos(ficha.pasta_download)
    assert not orfao.exists()
```

- [ ] **Step 6: Suíte inteira e ruff**

Run: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest -q`
Expected: `784 passed` (771 + 13). `test_imprimir_bloco_popup_download_e_renomeio` passa **sem ter sido tocado**: é a prova de que o comportamento não mudou. `ruff check .` limpo.

- [ ] **Step 7: Doc no mesmo commit**

`README.md`: na tabela do e-SIAPE, uma linha `impressao` — "imprimir via popup (Save as PDF): a sequência estabilizada, reutilizável por qualquer tela que imprime".

`CHANGELOG.md`, em `[Não publicado]` → `### Adicionado`:

```markdown
- **`integra_gov.esiape.impressao`**: a mecânica de imprimir via popup
  (esperar o popup, esperar o PDF ficar estável, fechar por Selenium com JS
  de reserva, voltar à janela principal com refresh) saiu de dentro de
  `ficha_anual` e virou funções públicas, com `imprimir_via_popup` como
  composição. Refatoração de mover: `ficha_anual` chama as funções na mesma
  ordem e o teste de impressão do bloco passa sem alteração. Motivo: a
  extração de dados cadastrais (CDCOINDPES) precisa da mesma sequência, e
  esse trecho já rendeu quatro defeitos só no gate ao vivo — não se duplica.
```

`docs/uso-basico.md`, logo após a seção da configuração de Chrome para impressão, uma subseção "Imprimir qualquer tela do e-SIAPE" com:

````markdown
```python
from integra_gov.esiape import imprimir_via_popup

def clicar():
    driver.find_element(By.CSS_SELECTOR, '[data-testtoolid="w_report.onGeneratePrintVersion"]').click()

pdf_bruto = imprimir_via_popup(driver, clicar, PASTA_DOWNLOAD)
pdf_bruto.rename(PASTA_SAIDA / "meu_nome.pdf")
```

A pasta é a MESMA `PASTA_DOWNLOAD` das prefs do Chrome. O PDF volta com o nome
bruto que o CIS dá; renomear é seu. Para conferir o conteúdo antes de fechar o
popup (como a ficha anual faz), use as funções soltas do mesmo módulo.
````

- [ ] **Step 8: Commit**

`git add integra_gov/esiape/impressao.py integra_gov/esiape/ficha_anual.py integra_gov/esiape/__init__.py tests/test_esiape_impressao.py tests/test_esiape_ficha_anual.py README.md CHANGELOG.md docs/uso-basico.md`

Mensagem: `refactor(esiape): a impressão via popup sai de ficha_anual e vira o módulo impressao`

- [ ] **Step 9: Contraprova por mutação (agora que está commitado)**

Em `impressao.py`, troque `if tamanho > 0 and tamanho_anterior.get(atual) == tamanho:` por `if tamanho > 0:`. Rode `tests/test_esiape_impressao.py`: Expected `test_aguardar_pdf_estavel_ignora_arquivo_vazio_ate_ter_conteudo` **não** falha (o arquivo vazio tem tamanho 0), mas o teste de estabilidade em duas leituras não existe — **acrescente-o**:

```python
def test_aguardar_pdf_estavel_espera_duas_leituras_iguais(tmp_path, monkeypatch):
    caminho = tmp_path / "a.pdf"
    caminho.write_bytes(b"%PDF-1")
    tamanhos = iter([5, 9, 9])  # cresce, depois estabiliza
    original = Path.stat

    class _Stat:
        def __init__(self, base, size):
            self.st_mtime = base.st_mtime
            self.st_size = size

    def _stat(self, *a, **k):
        base = original(self, *a, **k)
        if self == caminho:
            return _Stat(base, next(tamanhos, 9))
        return base

    monkeypatch.setattr(Path, "stat", _stat)
    assert aguardar_pdf_estavel(tmp_path, timeout=2, intervalo=0) == caminho
    assert next(tamanhos, None) is None  # consumiu as 3 leituras: só devolveu na 2ª igual
```

Com a mutação, este teste falha; `git checkout -- integra_gov/esiape/impressao.py` (seguro: commitado); o teste passa. Commit: `test(esiape): a estabilidade do PDF exige duas leituras iguais`.

---

### Task A2: `extrair_cadastral.py` — a fase 1, ao vivo

**Files:**
- Create: `dados_reais/apresentacao/extrair_cadastral.py` (gitignored)
- Create: `dados_reais/apresentacao/README.md` (gitignored; como rodar)

**Interfaces:**
- Consumes: `criar_driver_chrome`, `AcessoEsiape`, `navegar_para_transacao`, `esperar_seletor`, `procurar_em_frames`, `limpar_overlay` (lib); `imprimir_via_popup` (Task A1); a planilha `C:\Users\Thelemarco\PycharmProjects\integra-flow\dados_reais\apresentacao\planilha_apresentacao.xlsx`.
- Produces: `…\integra-flow\dados_reais\apresentacao\anexos\cadastral_<matricula>.pdf` e `…\planilha_apresentacao_com_anexos.xlsx`.

Fatos da tela CDCOINDPES (seletores `data-testtoolid`, os mesmos nomes que a tela expõe):

| o quê | seletor |
|---|---|
| campo de matrícula | `[data-testtoolid="w_matr_infor_alfa"]` |
| botão consultar | `[data-testtoolid="onClickbtnConsulta"]` |
| botão imprimir (abre a tela de impressão) | `[data-testtoolid="onClickbtnImprimir"]` |
| gerar PDF (dispara o popup) | `[data-testtoolid="w_report.onGeneratePrintVersion"]` |
| sair (volta ao menu) | `[data-testtoolid="onClickBtnSair"]` |

- [ ] **Step 1: Instalar o openpyxl como ferramenta local do venv**

Run: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pip install openpyxl`
(Não entra no `pyproject.toml`: é ferramenta do script, não dependência da lib.)

- [ ] **Step 2: Escrever o script**

`dados_reais/apresentacao/extrair_cadastral.py`:

```python
"""Fase 1 da apresentação: o documento cadastral (CDCOINDPES) de cada linha da
planilha, em PDF, e a cópia da planilha com a coluna ``arquivo`` preenchida.

    python dados_reais/apresentacao/extrair_cadastral.py [--so-primeira]

Chrome com as prefs de impressão validadas em produção (docs/uso-basico.md);
Serpro ID confirmado UMA vez no celular; depois, uma linha por vez, sem SEI
aberto. Linha que falhar fica com ``arquivo`` vazio (o ensaio do flow acusa).
Nada pessoal neste arquivo: matrículas e nomes vêm da planilha.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from openpyxl import load_workbook
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options as ChromeOptions

from integra_gov.esiape import AcessoEsiape, EsiapeError, imprimir_via_popup
from integra_gov.esiape.navegacao import (
    esperar_seletor,
    fechar_janelas_extras,
    limpar_overlay,
    navegar_para_transacao,
    procurar_em_frames,
)
from integra_gov.sei import criar_driver_chrome

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
_log = logging.getLogger("extrair_cadastral")

BASE = Path(r"C:\Users\Thelemarco\PycharmProjects\integra-flow\dados_reais\apresentacao")
PLANILHA = BASE / "planilha_apresentacao.xlsx"
PLANILHA_SAIDA = BASE / "planilha_apresentacao_com_anexos.xlsx"
PASTA_ANEXOS = BASE / "anexos"
PASTA_DOWNLOAD = BASE / "_download_esiape"

TRANSACAO = "CDCOINDPES"
SEL_MATRICULA = '[data-testtoolid="w_matr_infor_alfa"]'
SEL_CONSULTAR = '[data-testtoolid="onClickbtnConsulta"]'
SEL_IMPRIMIR = '[data-testtoolid="onClickbtnImprimir"]'
SEL_GERAR_PDF = '[data-testtoolid="w_report.onGeneratePrintVersion"]'
SEL_SAIR = '[data-testtoolid="onClickBtnSair"]'
TIMEOUT_TELA = 30


def abrir_chrome():
    destino = {"recentDestinations": [{"id": "Save as PDF", "origin": "local", "account": ""}],
               "selectedDestinationId": "Save as PDF", "version": 2}
    opts = ChromeOptions()
    opts.add_experimental_option("prefs", {
        "download.default_directory": str(PASTA_DOWNLOAD),
        "savefile.default_directory": str(PASTA_DOWNLOAD),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "plugins.plugins_disabled": ["Chrome PDF Viewer"],
        "profile.default_content_settings.popups": 0,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "printing.print_preview_sticky_settings.appState": json.dumps(destino),
    })
    return criar_driver_chrome(options=opts,
                               args_extra=["--kiosk-printing", "--disable-popup-blocking"])


def _clicar(driver, seletor: str) -> None:
    if esperar_seletor(driver, seletor, timeout=TIMEOUT_TELA) is None:
        raise RuntimeError(f"{TRANSACAO}: seletor {seletor} não apareceu")
    driver.find_element(By.CSS_SELECTOR, seletor).click()


def extrair_uma(driver, matricula: str) -> Path:
    """Consulta a matrícula, imprime e devolve o PDF já renomeado."""
    fechar_janelas_extras(driver)
    limpar_overlay(driver)
    if not navegar_para_transacao(driver, TRANSACAO, SEL_MATRICULA, timeout=TIMEOUT_TELA):
        raise RuntimeError(f"não abriu a transação {TRANSACAO}")
    campo = driver.find_element(By.CSS_SELECTOR, SEL_MATRICULA)
    campo.clear()
    campo.send_keys(matricula)
    campo.send_keys(Keys.ENTER)
    time.sleep(1.0)
    _clicar(driver, SEL_CONSULTAR)
    time.sleep(1.5)
    _clicar(driver, SEL_IMPRIMIR)  # abre a tela de impressão

    def gerar_pdf():
        _clicar(driver, SEL_GERAR_PDF)  # é este clique que dispara o popup

    pdf_bruto = imprimir_via_popup(driver, gerar_pdf, PASTA_DOWNLOAD)
    destino = PASTA_ANEXOS / f"cadastral_{matricula}.pdf"
    if destino.exists():
        destino.unlink()
    pdf_bruto.rename(destino)
    try:  # volta ao menu para a próxima (best-effort)
        if procurar_em_frames(driver, SEL_SAIR) is not None:
            driver.find_element(By.CSS_SELECTOR, SEL_SAIR).click()
            time.sleep(1.0)
    except Exception as exc:  # noqa: BLE001
        _log.warning("Sair falhou (ignorado): %s", exc)
    return destino


def main() -> int:
    so_primeira = "--so-primeira" in sys.argv
    PASTA_ANEXOS.mkdir(parents=True, exist_ok=True)
    PASTA_DOWNLOAD.mkdir(parents=True, exist_ok=True)

    wb = load_workbook(PLANILHA)
    ws = wb.active
    cabecalho = [c.value for c in ws[1]]
    col_mat = cabecalho.index("matricula") + 1
    col_arq = cabecalho.index("arquivo") + 1
    linhas = list(range(2, ws.max_row + 1))
    if so_primeira:
        linhas = linhas[:1]

    driver = abrir_chrome()
    falhas = 0
    try:
        print("\n== Login SERPRO ID — CONFIRME NO APP quando pedir ==")
        AcessoEsiape(driver).executar()
        print("✅ Menu acessível\n")
        for i, r in enumerate(linhas, start=1):
            matricula = "".join(ch for ch in str(ws.cell(r, col_mat).value or "") if ch.isdigit())
            print(f"== {i}/{len(linhas)}: matrícula *****{matricula[-2:]} ==")
            try:
                destino = extrair_uma(driver, matricula)
                ws.cell(r, col_arq).value = destino.name
                print(f"   ✅ {destino.name} ({destino.stat().st_size / 1024:.0f} KB)")
            except (EsiapeError, RuntimeError, TimeoutError) as exc:
                falhas += 1
                ws.cell(r, col_arq).value = ""
                print(f"   ❌ {type(exc).__name__}: {exc}")
    finally:
        wb.save(PLANILHA_SAIDA)
        print(f"\nPlanilha com anexos: {PLANILHA_SAIDA}")
        input(">> ENTER para fechar o Chrome... ")
        driver.quit()
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
```

`dados_reais/apresentacao/README.md`:

```markdown
# Fase 1 da apresentação

1. Confira `…\integra-flow\dados_reais\apresentacao\planilha_apresentacao.xlsx`.
2. Rode uma linha só:
   `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe C:\Users\Thelemarco\PycharmProjects\integra-publico\dados_reais\apresentacao\extrair_cadastral.py --so-primeira`
   Confirme o Serpro ID no celular. Abra o PDF gerado em `anexos\` e confira que é a pessoa da linha.
3. Rode as três (sem `--so-primeira`). Saída: `anexos\cadastral_<matricula>.pdf` ×3 e `planilha_apresentacao_com_anexos.xlsx`.
4. A fase 2 (flow) recebe a planilha **com anexos** e os três PDFs.
```

- [ ] **Step 3: Sessão ao vivo com uma linha**

Peça ao usuário para rodar o comando do README (passo 2). **Ele confirma no celular.** Confira: o PDF existe, abre, tem a matrícula da linha 1, e a pasta `_download_esiape` ficou vazia (o bruto foi renomeado).

Se `navegar_para_transacao` devolver `False` ou um seletor não aparecer: são os seletores da tela (fatos a confirmar na primeira sessão). Peça ao usuário para deixar o Chrome aberto na tela e inspecione o `data-testtoolid` real; corrija a constante; repita. Não mexa em `impressao.py` por causa disso.

- [ ] **Step 4: As três linhas**

Mesmo comando sem `--so-primeira`. Expected: três PDFs em `anexos\`, `planilha_apresentacao_com_anexos.xlsx` com a coluna `arquivo` preenchida nas três linhas, código de saída 0.

- [ ] **Step 5: Registrar na spec (no repositório do flow)**

Acrescente ao fim da spec `…\integra-flow\docs\superpowers\specs\2026-09-08-instrucao-completa-apresentacao-design.md`:

```markdown
## 11. Verificado ao vivo — fase 1 (AAAA-MM-DD)

Três linhas, CDCOINDPES, um Serpro ID. PDFs em `dados_reais/apresentacao/anexos/`,
planilha com anexos gravada. Achados: (o que a sessão mostrou; ou "nenhum").
Seletores confirmados na tela: (os cinco, ou o que mudou).
```

Commit no flow: `docs: registra o gate ao vivo da fase 1`.

---

## Depois deste plano

Plano B (flow): `…\integra-flow\docs\superpowers\plans\2026-09-08-instrucao-completa-apresentacao.md`. E, depois do vídeo, o porte formal: `extrair_uma` vira `integra_gov.esiape.dados_pessoais.DadosPessoais(driver, pasta_saida).extrair(matricula) -> Path`, com testes sobre `DriverFake`, README, CHANGELOG e uso-basico, pelo processo completo. Serve também ao `integra-exante-novo`, plano 2.

## Self-review

- **Cobertura da spec (§4, §10.1–2):** extração do auxiliar → A1; script com Serpro ID uma vez, CDCOINDPES por linha, PDF renomeado, planilha com `arquivo`, linha falha fica vazia → A2; sessão de uma linha antes das três → A2 passos 3–4.
- **Placeholders:** nenhum. O único ponto aberto (seletores reais da tela) está marcado como verificação ao vivo com o procedimento de correção.
- **Nomes:** `imprimir_via_popup(driver, clicar_imprimir, pasta_download, *, timeout_popup, timeout_download, delay)` igual em A1 (código, testes, doc) e A2; as funções soltas com os mesmos parâmetros nomeados em A1 e na chamada de `ficha_anual`.
