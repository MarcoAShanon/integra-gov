# e-SIAPE dados pessoais (CDCOINDPES) — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar `integra_gov.esiape.dados_pessoais`: leitura pura dos 9 campos cadastrais de um PDF da CDCOINDPES e a classe que navega, imprime e devolve o mesmo resultado.

**Architecture:** Duas camadas num único módulo. `ler_dados_pessoais(pdf)` é pura (pypdf + regex sobre a camada de texto em modo layout). `DadosPessoaisServidor(driver, pasta_saida, pasta_download=None).consultar(matricula)` compõe as funções já existentes de `navegacao` e `impressao`, renomeia o PDF e chama a leitura pura, conferindo a matrícula. Exceção nova `DadosPessoaisIndisponiveis`.

**Tech Stack:** Python 3.10+, Selenium (só via driver injetado), pypdf `extraction_mode="layout"`, pytest com driver falso e PDF sintético (`tests/_pdf_sintetico.pdf_bytes`).

**Spec:** `docs/superpowers/specs/2026-09-16-esiape-dados-pessoais-design.md`

## Global Constraints

- Nenhum dado pessoal ou órgão real em código, teste ou doc: matrícula `0000000`, CPF `000.000.000-00`, e-mail `fulano@exemplo.gov.br`, órgão `00000 - ORGAO/TESTE`.
- Logs só com os dois últimos dígitos da matrícula (`*****NN`); nunca nome, CPF, e-mail ou o `texto`.
- Padrões da lib: `logging` stdlib, exceções tipadas filhas de `EsiapeError`, type hints, docstrings em português, teste mockado para todo comportamento.
- Doc (README, CHANGELOG, `docs/uso-basico.md`) entra no MESMO commit do módulo exportado (Task 3).
- Comandos com caminhos absolutos. Python do venv: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe`. Suíte inteira hoje: **799 testes**; `ruff check .` limpo.
- Commit com `git commit -F <arquivo>` (mensagem sem aspas problemáticas no PowerShell), terminando com `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Não usar `git checkout -- <arquivo>` em arquivo não commitado.

---

## Estrutura de arquivos

| arquivo | responsabilidade |
|---|---|
| `integra_gov/esiape/exceptions.py` (modificar, ao fim) | `DadosPessoaisIndisponiveis(matricula, motivo)` |
| `integra_gov/esiape/dados_pessoais.py` (criar) | dataclass `DadosPessoais`, `ler_dados_pessoais`, normalizações privadas, `DadosPessoaisServidor` |
| `integra_gov/esiape/__init__.py` (modificar) | exportar os 4 nomes |
| `tests/test_esiape_dados_pessoais.py` (criar) | todos os testes do módulo |
| `README.md`, `CHANGELOG.md`, `docs/uso-basico.md` (modificar) | doc do módulo |
| `dados_reais/esiape_dados_pessoais_gate.py` (criar; pasta gitignored) | script do gate ao vivo |

---

### Task 1: exceção, dataclass e leitura pura do PDF

**Files:**
- Modify: `integra_gov/esiape/exceptions.py` (acrescentar ao final)
- Create: `integra_gov/esiape/dados_pessoais.py`
- Create: `tests/test_esiape_dados_pessoais.py`

**Interfaces:**
- Consumes: `integra_gov.ficha_financeira.tem_camada_de_texto(origem) -> bool` (levanta `PdfIlegivelError` se o arquivo nem abre); `tests._pdf_sintetico.pdf_bytes(paginas, *, com_fonte=True) -> bytes`.
- Produces: `DadosPessoais` (dataclass com os campos da spec), `ler_dados_pessoais(pdf: Path) -> DadosPessoais`, `extrair_campos(texto: str) -> dict[str, str | None]`, `DadosPessoaisIndisponiveis`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_esiape_dados_pessoais.py`:

```python
"""Testes de ``integra_gov.esiape.dados_pessoais`` (CDCOINDPES)."""

from __future__ import annotations

from pathlib import Path

import pytest

from integra_gov.esiape.exceptions import DadosPessoaisIndisponiveis, EsiapeError
from integra_gov.ficha_financeira import PdfIlegivelError
from tests._pdf_sintetico import pdf_bytes

# Rótulos reais da tela CDCOINDPES; valores fictícios.
LINHAS_PDF = [
    "DADOS INDIVIDUAIS PESSOAIS",
    "MATRICULA: 0000000     NOME: FULANO DE TAL",
    "SIT.SER.: 02 APOSENTADO     NUMERO DO CPF: 000.000.000-00",
    "DATA NASCIMENTO: 15AGO1960     E-MAIL PESSOAL: FULANO@EXEMPLO.GOV.BR",
    "MUNICIPIO: CIDADE EXEMPLO     UF: XX",
    "ORGAO SOLICITADO: 00000 - ORGAO/TESTE",
]
TEXTO = "\n".join(LINHAS_PDF)


def pdf_cadastral(caminho: Path, linhas=LINHAS_PDF) -> Path:
    caminho.write_bytes(pdf_bytes([linhas]))
    return caminho


def test_excecao_nova_e_esiape_error():
    exc = DadosPessoaisIndisponiveis("0000000", "botão Imprimir não apareceu")
    assert isinstance(exc, EsiapeError)
    assert exc.matricula == "0000000"
    assert exc.motivo == "botão Imprimir não apareceu"
    assert "*****00" in str(exc) and "0000000" not in str(exc)
    assert "Imprimir" in str(exc)


# ----------------------------------------------------------------- parsing
def test_extrair_campos_le_os_9_rotulos():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos(TEXTO)
    assert c == {
        "matricula": "0000000",
        "nome": "FULANO DE TAL",
        "situacao": "APOSENTADO",
        "cpf": "000.000.000-00",
        "data_nascimento": "15/08/1960",
        "email": "fulano@exemplo.gov.br",
        "municipio": "Cidade Exemplo",
        "uf": "XX",
        "orgao": "ORGAO/TESTE",
    }


def test_extrair_campos_rotulo_ausente_vira_none():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos("MATRICULA: 0000000\nNOME: FULANO DE TAL")
    assert c["matricula"] == "0000000"
    assert c["nome"] == "FULANO DE TAL"
    for k in ("situacao", "cpf", "data_nascimento", "email", "municipio", "uf", "orgao"):
        assert c[k] is None


def test_extrair_campos_corta_no_proximo_rotulo_da_mesma_linha():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    c = extrair_campos("NOME: FULANO DE TAL  SIT.SER.: 01 ATIVO PERMANENTE")
    assert c["nome"] == "FULANO DE TAL"
    assert c["situacao"] == "ATIVO PERMANENTE"


def test_extrair_campos_matricula_so_digitos():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    assert extrair_campos("MATRICULA: 00.000-00")["matricula"] == "0000000"


def test_extrair_campos_texto_irreconhecivel_tudo_none():
    from integra_gov.esiape.dados_pessoais import extrair_campos

    assert all(v is None for v in extrair_campos("tela irreconhecivel").values())


@pytest.mark.parametrize("bruto, esperado", [
    ("15AGO1960", "15/08/1960"),
    ("01JAN2001", "01/01/2001"),
    ("15XYZ1960", None),
    ("1960-08-15", None),
    ("", None),
])
def test_data_siape(bruto, esperado):
    from integra_gov.esiape.dados_pessoais import _data_siape

    assert _data_siape(bruto) == esperado


@pytest.mark.parametrize("bruto, esperado", [
    ("02 APOSENTADO", "APOSENTADO"),
    ("APOSENTADO", "APOSENTADO"),
    ("", None),
])
def test_situacao(bruto, esperado):
    from integra_gov.esiape.dados_pessoais import _situacao

    assert _situacao(bruto) == esperado


@pytest.mark.parametrize("bruto, esperado", [
    ("00000 - ORGAO/TESTE", "ORGAO/TESTE"),
    ("ORGAO/TESTE", "ORGAO/TESTE"),
    ("", None),
])
def test_orgao(bruto, esperado):
    from integra_gov.esiape.dados_pessoais import _orgao

    assert _orgao(bruto) == esperado


# ------------------------------------------------------ ler_dados_pessoais
def test_ler_dados_pessoais_devolve_dataclass_com_pdf_e_texto(tmp_path):
    from integra_gov.esiape.dados_pessoais import DadosPessoais, ler_dados_pessoais

    pdf = pdf_cadastral(tmp_path / "x.pdf")
    d = ler_dados_pessoais(pdf)
    assert isinstance(d, DadosPessoais)
    assert d.pdf == pdf
    assert d.matricula == "0000000"
    assert d.nome == "FULANO DE TAL"
    assert d.email == "fulano@exemplo.gov.br"
    assert "NUMERO DO CPF" in d.texto


def test_ler_dados_pessoais_pdf_sem_texto_levanta(tmp_path):
    from integra_gov.esiape.dados_pessoais import ler_dados_pessoais

    pdf = tmp_path / "vetor.pdf"
    pdf.write_bytes(pdf_bytes([None], com_fonte=False))
    with pytest.raises(PdfIlegivelError):
        ler_dados_pessoais(pdf)


def test_ler_dados_pessoais_arquivo_que_nao_abre_levanta(tmp_path):
    from integra_gov.esiape.dados_pessoais import ler_dados_pessoais

    pdf = tmp_path / "lixo.pdf"
    pdf.write_bytes(b"isto nao e um PDF")
    with pytest.raises(PdfIlegivelError):
        ler_dados_pessoais(pdf)


def test_ler_dados_pessoais_le_todas_as_paginas(tmp_path):
    from integra_gov.esiape.dados_pessoais import ler_dados_pessoais

    pdf = tmp_path / "duas.pdf"
    pdf.write_bytes(pdf_bytes([LINHAS_PDF[:3], LINHAS_PDF[3:]]))
    d = ler_dados_pessoais(pdf)
    assert d.uf == "XX" and d.orgao == "ORGAO/TESTE"
```

Observação sobre o guarda: `tem_camada_de_texto` devolve `False` para PDF vetorizado e levanta `PdfIlegivelError` para arquivo que nem abre. A spec pede `PdfIlegivelError` nos dois casos em `ler_dados_pessoais`, então a função converte o `False` em `PdfIlegivelError` com mensagem própria.

- [ ] **Step 2: Rodar e ver falhar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_dados_pessoais.py -q
```

Esperado: falha na coleta com `ImportError: cannot import name 'DadosPessoaisIndisponiveis'`.

- [ ] **Step 3: Acrescentar a exceção**

Ao final de `integra_gov/esiape/exceptions.py`:

```python
class DadosPessoaisIndisponiveis(EsiapeError):
    """A CDCOINDPES não devolveu os dados pessoais da matrícula pedida.

    Cobre três situações: o botão Consultar/Imprimir não apareceu no prazo
    (o sinal real para matrícula inexistente ainda não é conhecido — ver o
    comentário em ``dados_pessoais``), a impressão não produziu PDF, ou o PDF
    impresso traz OUTRA matrícula (tela anterior ainda carregada).

    Attributes:
        matricula: a matrícula pedida (na mensagem, só os 2 últimos dígitos).
        motivo: descrição curta do que faltou.
    """

    def __init__(self, matricula: str, motivo: str):
        self.matricula = matricula
        self.motivo = motivo
        super().__init__(
            f"dados pessoais indisponíveis para a matrícula "
            f"*****{str(matricula)[-2:]}: {motivo}"
        )
```

- [ ] **Step 4: Escrever o módulo (só a camada pura)**

Criar `integra_gov/esiape/dados_pessoais.py`:

```python
"""Dados individuais pessoais (CDCOINDPES): PDF impresso + campos lidos dele.

Duas camadas. :func:`ler_dados_pessoais` é pura — abre um PDF já no disco e
devolve os campos; serve a quem reprocessa PDFs sem abrir o navegador.
:class:`DadosPessoaisServidor` navega na transação, imprime via popup,
renomeia o PDF e chama a leitura pura, conferindo a matrícula.

Por que ler do PDF, e não da tela: os rótulos da camada de texto do PDF
(``MATRICULA``, ``NOME``, ``SIT.SER.``, ``NUMERO DO CPF``, ``DATA
NASCIMENTO``, ``E-MAIL PESSOAL``, ``MUNICIPIO``, ``UF``, ``ORGAO
SOLICITADO``) foram estáveis em todas as impressões do gate de 11/09/2026, e
o PDF é necessário de qualquer forma como documento a anexar. Campo cujo
rótulo não aparece fica ``None``: ausência é informação, não falha.

Nada pessoal neste arquivo — matrícula, nome e CPF são sempre parâmetro.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from ..ficha_financeira import PdfIlegivelError, tem_camada_de_texto

_log = logging.getLogger(__name__)

_MESES = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
          "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}

#: Rótulos da tela, como regex. ``SIT.SER.`` tem pontos literais.
_ROTULOS = {
    "matricula": r"MATRICULA",
    "nome": r"NOME",
    "situacao": r"SIT\.SER\.",
    "cpf": r"NUMERO DO CPF",
    "data_nascimento": r"DATA NASCIMENTO",
    "email": r"E-MAIL PESSOAL",
    "municipio": r"MUNICIPIO",
    "uf": r"UF",
    "orgao": r"ORGAO SOLICITADO",
}

#: O que encerra um valor: 2+ espaços seguidos de outro rótulo (MAIÚSCULAS,
#: pontos, barras, dígitos) e ``:``, ou o fim da linha.
_FIM_DO_VALOR = r"(?=\s{2,}[A-ZÀ-Ú][A-ZÀ-Ú ./0-9º-]*:|$)"


@dataclass
class DadosPessoais:
    """Os campos cadastrais lidos do PDF da CDCOINDPES (ausente = ``None``)."""

    matricula: str | None
    nome: str | None
    situacao: str | None
    cpf: str | None
    data_nascimento: str | None
    email: str | None
    municipio: str | None
    uf: str | None
    orgao: str | None
    texto: str
    pdf: Path | None = None


# ----------------------------------------------------------- normalizações
def _campo(texto: str, rotulo: str) -> str | None:
    """Valor cru após ``rotulo:`` até o próximo rótulo ou o fim da linha."""
    m = re.search(rf"(?<![A-Z]){rotulo}\s*:\s*(.*?){_FIM_DO_VALOR}", texto, re.M)
    if not m:
        return None
    valor = m.group(1).strip()
    return valor or None


def _data_siape(bruto: str | None) -> str | None:
    """``15AGO1960`` → ``15/08/1960``; qualquer outra forma → ``None``."""
    m = re.fullmatch(r"(\d{2})([A-Z]{3})(\d{4})", (bruto or "").strip().upper())
    if not m or m.group(2) not in _MESES:
        return None
    return f"{m.group(1)}/{_MESES[m.group(2)]:02d}/{m.group(3)}"


def _situacao(bruto: str | None) -> str | None:
    """``02 APOSENTADO`` → ``APOSENTADO`` (o código numérico não interessa)."""
    valor = re.sub(r"^\d+\s*", "", (bruto or "").strip())
    return valor or None


def _orgao(bruto: str | None) -> str | None:
    """``00000 - ORGAO/TESTE`` → ``ORGAO/TESTE``."""
    valor = re.sub(r"^\d+\s*-\s*", "", (bruto or "").strip())
    return valor or None


def extrair_campos(texto: str) -> dict[str, str | None]:
    """Os 9 campos normalizados a partir da camada de texto (ausente = None)."""
    cru = {chave: _campo(texto, rotulo) for chave, rotulo in _ROTULOS.items()}
    matricula = re.sub(r"\D", "", cru["matricula"] or "") or None
    return {
        "matricula": matricula,
        "nome": cru["nome"],
        "situacao": _situacao(cru["situacao"]),
        "cpf": cru["cpf"],
        "data_nascimento": _data_siape(cru["data_nascimento"]),
        "email": (cru["email"] or "").lower() or None,
        "municipio": (cru["municipio"] or "").title() or None,
        "uf": cru["uf"],
        "orgao": _orgao(cru["orgao"]),
    }


# ----------------------------------------------------------- leitura pura
def ler_dados_pessoais(pdf: Path) -> DadosPessoais:
    """Lê os campos de um PDF da CDCOINDPES já no disco (sem navegador).

    Raises:
        PdfIlegivelError: o arquivo não abre como PDF ou não tem camada de
            texto (impressora errada — ver ``docs/uso-basico.md``).
    """
    pdf = Path(pdf)
    if not tem_camada_de_texto(pdf):
        raise PdfIlegivelError(
            f"{pdf} não tem camada de texto: as fontes viraram contorno "
            f"vetorial. O destino da impressão tem de ser o 'Salvar como "
            f"PDF' nativo do Chrome (docs/uso-basico.md, 'Configuração do "
            f"Chrome')")
    texto = "\n".join(
        (p.extract_text(extraction_mode="layout") or "")
        for p in PdfReader(str(pdf)).pages)
    campos = extrair_campos(texto)
    return DadosPessoais(**campos, texto=texto, pdf=pdf)
```

Nota sobre `_campo`: o lookbehind `(?<![A-Z])` impede que `UF` case dentro de outra palavra; e `NOME` não casa em `NOME DO TECNICO` porque exige `:` logo após o rótulo. Se algum teste de parsing falhar por conta do regex, ajuste `_FIM_DO_VALOR` e reexecute: a regra é a do script validado ao vivo (2+ espaços + rótulo em maiúsculas + `:`).

- [ ] **Step 5: Rodar os testes da tarefa**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_dados_pessoais.py -q
```

Esperado: todos passam (1 + 5 + 11 parametrizados + 4 = 21 testes). Depois:

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m ruff check integra_gov/esiape/dados_pessoais.py integra_gov/esiape/exceptions.py tests/test_esiape_dados_pessoais.py
```

Esperado: `All checks passed!`

- [ ] **Step 6: Commit**

Mensagem em arquivo (`$env:TEMP\msg_t1.txt`):

```
feat(esiape): leitura pura dos dados pessoais da CDCOINDPES a partir do PDF

ler_dados_pessoais(pdf) devolve os 9 campos normalizados + texto bruto;
rotulo ausente vira None. Excecao DadosPessoaisIndisponiveis. Camada com
navegador vem no commit seguinte; o modulo ainda nao esta exportado.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
git add integra_gov/esiape/exceptions.py integra_gov/esiape/dados_pessoais.py tests/test_esiape_dados_pessoais.py
git commit -F "$env:TEMP\msg_t1.txt"
```

---

### Task 2: `DadosPessoaisServidor.consultar` (navegação + impressão)

**Files:**
- Modify: `integra_gov/esiape/dados_pessoais.py` (acrescentar imports e a classe)
- Modify: `tests/test_esiape_dados_pessoais.py` (acrescentar os testes)

**Interfaces:**
- Consumes (de `integra_gov.esiape.navegacao`): `navegar_para_transacao(driver, transacao, seletor_confirmacao, timeout=30) -> bool`, `esperar_seletor(driver, seletor_css, timeout=20) -> tuple | None`, `procurar_em_frames(driver, seletor_css) -> tuple | None`, `fechar_janelas_extras(driver, handle_principal=None)`, `limpar_overlay(driver, timeout=10)`, `relogin_pendente(driver) -> bool`, `limpar_flag_relogin(driver)`. De `integra_gov.esiape.impressao`: `imprimir_via_popup(driver, clicar_imprimir, pasta_download, *, timeout_popup=20, timeout_download=60, delay=1.0) -> Path`. Da Task 1: `ler_dados_pessoais`, `DadosPessoais`, `DadosPessoaisIndisponiveis`.
- Produces: `DadosPessoaisServidor(driver, pasta_saida: Path, pasta_download: Path | None = None)` com `consultar(matricula: str) -> DadosPessoais` e atributos de classe `TRANSACAO`, `SEL_MATRICULA`, `SEL_CONSULTAR`, `SEL_IMPRIMIR`, `SEL_GERAR_PDF`, `SEL_SAIR`, `TIMEOUT_TELA`.

- [ ] **Step 1: Escrever os testes que falham**

No topo de `tests/test_esiape_dados_pessoais.py`, junto aos imports existentes, acrescentar:

```python
from unittest.mock import patch

from selenium.webdriver.common.keys import Keys

from integra_gov.esiape import dados_pessoais as dmod
from integra_gov.esiape.exceptions import PdfImpressoIlegivel, TransacaoNaoAbriu
```

E acrescentar ao final do arquivo:

```python
# ------------------------------------------------- DadosPessoaisServidor
class _Elemento:
    def __init__(self):
        self.cliques = 0
        self.teclas = []

    def click(self):
        self.cliques += 1

    def clear(self):
        pass

    def send_keys(self, *t):
        self.teclas.extend(t)


class _Driver:
    """Driver mínimo: elementos por seletor CSS, relogin como atributo."""

    def __init__(self, seletores):
        self.el = {s: _Elemento() for s in seletores}
        self._esiape_relogin_pendente = False

    def find_element(self, by, valor):
        if valor not in self.el:
            raise Exception(f"no such element: {valor}")
        return self.el[valor]


S = dmod.DadosPessoaisServidor
TODOS = (S.SEL_MATRICULA, S.SEL_CONSULTAR, S.SEL_IMPRIMIR, S.SEL_GERAR_PDF, S.SEL_SAIR)


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """Navegação e impressão substituídas; devolve (driver, servidor, chamadas)."""
    monkeypatch.setattr(dmod.time, "sleep", lambda *_a, **_k: None)
    driver = _Driver(TODOS)
    chamadas = {"navegar": [], "limpar_flag": 0, "imprimir": 0}

    def navegar(d, transacao, seletor, timeout=30):
        chamadas["navegar"].append(transacao)
        return True

    def imprimir(d, clicar, pasta_download, **kw):
        chamadas["imprimir"] += 1
        clicar()
        bruto = Path(pasta_download) / "cis_bruto.pdf"
        pdf_cadastral(bruto)
        return bruto

    monkeypatch.setattr(dmod, "navegar_para_transacao", navegar)
    monkeypatch.setattr(dmod, "esperar_seletor", lambda d, s, timeout=20: (0,) if s in d.el else None)
    monkeypatch.setattr(dmod, "procurar_em_frames", lambda d, s: (0,) if s in d.el else None)
    monkeypatch.setattr(dmod, "fechar_janelas_extras", lambda d, *a, **k: None)
    monkeypatch.setattr(dmod, "limpar_overlay", lambda d, *a, **k: True)
    monkeypatch.setattr(dmod, "limpar_flag_relogin",
                        lambda d: chamadas.__setitem__("limpar_flag", chamadas["limpar_flag"] + 1))
    monkeypatch.setattr(dmod, "imprimir_via_popup", imprimir)
    servidor = S(driver, pasta_saida=tmp_path / "saida")
    return driver, servidor, chamadas


def test_pastas_default_como_ficha_anual(tmp_path):
    s = S(object(), pasta_saida=tmp_path / "s")
    assert s.pasta_saida == tmp_path / "s"
    assert s.pasta_download == tmp_path / "s" / "_download_esiape"
    assert s.pasta_saida.is_dir() and s.pasta_download.is_dir()


def test_matricula_vazia_levanta_value_error(ambiente):
    _, servidor, _ = ambiente
    with pytest.raises(ValueError):
        servidor.consultar("   ")


def test_consultar_caminho_feliz(ambiente):
    driver, servidor, chamadas = ambiente
    d = servidor.consultar(" 0000000 ")
    assert chamadas["navegar"] == ["CDCOINDPES"]
    assert driver.el[S.SEL_MATRICULA].teclas == ["0000000", Keys.ENTER]
    for sel in (S.SEL_CONSULTAR, S.SEL_IMPRIMIR, S.SEL_GERAR_PDF, S.SEL_SAIR):
        assert driver.el[sel].cliques == 1, sel
    assert d.pdf == servidor.pasta_saida / "dados_pessoais_0000000.pdf"
    assert d.pdf.exists()
    assert not (servidor.pasta_download / "cis_bruto.pdf").exists()
    assert d.nome == "FULANO DE TAL" and d.matricula == "0000000"


def test_consultar_sobrescreve_pdf_anterior(ambiente):
    _, servidor, _ = ambiente
    destino = servidor.pasta_saida / "dados_pessoais_0000000.pdf"
    destino.write_bytes(b"velho")
    d = servidor.consultar("0000000")
    assert d.pdf == destino and destino.read_bytes() != b"velho"


def test_relogin_atravessado_repete_uma_vez(ambiente):
    driver, servidor, chamadas = ambiente
    tentativas = []

    def navegar(d, transacao, seletor, timeout=30):
        tentativas.append(1)
        if len(tentativas) == 1:
            d._esiape_relogin_pendente = True
            return False
        return True

    with patch.object(dmod, "navegar_para_transacao", navegar):
        d = servidor.consultar("0000000")
    assert len(tentativas) == 2
    assert chamadas["limpar_flag"] == 1
    assert d.matricula == "0000000"


def test_falha_sem_relogin_nao_repete(ambiente):
    driver, servidor, chamadas = ambiente
    with patch.object(dmod, "navegar_para_transacao", lambda *a, **k: False):
        with pytest.raises(TransacaoNaoAbriu):
            servidor.consultar("0000000")
    assert chamadas["limpar_flag"] == 0


def test_relogin_persistente_levanta_apos_segunda_falha(ambiente):
    driver, servidor, chamadas = ambiente

    def navegar(d, transacao, seletor, timeout=30):
        d._esiape_relogin_pendente = True
        return False

    with patch.object(dmod, "navegar_para_transacao", navegar):
        with pytest.raises(TransacaoNaoAbriu):
            servidor.consultar("0000000")
    assert chamadas["limpar_flag"] == 1


def test_botao_imprimir_ausente_levanta_indisponiveis(ambiente):
    driver, servidor, _ = ambiente
    del driver.el[S.SEL_IMPRIMIR]
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("0000000")
    assert "Imprimir" in str(exc.value) or S.SEL_IMPRIMIR in str(exc.value)


def test_impressao_sem_pdf_levanta_indisponiveis(ambiente):
    _, servidor, _ = ambiente

    def imprimir(*a, **k):
        raise TimeoutError("nenhum PDF apareceu")

    with patch.object(dmod, "imprimir_via_popup", imprimir):
        with pytest.raises(DadosPessoaisIndisponiveis) as exc:
            servidor.consultar("0000000")
    assert "nenhum PDF apareceu" in str(exc.value)


def test_matricula_divergente_no_pdf_levanta(ambiente):
    _, servidor, _ = ambiente
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("1111111")
    assert "*****00" in str(exc.value) and "*****11" in str(exc.value)


def test_pdf_sem_texto_levanta_ilegivel_e_mantem_arquivo(ambiente):
    _, servidor, _ = ambiente

    def imprimir(d, clicar, pasta_download, **kw):
        bruto = Path(pasta_download) / "cis_bruto.pdf"
        bruto.write_bytes(pdf_bytes([None], com_fonte=False))
        return bruto

    with patch.object(dmod, "imprimir_via_popup", imprimir):
        with pytest.raises(PdfImpressoIlegivel) as exc:
            servidor.consultar("0000000")
    assert Path(exc.value.caminho).exists()


def test_sair_falhando_nao_derruba(ambiente, caplog):
    driver, servidor, _ = ambiente
    driver.el[S.SEL_SAIR].click = lambda: (_ for _ in ()).throw(RuntimeError("stale"))
    d = servidor.consultar("0000000")
    assert d.matricula == "0000000"
    assert any("Sair" in r.message for r in caplog.records)


def test_log_nao_expoe_matricula_inteira(ambiente, caplog):
    import logging

    _, servidor, _ = ambiente
    with caplog.at_level(logging.INFO, logger="integra_gov.esiape.dados_pessoais"):
        with pytest.raises(DadosPessoaisIndisponiveis):   # PDF traz 0000000
            servidor.consultar("1234567")
    texto = "
".join(r.getMessage() for r in caplog.records)
    assert "1234567" not in texto and "*****67" in texto


def test_pdf_impresso_ilegivel_sem_bloco_tem_mensagem_sem_bloco(tmp_path):
    exc = PdfImpressoIlegivel(tmp_path / "x.pdf", None, "motivo")
    assert "bloco" not in str(exc) and "ilegível" in str(exc)
```

Em `test_matricula_divergente_no_pdf_levanta` o PDF sintético traz `0000000` e a pedida é `1111111`; a mensagem mostra as duas mascaradas.

- [ ] **Step 2: Rodar e ver falhar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_dados_pessoais.py -q
```

Esperado: `AttributeError: module ... has no attribute 'DadosPessoaisServidor'` nos testes novos; os da Task 1 seguem passando.

- [ ] **Step 3: Implementar a classe**

Em `integra_gov/esiape/dados_pessoais.py`, acrescentar aos imports:

```python
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from .exceptions import (
    DadosPessoaisIndisponiveis,
    PdfImpressoIlegivel,
    TransacaoNaoAbriu,
)
from .impressao import imprimir_via_popup
from .navegacao import (
    esperar_seletor,
    fechar_janelas_extras,
    limpar_flag_relogin,
    limpar_overlay,
    navegar_para_transacao,
    procurar_em_frames,
    relogin_pendente,
)
```

E ao final do arquivo:

```python
# --------------------------------------------------------- com navegador
def _mascarar(matricula: str) -> str:
    return f"*****{matricula[-2:]}"


class DadosPessoaisServidor:
    """Consulta a CDCOINDPES, imprime o PDF e devolve os campos lidos dele.

    Args:
        driver: WebDriver com a sessão do e-SIAPE autenticada e o Chrome
            configurado para "Salvar como PDF" (``docs/uso-basico.md``).
        pasta_saida: onde fica ``dados_pessoais_<matricula>.pdf``.
        pasta_download: pasta de download do Chrome (default: subpasta
            ``_download_esiape`` de ``pasta_saida``). Tem de ser DEDICADA:
            :func:`~integra_gov.esiape.impressao.imprimir_via_popup` apaga
            todos os PDFs dela antes de imprimir.
    """

    TRANSACAO = "CDCOINDPES"
    SEL_MATRICULA = '[data-testtoolid="w_matr_infor_alfa"]'
    SEL_CONSULTAR = '[data-testtoolid="onClickbtnConsulta"]'
    SEL_IMPRIMIR = '[data-testtoolid="onClickbtnImprimir"]'
    SEL_GERAR_PDF = '[data-testtoolid="w_report.onGeneratePrintVersion"]'
    SEL_SAIR = '[data-testtoolid="onClickBtnSair"]'
    # PENDÊNCIA (gate ao vivo): o sinal da tela para matrícula inexistente
    # não é conhecido. Se houver mensagem, ela entra aqui e é detectada
    # antes do timeout do botão Imprimir.
    MSG_NAO_ENCONTRADA: str | None = None

    TIMEOUT_TELA = 30
    DELAY_APOS_ENTER = 1.0
    DELAY_APOS_CONSULTAR = 1.5

    def __init__(self, driver, pasta_saida: Path,
                 pasta_download: Path | None = None):
        self.driver = driver
        self.pasta_saida = Path(pasta_saida)
        self.pasta_saida.mkdir(parents=True, exist_ok=True)
        self.pasta_download = (Path(pasta_download) if pasta_download
                               else self.pasta_saida / "_download_esiape")
        self.pasta_download.mkdir(parents=True, exist_ok=True)

    # ----- passos -----

    def _abrir_transacao(self) -> None:
        """Abre a CDCOINDPES; se a lib abortou por relogin atravessado,
        limpa a flag e tenta UMA vez mais (a transação é por matrícula e não
        depende da habilitação, que o relogin devolve ao padrão)."""
        for tentativa in (1, 2):
            if navegar_para_transacao(self.driver, self.TRANSACAO,
                                      self.SEL_MATRICULA,
                                      timeout=self.TIMEOUT_TELA):
                return
            if tentativa == 1 and relogin_pendente(self.driver):
                _log.warning("%s: relogin atravessado; repetindo a navegação",
                             self.TRANSACAO)
                limpar_flag_relogin(self.driver)
                continue
            break
        raise TransacaoNaoAbriu(self.TRANSACAO, self.SEL_MATRICULA)

    def _clicar(self, seletor: str, matricula: str, rotulo: str) -> None:
        if esperar_seletor(self.driver, seletor,
                           timeout=self.TIMEOUT_TELA) is None:
            raise DadosPessoaisIndisponiveis(
                matricula, f"o botão {rotulo} ({seletor}) não apareceu em "
                           f"{self.TIMEOUT_TELA}s")
        self.driver.find_element(By.CSS_SELECTOR, seletor).click()

    def _sair(self) -> None:
        try:
            if procurar_em_frames(self.driver, self.SEL_SAIR) is not None:
                self.driver.find_element(By.CSS_SELECTOR, self.SEL_SAIR).click()
                time.sleep(self.DELAY_APOS_ENTER)
        except Exception as exc:  # noqa: BLE001 — Sair é cortesia, não etapa
            _log.warning("%s: Sair falhou (ignorado): %s", self.TRANSACAO, exc)

    # ----- API -----

    def consultar(self, matricula: str) -> DadosPessoais:
        """Imprime e lê os dados pessoais da matrícula.

        Raises:
            ValueError: matrícula vazia.
            TransacaoNaoAbriu: a tela não montou (mesmo após a repetição
                por relogin).
            DadosPessoaisIndisponiveis: botão ausente no prazo, impressão
                sem PDF, ou PDF de outra matrícula.
            PdfImpressoIlegivel: o PDF veio sem camada de texto (arquivo
                mantido na pasta de download para inspeção).
        """
        matricula = str(matricula).strip()
        if not matricula:
            raise ValueError("matricula é obrigatória")
        mascarada = _mascarar(matricula)
        _log.info("%s: consultando a matrícula %s", self.TRANSACAO, mascarada)

        fechar_janelas_extras(self.driver)
        limpar_overlay(self.driver)
        self._abrir_transacao()

        campo = self.driver.find_element(By.CSS_SELECTOR, self.SEL_MATRICULA)
        campo.clear()
        campo.send_keys(matricula)
        campo.send_keys(Keys.ENTER)
        time.sleep(self.DELAY_APOS_ENTER)
        self._clicar(self.SEL_CONSULTAR, matricula, "Consultar")
        time.sleep(self.DELAY_APOS_CONSULTAR)
        self._clicar(self.SEL_IMPRIMIR, matricula, "Imprimir")

        try:
            bruto = imprimir_via_popup(
                self.driver,
                lambda: self._clicar(self.SEL_GERAR_PDF, matricula, "Gerar PDF"),
                self.pasta_download)
        except DadosPessoaisIndisponiveis:
            raise
        except Exception as exc:  # noqa: BLE001 — timeout de popup/download
            raise DadosPessoaisIndisponiveis(
                matricula, f"a impressão não produziu PDF: {exc}") from exc

        try:
            legivel = tem_camada_de_texto(bruto)
            motivo = "as fontes viraram contorno vetorial"
        except PdfIlegivelError as exc:
            legivel, motivo = False, f"o arquivo não pôde ser aberto: {exc}"
        if not legivel:
            # fica com o nome bruto, na pasta de download, para inspeção
            raise PdfImpressoIlegivel(bruto, None, motivo)

        destino = self.pasta_saida / f"dados_pessoais_{matricula}.pdf"
        if destino.exists():
            destino.unlink()
        bruto.rename(destino)
        self._sair()

        dados = ler_dados_pessoais(destino)
        if dados.matricula != matricula:
            raise DadosPessoaisIndisponiveis(
                matricula, f"o PDF traz a matrícula "
                           f"{_mascarar(dados.matricula or '')}, não a pedida")
        _log.info("%s: %s lida, %d/9 campos", self.TRANSACAO, mascarada,
                  sum(1 for c in extrair_campos(dados.texto).values() if c))
        return dados
```

`PdfImpressoIlegivel` nasceu na ficha anual e exige um `bloco` na mensagem ("o PDF do bloco 0-0"). Mudança mínima em `integra_gov/esiape/exceptions.py`, dentro de `PdfImpressoIlegivel.__init__`, para que `bloco=None` produza mensagem sem "bloco". Substituir o início da f-string por:

```python
        onde = (f"o PDF do bloco {bloco[0]}-{bloco[1]}" if bloco
                else "o PDF impresso")
        super().__init__(
            f"{onde} saiu ilegível por máquina "
```

mantendo o restante da mensagem como está. Atualizar a docstring do atributo `bloco` para "o par ``(ano_de, ano_ate)`` que estava sendo impresso, ou ``None`` fora da ficha anual".

- [ ] **Step 4: Rodar os testes**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_dados_pessoais.py tests/test_esiape_ficha_anual.py -q
```

Esperado: todos passam (os de `ficha_anual` continuam passando com a mensagem da exceção inalterada quando há bloco).

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m ruff check integra_gov tests
```

Esperado: `All checks passed!`

- [ ] **Step 5: Commit**

Mensagem (`$env:TEMP\msg_t2.txt`):

```
feat(esiape): DadosPessoaisServidor.consultar imprime a CDCOINDPES e le os campos

Navega (uma repeticao se um relogin atravessou), imprime via popup, guarda
tem_camada_de_texto, renomeia para dados_pessoais_<matricula>.pdf e confere
que o PDF e da matricula pedida. PdfImpressoIlegivel aceita bloco=None.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
git add integra_gov/esiape/dados_pessoais.py integra_gov/esiape/exceptions.py tests/test_esiape_dados_pessoais.py
git commit -F "$env:TEMP\msg_t2.txt"
```

---

### Task 3: exports, documentação e script do gate ao vivo

**Files:**
- Modify: `integra_gov/esiape/__init__.py`
- Modify: `README.md` (exemplo após o bloco de `FichaMultiOrgao`, ~linha 500; linha na tabela após `dados_funcionais`, ~linha 623)
- Modify: `CHANGELOG.md` (seção `### Adicionado` de `[Não publicado]`, ~linha 103, no topo da lista)
- Modify: `docs/uso-basico.md` (nova subseção antes de `## Ler uma ficha financeira`, ~linha 1150)
- Modify: `tests/test_esiape_dados_pessoais.py` (teste de export)
- Create: `dados_reais/esiape_dados_pessoais_gate.py` (pasta gitignored; não entra no commit)

**Interfaces:**
- Consumes: tudo da Task 1 e 2.
- Produces: `from integra_gov.esiape import DadosPessoais, DadosPessoaisServidor, DadosPessoaisIndisponiveis, ler_dados_pessoais`.

- [ ] **Step 1: Teste de export (falha)**

Acrescentar ao final de `tests/test_esiape_dados_pessoais.py`:

```python
def test_exportado_no_subpacote():
    import integra_gov.esiape as pkg

    for nome in ("DadosPessoais", "DadosPessoaisServidor",
                 "DadosPessoaisIndisponiveis", "ler_dados_pessoais"):
        assert hasattr(pkg, nome), nome
        assert nome in pkg.__all__, nome
```

Rodar:

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_dados_pessoais.py::test_exportado_no_subpacote -q
```

Esperado: `AssertionError: DadosPessoais`.

- [ ] **Step 2: Exportar**

Em `integra_gov/esiape/__init__.py`: após `from .dados_funcionais import ...`, inserir

```python
from .dados_pessoais import DadosPessoais, DadosPessoaisServidor, ler_dados_pessoais
```

Na lista de `from .exceptions import (...)`, inserir `DadosPessoaisIndisponiveis,` em ordem alfabética (após `AutenticacaoNaoConfirmada`). Em `__all__`, inserir em ordem: `"DadosPessoais"`, `"DadosPessoaisIndisponiveis"`, `"DadosPessoaisServidor"` (após `"DadosFuncionaisOrgao"`) e `"ler_dados_pessoais"` (após `"imprimir_via_popup"`). No docstring do pacote, na primeira frase, trocar "acesso via SERPRO ID (você autentica) e troca de habilitação (TROCAHAB)." por "acesso via SERPRO ID (você autentica), troca de habilitação (TROCAHAB) e dados pessoais (CDCOINDPES) lidos do PDF impresso."

Rodar o teste de export: PASS.

- [ ] **Step 3: README**

Após o bloco de código de `FichaMultiOrgao` (termina com `print(...)` e uma linha em branco, antes do próximo parágrafo), inserir:

````markdown
Os **dados pessoais** de uma matrícula (`CDCOINDPES`) saem como PDF e como
campos lidos dele — nome, situação, CPF, data de nascimento, e-mail,
município, UF e órgão. Quem já tem o PDF no disco lê sem abrir o navegador:

```python
from pathlib import Path
from integra_gov.esiape import DadosPessoaisServidor, ler_dados_pessoais

dados = DadosPessoaisServidor(driver, pasta_saida=Path("cadastrais/")).consultar("0000000")
print(dados.pdf, dados.nome, dados.situacao)   # matrícula fictícia

dados = ler_dados_pessoais(Path("cadastrais/dados_pessoais_0000000.pdf"))  # sem navegador
```

Campo cujo rótulo não aparece no PDF fica `None`; o texto inteiro do PDF vem
em `dados.texto` para quem precisar de outro rótulo.
````

Na tabela, após a linha de `dados_funcionais`:

```markdown
| `integra_gov.esiape.dados_pessoais` | `CDCOINDPES`: PDF dos dados pessoais + 9 campos lidos dele (`ler_dados_pessoais` funciona sem navegador); confere a matrícula do PDF | ✅ |
```

- [ ] **Step 4: CHANGELOG**

No topo de `### Adicionado` em `[Não publicado]`:

```markdown
- **`integra_gov.esiape.dados_pessoais`** (`CDCOINDPES`): `DadosPessoaisServidor.consultar(matricula)`
  imprime o PDF dos dados pessoais e devolve `DadosPessoais` com nove campos
  lidos da camada de texto (matrícula, nome, situação, CPF, nascimento,
  e-mail, município, UF, órgão) mais o texto bruto; `ler_dados_pessoais(pdf)`
  faz a leitura sem navegador. Rótulo ausente vira `None`, nunca exceção. A
  matrícula lida do PDF é conferida com a pedida (`DadosPessoaisIndisponiveis`
  se divergir); um relogin do SERPRO atravessado entre consultas é absorvido
  com uma repetição. Porte do script que rodou na apresentação de 11/09/2026
  (5 matrículas, 9/9 campos). `PdfImpressoIlegivel` passa a aceitar
  `bloco=None`. **Ainda não verificado ao vivo pelo módulo** (o gate está
  planejado; até lá, o sinal de matrícula inexistente é o timeout do botão
  Imprimir).
```

- [ ] **Step 5: uso-basico**

Antes de `## Ler uma ficha financeira`, inserir:

````markdown
## Dados pessoais de uma matrícula (e-SIAPE)

A `CDCOINDPES` mostra o cadastro de uma matrícula e imprime um PDF. O módulo
imprime e lê os campos **do PDF** (os rótulos da camada de texto são estáveis;
o texto dos frames CIS, não).

```python
from pathlib import Path
from integra_gov.esiape import AcessoEsiape, DadosPessoaisServidor

AcessoEsiape(driver).executar()                      # você confirma no app
cad = DadosPessoaisServidor(driver, pasta_saida=Path("cadastrais/"))
dados = cad.consultar("0000000")                     # matrícula fictícia
dados.pdf            # cadastrais/dados_pessoais_0000000.pdf
dados.nome, dados.situacao, dados.cpf, dados.data_nascimento   # "15/08/1960"
dados.email, dados.municipio, dados.uf, dados.orgao
dados.texto          # o PDF inteiro, para outro rótulo que você precise
```

O Chrome precisa das prefs de impressão da seção "Configuração do Chrome"
(acima), e `pasta_download` (default `cadastrais/_download_esiape`) tem de
ser **dedicada**: a impressão apaga todos os PDFs dela antes de começar.

Regras de honestidade do módulo:

- campo cujo rótulo não aparece fica `None`; não é erro;
- o PDF é conferido: se trouxer outra matrícula (tela anterior ainda
  carregada), `DadosPessoaisIndisponiveis`;
- PDF sem camada de texto (impressora errada) → `PdfImpressoIlegivel`, com o
  arquivo mantido na pasta de download para inspeção;
- se um relogin do SERPRO atravessar entre duas consultas, a navegação é
  repetida uma vez (a transação é por matrícula, não depende da
  habilitação); persistindo, `TransacaoNaoAbriu`.

Para reler PDFs já no disco, sem navegador:

```python
from integra_gov.esiape import ler_dados_pessoais
dados = ler_dados_pessoais(Path("cadastrais/dados_pessoais_0000000.pdf"))
```

Nos logs só aparecem os dois últimos dígitos da matrícula; nome, CPF e
e-mail nunca são logados.
````

- [ ] **Step 6: Script do gate ao vivo (gitignored)**

Criar `dados_reais/esiape_dados_pessoais_gate.py`:

```python
"""Gate ao vivo do modulo esiape.dados_pessoais.

    python dados_reais/esiape_dados_pessoais_gate.py <matricula1> <matricula2> <inexistente>

Chrome com as prefs de impressao de docs/uso-basico.md; Serpro ID confirmado
pelo usuario. Imprime so os 2 ultimos digitos e a contagem de campos.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from selenium.webdriver.chrome.options import Options as ChromeOptions

from integra_gov.esiape import AcessoEsiape, DadosPessoaisServidor, EsiapeError
from integra_gov.sei import criar_driver_chrome

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
SAIDA = Path(__file__).parent / "_gate_dados_pessoais"
DOWNLOAD = SAIDA / "_download_esiape"


def abrir_chrome():
    destino = {"recentDestinations": [{"id": "Save as PDF", "origin": "local", "account": ""}],
               "selectedDestinationId": "Save as PDF", "version": 2}
    opts = ChromeOptions()
    opts.add_experimental_option("prefs", {
        "download.default_directory": str(DOWNLOAD),
        "savefile.default_directory": str(DOWNLOAD),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "plugins.plugins_disabled": ["Chrome PDF Viewer"],
        "profile.default_content_settings.popups": 0,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "printing.print_preview_sticky_settings.appState": json.dumps(destino),
    })
    return criar_driver_chrome(options=opts, args_extra=["--kiosk-printing", "--disable-popup-blocking"])


def main() -> int:
    matriculas = sys.argv[1:]
    if len(matriculas) < 2:
        print(__doc__)
        return 2
    SAIDA.mkdir(parents=True, exist_ok=True)
    driver = abrir_chrome()
    try:
        print("== Login SERPRO ID: CONFIRME NO APP ==")
        AcessoEsiape(driver).executar()
        cad = DadosPessoaisServidor(driver, pasta_saida=SAIDA, pasta_download=DOWNLOAD)
        for m in matriculas:
            m = m.strip()
            print(f"== matricula *****{m[-2:]} ==")
            try:
                d = cad.consultar(m)
                campos = [k for k in ("matricula", "nome", "situacao", "cpf", "data_nascimento",
                                      "email", "municipio", "uf", "orgao") if getattr(d, k)]
                print(f"   OK {d.pdf.name}: {len(campos)}/9 campos; faltam: "
                      f"{sorted(set(('matricula', 'nome', 'situacao', 'cpf', 'data_nascimento', 'email', 'municipio', 'uf', 'orgao')) - set(campos)) or 'nenhum'}")
            except EsiapeError as exc:
                print(f"   EXC {type(exc).__name__}: {exc}")
                print("   (se foi a matricula inexistente: anote o que a tela mostrou)")
    finally:
        input(">> ENTER para fechar o Chrome da automacao... ")
        driver.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Confirmar que `dados_reais/` está no `.gitignore` (`git check-ignore dados_reais/esiape_dados_pessoais_gate.py` imprime o caminho).

- [ ] **Step 7: Suíte inteira + lint**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest -q
```

Esperado: `799 + (testes novos) passed`, nenhum falhando ou pulado a mais que antes.

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m ruff check .
```

Esperado: `All checks passed!`

- [ ] **Step 8: Commit**

Mensagem (`$env:TEMP\msg_t3.txt`):

```
feat(esiape): exporta dados_pessoais e documenta (README, CHANGELOG, uso-basico)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

```bash
git add integra_gov/esiape/__init__.py README.md CHANGELOG.md docs/uso-basico.md tests/test_esiape_dados_pessoais.py
git commit -F "$env:TEMP\msg_t3.txt"
```

---

## Depois das três tarefas (fora do plano de código)

1. Review final da branch (modelo mais capaz) e onda de correções.
2. Gate ao vivo pelo usuário: `python dados_reais/esiape_dados_pessoais_gate.py <m1> <m2> <inexistente>`; registrar na spec (§ "Verificado ao vivo"), ajustar `MSG_NAO_ENCONTRADA` se houver mensagem, trocar a nota "Ainda não verificado ao vivo" do CHANGELOG por "Verificado ao vivo em <data>".
3. `dados_reais/apresentacao/extrair_cadastral.py` passa a importar `DadosPessoaisServidor` e `ler_dados_pessoais` (substituindo `extrair_pdf` e `ler_pdf`).
4. Merge em `main`, push só com ordem do usuário.
