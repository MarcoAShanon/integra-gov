# Ficha anual e-SIAPE + multi-órgão (E2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `FichaAnualServidor` (FPEMFICHAF em blocos ≤15 anos, PDF mesclado), `DadosFuncionaisOrgao` (CDCOINDFUN) e `FichaMultiOrgao` (encadeamento com lacunas declaradas) no subpacote público `integra_gov.esiape`.

**Architecture:** três módulos sobre a fundação E1 (`navegacao`, `habilitacao`). `FichaAnualServidor` isola a interação de tela em métodos internos (`_consultar_bloco`, `_imprimir_bloco`) — testes de nível `extrair` os mockam; testes próprios os exercitam com o `DriverFake` estendido (janelas + download roteirizados). Mesclagem com pypdf real (PDFs mínimos gerados nos testes).

**Tech Stack:** Python 3.10+, Selenium, **pypdf>=3.0 (dependência NOVA do núcleo)**, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-08-06-esiape-ficha-anual-design.md`

## Global Constraints

- Padrões da lib: logging stdlib, exceções filhas de `EsiapeError`, type hints, docstrings PT, nenhum dado pessoal/órgão real (usar `0000000`/`00000`/`11111` etc.), mensagens honestas.
- Mecânicas vêm dos módulos privados VALIDADOS EM PRODUÇÃO (lote 14/14) — não "melhorar" sequência sem verificação ao vivo.
- Venv SEMPRE: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe`; suíte completa + `ruff check .` verdes ao fim de cada task.
- Semânticas invioláveis: bloco com ERRO aborta a pessoa (exceção com `blocos_processados`); SEM DADOS não é erro (mensagem do CIS, nunca timeout); ano da VIRADA pertence aos DOIS órgãos (`pendente_ate = ano_de`); lacunas SEMPRE declaradas; PDF de bloco RENOMEADO antes do bloco seguinte; flag de relogin consumida com re-habilitação antes de consultar.
- Fakes: REUSAR `ElementoFake`/`FrameFake`/`DriverFake` de `tests/test_esiape_navegacao.py`; extensões (refresh/download) via SUBCLASSE no arquivo de teste novo — nunca editar os fakes existentes.
- Commits PT (`feat(esiape): ...`).

## File Structure

- Modify: `integra_gov/esiape/exceptions.py` (+2), `integra_gov/esiape/__init__.py`, `pyproject.toml` (pypdf).
- Create: `integra_gov/esiape/ficha_anual.py`, `integra_gov/esiape/dados_funcionais.py`, `integra_gov/esiape/ficha_multi_orgao.py`.
- Create: `tests/test_esiape_ficha_anual.py`, `tests/test_esiape_dados_funcionais.py`, `tests/test_esiape_multi_orgao.py`.
- Modify: `README.md`, `docs/uso-basico.md`, `CHANGELOG.md`.

---

### Task 1: Exceções + dependência pypdf

**Files:**
- Modify: `integra_gov/esiape/exceptions.py`, `integra_gov/esiape/__init__.py`, `pyproject.toml`
- Test: `tests/test_esiape_ficha_anual.py` (criado aqui)

**Interfaces:**
- Produces: `ExtracaoFichaEsiapeInterrompida(blocos_processados: list[tuple[int, int]], causa: BaseException | None)` com atributos homônimos; `FichaEsiapeIndisponivel(EsiapeError)`; `pypdf` importável no venv. Tasks 2-6 usam esses nomes.

- [ ] **Step 1: Instalar pypdf no venv e declarar no pyproject**

Run: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pip install "pypdf>=3.0"`
Em `pyproject.toml`, `dependencies`:

```toml
dependencies = [
    "selenium>=4.0",
    "pypdf>=3.0",
]
```

- [ ] **Step 2: Write the failing tests** — criar `tests/test_esiape_ficha_anual.py`:

```python
"""Testes de ``integra_gov.esiape.ficha_anual`` — DriverFake estendido."""

from __future__ import annotations

from integra_gov.esiape.exceptions import (
    EsiapeError,
    ExtracaoFichaEsiapeInterrompida,
    FichaEsiapeIndisponivel,
)


def test_excecoes_novas_sao_esiape_error():
    assert issubclass(ExtracaoFichaEsiapeInterrompida, EsiapeError)
    assert issubclass(FichaEsiapeIndisponivel, EsiapeError)


def test_extracao_interrompida_carrega_blocos_e_causa():
    causa = RuntimeError("popup sumiu")
    exc = ExtracaoFichaEsiapeInterrompida([(2008, 2022)], causa)
    assert exc.blocos_processados == [(2008, 2022)]
    assert exc.causa is causa
    assert "2008" in str(exc)


def test_pypdf_disponivel():
    from pypdf import PdfReader, PdfWriter  # noqa: F401
```

- [ ] **Step 3: Run FAIL** — `ImportError: ... ExtracaoFichaEsiapeInterrompida`.

- [ ] **Step 4: Implement** — ao final de `integra_gov/esiape/exceptions.py`:

```python
class FichaEsiapeIndisponivel(EsiapeError):
    """A matrícula não foi encontrada na habilitação ativa (a mensagem traz
    o que o CIS mostrou). Distinta de "bloco sem dados"."""


class ExtracaoFichaEsiapeInterrompida(EsiapeError):
    """A extração da ficha anual abortou no meio da faixa de blocos.

    Os PDFs dos blocos já salvos ficam no disco; nenhum resultado parcial é
    devolvido como completo.

    Attributes:
        blocos_processados: blocos ``(ano_de, ano_ate)`` concluídos antes da
            falha (com ou sem dados).
        causa: exceção original.
    """

    def __init__(self, blocos_processados: list[tuple[int, int]],
                 causa: BaseException | None):
        self.blocos_processados = list(blocos_processados)
        self.causa = causa
        super().__init__(
            f"extração interrompida após os blocos {self.blocos_processados} "
            f"(causa: {causa!r})"
        )
```

`__init__.py`: adicionar as duas ao import de `.exceptions` e ao `__all__` (alfabético).

- [ ] **Step 5: PASS (3) → suíte + ruff → commit**

```bash
git add integra_gov/esiape/exceptions.py integra_gov/esiape/__init__.py pyproject.toml tests/test_esiape_ficha_anual.py
git commit -m "feat(esiape): excecoes da ficha anual + dependencia pypdf no nucleo"
```

---

### Task 2: `ResultadoFichaEsiape` + esqueleto + blocos + fakes estendidos

**Files:**
- Create: `integra_gov/esiape/ficha_anual.py`
- Test: `tests/test_esiape_ficha_anual.py` (append)

**Interfaces:**
- Produces: `ResultadoFichaEsiape(pdf: Path | None, pdfs_blocos: list[Path], blocos_com_dados: list[tuple[int, int]], blocos_sem_dados: list[tuple[int, int]], duracao_s: float)`; `FichaAnualServidor(driver, pasta_saida, pasta_download=None)` com `MAX_ANOS_POR_CONSULTA=15`, `_dividir_blocos(ano_ini, ano_fim) -> list[tuple[int, int]]` (staticmethod/classmethod) e `extrair(...)` validando (ValueError) e `raise NotImplementedError` (Task 4 completa).
- Produces (teste): `DriverFicha(DriverFake)` com `refresh()` contador e `pdf_minimo(caminho)` helper (pypdf real) — Tasks 3-4 e 6 reutilizam.

- [ ] **Step 1: Write the failing tests** (append):

```python
from pathlib import Path

import pytest

from integra_gov.esiape import navegacao as nav
from integra_gov.esiape.ficha_anual import (
    FichaAnualServidor,
    ResultadoFichaEsiape,
)
from tests.test_esiape_navegacao import DriverFake, ElementoFake, FrameFake


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    from integra_gov.esiape import ficha_anual as fmod

    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(fmod.time, "sleep", lambda *_a, **_k: None)


class DriverFicha(DriverFake):
    """DriverFake + refresh() (a impressão exige refresh pós-popup)."""

    def __init__(self, raiz):
        super().__init__(raiz)
        self.refreshes = 0

    def refresh(self):
        self.refreshes += 1


def pdf_minimo(caminho: Path) -> Path:
    """PDF real de 1 página em branco (pypdf) para testes de mesclagem."""
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    with open(caminho, "wb") as f:
        w.write(f)
    return caminho


def test_dividir_blocos_respeita_limite_de_15():
    assert FichaAnualServidor._dividir_blocos(2008, 2026) == [
        (2008, 2022), (2023, 2026)]
    assert FichaAnualServidor._dividir_blocos(2020, 2026) == [(2020, 2026)]
    assert FichaAnualServidor._dividir_blocos(2010, 2010) == [(2010, 2010)]


def test_construtor_cria_pastas(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()),
                               pasta_saida=tmp_path / "saida")
    assert (tmp_path / "saida").is_dir()
    assert ficha.pasta_download == tmp_path / "saida" / "_download_esiape"
    assert ficha.pasta_download.is_dir()


def test_extrair_valida_parametros(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)
    with pytest.raises(ValueError):
        ficha.extrair("", 2008, 2026)
    with pytest.raises(ValueError):
        ficha.extrair("0000000", 2026, 2008)


def test_resultado_dataclass():
    r = ResultadoFichaEsiape()
    assert r.pdf is None
    assert r.pdfs_blocos == []
    assert r.blocos_com_dados == []
    assert r.blocos_sem_dados == []
    assert r.duracao_s == 0.0
```

- [ ] **Step 2: FAIL** — `ModuleNotFoundError: ... ficha_anual`.

- [ ] **Step 3: Implement** — `integra_gov/esiape/ficha_anual.py`:

```python
"""Ficha financeira anual do servidor/aposentado/instituidor (FPEMFICHAF).

O e-SIAPE limita cada consulta a 15 anos: a faixa é dividida em BLOCOS, cada
bloco vira um PDF (renomeado antes do seguinte — a tela salva sempre com o
mesmo nome) e tudo é mesclado em ordem cronológica ao final.

Semântica de honestidade (validada em produção): bloco com ERRO aborta a
pessoa inteira (:class:`ExtracaoFichaEsiapeInterrompida`); bloco SEM DADOS
não é erro — a mensagem do CIS é a evidência, nunca um timeout.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from selenium.webdriver.common.by import By

from .exceptions import (
    ExtracaoFichaEsiapeInterrompida,
    FichaEsiapeIndisponivel,
    TransacaoNaoAbriu,
)
from .navegacao import (
    esperar_seletor,
    fechar_janelas_extras,
    frames_visiveis,
    ir_para_frame,
    limpar_overlay,
    navegar_para_transacao,
    procurar_em_frames,
)

_log = logging.getLogger(__name__)


@dataclass
class ResultadoFichaEsiape:
    """Resultado da extração da ficha anual em blocos."""

    pdf: Path | None = None
    pdfs_blocos: list[Path] = field(default_factory=list)
    blocos_com_dados: list[tuple[int, int]] = field(default_factory=list)
    blocos_sem_dados: list[tuple[int, int]] = field(default_factory=list)
    duracao_s: float = 0.0


class FichaAnualServidor:
    """Extrai a ficha anual (FPEMFICHAF) da matrícula na habilitação ATIVA.

    Args:
        driver: WebDriver com a sessão do e-SIAPE autenticada.
        pasta_saida: destino dos PDFs (bloco e mesclado).
        pasta_download: pasta de download do Chrome (default: subpasta
            ``_download_esiape`` de ``pasta_saida``). DEVE coincidir com a
            configuração do driver — ver docs.
    """

    TRANSACAO = "FPEMFICHAF"
    MAX_ANOS_POR_CONSULTA = 15

    SEL_CONSULTA_ONLINE = '[data-testtoolid="onClickBtnConsultaOnline"]'
    SEL_MATRICULA = '[data-testtoolid="w_matr_infor_alfa"]'
    SEL_ANO_INICIO = '[data-testtoolid="w_ano_inicio"]'
    SEL_ANO_FIM = '[data-testtoolid="w_ano_fim"]'
    SEL_GERAR_RELATORIO = '[data-testtoolid="onClickBtnGerarTodosSemestres"]'
    SEL_IMPRIMIR = '[data-testtoolid="w_report.onGeneratePrintVersion"]'
    SEL_SAIR = '[data-testtoolid="onClickBtnSair"]'
    MSG_SEM_DADOS = "NAO HOUVE DADOS PARA CRITERIO SOLICITADO"

    TIMEOUT_TELA = 30
    TIMEOUT_CONSULTA = 30
    TIMEOUT_POPUP = 20
    TIMEOUT_DOWNLOAD = 60
    DELAY_CURTO = 0.3
    DELAY_PADRAO = 1.0

    def __init__(self, driver, pasta_saida: Path,
                 pasta_download: Path | None = None):
        self.driver = driver
        self.pasta_saida = Path(pasta_saida)
        self.pasta_saida.mkdir(parents=True, exist_ok=True)
        self.pasta_download = (Path(pasta_download) if pasta_download
                               else self.pasta_saida / "_download_esiape")
        self.pasta_download.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _dividir_blocos(cls, ano_ini: int, ano_fim: int
                        ) -> list[tuple[int, int]]:
        """Divide ``[ano_ini, ano_fim]`` em blocos de até 15 anos."""
        blocos: list[tuple[int, int]] = []
        ini = int(ano_ini)
        while ini <= int(ano_fim):
            ate = min(ini + cls.MAX_ANOS_POR_CONSULTA - 1, int(ano_fim))
            blocos.append((ini, ate))
            ini = ate + 1
        return blocos

    def extrair(self, matricula: str, ano_inicial: int, ano_final: int
                ) -> ResultadoFichaEsiape:
        """Extrai a ficha da faixa completa (blocos + mesclagem).

        Raises:
            ValueError: parâmetros inválidos.
            FichaEsiapeIndisponivel: matrícula não encontrada.
            ExtracaoFichaEsiapeInterrompida: bloco com erro (carrega
                ``blocos_processados`` e ``causa``).
        """
        matricula = str(matricula).strip()
        if not matricula:
            raise ValueError("matricula é obrigatória")
        if int(ano_inicial) > int(ano_final):
            raise ValueError(
                f"faixa invertida: {ano_inicial} > {ano_final}")
        raise NotImplementedError  # Tasks 3-4
```

- [ ] **Step 4: PASS (8 no arquivo) → suíte + ruff → commit**

```bash
git add integra_gov/esiape/ficha_anual.py tests/test_esiape_ficha_anual.py
git commit -m "feat(esiape): esqueleto da FichaAnualServidor (blocos de 15 anos + resultado tipado)"
```

---

### Task 3: Consulta do bloco (tela FPEMFICHAF, dados vs sem-dados)

**Files:**
- Modify: `integra_gov/esiape/ficha_anual.py`
- Test: `tests/test_esiape_ficha_anual.py` (append)

**Interfaces:**
- Consumes: fundação (`navegar_para_transacao`, `esperar_seletor`, `procurar_em_frames`).
- Produces: `_consultar_bloco(matricula: str, ano_de: int, ano_ate: int) -> bool` (True = tem dados; False = CIS respondeu SEM DADOS; levanta `TransacaoNaoAbriu`/`FichaEsiapeIndisponivel`); `_texto_da_tela() -> str`; `_sair_da_tela() -> None` (best-effort, botão Sair).

- [ ] **Step 1: Write the failing tests** (append):

```python
def _arvore_fpemfichaf():
    """Menu com lupa; clicar Ir abre a tela do FPEMFICHAF completa."""
    raiz = FrameFake()
    wa1 = FrameFake("WA1", visivel=True)
    wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    ir = ElementoFake()
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]
    raiz.filhos = [wa1]

    consulta_online = ElementoFake()
    matricula = ElementoFake()
    ano_ini, ano_fim = ElementoFake(), ElementoFake()
    pesquisar_seletores = {
        FichaAnualServidor.SEL_CONSULTA_ONLINE: [consulta_online],
        FichaAnualServidor.SEL_MATRICULA: [matricula],
        FichaAnualServidor.SEL_ANO_INICIO: [ano_ini],
        FichaAnualServidor.SEL_ANO_FIM: [ano_fim],
    }

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos.update(pesquisar_seletores)

    ir.click = ir_click
    return raiz, wa1, matricula


def test_consultar_bloco_com_dados(tmp_path):
    raiz, wa1, matricula = _arvore_fpemfichaf()
    driver = DriverFicha(raiz)
    driver.resultado_script = ""  # texto da tela sem MSG_SEM_DADOS
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)
    # após a consulta, o botão Gerar Relatório aparece = tem dados
    _click_mat = matricula.send_keys

    def mat_keys(*teclas):
        _click_mat(*teclas)
        wa1.elementos[FichaAnualServidor.SEL_GERAR_RELATORIO] = [ElementoFake()]

    matricula.send_keys = mat_keys
    assert ficha._consultar_bloco("0000000", 2008, 2022) is True
    assert "0000000" in matricula.teclas


def test_consultar_bloco_sem_dados_devolve_false(tmp_path):
    from unittest.mock import patch

    raiz, wa1, matricula = _arvore_fpemfichaf()
    driver = DriverFicha(raiz)
    driver.resultado_script = (
        "mensagem: NAO HOUVE DADOS PARA CRITERIO SOLICITADO")
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)
    with patch.object(FichaAnualServidor, "TIMEOUT_CONSULTA", 0.05):
        assert ficha._consultar_bloco("0000000", 2008, 2022) is False


def test_consultar_bloco_tela_nao_abre_levanta(tmp_path):
    from unittest.mock import patch

    driver = DriverFicha(FrameFake())  # sem lupa, sem nada
    driver.resultado_script = ""
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)
    from integra_gov.esiape.exceptions import TransacaoNaoAbriu

    # garantir_menu tem timeout REAL de 60s (monotonic) — atalha p/ o teste
    with patch.object(nav, "garantir_menu", lambda d, timeout=60: False):
        with pytest.raises(TransacaoNaoAbriu):
            ficha._consultar_bloco("0000000", 2008, 2022)
```

- [ ] **Step 2: FAIL** — `AttributeError: ... '_consultar_bloco'`.

- [ ] **Step 3: Implement** (adicionar à classe):

```python
    # ----- consulta de um bloco -----

    def _consultar_bloco(self, matricula: str, ano_de: int, ano_ate: int
                         ) -> bool:
        """Abre a tela, consulta o período e responde se HÁ dados.

        ``False`` SÓ quando o CIS respondeu com a mensagem de "sem dados" —
        nunca por timeout (timeout sem resposta clara vira exceção).
        """
        if not navegar_para_transacao(self.driver, self.TRANSACAO,
                                      self.SEL_CONSULTA_ONLINE,
                                      timeout=self.TIMEOUT_TELA):
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SEL_CONSULTA_ONLINE)
        self.driver.find_element(By.CSS_SELECTOR,
                                 self.SEL_CONSULTA_ONLINE).click()
        time.sleep(self.DELAY_PADRAO)

        if esperar_seletor(self.driver, self.SEL_MATRICULA,
                           timeout=self.TIMEOUT_TELA) is None:
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SEL_MATRICULA)
        campo = self.driver.find_element(By.CSS_SELECTOR, self.SEL_MATRICULA)
        campo.clear()
        campo.send_keys(matricula)
        time.sleep(self.DELAY_CURTO)
        for seletor, valor in ((self.SEL_ANO_INICIO, str(ano_de)),
                               (self.SEL_ANO_FIM, str(ano_ate))):
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, seletor)
                el.clear()
                el.send_keys(valor)
                time.sleep(self.DELAY_CURTO)
            except Exception as exc:
                raise TransacaoNaoAbriu(self.TRANSACAO, seletor) from exc

        # dispara a consulta (ENTER no campo de ano final)
        self.driver.find_element(By.CSS_SELECTOR, self.SEL_ANO_FIM
                                 ).send_keys("\n")

        # decide por EVIDÊNCIA: relatório disponível OU mensagem de sem-dados
        limite = time.monotonic() + self.TIMEOUT_CONSULTA
        while time.monotonic() < limite:
            if procurar_em_frames(self.driver,
                                  self.SEL_GERAR_RELATORIO) is not None:
                _log.info("Bloco %d-%d: consulta com dados", ano_de, ano_ate)
                return True
            texto = self._texto_da_tela()
            if self.MSG_SEM_DADOS in texto.upper():
                _log.info("Bloco %d-%d: sem dados no período", ano_de, ano_ate)
                self._sair_da_tela()
                return False
            time.sleep(self.DELAY_CURTO)
        raise FichaEsiapeIndisponivel(
            f"matrícula {matricula}: a consulta {ano_de}-{ano_ate} não "
            f"respondeu nem com relatório nem com '{self.MSG_SEM_DADOS}' em "
            f"{self.TIMEOUT_CONSULTA}s — matrícula fora da habilitação ativa?"
        )

    def _texto_da_tela(self) -> str:
        """Texto concatenado de TODOS os frames visíveis (best-effort)."""
        textos: list[str] = []
        try:
            self.driver.switch_to.default_content()
        except Exception:
            return ""
        for caminho in frames_visiveis(self.driver):
            if not ir_para_frame(self.driver, caminho):
                continue
            try:
                textos.append(self.driver.execute_script(
                    "return document.body ? document.body.innerText : ''"
                ) or "")
            except Exception:
                continue
        return "\n".join(textos)

    def _sair_da_tela(self) -> None:
        """Clica Sair para voltar ao menu (best-effort)."""
        try:
            if procurar_em_frames(self.driver, self.SEL_SAIR) is not None:
                self.driver.find_element(By.CSS_SELECTOR, self.SEL_SAIR).click()
                time.sleep(self.DELAY_PADRAO)
        except Exception as exc:
            _log.warning("Sair falhou (ignorado): %s", exc)
```

- [ ] **Step 4: PASS (11 no arquivo) → suíte + ruff → commit**

```bash
git add integra_gov/esiape/ficha_anual.py tests/test_esiape_ficha_anual.py
git commit -m "feat(esiape): consulta do bloco FPEMFICHAF decide por evidencia (relatorio ou sem-dados)"
```

---

### Task 4: Impressão + `extrair` completo + mesclagem

**Files:**
- Modify: `integra_gov/esiape/ficha_anual.py`
- Test: `tests/test_esiape_ficha_anual.py` (append)

**Interfaces:**
- Produces: `_imprimir_bloco(matricula, ano_de, ano_ate) -> Path` (PDF do bloco renomeado em `pasta_saida`; internamente: `_limpar_downloads_orfaos()`, `_aguardar_pdf_estavel() -> Path`, `_fechar_popup(handle) -> None`, `_retornar_apos_impressao(handle_principal)`); `_mesclar(pdfs: list[Path], destino: Path) -> Path`; `extrair` completo. Testes de nível `extrair` mockam `_consultar_bloco`/`_imprimir_bloco`; Task 6 consome `extrair`.

- [ ] **Step 1: Write the failing tests** (append):

```python
from unittest.mock import patch


def test_imprimir_bloco_popup_download_e_renomeio(tmp_path):
    raiz, wa1, _mat = _arvore_fpemfichaf()
    driver = DriverFicha(raiz)
    driver.resultado_script = False
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)

    imprimir = ElementoFake()
    wa1.elementos[FichaAnualServidor.SEL_IMPRIMIR] = [imprimir]
    wa1.elementos[FichaAnualServidor.SEL_GERAR_RELATORIO] = [ElementoFake()]

    _click_imp = imprimir.click

    def imprimir_click():
        _click_imp()
        driver.window_handles = ["principal", "popup_impressao"]
        pdf_minimo(ficha.pasta_download / "fichas_financeiras.pdf")

    imprimir.click = imprimir_click

    caminho = ficha._imprimir_bloco("0000000", 2008, 2022)
    assert caminho == tmp_path / "ficha_0000000_2008_2022.pdf"
    assert caminho.exists()
    assert "popup_impressao" in driver.fechadas       # fechado por Selenium
    assert driver.janela_atual == "principal"
    assert driver.refreshes >= 1                       # refresh pós-popup
    # download não deixou órfão com o nome bruto
    assert not (ficha.pasta_download / "fichas_financeiras.pdf").exists()


def test_limpar_downloads_orfaos_remove_pdfs_antigos(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)
    orfao = pdf_minimo(ficha.pasta_download / "resto_antigo.pdf")
    ficha._limpar_downloads_orfaos()
    assert not orfao.exists()


def test_extrair_blocos_com_e_sem_dados_mescla_e_renomeia(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)

    def consulta(matricula, ano_de, ano_ate):
        return ano_de != 2023  # 2º bloco sem dados

    def imprime(matricula, ano_de, ano_ate):
        return pdf_minimo(
            tmp_path / f"ficha_{matricula}_{ano_de}_{ano_ate}.pdf")

    with patch.object(ficha, "_consultar_bloco", side_effect=consulta), \
         patch.object(ficha, "_imprimir_bloco", side_effect=imprime):
        r = ficha.extrair("0000000", 2008, 2026)

    assert r.blocos_com_dados == [(2008, 2022)]
    assert r.blocos_sem_dados == [(2023, 2026)]
    assert r.pdfs_blocos == [tmp_path / "ficha_0000000_2008_2022.pdf"]
    assert r.pdf == tmp_path / "ficha_0000000_2008_2026.pdf"
    assert r.pdf.exists() and r.duracao_s >= 0


def test_extrair_todos_sem_dados_pdf_none(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)
    with patch.object(ficha, "_consultar_bloco", return_value=False):
        r = ficha.extrair("0000000", 2020, 2024)
    assert r.pdf is None
    assert r.blocos_sem_dados == [(2020, 2024)]


def test_extrair_erro_no_bloco_aborta_com_processados(tmp_path):
    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)

    def consulta(matricula, ano_de, ano_ate):
        if ano_de == 2023:
            raise RuntimeError("Browser window not found")
        return True

    def imprime(matricula, ano_de, ano_ate):
        return pdf_minimo(
            tmp_path / f"ficha_{matricula}_{ano_de}_{ano_ate}.pdf")

    with patch.object(ficha, "_consultar_bloco", side_effect=consulta), \
         patch.object(ficha, "_imprimir_bloco", side_effect=imprime):
        with pytest.raises(ExtracaoFichaEsiapeInterrompida) as exc:
            ficha.extrair("0000000", 2008, 2026)
    assert exc.value.blocos_processados == [(2008, 2022)]
    assert isinstance(exc.value.causa, RuntimeError)
    # parcial fica no disco para diagnóstico
    assert (tmp_path / "ficha_0000000_2008_2022.pdf").exists()


def test_mesclar_ordem_cronologica(tmp_path):
    from pypdf import PdfReader

    ficha = FichaAnualServidor(DriverFicha(FrameFake()), pasta_saida=tmp_path)
    a = pdf_minimo(tmp_path / "a.pdf")
    b = pdf_minimo(tmp_path / "b.pdf")
    destino = ficha._mesclar([a, b], tmp_path / "final.pdf")
    assert PdfReader(destino).get_num_pages() == 2
```

- [ ] **Step 2: FAIL** — `AttributeError: ... '_imprimir_bloco'`.

- [ ] **Step 3: Implement** (adicionar à classe; substituir o `raise NotImplementedError` do `extrair`):

```python
    # ----- impressão de um bloco (sequência estabilizada em produção) -----

    def _imprimir_bloco(self, matricula: str, ano_de: int, ano_ate: int
                        ) -> Path:
        """Gera o relatório, imprime via popup e devolve o PDF RENOMEADO.

        O popup de impressão é a origem histórica da degradação de sessão:
        fechamos por handle Selenium (confiável) e SÓ então retornamos à
        janela principal com refresh.
        """
        self._limpar_downloads_orfaos()
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

        popup = self._aguardar_popup(handles_antes)
        pdf_bruto = self._aguardar_pdf_estavel()
        if popup is not None:
            self._fechar_popup(popup)
        self._retornar_apos_impressao(handle_principal)

        destino = (self.pasta_saida
                   / f"ficha_{matricula}_{ano_de}_{ano_ate}.pdf")
        if destino.exists():
            destino.unlink()
        pdf_bruto.rename(destino)
        _log.info("Bloco %d-%d salvo em %s", ano_de, ano_ate, destino)
        return destino

    def _aguardar_popup(self, handles_antes: list) -> str | None:
        """Handle do popup de impressão (``None`` se não abriu — o download
        pode disparar mesmo assim; quem decide é o PDF no disco)."""
        limite = time.monotonic() + self.TIMEOUT_POPUP
        while time.monotonic() < limite:
            novos = [h for h in self.driver.window_handles
                     if h not in handles_antes]
            if novos:
                return novos[0]
            time.sleep(self.DELAY_CURTO)
        _log.warning("Popup de impressão não detectado em %.0fs",
                     self.TIMEOUT_POPUP)
        return None

    def _aguardar_pdf_estavel(self) -> Path:
        """Espera UM PDF aparecer na pasta de download e ficar estável
        (tamanho constante em 2 leituras). Erro honesto no timeout."""
        limite = time.monotonic() + self.TIMEOUT_DOWNLOAD
        tamanho_anterior: dict[Path, int] = {}
        while time.monotonic() < limite:
            pdfs = sorted(self.pasta_download.glob("*.pdf"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
            if pdfs:
                atual = pdfs[0]
                tamanho = atual.stat().st_size
                if tamanho > 0 and tamanho_anterior.get(atual) == tamanho:
                    return atual
                tamanho_anterior[atual] = tamanho
            time.sleep(self.DELAY_CURTO)
        raise TimeoutError(
            f"o PDF do bloco não apareceu em {self.pasta_download} em "
            f"{self.TIMEOUT_DOWNLOAD}s — a pasta de download do driver "
            f"coincide com pasta_download?")

    def _fechar_popup(self, popup_handle: str) -> None:
        """Fecha o popup por handle Selenium (retry); JS como fallback."""
        for _tentativa in range(2):
            try:
                if popup_handle not in self.driver.window_handles:
                    return
                self.driver.switch_to.window(popup_handle)
                self.driver.close()
                time.sleep(self.DELAY_CURTO)
                if popup_handle not in self.driver.window_handles:
                    return
            except Exception:
                pass
        try:  # fallback JS
            if popup_handle in self.driver.window_handles:
                self.driver.switch_to.window(popup_handle)
                self.driver.execute_script("window.close();")
        except Exception:
            pass
        if popup_handle in self.driver.window_handles:
            _log.warning("Popup de impressão resistiu — janela órfã será "
                         "varrida por fechar_janelas_extras")

    def _retornar_apos_impressao(self, handle_principal: str) -> None:
        """Volta à janela principal, refresh e contexto raiz (a página fica
        em carregamento eterno sem o refresh — comportamento real do CIS)."""
        try:
            if handle_principal in self.driver.window_handles:
                self.driver.switch_to.window(handle_principal)
            elif self.driver.window_handles:
                self.driver.switch_to.window(self.driver.window_handles[0])
            self.driver.refresh()
            self.driver.switch_to.default_content()
            time.sleep(self.DELAY_PADRAO)
        except Exception as exc:
            _log.warning("Retorno pós-impressão com falha (%s)", exc)

    def _limpar_downloads_orfaos(self) -> None:
        """Remove PDFs de tentativas anteriores da pasta de download (o
        'mais recente' confundiria resto antigo com o bloco atual)."""
        for pdf in self.pasta_download.glob("*.pdf"):
            try:
                pdf.unlink()
                _log.debug("Órfão removido: %s", pdf.name)
            except OSError:
                pass

    # ----- mesclagem -----

    @staticmethod
    def _mesclar(pdfs: list[Path], destino: Path) -> Path:
        """Mescla os PDFs em ordem (pypdf) e devolve o destino."""
        from pypdf import PdfWriter

        w = PdfWriter()
        for pdf in pdfs:
            w.append(str(pdf))
        with open(destino, "wb") as f:
            w.write(f)
        w.close()
        return destino
```

E o corpo final do `extrair` (após as validações da Task 2):

```python
        inicio = time.monotonic()
        resultado = ResultadoFichaEsiape()
        try:
            for ano_de, ano_ate in self._dividir_blocos(ano_inicial, ano_final):
                if not self._consultar_bloco(matricula, ano_de, ano_ate):
                    resultado.blocos_sem_dados.append((ano_de, ano_ate))
                    continue
                caminho = self._imprimir_bloco(matricula, ano_de, ano_ate)
                resultado.blocos_com_dados.append((ano_de, ano_ate))
                resultado.pdfs_blocos.append(caminho)
        except Exception as exc:
            blocos = sorted(resultado.blocos_com_dados
                            + resultado.blocos_sem_dados)
            raise ExtracaoFichaEsiapeInterrompida(blocos, exc) from exc

        if resultado.pdfs_blocos:
            destino = (self.pasta_saida
                       / f"ficha_{matricula}_{ano_inicial}_{ano_final}.pdf")
            if len(resultado.pdfs_blocos) == 1:
                import shutil

                shutil.copy2(resultado.pdfs_blocos[0], destino)
            else:
                self._mesclar(resultado.pdfs_blocos, destino)
            resultado.pdf = destino
        resultado.duracao_s = time.monotonic() - inicio
        _log.info("Matrícula %s: %d bloco(s) com dados, %d sem, %.1fs",
                  matricula, len(resultado.blocos_com_dados),
                  len(resultado.blocos_sem_dados), resultado.duracao_s)
        return resultado
```

E o teste do popup que RESISTE ao fechamento (cenário 5 da spec) — append:

```python
class DriverPopupTeimoso(DriverFicha):
    """close() não fecha de verdade (popup teimoso do CIS)."""

    def close(self):
        self.fechadas.append(self.janela_atual)  # registra, mas não remove


def test_popup_teimoso_fallback_js_e_fluxo_segue(tmp_path):
    raiz, wa1, _mat = _arvore_fpemfichaf()
    driver = DriverPopupTeimoso(raiz)
    driver.resultado_script = False
    ficha = FichaAnualServidor(driver, pasta_saida=tmp_path)

    imprimir = ElementoFake()
    wa1.elementos[FichaAnualServidor.SEL_IMPRIMIR] = [imprimir]
    wa1.elementos[FichaAnualServidor.SEL_GERAR_RELATORIO] = [ElementoFake()]

    _click_imp = imprimir.click

    def imprimir_click():
        _click_imp()
        driver.window_handles = ["principal", "popup_teimoso"]
        pdf_minimo(ficha.pasta_download / "fichas_financeiras.pdf")

    imprimir.click = imprimir_click

    caminho = ficha._imprimir_bloco("0000000", 2008, 2022)
    assert caminho.exists()                       # o fluxo NÃO morre
    assert any("window.close" in s for s in driver.scripts)  # fallback JS
    assert "popup_teimoso" in driver.window_handles  # órfã fica p/ a varredura
```

- [ ] **Step 4: PASS (18 no arquivo) → suíte + ruff → commit**

```bash
git add integra_gov/esiape/ficha_anual.py tests/test_esiape_ficha_anual.py
git commit -m "feat(esiape): impressao estabilizada + extrair completo com mesclagem e aborto honesto"
```

---

### Task 5: `DadosFuncionaisOrgao` (CDCOINDFUN)

**Files:**
- Create: `integra_gov/esiape/dados_funcionais.py`
- Test: `tests/test_esiape_dados_funcionais.py` (novo)

**Interfaces:**
- Consumes: fundação (`navegar_para_transacao`, `esperar_seletor`, `frames_visiveis`, `ir_para_frame`); `TransacaoNaoAbriu`.
- Produces: `DadosFuncionais(orgao_anterior: str | None, matricula_anterior: str | None, ano_ingresso: int | None, cadastramento_siape: str | None)` (dataclass); `DadosFuncionaisOrgao(driver)` com `consultar(matricula, orgao) -> DadosFuncionais`; parsing `_extrair(texto) -> DadosFuncionais` (staticmethod). Task 6 consome.

- [ ] **Step 1: Write the failing tests** — criar `tests/test_esiape_dados_funcionais.py`:

```python
"""Testes de ``integra_gov.esiape.dados_funcionais`` (CDCOINDFUN)."""

from __future__ import annotations

import pytest

from integra_gov.esiape import navegacao as nav
from integra_gov.esiape.dados_funcionais import (
    DadosFuncionais,
    DadosFuncionaisOrgao,
)
from integra_gov.esiape.exceptions import TransacaoNaoAbriu
from tests.test_esiape_navegacao import DriverFake, ElementoFake, FrameFake


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    from integra_gov.esiape import dados_funcionais as dmod

    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(dmod.time, "sleep", lambda *_a, **_k: None)


TEXTO_TELA_3 = """
DADOS INDIVIDUAIS FUNCIONAIS
Cadastramento no SIAPE: 11DEZ2014
INGRESSO NO ORGAO
DATA OCORRENCIA : 01DEZ2014
ORGAO/MATRIC ANTER.: 11111 / 0000000
"""


def test_extrair_parseia_orgao_anterior_e_ingresso():
    d = DadosFuncionaisOrgao._extrair(TEXTO_TELA_3)
    assert d.orgao_anterior == "11111"
    assert d.matricula_anterior == "0000000"
    assert d.ano_ingresso == 2014
    assert d.cadastramento_siape == "11DEZ2014"


def test_extrair_sem_orgao_anterior_devolve_none():
    d = DadosFuncionaisOrgao._extrair("Cadastramento no SIAPE: 05JAN2001")
    assert d.orgao_anterior is None
    assert d.matricula_anterior is None
    assert d.ano_ingresso == 2001  # cai no cadastramento sem a ocorrência


def test_extrair_texto_ilegivel_tudo_none():
    d = DadosFuncionaisOrgao._extrair("tela irreconhecivel")
    assert d == DadosFuncionais(None, None, None, None)


def test_consultar_tela_nao_abre_levanta():
    from unittest.mock import patch

    driver = DriverFake(FrameFake())
    driver.resultado_script = ""
    with patch.object(nav, "garantir_menu", lambda d, timeout=60: False):
        with pytest.raises(TransacaoNaoAbriu):
            DadosFuncionaisOrgao(driver).consultar("0000000", orgao="00000")


def test_consultar_fluxo_completo_3_telas_com_armadilha_do_rotulo():
    """As 3 telas felizes — e a prova do marcador: a tela 2 contém o rótulo
    'INGRESSO NO ORGAO' (checkbox) mas NÃO 'Cadastramento no SIAPE'; o
    parse só acontece quando a tela 3 de fato chega."""
    raiz = FrameFake()
    wa1 = FrameFake("WA1", visivel=True)
    wa1.elementos[nav.SELETOR_LUPA] = [ElementoFake()]
    wa1.elementos[nav.SELETOR_CAMPO_TRANSACAO] = [ElementoFake()]
    ir = ElementoFake()
    wa1.elementos[nav.SELETOR_BTN_IR] = [ir]
    raiz.filhos = [wa1]

    matricula, orgao_campo = ElementoFake(), ElementoFake()
    pesquisar_1, pesquisar_2 = ElementoFake(), ElementoFake()
    checkboxes = {tid: ElementoFake()
                  for tid in DadosFuncionaisOrgao.CHECKBOXES}
    estado = {"tela": 1}

    _click_ir = ir.click

    def ir_click():
        _click_ir()
        wa1.elementos[DadosFuncionaisOrgao.SEL_MATRICULA] = [matricula]
        wa1.elementos[DadosFuncionaisOrgao.SEL_ORGAO] = [orgao_campo]
        wa1.elementos[DadosFuncionaisOrgao.SEL_PESQUISAR_1] = [pesquisar_1]

    ir.click = ir_click

    _click_p1 = pesquisar_1.click

    def p1_click():
        _click_p1()
        estado["tela"] = 2
        for tid, cb in checkboxes.items():
            wa1.elementos[f'[data-testtoolid="{tid}"]'] = [cb]
        wa1.elementos[DadosFuncionaisOrgao.SEL_PESQUISAR_2] = [pesquisar_2]

    pesquisar_1.click = p1_click

    _click_p2 = pesquisar_2.click

    def p2_click():
        _click_p2()
        estado["tela"] = 3

    pesquisar_2.click = p2_click

    driver = DriverFake(raiz)

    def texto_da_tela(script, *args):
        if estado["tela"] == 2:
            return "SELECIONE:\nINGRESSO NO ORGAO\nORGAO ATUAL/ANTERIOR"
        if estado["tela"] == 3:
            return TEXTO_TELA_3
        return False  # overlay_presente etc.

    driver.resultado_script = texto_da_tela

    d = DadosFuncionaisOrgao(driver).consultar("0000000", orgao="22222")
    assert d.orgao_anterior == "11111"
    assert d.ano_ingresso == 2014
    assert "22222" in orgao_campo.teclas       # órgão EXPLÍCITO preenchido
    assert all(cb.cliques == 1 for cb in checkboxes.values())
```

- [ ] **Step 2: FAIL** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `integra_gov/esiape/dados_funcionais.py`:

```python
"""Dados individuais funcionais (CDCOINDFUN): órgão anterior e ingresso.

A transação resolve deterministicamente a descoberta do órgão anterior de
quem migrou — sem sondar ficha mês a mês. 3 telas: (1) órgão EXPLÍCITO +
matrícula, (2) checkboxes do que consultar, (3) resultado lido por TEXTO.

ARMADILHA REAL: o marcador da tela 3 tem que ser "Cadastramento no SIAPE" —
"INGRESSO NO ÓRGÃO" também é rótulo de checkbox da tela 2 e faz parsear a
tela errada (concluindo "sem órgão anterior" incorretamente).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from selenium.webdriver.common.by import By

from .exceptions import TransacaoNaoAbriu
from .navegacao import (
    esperar_seletor,
    frames_visiveis,
    ir_para_frame,
    navegar_para_transacao,
)

_log = logging.getLogger(__name__)

_MESES = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
          "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}


def _ano_de(texto: str | None) -> int | None:
    """Ano de uma data SIAPE ``DDMMMAAAA`` (ex.: ``01DEZ2014``)."""
    m = re.match(r"(\d{2})([A-Z]{3})(\d{4})", (texto or "").strip().upper())
    if not m or m.group(2) not in _MESES:
        return None
    return int(m.group(3))


@dataclass
class DadosFuncionais:
    """Resultado do CDCOINDFUN (campos ilegíveis ficam ``None``)."""

    orgao_anterior: str | None
    matricula_anterior: str | None
    ano_ingresso: int | None
    cadastramento_siape: str | None


class DadosFuncionaisOrgao:
    """Consulta o CDCOINDFUN para descobrir o órgão anterior do servidor."""

    TRANSACAO = "CDCOINDFUN"
    SEL_MATRICULA = '[data-testtoolid="w_matr_infor_alfa"]'
    SEL_ORGAO = '[data-testtoolid="w_orgao_infor"]'
    SEL_PESQUISAR_1 = '[data-testtoolid="onClickbtnPesquisar"]'
    SEL_PESQUISAR_2 = '[data-testtoolid="onClickbtnConsulta"]'
    CHECKBOXES = ("w_orgao_atual", "w_orgao_origem", "w_ing_orgao")
    MARCADOR_RESULTADO = "CADASTRAMENTO NO SIAPE"
    TIMEOUT = 30

    def __init__(self, driver):
        self.driver = driver

    # ----- parsing -----

    @staticmethod
    def _extrair(texto: str) -> DadosFuncionais:
        """Extrai os campos do texto da tela 3 (ilegível → ``None``)."""
        def busca(padrao: str) -> str | None:
            m = re.search(padrao, texto, re.I)
            return m.group(1).strip() if m else None

        anter = busca(r"[OÓ]RG[AÃ]O/MATR[IÍ]C\s*ANTER\.?:\s*"
                      r"([0-9]+\s*/\s*[0-9]+)")
        orgao_ant = mat_ant = None
        if anter:
            partes = [p.strip() for p in anter.split("/")]
            orgao_ant = partes[0] or None
            mat_ant = partes[1] if len(partes) > 1 else None

        cadastramento = busca(
            r"Cadastramento no SIAPE:\s*([0-9]{2}[A-Z]{3}[0-9]{4})")
        ocorrencia = busca(
            r"DATA OCORRENCIA\s*:\s*([0-9]{2}[A-Z]{3}[0-9]{4})")
        # a data que importa é a do ingresso no órgão atual: ocorrência,
        # caindo no cadastramento quando ela não vier
        ano = _ano_de(ocorrencia) or _ano_de(cadastramento)
        return DadosFuncionais(orgao_ant, mat_ant, ano, cadastramento)

    # ----- navegação -----

    def consultar(self, matricula: str, orgao: str) -> DadosFuncionais:
        """Executa as 3 telas e devolve os dados.

        ``orgao`` é EXPLÍCITO: ao encadear trocas de habilitação não dá para
        confiar no órgão default do formulário.

        Raises:
            TransacaoNaoAbriu: alguma tela não confirmou.
        """
        if not navegar_para_transacao(self.driver, self.TRANSACAO,
                                      self.SEL_MATRICULA,
                                      timeout=self.TIMEOUT):
            raise TransacaoNaoAbriu(self.TRANSACAO, self.SEL_MATRICULA)

        campo_orgao = self.driver.find_element(By.CSS_SELECTOR, self.SEL_ORGAO)
        campo_orgao.clear()
        campo_orgao.send_keys(str(orgao).strip())
        campo = self.driver.find_element(By.CSS_SELECTOR, self.SEL_MATRICULA)
        campo.clear()
        campo.send_keys(str(matricula).strip())
        self.driver.find_element(By.CSS_SELECTOR, self.SEL_PESQUISAR_1).click()

        # tela 2 (em OUTRO frame — os WA* se revezam)
        primeiro = f'[data-testtoolid="{self.CHECKBOXES[0]}"]'
        if esperar_seletor(self.driver, primeiro,
                           timeout=self.TIMEOUT) is None:
            raise TransacaoNaoAbriu(self.TRANSACAO, primeiro)
        for tid in self.CHECKBOXES:
            try:
                cb = self.driver.find_element(
                    By.CSS_SELECTOR, f'[data-testtoolid="{tid}"]')
                cb.click()
            except Exception as exc:
                _log.warning("Checkbox %s não marcado: %s", tid, exc)
        self.driver.find_element(By.CSS_SELECTOR, self.SEL_PESQUISAR_2).click()

        time.sleep(1.0)  # deixa a tela 2 sair de cena (armadilha do rótulo)
        texto = self._esperar_texto(self.MARCADOR_RESULTADO)
        if texto is None:
            raise TransacaoNaoAbriu(self.TRANSACAO,
                                    f"texto '{self.MARCADOR_RESULTADO}'")
        dados = self._extrair(texto)
        if dados.orgao_anterior:
            _log.info("Órgão anterior: %s (matrícula %s), ingresso %s",
                      dados.orgao_anterior, dados.matricula_anterior,
                      dados.ano_ingresso)
        else:
            _log.info("Sem órgão anterior registrado")
        return dados

    def _esperar_texto(self, marcador: str) -> str | None:
        """Espera o marcador textual em algum frame VISÍVEL; texto ou None."""
        limite = time.monotonic() + self.TIMEOUT
        while time.monotonic() < limite:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            for caminho in frames_visiveis(self.driver):
                if not ir_para_frame(self.driver, caminho):
                    continue
                try:
                    texto = self.driver.execute_script(
                        "return document.body ? document.body.innerText : ''"
                    ) or ""
                except Exception:
                    continue
                if marcador.upper() in texto.upper():
                    return texto
            time.sleep(0.5)
        return None
```

- [ ] **Step 4: PASS (5 no arquivo novo) → suíte + ruff → commit**

```bash
git add integra_gov/esiape/dados_funcionais.py tests/test_esiape_dados_funcionais.py
git commit -m "feat(esiape): CDCOINDFUN — orgao anterior e ano de ingresso com marcador anti-armadilha"
```

---

### Task 6: `FichaMultiOrgao`

**Files:**
- Create: `integra_gov/esiape/ficha_multi_orgao.py`
- Test: `tests/test_esiape_multi_orgao.py` (novo)

**Interfaces:**
- Consumes: `FichaAnualServidor` (Task 4), `DadosFuncionaisOrgao`/`DadosFuncionais` (Task 5), `TrocaHabilitacaoEsiape`, `relogin_pendente`/`limpar_flag_relogin`/`fechar_janelas_extras`/`limpar_overlay` (fundação), `HabilitacaoNaoEncontrada`.
- Produces: `ResultadoMultiOrgao(pdf, trilha, lacunas, falhas_tecnicas, voltou_ao_orgao_inicial, duracao_s)`; `FichaMultiOrgao(driver, orgao_inicial, pasta_saida, max_saltos=5)` com `extrair(matricula, ano_inicial, ano_final) -> ResultadoMultiOrgao` e `TENTATIVAS_POR_FAIXA=2`. **Os testes mockam os COLABORADORES** (`DadosFuncionaisOrgao.consultar`, `FichaAnualServidor.extrair`, `TrocaHabilitacaoEsiape.trocar`) via `unittest.mock.patch` — o que se testa aqui é o LAÇO (faixas, virada, lacunas, retries, retorno).

- [ ] **Step 1: Write the failing tests** — criar `tests/test_esiape_multi_orgao.py`:

```python
"""Testes do laço multi-órgão — colaboradores mockados, laço real."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from integra_gov.esiape import navegacao as nav
from integra_gov.esiape.dados_funcionais import DadosFuncionais
from integra_gov.esiape.ficha_anual import ResultadoFichaEsiape
from integra_gov.esiape.ficha_multi_orgao import (
    FichaMultiOrgao,
    ResultadoMultiOrgao,
)
from tests.test_esiape_ficha_anual import pdf_minimo
from tests.test_esiape_navegacao import DriverFake, FrameFake


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    from integra_gov.esiape import ficha_multi_orgao as mmod

    monkeypatch.setattr(nav.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(mmod.time, "sleep", lambda *_a, **_k: None)


def _driver():
    d = DriverFake(FrameFake())
    d.resultado_script = False
    return d


def _resultado_ficha(tmp_path, matricula, ano_de, ano_ate):
    # PDF REAL mínimo: a mesclagem final usa pypdf de verdade
    pdf = pdf_minimo(tmp_path / f"ficha_{matricula}_{ano_de}_{ano_ate}.pdf")
    return ResultadoFichaEsiape(pdf=pdf, pdfs_blocos=[pdf],
                                blocos_com_dados=[(ano_de, ano_ate)])


def test_um_salto_com_ano_da_virada_nos_dois_orgaos(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)
    dados = {
        ("0000001", "22222"): DadosFuncionais("11111", "0000001", 2014,
                                              "11DEZ2014"),
        ("0000001", "11111"): DadosFuncionais(None, None, 2001, "05JAN2001"),
    }
    faixas = []

    def consultar(self, matricula, orgao):
        return dados[(matricula, orgao)]

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        faixas.append((ano_inicial, ano_final))
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", lambda self: None):
        r = multi.extrair("0000001", 2008, 2026)

    # faixa do órgão atual: 2014-2026; a do anterior INCLUI o ano da virada
    assert faixas == [(2014, 2026), (2008, 2014)]
    assert r.trilha == [("22222", "0000001", 2014, 2026),
                        ("11111", "0000001", 2008, 2014)]
    assert r.lacunas == []
    assert r.pdf is not None and r.pdf.exists()
    assert r.voltou_ao_orgao_inicial is True


def test_sem_orgao_anterior_declara_lacuna(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)

    def consultar(self, matricula, orgao):
        return DadosFuncionais(None, None, 2014, "11DEZ2014")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", lambda self: None):
        r = multi.extrair("0000001", 2008, 2026)

    assert r.pdf is not None
    assert any("2008-2013" in lac for lac in r.lacunas)


def test_relogin_pendente_rehabilita_antes_de_consultar(tmp_path):
    driver = _driver()
    driver._esiape_relogin_pendente = True
    multi = FichaMultiOrgao(driver, orgao_inicial="22222",
                            pasta_saida=tmp_path)
    trocas = []

    def trocar(self):
        trocas.append(self.orgao)
        nav.limpar_flag_relogin(driver)

    def consultar(self, matricula, orgao):
        assert not nav.relogin_pendente(driver)  # re-habilitou ANTES
        return DadosFuncionais(None, None, 2008, "01JAN2008")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", trocar):
        r = multi.extrair("0000001", 2008, 2026)
    assert "22222" in trocas  # re-habilitação aconteceu
    assert r.pdf is not None


def test_falha_intermitente_retenta_faixa(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)
    chamadas = {"n": 0}

    def consultar(self, matricula, orgao):
        return DadosFuncionais(None, None, 2008, "01JAN2008")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise RuntimeError("Browser window not found")
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", lambda self: None):
        r = multi.extrair("0000001", 2008, 2026)
    assert chamadas["n"] == 2  # 1 falha + 1 retry com sucesso
    assert r.pdf is not None
    assert r.falhas_tecnicas == []


def test_faixa_falha_2x_vira_lacuna_e_falha_tecnica(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)

    def consultar(self, matricula, orgao):
        return DadosFuncionais(None, None, 2008, "01JAN2008")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        raise RuntimeError("sessao caiu")

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", lambda self: None):
        r = multi.extrair("0000001", 2008, 2026)
    assert r.pdf is None
    assert len(r.falhas_tecnicas) == 1
    assert any("2008-2026" in f for f in r.falhas_tecnicas)


def test_ciclo_detectado_para(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)

    def consultar(self, matricula, orgao):
        # 22222 -> 11111 -> 22222 (ciclo)
        anterior = "11111" if orgao == "22222" else "22222"
        return DadosFuncionais(anterior, matricula, 2015, "01JAN2015")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", lambda self: None):
        r = multi.extrair("0000001", 2008, 2026)
    assert len(r.trilha) <= 2  # parou no ciclo, não loopou até max_saltos


def test_sem_habilitacao_no_anterior_declara_lacuna_e_entrega(tmp_path):
    from integra_gov.esiape.exceptions import HabilitacaoNaoEncontrada

    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)

    def consultar(self, matricula, orgao):
        return DadosFuncionais("11111", matricula, 2014, "11DEZ2014")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    def trocar(self):
        if self.orgao == "11111":  # usuário NÃO possui o órgão anterior
            raise HabilitacaoNaoEncontrada("11111", ["22222"])

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", trocar):
        r = multi.extrair("0000001", 2008, 2026)

    assert r.pdf is not None                       # entrega o que cobriu
    assert any("sem habilitação no órgão 11111" in lac for lac in r.lacunas)
    assert r.voltou_ao_orgao_inicial is True       # nunca saiu do 22222


def test_retorno_ao_orgao_inicial_falha_sinaliza(tmp_path):
    multi = FichaMultiOrgao(_driver(), orgao_inicial="22222",
                            pasta_saida=tmp_path)

    def consultar(self, matricula, orgao):
        if orgao == "22222":
            return DadosFuncionais("11111", matricula, 2014, "11DEZ2014")
        return DadosFuncionais(None, None, 2001, "05JAN2001")

    def extrair_ficha(self, matricula, ano_inicial, ano_final):
        return _resultado_ficha(tmp_path, matricula, ano_inicial, ano_final)

    def trocar(self):
        if self.orgao == "22222":  # só o RETORNO falha (ida ao 11111 ok)
            raise HabilitacaoNaoEncontrada("22222", ["11111"])

    from integra_gov.esiape.exceptions import HabilitacaoNaoEncontrada

    with patch("integra_gov.esiape.ficha_multi_orgao."
               "DadosFuncionaisOrgao.consultar", consultar), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "FichaAnualServidor.extrair", extrair_ficha), \
         patch("integra_gov.esiape.ficha_multi_orgao."
               "TrocaHabilitacaoEsiape.trocar", trocar):
        r = multi.extrair("0000001", 2008, 2026)

    assert r.pdf is not None
    assert r.voltou_ao_orgao_inicial is False
    assert any("não voltou" in f for f in r.falhas_tecnicas)
```

- [ ] **Step 2: FAIL** — `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `integra_gov/esiape/ficha_multi_orgao.py`:

```python
"""Ficha anual cobrindo TODOS os órgãos por onde o servidor passou.

A ficha anual (FPEMFICHAF) só enxerga o órgão ATIVO — quem migrou perde os
anos anteriores SILENCIOSAMENTE. Este módulo encadeia: CDCOINDFUN (órgão
anterior) → extrai a faixa do órgão → troca a habilitação → repete; mescla
tudo e SEMPRE declara o que não conseguiu cobrir (``lacunas``).

Regra validada em produção: o ano da VIRADA pertence aos DOIS órgãos —
quem entrou no órgão novo em DEZ deixa JAN-NOV no órgão anterior.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from .dados_funcionais import DadosFuncionaisOrgao
from .exceptions import EsiapeError
from .ficha_anual import FichaAnualServidor
from .habilitacao import TrocaHabilitacaoEsiape
from .navegacao import (
    fechar_janelas_extras,
    limpar_overlay,
    relogin_pendente,
)

_log = logging.getLogger(__name__)


@dataclass
class ResultadoMultiOrgao:
    """Resultado do encadeamento — lacunas SEMPRE declaradas."""

    pdf: Path | None = None
    trilha: list[tuple[str, str, int, int]] = field(default_factory=list)
    lacunas: list[str] = field(default_factory=list)
    falhas_tecnicas: list[str] = field(default_factory=list)
    voltou_ao_orgao_inicial: bool = True
    duracao_s: float = 0.0


class FichaMultiOrgao:
    """Encadeia a extração da ficha anual pelos órgãos do servidor.

    Args:
        driver: WebDriver com a sessão do e-SIAPE autenticada.
        orgao_inicial: órgão da habilitação de partida (e de retorno).
        pasta_saida: destino dos PDFs.
        max_saltos: limite de órgãos encadeados (salvaguarda).
    """

    TENTATIVAS_POR_FAIXA = 2

    def __init__(self, driver, orgao_inicial: str, pasta_saida: Path,
                 max_saltos: int = 5):
        self.driver = driver
        self.orgao_inicial = str(orgao_inicial).strip()
        self.pasta_saida = Path(pasta_saida)
        self.max_saltos = max_saltos

    def extrair(self, matricula: str, ano_inicial: int, ano_final: int
                ) -> ResultadoMultiOrgao:
        """Percorre a cadeia de órgãos e devolve o resultado consolidado.

        Nunca levanta por lacuna legítima — entrega o que cobriu com as
        ``lacunas`` declaradas.
        """
        inicio = time.monotonic()
        r = ResultadoMultiOrgao()
        orgao, mat = self.orgao_inicial, str(matricula).strip()
        pendente_ate = int(ano_final)
        visitados: set[tuple[str, str]] = set()
        pdfs: list[tuple[int, Path]] = []

        fechar_janelas_extras(self.driver)
        limpar_overlay(self.driver)
        self._rehabilitar_se_relogin(orgao)

        for _salto in range(self.max_saltos):
            if (orgao, mat) in visitados:
                _log.warning("Ciclo detectado em %s/%s — parando", orgao, mat)
                break
            visitados.add((orgao, mat))

            dados = DadosFuncionaisOrgao(self.driver).consultar(mat, orgao)
            ano_de = (max(int(ano_inicial), dados.ano_ingresso)
                      if dados.ano_ingresso else int(ano_inicial))

            if ano_de <= pendente_ate:
                pdf = self._extrair_faixa(mat, ano_de, pendente_ate, orgao)
                if pdf is not None:
                    pdfs.append((ano_de, pdf))
                    r.trilha.append((orgao, mat, ano_de, pendente_ate))
                else:
                    msg = (f"{ano_de}-{pendente_ate} (órgão {orgao}): "
                           f"extração falhou após "
                           f"{self.TENTATIVAS_POR_FAIXA} tentativas")
                    r.lacunas.append(msg)
                    r.falhas_tecnicas.append(msg)

            if ano_de <= int(ano_inicial):
                _log.info("Cobertura alcançou %d — completo", ano_inicial)
                break
            if not dados.orgao_anterior:
                r.lacunas.append(
                    f"{ano_inicial}-{ano_de - 1}: sem órgão anterior no "
                    f"CDCOINDFUN")
                break
            # o ano da VIRADA pertence aos DOIS órgãos
            pendente_ate = ano_de
            mat = dados.matricula_anterior or mat
            try:
                TrocaHabilitacaoEsiape(self.driver,
                                       orgao=dados.orgao_anterior).trocar()
            except EsiapeError as exc:
                falta = f"{ano_inicial}-{pendente_ate}"
                _log.error("Sem habilitação no órgão %s: %s",
                           dados.orgao_anterior, exc)
                r.lacunas.append(
                    f"{falta}: sem habilitação no órgão "
                    f"{dados.orgao_anterior}")
                r.falhas_tecnicas.append(
                    f"{falta}: sem habilitação no órgão "
                    f"{dados.orgao_anterior}")
                break
            orgao = dados.orgao_anterior
        else:
            r.lacunas.append(f"limite de {self.max_saltos} saltos atingido")

        self._voltar_ao_orgao_inicial(orgao, r)

        if pdfs:
            ordenados = [p for _, p in sorted(pdfs)]
            destino = (self.pasta_saida
                       / f"ficha_{matricula}_{ano_inicial}_{ano_final}"
                         f"_multiorgao.pdf")
            if len(ordenados) == 1:
                import shutil

                shutil.copy2(ordenados[0], destino)
            else:
                FichaAnualServidor._mesclar(ordenados, destino)
            r.pdf = destino
        if r.lacunas:
            _log.warning("Ficha entregue com lacunas: %s",
                         "; ".join(r.lacunas))
        r.duracao_s = time.monotonic() - inicio
        return r

    # ----- passos internos -----

    def _rehabilitar_se_relogin(self, orgao: str) -> None:
        """Relogin atravessado = habilitação no padrão do usuário — re-troca
        ANTES de consultar (senão 'sem dados' FALSO = lacuna silenciosa)."""
        if not relogin_pendente(self.driver):
            return
        _log.warning("Relogin pendente — refazendo a habilitação no órgão %s",
                     orgao)
        TrocaHabilitacaoEsiape(self.driver, orgao=orgao).trocar()

    def _extrair_faixa(self, matricula: str, ano_de: int, ano_ate: int,
                       orgao: str) -> Path | None:
        """Uma faixa com retry (falha intermitente de popup não pode custar
        a pessoa). ``None`` = falhou todas as tentativas."""
        for tentativa in range(1, self.TENTATIVAS_POR_FAIXA + 1):
            fechar_janelas_extras(self.driver)
            limpar_overlay(self.driver)
            self._rehabilitar_se_relogin(orgao)
            try:
                resultado = FichaAnualServidor(
                    self.driver, pasta_saida=self.pasta_saida
                ).extrair(matricula, ano_de, ano_ate)
            except Exception as exc:
                _log.warning("Faixa %d-%d falhou (tentativa %d): %s",
                             ano_de, ano_ate, tentativa, exc)
                time.sleep(2)
                continue
            fechar_janelas_extras(self.driver)
            if resultado.pdf is not None:
                # nome único por órgão (a próxima faixa não pode sobrescrever)
                unico = resultado.pdf.with_name(
                    resultado.pdf.stem + f"_org{orgao}.pdf")
                if unico.exists():
                    unico.unlink()
                resultado.pdf.rename(unico)
                return unico
            return None  # faixa legitimamente sem dados
        return None

    def _voltar_ao_orgao_inicial(self, orgao_atual: str,
                                 r: ResultadoMultiOrgao) -> None:
        """Devolve a habilitação ao órgão inicial (a próxima pessoa do
        chamador falharia no órgão errado). Sinaliza quando não consegue."""
        if orgao_atual == self.orgao_inicial:
            return
        for _tentativa in range(3):
            try:
                TrocaHabilitacaoEsiape(self.driver,
                                       orgao=self.orgao_inicial).trocar()
                return
            except EsiapeError as exc:
                _log.warning("Retorno ao órgão %s falhou: %s",
                             self.orgao_inicial, exc)
                time.sleep(2)
        r.voltou_ao_orgao_inicial = False
        r.falhas_tecnicas.append(
            f"sessão ficou no órgão {orgao_atual} (não voltou para "
            f"{self.orgao_inicial})")
```

- [ ] **Step 4: PASS (8 no arquivo novo) → suíte + ruff → commit**

```bash
git add integra_gov/esiape/ficha_multi_orgao.py tests/test_esiape_multi_orgao.py
git commit -m "feat(esiape): FichaMultiOrgao — encadeamento com ano da virada e lacunas declaradas"
```

---

### Task 7: Exports + documentação

**Files:**
- Modify: `integra_gov/esiape/__init__.py`, `README.md`, `docs/uso-basico.md`, `CHANGELOG.md`
- Test: `tests/test_esiape_ficha_anual.py` (append: exports)

**Interfaces:**
- Produces: `from integra_gov.esiape import FichaAnualServidor, ResultadoFichaEsiape, DadosFuncionais, DadosFuncionaisOrgao, FichaMultiOrgao, ResultadoMultiOrgao` (+ exceções novas já exportadas na Task 1).

- [ ] **Step 1: Teste de exports** (append):

```python
def test_exports_do_ciclo_e2():
    import integra_gov.esiape as pacote

    for nome in ("FichaAnualServidor", "ResultadoFichaEsiape",
                 "DadosFuncionais", "DadosFuncionaisOrgao",
                 "FichaMultiOrgao", "ResultadoMultiOrgao"):
        assert hasattr(pacote, nome), nome
        assert nome in pacote.__all__
```

- [ ] **Step 2: FAIL → Step 3: Implement** — `__init__.py` importa dos 3 módulos novos; `__all__` alfabético.
- [ ] **Step 4: Docs** — seguir o ESTILO EXISTENTE:
  - README: linhas dos 3 módulos na tabela do esiape + exemplo dos DOIS caminhos (um órgão / multi-órgão) com matrícula `"0000000"` e órgão `"00000"`.
  - `docs/uso-basico.md`: seção "Ficha anual e multi-órgão (e-SIAPE)" — blocos de ≤15 anos; requisito da pasta de download do driver (deve coincidir com `pasta_download`); semântica: bloco sem dados vs erro (aborto com `blocos_processados`); multi-órgão: ano da virada, `lacunas`/`falhas_tecnicas`, `voltou_ao_orgao_inicial`; exemplo de leitura do resultado.
  - CHANGELOG `[Não publicado]`: os 3 módulos, pypdf no núcleo, comportamento portado do extrator validado (lote 14/14 multi-órgão), "PENDENTE: verificação ao vivo do módulo público".
- [ ] **Step 5: Suíte + ruff + commit**

```bash
git add integra_gov/esiape/__init__.py tests/test_esiape_ficha_anual.py README.md docs/uso-basico.md CHANGELOG.md
git commit -m "feat(esiape): exports do ciclo E2 + docs (README, uso-basico, CHANGELOG)"
```

---

### Task 8 (gate final, manual): Verificação ao vivo

**NÃO automatizável** — requer o usuário (app SERPRO ID).

- [ ] Script `dados_reais/verifica_esiape_ficha.py` (gitignored): `criar_driver_chrome` (conferir/configurar a pasta de download!) → `AcessoEsiape` → `FichaMultiOrgao(driver, orgao_inicial=..., pasta_saida=...)` → `extrair` de um reformado multi-órgão REAL (matrícula em runtime via `input()`, nada em arquivo) → imprimir `ResultadoMultiOrgao` completo.
- [ ] Conferir: PDF mesclado abre e cobre a faixa (trilha com 2+ órgãos), `lacunas` vazias ou justificadas, cabeçalho de volta ao `orgao_inicial`, sem janelas órfãs.
- [ ] Corrigir o que a verificação apontar (com teste de regressão para cada correção).
- [ ] CHANGELOG: "Verificado ao vivo em AAAA-MM-DD" + o que corrigiu.
- [ ] Commit final e merge.
