# Ficha Anual do Pensionista (SIAPE 3270) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Módulo público `integra_gov.siape.ficha_pensionista` — extrai a ficha financeira anual de UMA pensionista (transação `>FPEMPSFICF`), um PDF por ano, com resultado tipado e mensagens honestas.

**Architecture:** Classe `FichaAnualPensionista` sobre o `ControleTerminal3270` público (mesmo padrão de `TrocaHabilitacao`): posiciona via menu → transação → matrícula (com seleção de instituidor quando pensão múltipla), processa ano a ano decidindo por evidência (janela nativa de salvar = dados; `(0034)` no terminal = vazio), salva via `Edit.set_edit_text` e só declara sucesso com o arquivo no disco. pywinauto tocado APENAS nos dois métodos de diálogo — testes mockam esses métodos e a CI Linux segue verde.

**Tech Stack:** Python 3.10+ (repo), pywinauto (extra `[siape]`, import protegido), pytest + MagicMock(spec=...), ruff.

**Spec:** `docs/superpowers/specs/2026-08-05-ficha-pensionista-3270-design.md`

## Global Constraints

- Padrões da lib: logging stdlib (`_log = logging.getLogger(__name__)`), exceções tipadas filhas de `SiapeError`, type hints, docstrings PT, nenhum dado pessoal/órgão embutido.
- Testes SEMPRE mockados (nada de terminal real); suíte inteira e ruff verdes ao final de cada task.
- Venv do repo SEMPRE (colisão com o `integra` de trabalho global):
  `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe`
- Comandos de teste: `<venv> -m pytest tests/test_siape_ficha_pensionista.py -v` e, no fim de cada task, `<venv> -m pytest -q` + `<venv> -m ruff check .`
- Commits frequentes, mensagens em PT no padrão do repo (`feat(siape): ...`).
- Sequências de terminal e marcadores vêm do extrator privado VALIDADO EM PRODUÇÃO (649 fichas) — não "melhorar" a sequência sem verificação ao vivo.

## File Structure

- Create: `integra_gov/siape/ficha_pensionista.py` — classe + dataclass do resultado (único módulo novo).
- Modify: `integra_gov/siape/exceptions.py` — 3 exceções novas.
- Modify: `integra_gov/siape/_dependencias.py` — expõe `Desktop` (import protegido).
- Modify: `integra_gov/siape/__init__.py` — exports.
- Create: `tests/test_siape_ficha_pensionista.py` — todos os testes do módulo.
- Modify: `README.md`, `docs/uso-basico.md`, `CHANGELOG.md` — docs junto com o módulo.

---

### Task 1: Exceções novas + Desktop protegido + exports

**Files:**
- Modify: `integra_gov/siape/exceptions.py`
- Modify: `integra_gov/siape/_dependencias.py`
- Modify: `integra_gov/siape/__init__.py`
- Test: `tests/test_siape_ficha_pensionista.py`

**Interfaces:**
- Produces: `InstituidorObrigatorio(matriculas_encontradas: list[str])`,
  `FichaIndisponivel(SiapeError)`,
  `ExtracaoFichaInterrompida(anos_processados: list[int], causa: BaseException | None)`,
  `_dependencias.Desktop` (None sem pywinauto). Tasks 3-6 usam exatamente esses nomes.

- [ ] **Step 1: Write the failing tests**

Criar `tests/test_siape_ficha_pensionista.py`:

```python
"""Testes de ``integra_gov.siape.ficha_pensionista`` — terminal mockado."""

from __future__ import annotations

import pytest

from integra_gov.siape.exceptions import (
    ExtracaoFichaInterrompida,
    FichaIndisponivel,
    InstituidorObrigatorio,
    SiapeError,
)


def test_excecoes_sao_siape_error():
    assert issubclass(InstituidorObrigatorio, SiapeError)
    assert issubclass(FichaIndisponivel, SiapeError)
    assert issubclass(ExtracaoFichaInterrompida, SiapeError)


def test_instituidor_obrigatorio_lista_matriculas():
    exc = InstituidorObrigatorio(["1111111", "2222222"])
    assert exc.matriculas_encontradas == ["1111111", "2222222"]
    assert "1111111" in str(exc)
    assert "2222222" in str(exc)


def test_extracao_interrompida_carrega_anos_e_causa():
    causa = RuntimeError("terminal caiu")
    exc = ExtracaoFichaInterrompida([2008, 2009], causa)
    assert exc.anos_processados == [2008, 2009]
    assert exc.causa is causa
    assert "2009" in str(exc)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: FAIL — `ImportError: cannot import name 'ExtracaoFichaInterrompida'`

- [ ] **Step 3: Implement**

Em `integra_gov/siape/exceptions.py`, ao final (mantendo o padrão das existentes):

```python
class InstituidorObrigatorio(SiapeError):
    """A pensionista tem mais de um instituidor e ``matricula_instituidor``
    não foi informada (ou não está entre as opções da tela).

    Attributes:
        matriculas_encontradas: matrículas listadas na tela de seleção,
            para o chamador decidir qual usar.
    """

    def __init__(self, matriculas_encontradas: list[str]):
        self.matriculas_encontradas = list(matriculas_encontradas)
        super().__init__(
            "a pensionista tem mais de um instituidor; informe "
            "matricula_instituidor. Matrículas na tela: "
            + (", ".join(self.matriculas_encontradas) or "(nenhuma legível)")
        )


class FichaIndisponivel(SiapeError):
    """O fluxo não chegou à tela da ficha (matrícula inexistente ou sem
    acesso na habilitação ativa). Distinta de "ano sem dados"."""


class ExtracaoFichaInterrompida(SiapeError):
    """A extração abortou no meio da faixa de anos.

    Os PDFs dos anos já salvos ficam no disco; nenhum resultado parcial é
    devolvido como completo.

    Attributes:
        anos_processados: anos concluídos (com ou sem dados) antes da falha.
        causa: exceção original.
    """

    def __init__(self, anos_processados: list[int], causa: BaseException | None):
        self.anos_processados = list(anos_processados)
        self.causa = causa
        super().__init__(
            f"extração interrompida após os anos {self.anos_processados} "
            f"(causa: {causa!r})"
        )
```

Em `integra_gov/siape/_dependencias.py`, incluir `Desktop` nos dois ramos:

```python
try:
    from pywinauto import Application, Desktop, clipboard
    from pywinauto.findwindows import ElementNotFoundError

    PYWINAUTO_DISPONIVEL = True
except ImportError:  # pywinauto ausente (ex.: Linux/CI ou extra não instalado)
    Application = None
    Desktop = None
    clipboard = None

    class ElementNotFoundError(Exception):  # placeholder p/ blocos ``except``
        """Substituto de ``pywinauto.findwindows.ElementNotFoundError`` quando o
        pywinauto não está instalado."""

    PYWINAUTO_DISPONIVEL = False
```

(única mudança real: `Desktop` importado no try e `Desktop = None` no except;
`exigir_pywinauto` continua checando `Application is None`.)

Em `integra_gov/siape/__init__.py`: adicionar `ExtracaoFichaInterrompida`, `FichaIndisponivel`, `InstituidorObrigatorio` ao import de `exceptions` e ao `__all__` (ordem alfabética, como está).

- [ ] **Step 4: Run tests to verify they pass**

Run: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: 3 passed

- [ ] **Step 5: Suite + lint + commit**

Run: `<venv> -m pytest -q` (≈293+3 passed) e `<venv> -m ruff check .` (limpo)

```bash
git add integra_gov/siape/exceptions.py integra_gov/siape/_dependencias.py integra_gov/siape/__init__.py tests/test_siape_ficha_pensionista.py
git commit -m "feat(siape): excecoes da ficha anual do pensionista + Desktop protegido"
```

---

### Task 2: `ResultadoFichaAnual` + construtor com validações

**Files:**
- Create: `integra_gov/siape/ficha_pensionista.py`
- Test: `tests/test_siape_ficha_pensionista.py` (append)

**Interfaces:**
- Consumes: `ControleTerminal3270` (público), exceções da Task 1.
- Produces: `ResultadoFichaAnual(pdfs: list[Path], anos_com_dados: list[int], anos_sem_dados: list[int], duracao_s: float)`;
  `FichaAnualPensionista(controle, pasta_saida: Path, impressora: str = "Microsoft Print to PDF")` com constantes de classe
  `COMANDO_FICHA=">FPEMPSFICF"`, `CODIGO_SEM_DADOS="(0034)"`, `TEXTO_SEM_DADOS="NAO EXISTEM DADOS"`,
  `TEXTO_SELECAO_INSTITUIDOR="SELECIONE O INSTITUIDOR DO PENSIONISTA"`,
  `TITULO_JANELA_SALVAR="Salvar Saída de Impressão como"`. Tasks 3-6 estendem esta classe.

- [ ] **Step 1: Write the failing tests** (append no arquivo de teste)

```python
from pathlib import Path
from unittest.mock import MagicMock

from integra_gov.siape.controle import ControleTerminal3270
from integra_gov.siape.ficha_pensionista import (
    FichaAnualPensionista,
    ResultadoFichaAnual,
)


def _controle():
    return MagicMock(spec=ControleTerminal3270)


def _ficha(tmp_path, **kw):
    return FichaAnualPensionista(_controle(), pasta_saida=tmp_path, **kw)


def test_resultado_dataclass_campos():
    r = ResultadoFichaAnual(
        pdfs=[Path("a.pdf")], anos_com_dados=[2024],
        anos_sem_dados=[2023], duracao_s=1.5,
    )
    assert r.pdfs == [Path("a.pdf")]
    assert r.anos_com_dados == [2024]
    assert r.anos_sem_dados == [2023]
    assert r.duracao_s == 1.5


def test_construtor_cria_pasta_saida(tmp_path):
    destino = tmp_path / "fichas"
    FichaAnualPensionista(_controle(), pasta_saida=destino)
    assert destino.is_dir()


def test_extrair_valida_matricula_e_anos(tmp_path):
    ficha = _ficha(tmp_path)
    with pytest.raises(ValueError):
        ficha.extrair("", 2008, 2026)
    with pytest.raises(ValueError):
        ficha.extrair("0000001", 2026, 2008)  # faixa invertida
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv> -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: FAIL — `ModuleNotFoundError: integra_gov.siape.ficha_pensionista`

- [ ] **Step 3: Implement** — criar `integra_gov/siape/ficha_pensionista.py`:

```python
"""Ficha financeira anual do pensionista no SIAPE 3270 (``>FPEMPSFICF``).

Extrai a ficha de UMA pensionista para uma faixa de anos: um PDF por ano com
dados, salvo em ``pasta_saida``. Ano sem dados (código ``(0034)`` do SIAPE)
não é erro — entra em ``anos_sem_dados`` no resultado.

Requer terminal já conectado/autenticado (:class:`ControleTerminal3270`) e a
habilitação correta já ativa (:class:`TrocaHabilitacao`). A impressão usa a
impressora de PDF configurada no ambiente (ver ``docs/uso-basico.md``).

Restrições herdadas do 3270: sessão Windows GUI interativa; clipboard e foco
são globais — execução estritamente serial.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from ._menu import garantir_menu_principal
from ._dependencias import Desktop, exigir_pywinauto
from .controle import ControleTerminal3270
from .exceptions import (
    ExtracaoFichaInterrompida,
    FichaIndisponivel,
    InstituidorObrigatorio,
    TransacaoError,
)

_log = logging.getLogger(__name__)


@dataclass
class ResultadoFichaAnual:
    """Resultado da extração de uma pensionista em uma faixa de anos."""

    pdfs: list[Path] = field(default_factory=list)
    anos_com_dados: list[int] = field(default_factory=list)
    anos_sem_dados: list[int] = field(default_factory=list)
    duracao_s: float = 0.0


class FichaAnualPensionista:
    """Extrai a ficha financeira anual de uma pensionista (``>FPEMPSFICF``).

    Args:
        controle: :class:`ControleTerminal3270` conectado.
        pasta_saida: pasta onde os PDFs anuais são salvos (criada se preciso).
        impressora: nome da impressora de PDF esperada no ambiente — usada em
            mensagens de erro quando a janela de salvar não aparece (o módulo
            NÃO configura a impressora).
    """

    COMANDO_FICHA = ">FPEMPSFICF"
    TEXTO_SELECAO_INSTITUIDOR = "SELECIONE O INSTITUIDOR DO PENSIONISTA"
    CODIGO_SEM_DADOS = "(0034)"
    TEXTO_SEM_DADOS = "NAO EXISTEM DADOS"
    TITULO_JANELA_SALVAR = "Salvar Saída de Impressão como"
    # Qualquer código (0NNN) fora do fluxo do ano indica problema no acesso
    # (matrícula inexistente, sem habilitação, etc.).
    PADRAO_CODIGO_ERRO = re.compile(r"\(0\d{3}\)")

    # Geometria da tela de seleção de instituidores (validada em produção).
    LINHA_INICIO_LISTA_INSTITUIDORES = 7
    LINHA_FIM_LISTA_INSTITUIDORES = 18

    # Esperas (valores otimizados validados; máquinas lentas podem folgar).
    DELAY_PADRAO = 0.5
    DELAY_CURTO = 0.15
    ESPERA_MSG_IMPRESSAO = 1.0   # após S+ENTER, mensagem de impressão
    ESPERA_POS_CONFIRMACAO = 2.2  # janela de salvar OU (0034) surgirem
    TIMEOUT_JANELA_SALVAR = 15.0
    TIMEOUT_ARQUIVO = 10.0

    def __init__(
        self,
        controle: ControleTerminal3270,
        pasta_saida: Path,
        impressora: str = "Microsoft Print to PDF",
    ):
        self.controle = controle
        self.pasta_saida = Path(pasta_saida)
        self.pasta_saida.mkdir(parents=True, exist_ok=True)
        self.impressora = impressora

    def extrair(
        self,
        matricula_pensionista: str,
        ano_inicial: int,
        ano_final: int,
        matricula_instituidor: str | None = None,
    ) -> ResultadoFichaAnual:
        """Extrai a ficha anual da pensionista na faixa ``[ano_inicial, ano_final]``.

        Raises:
            ValueError: parâmetros inválidos.
            InstituidorObrigatorio: pensão múltipla sem ``matricula_instituidor``.
            FichaIndisponivel: matrícula inexistente/sem acesso.
            ExtracaoFichaInterrompida: falha no meio da faixa (carrega
                ``anos_processados`` e ``causa``).
        """
        matricula = str(matricula_pensionista).strip()
        if not matricula:
            raise ValueError("matricula_pensionista é obrigatória")
        if int(ano_inicial) > int(ano_final):
            raise ValueError(
                f"faixa invertida: ano_inicial={ano_inicial} > ano_final={ano_final}"
            )
        raise NotImplementedError  # fluxo completo entra nas Tasks 3-6
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv> -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: 6 passed (os 3 da Task 1 + estes 3)

- [ ] **Step 5: Commit**

```bash
git add integra_gov/siape/ficha_pensionista.py tests/test_siape_ficha_pensionista.py
git commit -m "feat(siape): esqueleto da FichaAnualPensionista (resultado tipado + validacoes)"
```

---

### Task 3: Posicionamento (menu → transação → matrícula) + `FichaIndisponivel`

**Files:**
- Modify: `integra_gov/siape/ficha_pensionista.py`
- Test: `tests/test_siape_ficha_pensionista.py` (append)

**Interfaces:**
- Consumes: `garantir_menu_principal(controle)` (`_menu`), constantes da Task 2.
- Produces: `_posicionar(matricula: str, matricula_instituidor: str | None) -> None`
  (deixa o terminal no prompt de ano); `_tela_de_selecao(tela: str) -> bool`;
  Task 4 implementa `_selecionar_instituidor`; Task 6 chama `_posicionar`.

- [ ] **Step 1: Write the failing tests** (append)

```python
from integra_gov.siape import _menu


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    from integra_gov.siape import ficha_pensionista as fmod

    monkeypatch.setattr(fmod.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(_menu.time, "sleep", lambda *_a, **_k: None)


def _controle_posicionavel(tela_apos_matricula="TELA DA FICHA  EXERCICIO"):
    c = MagicMock(spec=ControleTerminal3270)
    c.extrair_texto.return_value = _menu.TEXTO_LINHA_COMANDO  # menu alcançável
    c.copiar_tela.return_value = tela_apos_matricula
    return c


def test_posicionar_envia_comando_e_matricula(tmp_path):
    c = _controle_posicionavel()
    ficha = FichaAnualPensionista(c, pasta_saida=tmp_path)
    ficha._posicionar("0000001", None)
    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert FichaAnualPensionista.COMANDO_FICHA in enviados
    assert "0000001" in enviados


def test_posicionar_matricula_inexistente_levanta_ficha_indisponivel(tmp_path):
    # Código de erro (0NNN) na tela após a matrícula, sem tela de seleção.
    c = _controle_posicionavel("(0125) MATRICULA NAO CADASTRADA")
    ficha = FichaAnualPensionista(c, pasta_saida=tmp_path)
    with pytest.raises(FichaIndisponivel) as exc:
        ficha._posicionar("9999999", None)
    assert "(0125)" in str(exc.value)


def test_posicionar_0034_no_ano_nao_e_ficha_indisponivel(tmp_path):
    # (0034) é "sem dados" do ANO — não deve virar FichaIndisponivel aqui,
    # pois a tela da ficha abriu (o marcador de seleção não está presente e
    # não há outro código de erro).
    c = _controle_posicionavel("TELA DA FICHA (0034) NAO EXISTEM DADOS")
    ficha = FichaAnualPensionista(c, pasta_saida=tmp_path)
    ficha._posicionar("0000001", None)  # não levanta
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv> -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: FAIL — `AttributeError: ... has no attribute '_posicionar'`

- [ ] **Step 3: Implement** — adicionar à classe (substituindo nada da Task 2):

```python
    # ----- posicionamento -----

    def _posicionar(self, matricula: str, matricula_instituidor: str | None) -> None:
        """Menu → ``>FPEMPSFICF`` → matrícula; trata a tela de seleção de
        instituidores; deixa o terminal no prompt de ano (EXERCÍCIO)."""
        garantir_menu_principal(self.controle)
        self.controle.enviar_teclas(self.COMANDO_FICHA)
        self.controle.enviar_teclas("{ENTER}")
        time.sleep(self.DELAY_PADRAO)

        self.controle.enviar_teclas(matricula)
        self.controle.enviar_teclas("{ENTER}")
        time.sleep(self.DELAY_PADRAO)

        tela = self._normalizar(self.controle.copiar_tela() or "")
        if self._tela_de_selecao(tela):
            self._selecionar_instituidor(tela, matricula_instituidor)
            return
        codigo = self.PADRAO_CODIGO_ERRO.search(tela)
        if codigo and codigo.group(0) != self.CODIGO_SEM_DADOS:
            linha_erro = self._linha_do_codigo(tela, codigo.start())
            raise FichaIndisponivel(
                f"matrícula {matricula} indisponível na habilitação ativa: "
                f"{linha_erro}"
            )
        _log.info("Posicionado na ficha da matrícula %s", matricula)

    def _tela_de_selecao(self, tela: str) -> bool:
        return self.TEXTO_SELECAO_INSTITUIDOR in tela

    def _selecionar_instituidor(
        self, tela: str, matricula_instituidor: str | None
    ) -> None:
        raise NotImplementedError  # Task 4

    # ----- utilitários de tela -----

    @staticmethod
    def _normalizar(tela: str) -> str:
        return tela.replace("\xa0", " ")

    def _linha_do_codigo(self, tela: str, posicao: int) -> str:
        largura = ControleTerminal3270.CARACTERES_POR_LINHA
        inicio = (posicao // largura) * largura
        return tela[inicio : inicio + largura].strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv> -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add integra_gov/siape/ficha_pensionista.py tests/test_siape_ficha_pensionista.py
git commit -m "feat(siape): posicionamento da ficha anual com FichaIndisponivel honesta"
```

---

### Task 4: Seleção de instituidor (pensão múltipla)

**Files:**
- Modify: `integra_gov/siape/ficha_pensionista.py` (substitui o stub `_selecionar_instituidor`)
- Test: `tests/test_siape_ficha_pensionista.py` (append)

**Interfaces:**
- Consumes: `_posicionar` (Task 3), `InstituidorObrigatorio` (Task 1).
- Produces: `_selecionar_instituidor(tela, matricula_instituidor)` funcional;
  `_matriculas_da_selecao(tela) -> list[str]` (ordem das opções na tela).

- [ ] **Step 1: Write the failing tests** (append)

```python
LARGURA_FICHA = ControleTerminal3270.CARACTERES_POR_LINHA


def _tela_selecao(*linhas_de_opcao):
    """Tela com o marcador de seleção e opções '( ) <matricula> NOME' a partir
    da linha LINHA_INICIO_LISTA_INSTITUIDORES."""
    inicio = FichaAnualPensionista.LINHA_INICIO_LISTA_INSTITUIDORES
    linhas = [""] * 30
    linhas[2] = FichaAnualPensionista.TEXTO_SELECAO_INSTITUIDOR
    for i, opcao in enumerate(linhas_de_opcao):
        linhas[inicio - 1 + i] = opcao
    return "".join(linha.ljust(LARGURA_FICHA)[:LARGURA_FICHA] for linha in linhas)


def test_selecao_sem_matricula_levanta_com_lista(tmp_path):
    tela = _tela_selecao("( ) 1111111 FULANO", "( ) 2222222 BELTRANO")
    c = _controle_posicionavel(tela)
    ficha = FichaAnualPensionista(c, pasta_saida=tmp_path)
    with pytest.raises(InstituidorObrigatorio) as exc:
        ficha._posicionar("0000002", None)
    assert exc.value.matriculas_encontradas == ["1111111", "2222222"]


def test_selecao_matricula_fora_da_lista_levanta(tmp_path):
    tela = _tela_selecao("( ) 1111111 FULANO")
    c = _controle_posicionavel(tela)
    ficha = FichaAnualPensionista(c, pasta_saida=tmp_path)
    with pytest.raises(InstituidorObrigatorio):
        ficha._posicionar("0000002", "7777777")


def test_selecao_segunda_opcao_navega_e_marca(tmp_path):
    tela = _tela_selecao("( ) 1111111 FULANO", "( ) 2222222 BELTRANO")
    c = _controle_posicionavel(tela)
    ficha = FichaAnualPensionista(c, pasta_saida=tmp_path)
    ficha._posicionar("0000002", "2222222")
    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert enviados.count("{TAB}") == 1  # 2ª opção = 1 TAB
    assert "X" in enviados


def test_selecao_tolera_zeros_a_esquerda(tmp_path):
    tela = _tela_selecao("( ) 1111111 FULANO")
    c = _controle_posicionavel(tela)
    ficha = FichaAnualPensionista(c, pasta_saida=tmp_path)
    ficha._posicionar("0000002", "01111111")  # zero-pad da planilha
    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert "X" in enviados
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv> -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: FAIL — `NotImplementedError` em `_selecionar_instituidor`

- [ ] **Step 3: Implement** — substituir o stub:

```python
    def _selecionar_instituidor(
        self, tela: str, matricula_instituidor: str | None
    ) -> None:
        """Seleciona a linha do instituidor na tela de pensão múltipla.

        Comparação NUMÉRICA (tolerante a zeros à esquerda): a tela mostra
        ``146605`` enquanto planilhas costumam trazer ``0146605``.
        """
        opcoes = self._matriculas_da_selecao(tela)
        if matricula_instituidor is None:
            raise InstituidorObrigatorio(opcoes)
        alvo = int(str(matricula_instituidor).lstrip("0") or "0")
        posicao = next(
            (i for i, m in enumerate(opcoes) if int(m.lstrip("0") or "0") == alvo),
            None,
        )
        if posicao is None:
            raise InstituidorObrigatorio(opcoes)
        for _ in range(posicao):
            self.controle.enviar_teclas("{TAB}")
            time.sleep(self.DELAY_CURTO)
        self.controle.enviar_teclas("X")
        self.controle.enviar_teclas("{ENTER}")
        time.sleep(self.DELAY_PADRAO)
        _log.info(
            "Instituidor %s selecionado (opção %d de %d)",
            matricula_instituidor, posicao + 1, len(opcoes),
        )

    def _matriculas_da_selecao(self, tela: str) -> list[str]:
        """Matrículas das linhas de opção (com parênteses), na ordem da tela."""
        largura = ControleTerminal3270.CARACTERES_POR_LINHA
        matriculas: list[str] = []
        for n_linha in range(
            self.LINHA_INICIO_LISTA_INSTITUIDORES,
            self.LINHA_FIM_LISTA_INSTITUIDORES + 1,
        ):
            linha = tela[(n_linha - 1) * largura : n_linha * largura]
            if "(" not in linha or ")" not in linha:
                continue
            numeros = re.findall(r"\d{6,9}", linha)
            if numeros:
                matriculas.append(numeros[0])
        return matriculas
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv> -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add integra_gov/siape/ficha_pensionista.py tests/test_siape_ficha_pensionista.py
git commit -m "feat(siape): selecao de instituidor em pensao multipla (nunca escolhe sozinha)"
```

---

### Task 5: Processamento do ano (dados / sem dados / janela de salvar)

**Files:**
- Modify: `integra_gov/siape/ficha_pensionista.py`
- Test: `tests/test_siape_ficha_pensionista.py` (append)

**Interfaces:**
- Consumes: constantes de espera (Task 2).
- Produces: `_processar_ano(matricula: str, ano: int) -> Path | None` (None = sem
  dados); pontos de contato pywinauto ISOLADOS em `_janela_salvar_existe() -> bool`
  e `_salvar_via_dialogo(caminho: Path) -> None` (os testes mockam ESTES DOIS);
  `_confirmar_arquivo(caminho: Path) -> None` (levanta `TransacaoError` se o
  arquivo não materializar). Task 6 chama `_processar_ano`.

- [ ] **Step 1: Write the failing tests** (append)

```python
from unittest.mock import patch


def _ficha_ano(tmp_path, tela_terminal=""):
    c = _controle_posicionavel(tela_terminal)
    return FichaAnualPensionista(c, pasta_saida=tmp_path), c


def test_ano_sem_dados_detecta_0034_e_recupera_com_f2(tmp_path):
    ficha, c = _ficha_ano(tmp_path, "(0034) NAO EXISTEM DADOS PARA ESTA CONSULTA")
    with patch.object(ficha, "_janela_salvar_existe", return_value=False):
        resultado = ficha._processar_ano("0000001", 2010)
    assert resultado is None
    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert "2010" in enviados
    assert "S" in enviados
    assert "{F2}" in enviados  # recuperação do cursor pós-(0034)


def test_ano_com_dados_salva_e_confirma_no_disco(tmp_path):
    ficha, c = _ficha_ano(tmp_path)
    destino_esperado = tmp_path / "ficha_0000001_2024.pdf"

    def _salva(caminho):
        caminho.write_bytes(b"%PDF-conteudo")

    with patch.object(ficha, "_janela_salvar_existe", return_value=True), \
         patch.object(ficha, "_salvar_via_dialogo", side_effect=_salva):
        resultado = ficha._processar_ano("0000001", 2024)
    assert resultado == destino_esperado
    assert destino_esperado.read_bytes() == b"%PDF-conteudo"


def test_ano_com_dados_mas_arquivo_nao_materializa_levanta(tmp_path):
    ficha, c = _ficha_ano(tmp_path)
    from integra_gov.siape.exceptions import TransacaoError

    with patch.object(ficha, "_janela_salvar_existe", return_value=True), \
         patch.object(ficha, "_salvar_via_dialogo", return_value=None), \
         patch.object(FichaAnualPensionista, "TIMEOUT_ARQUIVO", 0.01):
        with pytest.raises(TransacaoError):
            ficha._processar_ano("0000001", 2024)


def test_nem_janela_nem_0034_levanta_com_nome_da_impressora(tmp_path):
    ficha, c = _ficha_ano(tmp_path, "tela sem nada reconhecivel")
    from integra_gov.siape.exceptions import TransacaoError

    with patch.object(ficha, "_janela_salvar_existe", return_value=False), \
         patch.object(FichaAnualPensionista, "TIMEOUT_JANELA_SALVAR", 0.01):
        with pytest.raises(TransacaoError) as exc:
            ficha._processar_ano("0000001", 2024)
    assert "Microsoft Print to PDF" in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv> -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: FAIL — `AttributeError: ... no attribute '_processar_ano'`

- [ ] **Step 3: Implement** — adicionar à classe:

```python
    # ----- processamento de um ano -----

    def _processar_ano(self, matricula: str, ano: int) -> Path | None:
        """Emite e salva a ficha de um ano. ``None`` = ano sem dados (0034).

        Sequência validada em produção: ano → X → ENTER (tela "CONFIRMA
        EMISSÃO? S/N") → S + ENTER → mensagem de impressão (ENTER) → então a
        janela de salvar surge (há dados) OU o (0034) aparece no terminal.
        A decisão é pelo que EXISTE, não por timeout cego.
        """
        self.controle.enviar_teclas(str(ano))
        time.sleep(self.DELAY_CURTO)
        self.controle.enviar_teclas("X")
        time.sleep(self.DELAY_CURTO)
        self.controle.enviar_teclas("{ENTER}")
        time.sleep(self.DELAY_PADRAO)
        self.controle.enviar_teclas("S")
        self.controle.enviar_teclas("{ENTER}")
        time.sleep(self.ESPERA_MSG_IMPRESSAO)
        self.controle.enviar_teclas("{ENTER}")  # fecha a mensagem de impressão
        time.sleep(self.ESPERA_POS_CONFIRMACAO)

        limite = time.monotonic() + self.TIMEOUT_JANELA_SALVAR
        while True:
            if self._janela_salvar_existe():
                break
            if self._sem_dados_no_terminal():
                _log.info("Ano %d sem dados (0034)", ano)
                self._recuperar_cursor_apos_sem_dados()
                return None
            if time.monotonic() >= limite:
                raise TransacaoError(
                    f"ano {ano}: nem a janela '{self.TITULO_JANELA_SALVAR}' nem "
                    f"o {self.CODIGO_SEM_DADOS} apareceram em "
                    f"{self.TIMEOUT_JANELA_SALVAR}s — confira se a impressora "
                    f"ativa do SIAPE é '{self.impressora}'"
                )
            time.sleep(self.DELAY_CURTO)

        caminho = self.pasta_saida / f"ficha_{matricula}_{ano}.pdf"
        self._salvar_via_dialogo(caminho)
        self._confirmar_arquivo(caminho)
        _log.info("Ano %d salvo em %s", ano, caminho)
        return caminho

    def _sem_dados_no_terminal(self) -> bool:
        tela = self._normalizar(self.controle.copiar_tela() or "")
        return self.CODIGO_SEM_DADOS in tela or self.TEXTO_SEM_DADOS in tela

    def _recuperar_cursor_apos_sem_dados(self) -> None:
        """A leitura da tela desalinha o cursor; F2 o devolve ao campo
        EXERCÍCIO — sem isso os dígitos do próximo ano caem em campos errados."""
        self.controle.enviar_teclas("{F2}")
        time.sleep(self.DELAY_PADRAO)

    def _confirmar_arquivo(self, caminho: Path) -> None:
        """Só declara o ano salvo quando o arquivo EXISTE com tamanho > 0."""
        limite = time.monotonic() + self.TIMEOUT_ARQUIVO
        while time.monotonic() < limite:
            if caminho.exists() and caminho.stat().st_size > 0:
                return
            time.sleep(self.DELAY_CURTO)
        raise TransacaoError(
            f"o PDF não se materializou em {caminho} "
            f"(timeout {self.TIMEOUT_ARQUIVO}s)"
        )

    # ----- pontos de contato com o pywinauto (mockados nos testes) -----

    def _janela_salvar_existe(self) -> bool:
        """True se a janela nativa de salvar impressão está aberta."""
        exigir_pywinauto()
        try:
            return Desktop(backend="win32").window(
                title=self.TITULO_JANELA_SALVAR
            ).exists()
        except Exception:  # janela sumiu entre o find e o exists
            return False

    def _salvar_via_dialogo(self, caminho: Path) -> None:
        """Preenche a janela de salvar de forma ATÔMICA (``set_edit_text``,
        imune a interferência de clipboard) e confirma."""
        exigir_pywinauto()
        dlg = Desktop(backend="win32").window(title=self.TITULO_JANELA_SALVAR)
        dlg.wait("ready", timeout=self.TIMEOUT_JANELA_SALVAR)
        escreveu = False
        for classe in ("Edit", "ComboBox"):
            try:
                dlg.child_window(class_name=classe, found_index=0).set_edit_text(
                    str(caminho)
                )
                escreveu = True
                break
            except Exception:
                continue
        if not escreveu:  # fallback: digitação direta
            dlg.type_keys(str(caminho), with_spaces=True)
        time.sleep(self.DELAY_CURTO)
        try:
            dlg.child_window(title_re="Salvar.*", class_name="Button").click_input()
        except Exception:
            dlg.type_keys("{ENTER}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv> -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add integra_gov/siape/ficha_pensionista.py tests/test_siape_ficha_pensionista.py
git commit -m "feat(siape): processamento por ano — janela=dados, (0034)=vazio, arquivo confirmado no disco"
```

---

### Task 6: `extrair` completo + `ExtracaoFichaInterrompida` + F12

**Files:**
- Modify: `integra_gov/siape/ficha_pensionista.py` (completa o `extrair` da Task 2)
- Modify: `integra_gov/siape/__init__.py` (exporta `FichaAnualPensionista`, `ResultadoFichaAnual`)
- Test: `tests/test_siape_ficha_pensionista.py` (append)

**Interfaces:**
- Consumes: `_posicionar` (Task 3-4), `_processar_ano` (Task 5).
- Produces: `extrair(...) -> ResultadoFichaAnual` público e exportado no pacote.

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_extrair_integra_anos_com_e_sem_dados(tmp_path):
    ficha, c = _ficha_ano(tmp_path)

    def _processa(matricula, ano):  # 2023 sem dados; 2024 com
        if ano == 2023:
            return None
        p = tmp_path / f"ficha_{matricula}_{ano}.pdf"
        p.write_bytes(b"%PDF")
        return p

    with patch.object(ficha, "_posicionar") as pos, \
         patch.object(ficha, "_processar_ano", side_effect=_processa):
        r = ficha.extrair("0000001", 2023, 2024)
    pos.assert_called_once_with("0000001", None)
    assert r.anos_sem_dados == [2023]
    assert r.anos_com_dados == [2024]
    assert r.pdfs == [tmp_path / "ficha_0000001_2024.pdf"]
    assert r.duracao_s >= 0
    # F12 de finalização (volta ao prompt de matrícula)
    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert "{F12}" in enviados


def test_extrair_falha_no_meio_aborta_com_anos_processados(tmp_path):
    ficha, c = _ficha_ano(tmp_path)
    from integra_gov.siape.exceptions import SessaoSiapePerdida

    def _processa(matricula, ano):
        if ano == 2025:
            raise SessaoSiapePerdida("terminal corrompido")
        p = tmp_path / f"ficha_{matricula}_{ano}.pdf"
        p.write_bytes(b"%PDF")
        return p

    with patch.object(ficha, "_posicionar"), \
         patch.object(ficha, "_processar_ano", side_effect=_processa):
        with pytest.raises(ExtracaoFichaInterrompida) as exc:
            ficha.extrair("0000001", 2024, 2026)
    assert exc.value.anos_processados == [2024]
    assert isinstance(exc.value.causa, SessaoSiapePerdida)
    # o PDF de 2024 fica no disco para diagnóstico
    assert (tmp_path / "ficha_0000001_2024.pdf").exists()


def test_excecoes_de_contrato_nao_sao_embrulhadas(tmp_path):
    # InstituidorObrigatorio/FichaIndisponivel acontecem ANTES do loop de anos
    # e chegam puras ao chamador.
    ficha, c = _ficha_ano(tmp_path)
    with patch.object(
        ficha, "_posicionar", side_effect=InstituidorObrigatorio(["1111111"])
    ):
        with pytest.raises(InstituidorObrigatorio):
            ficha.extrair("0000002", 2024, 2024)


def test_exports_do_pacote():
    from integra_gov.siape import FichaAnualPensionista as F
    from integra_gov.siape import ResultadoFichaAnual as R

    assert F is FichaAnualPensionista
    assert R is ResultadoFichaAnual
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `<venv> -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: FAIL — `NotImplementedError` no `extrair` / `ImportError` no export

- [ ] **Step 3: Implement** — substituir o `raise NotImplementedError` do `extrair`:

```python
        inicio = time.monotonic()
        resultado = ResultadoFichaAnual()
        self._posicionar(matricula, matricula_instituidor)
        try:
            for ano in range(int(ano_inicial), int(ano_final) + 1):
                caminho = self._processar_ano(matricula, ano)
                if caminho is None:
                    resultado.anos_sem_dados.append(ano)
                else:
                    resultado.anos_com_dados.append(ano)
                    resultado.pdfs.append(caminho)
        except Exception as exc:
            anos = resultado.anos_com_dados + resultado.anos_sem_dados
            raise ExtracaoFichaInterrompida(sorted(anos), exc) from exc
        finally:
            self._finalizar()
        resultado.duracao_s = time.monotonic() - inicio
        _log.info(
            "Matrícula %s: %d anos com dados, %d sem dados, %.1fs",
            matricula, len(resultado.anos_com_dados),
            len(resultado.anos_sem_dados), resultado.duracao_s,
        )
        return resultado
```

E adicionar à classe:

```python
    def _finalizar(self) -> None:
        """F12: devolve o terminal ao prompt de matrícula (o chamador pode
        emendar a próxima pensionista). Falha aqui não mascara o resultado."""
        try:
            self.controle.enviar_teclas("{F12}")
            time.sleep(self.DELAY_PADRAO)
        except Exception:
            _log.warning("F12 de finalização falhou; terminal pode exigir menu")
```

No `integra_gov/siape/__init__.py`: importar `FichaAnualPensionista` e
`ResultadoFichaAnual` de `.ficha_pensionista` e incluir no `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `<venv> -m pytest tests/test_siape_ficha_pensionista.py -v`
Expected: 21 passed

- [ ] **Step 5: Suite + lint + commit**

Run: `<venv> -m pytest -q` e `<venv> -m ruff check .` — verdes.

```bash
git add integra_gov/siape/ficha_pensionista.py integra_gov/siape/__init__.py tests/test_siape_ficha_pensionista.py
git commit -m "feat(siape): FichaAnualPensionista.extrair completo com aborto honesto"
```

---

### Task 7: Documentação (junto com o módulo)

**Files:**
- Modify: `README.md` (linha na tabela do siape + exemplo)
- Modify: `docs/uso-basico.md` (seção nova)
- Modify: `CHANGELOG.md` (entrada "Não lançado")

**Interfaces:**
- Consumes: API pública final da Task 6 (exemplos DEVEM compilar contra ela).

- [ ] **Step 1: README** — na tabela de módulos do `integra_gov.siape`, adicionar:

```markdown
| `ficha_pensionista` | Ficha financeira anual do pensionista (`>FPEMPSFICF`): um PDF por ano, resultado tipado, ano sem dados não é erro |
```

E no bloco de exemplo do siape (após a troca de habilitação):

```python
from pathlib import Path
from integra_gov.siape import FichaAnualPensionista

ficha = FichaAnualPensionista(controle, pasta_saida=Path("fichas/"))
resultado = ficha.extrair("0000001", 2008, 2026)
print(resultado.anos_com_dados, resultado.anos_sem_dados)
# pensão múltipla: informe matricula_instituidor= (senão InstituidorObrigatorio
# lista as opções da tela para você escolher)
```

- [ ] **Step 2: docs/uso-basico.md** — seção "Ficha anual do pensionista (SIAPE 3270)" com: pré-requisitos (terminal conectado, habilitação ativa via `TrocaHabilitacao`, impressora de PDF configurada como saída do SIAPE, sessão Windows GUI interativa, execução serial — clipboard/foco globais, locale PT-BR); o exemplo do README; a tabela de exceções (`InstituidorObrigatorio`, `FichaIndisponivel`, `ExtracaoFichaInterrompida` com `anos_processados`/`causa`, `SessaoSiapePerdida`); nota de que constantes de espera são atributos de classe ajustáveis.

- [ ] **Step 3: CHANGELOG** — em "Não lançado":

```markdown
- feat(siape): `FichaAnualPensionista` — ficha financeira anual do pensionista
  (`>FPEMPSFICF`), um PDF por ano com confirmação em disco, seleção de
  instituidor em pensão múltipla (nunca escolhe sozinha) e aborto honesto
  (`ExtracaoFichaInterrompida` com `anos_processados`). Comportamento portado
  do extrator validado em produção (649 fichas). PENDENTE: verificação ao vivo.
```

- [ ] **Step 4: Suite + lint + commit**

Run: `<venv> -m pytest -q` e `<venv> -m ruff check .` — verdes.

```bash
git add README.md docs/uso-basico.md CHANGELOG.md
git commit -m "docs(siape): ficha anual do pensionista no README, uso-basico e CHANGELOG"
```

---

### Task 8 (gate final, manual): Verificação ao vivo

**NÃO automatizável** — requer o usuário (PIN/OTP; dia útil 7h-22h).

- [ ] Script descartável em `dados_reais/verifica_ficha_pensionista.py` (gitignored): conecta com `LancadorHod`/`ConexaoTerminal3270`/`ControleTerminal3270`, `TrocaHabilitacao` para o órgão do usuário, `FichaAnualPensionista.extrair` de UMA pensionista de faixa curta (2-3 anos, incluindo 1 ano sabidamente vazio), imprime o `ResultadoFichaAnual`.
- [ ] Rodar com o usuário presente; conferir: PDFs válidos no destino, ano vazio em `anos_sem_dados`, F12 deixou o terminal utilizável.
- [ ] Corrigir o que a verificação apontar (com teste de regressão mockado para cada correção).
- [ ] Atualizar o CHANGELOG: trocar "PENDENTE: verificação ao vivo" por "Verificado ao vivo em AAAA-MM-DD" + o que a verificação corrigiu.
- [ ] Commit final e merge.
