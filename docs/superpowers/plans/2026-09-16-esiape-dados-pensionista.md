# e-SIAPE dados do pensionista (CDCOPSBENE) — plano de implementação

> **SUPERADO.** Este plano foi escrito antes dos gates ao vivo. O que foi
> entregue diverge dele: não há documento, não há clique em Consultar, e o
> construtor de `DadosPessoaisPensionista` recebe só o `driver`. Toda
> divergência está registrada nas notas medidas da spec e na sua seção
> "Decisão de 17/09: sem documento". Não implemente este plano como está
> escrito.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar `integra_gov.esiape.dados_pensionista`: os 12 campos cadastrais do pensionista lidos do formulário da CDCOPSBENE, mais o PDF impresso da tela.

**Architecture:** Um módulo novo ao lado do de servidor. Os campos saem dos elementos de entrada do formulário por `data-testtoolid`, não do PDF, porque a CDCOPSBENE é formulário e não relatório. A impressão usa `esiape.impressao`, já estabilizada. Uma tela intermediária de procuração é atravessada e registrada. Antes disso, um arquivo compartilhado recebe a máscara de dígitos e a conversão de data SIAPE, hoje privadas do módulo de servidor.

**Tech Stack:** Python 3.10+, Selenium (só via driver injetado), pytest com driver falso e PDF sintético (`tests/_pdf_sintetico.pdf_bytes`).

**Spec:** `docs/superpowers/specs/2026-09-16-esiape-dados-pensionista-design.md`

## Global Constraints

- Nenhum dado pessoal ou órgão real em código, teste ou doc: matrícula `0000000`, CPF `000.000.000-00`, e-mail `fulano@exemplo.gov.br`, cidade `CIDADE EXEMPLO`, UF `XX`, CEP `00000-000`.
- Logs e mensagens de exceção só com os dois últimos dígitos da matrícula (`*****NN`); nunca nome, CPF, e-mail ou endereço.
- Campo vazio vira `None`, nunca exceção: ausência é informação, não falha.
- Padrões da lib: `logging` stdlib, exceções tipadas filhas de `EsiapeError`, type hints, docstrings em português, teste mockado para todo comportamento.
- Doc (README, CHANGELOG, `docs/uso-basico.md`) entra no MESMO commit do módulo exportado (Task 4).
- Python do venv, caminho absoluto: `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe`. Suíte inteira hoje: **860 testes**; `ruff check .` limpo.
- Commit com `git commit -F <arquivo>` (aspas quebram no PowerShell), terminando com `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Não usar `git checkout -- <arquivo>` em arquivo não commitado.
- Não portar a impressão do privado (dez tabulações + caça ao arquivo em três pastas); usar `imprimir_via_popup`.

---

## Estrutura de arquivos

| arquivo | responsabilidade |
|---|---|
| `integra_gov/esiape/_campos.py` (criar) | `mascarar_matricula`, `mascarar_digitos`, `data_siape`, `MESES_SIAPE` |
| `integra_gov/esiape/dados_pessoais.py` (modificar) | passa a importar de `_campos`; sem mudança de comportamento |
| `tests/test_esiape_campos.py` (criar) | testes de máscara e data, movidos do arquivo de servidor |
| `tests/test_esiape_dados_pessoais.py` (modificar) | perde os testes movidos |
| `integra_gov/esiape/dados_pensionista.py` (criar) | dataclass, leitura do formulário, procuração, `DadosPessoaisPensionista` |
| `tests/test_esiape_dados_pensionista.py` (criar) | todos os testes do módulo novo |
| `integra_gov/esiape/__init__.py` (modificar) | exportar os 2 nomes novos |
| `README.md`, `CHANGELOG.md`, `docs/uso-basico.md` (modificar) | doc do módulo |
| `dados_reais/esiape_dados_pensionista_gate.py` (criar; pasta gitignored) | script do gate ao vivo |

---

### Task 1: extrair `_campos.py` (refatoração sem mudança de comportamento)

**Files:**
- Create: `integra_gov/esiape/_campos.py`
- Modify: `integra_gov/esiape/dados_pessoais.py`
- Create: `tests/test_esiape_campos.py`
- Modify: `tests/test_esiape_dados_pessoais.py`

**Interfaces:**
- Consumes: nada de tarefas anteriores.
- Produces: `integra_gov.esiape._campos` com `MESES_SIAPE: dict[str, int]`, `mascarar_matricula(matricula: str) -> str`, `mascarar_digitos(texto: str) -> str`, `data_siape(bruto: str | None) -> str | None`.

- [ ] **Step 1: Criar o módulo compartilhado**

Criar `integra_gov/esiape/_campos.py` com o conteúdo abaixo. As três funções são MOVIDAS de `dados_pessoais.py` sem alteração de corpo (`_mascarar` vira `mascarar_matricula`, `_mascarar_digitos` vira `mascarar_digitos`, `_data_siape` vira `data_siape`):

```python
"""Normalização e máscara de campos cadastrais do e-SIAPE.

Compartilhado pelos módulos que devolvem dados pessoais — CDCOINDPES
(:mod:`~integra_gov.esiape.dados_pessoais`) e CDCOPSBENE
(:mod:`~integra_gov.esiape.dados_pensionista`): uma implementação por regra,
dois usos.

Máscara: a matrícula e qualquer número longo só aparecem pelos 2 últimos
dígitos, em log, mensagem de exceção ou ``repr``.

Nada pessoal neste arquivo.
"""

from __future__ import annotations

import re

__all__ = ["MESES_SIAPE", "data_siape", "mascarar_digitos",
           "mascarar_matricula"]

#: Meses como o SIAPE os escreve em datas ``DDMMMAAAA``.
MESES_SIAPE = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
               "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}


def mascarar_matricula(matricula: str) -> str:
    """``matricula`` reduzida aos 2 últimos dígitos; nunca expõe tudo, mesmo
    para uma matrícula mais curta que 2 caracteres."""
    return f"*****{matricula[-2:].rjust(2, '*')}"


def mascarar_digitos(texto: str) -> str:
    """Todo grupo de 3+ dígitos vira ``*****`` + os 2 últimos dígitos do
    grupo — cobre tanto uma sequência corrida (``1234567``) quanto uma
    pontuada por ``.``, ``-``, ``/`` ou um único espaço entre dígitos
    (matrícula ``000.000-0``, CPF ``123.456.789-00``). Um grupo de 1 ou 2
    dígitos (ex.: ``UF: 12``) não é matrícula nem CPF e fica intocado."""
    return re.sub(
        r"\d(?:[.\-/ ]?\d){2,}",
        lambda m: "*****" + re.sub(r"\D", "", m.group(0))[-2:],
        texto,
    )


def data_siape(bruto: str | None) -> str | None:
    """``15AGO1960`` → ``15/08/1960``; qualquer outra forma → ``None``."""
    m = re.fullmatch(r"(\d{2})([A-Z]{3})(\d{4})", (bruto or "").strip().upper())
    if not m or m.group(2) not in MESES_SIAPE:
        return None
    return f"{m.group(1)}/{MESES_SIAPE[m.group(2)]:02d}/{m.group(3)}"
```

- [ ] **Step 2: Mover os testes**

Criar `tests/test_esiape_campos.py`:

```python
"""Testes de ``integra_gov.esiape._campos`` (máscara e data SIAPE).

Vieram de ``test_esiape_dados_pessoais.py`` quando as funções saíram de lá
para serem compartilhadas com o módulo de pensionista.
"""

from __future__ import annotations

import pytest

from integra_gov.esiape._campos import (
    data_siape,
    mascarar_digitos,
    mascarar_matricula,
)


def test_mascarar_matricula_curta_nao_expoe_tudo():
    assert mascarar_matricula("5") == "******5"


def test_mascarar_matricula_comum():
    assert mascarar_matricula("0000000") == "*****00"


@pytest.mark.parametrize("bruto, esperado", [
    ("MATRICULA 1234567 NAO CADASTRADA", "MATRICULA *****67 NAO CADASTRADA"),
    ("000.000-0", "*****00"),
    ("123.456.789-00", "*****00"),
    ("1234", "*****34"),
    ("UF 12", "UF 12"),
    ("ORGAO 40806 - X", "ORGAO *****06 - X"),
])
def test_mascarar_digitos(bruto, esperado):
    assert mascarar_digitos(bruto) == esperado


@pytest.mark.parametrize("bruto, esperado", [
    ("15AGO1960", "15/08/1960"),
    ("01JAN2001", "01/01/2001"),
    ("15XYZ1960", None),
    ("1960-08-15", None),
    ("", None),
    (None, None),
])
def test_data_siape(bruto, esperado):
    assert data_siape(bruto) == esperado
```

Em `tests/test_esiape_dados_pessoais.py`, REMOVER as três funções de teste que passaram para o arquivo novo: `test_mascarar_matricula_curta_nao_expoe_tudo`, o bloco parametrizado `test_mascarar_digitos` (com o seu decorador) e o bloco parametrizado `test_data_siape` (com o seu decorador). Não mexer em nenhum outro teste do arquivo.

- [ ] **Step 3: Rodar os testes movidos**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_campos.py -q
```

Esperado: `14 passed`.

**Esta tarefa e uma refatoracao de MOVER, nao TDD.** Nao existe fase RED
honesta: os corpos das funcoes nao mudam, entao nenhum teste novo poderia
falhar antes e passar depois. A prova de que nada mudou e a suite inteira
continuar verde no Step 5, com o modulo de servidor ja apontando para o
arquivo novo. Registre isso no relatorio em vez de inventar um RED.

- [ ] **Step 4: Apontar `dados_pessoais.py` para o módulo novo**

Em `integra_gov/esiape/dados_pessoais.py`:

1. REMOVER a constante `_MESES` e as três funções `_mascarar`, `_mascarar_digitos` e `_data_siape` (os corpos foram para `_campos.py`).
2. Acrescentar ao bloco de imports relativos, ANTES de `from .exceptions import (`:

```python
from ._campos import data_siape, mascarar_digitos, mascarar_matricula
```

3. Renomear as chamadas no arquivo inteiro: `_mascarar(` → `mascarar_matricula(`, `_mascarar_digitos(` → `mascarar_digitos(`, `_data_siape(` → `data_siape(`. São seis pontos de uso: `_texto_popup_cis` (um `mascarar_digitos`), `DadosPessoais.__repr__` (um de cada), `extrair_campos` (um `data_siape`) e `consultar` (dois `mascarar_matricula`). Confirme com:

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_dados_pessoais.py -q
```

Se sobrar alguma chamada antiga, o teste falha com `NameError`.

- [ ] **Step 5: Rodar tudo**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest -q
```

Esperado: `862 passed`. A conta: saem 12 casos do arquivo de servidor (1 de mascara de matricula, 6 de mascara de digitos, 5 de data) e entram 14 no arquivo novo (os mesmos 12, mais `test_mascarar_matricula_comum` e o caso `(None, None)` de data). Se o total divergir, algum teste se perdeu na mudanca: confira antes de seguir e relate o numero real.

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m ruff check .
```

Esperado: `All checks passed!`

- [ ] **Step 6: Commit**

Escrever a mensagem em `$env:TEMP\msg_p1.txt`:

```
refactor(esiape): mascara e data SIAPE saem para _campos, compartilhadas

Sem mudanca de comportamento: os corpos sao os mesmos e os testes que os
cobriam foram movidos junto. Motivo: o modulo de pensionista (CDCOPSBENE)
precisa das mesmas regras e duplica-las seria duplicar logica.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

```bash
git add integra_gov/esiape/_campos.py integra_gov/esiape/dados_pessoais.py tests/test_esiape_campos.py tests/test_esiape_dados_pessoais.py
git commit -F "$env:TEMP\msg_p1.txt"
```

---

### Task 2: leitura do formulário e tela de procuração

**Files:**
- Create: `integra_gov/esiape/dados_pensionista.py`
- Create: `tests/test_esiape_dados_pensionista.py`

**Interfaces:**
- Consumes: `integra_gov.esiape._campos.data_siape(bruto) -> str | None`, `mascarar_matricula(str) -> str`, `mascarar_digitos(str) -> str`. De `integra_gov.esiape.navegacao`: `frames_visiveis(driver, caminho=(), saida=None, prof=0) -> list[tuple]`, `ir_para_frame(driver, caminho) -> bool`.
- Produces: `TRANSACAO = "CDCOPSBENE"`, `CAMPOS_FORMULARIO: dict[str, str]`, `DadosPensionista` (dataclass), `ler_campos(driver) -> dict[str, str | None]`, `atravessar_procuracao(driver) -> bool`, `_data_nascimento(bruto) -> str | None`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_esiape_dados_pensionista.py`:

```python
"""Testes de ``integra_gov.esiape.dados_pensionista`` (CDCOPSBENE)."""

from __future__ import annotations

from pathlib import Path

import pytest
from selenium.webdriver.common.keys import Keys

from integra_gov.esiape import dados_pensionista as dmod

# Valores fictícios; nada real neste arquivo.
VALORES = {
    "w_tl_no_benef": "FULANO DE TAL",
    "w_tl_nu_cpf": "000.000.000-00",
    "w_da_nascimento": "15AGO1960",
    "w_tl_ed_correio_eletronico": "FULANO@EXEMPLO.GOV.BR",
    "w_tl_no_logradouro": "RUA EXEMPLO",
    "w_nu_end": "100",
    "w_tl_complemento_endereco": "APTO 1",
    "w_tl_no_bairro_novo": "BAIRRO EXEMPLO",
    "w_tl_no_municipio": "CIDADE EXEMPLO",
    "w_tl_uf_end": "XX",
    "w_co_cep": "00000-000",
}


class _Campo:
    """Elemento de entrada do formulário: só devolve ``value``."""

    def __init__(self, valor=""):
        self.valor = valor

    def get_attribute(self, nome):
        return self.valor if nome == "value" else None


class _DriverCampos:
    """Driver que resolve ``input[data-testtoolid="X"]`` por um dicionário."""

    def __init__(self, valores=None, ausentes=()):
        self.valores = dict(valores if valores is not None else VALORES)
        for tid in ausentes:
            self.valores.pop(tid, None)

    def find_element(self, by, valor):
        for tid, conteudo in self.valores.items():
            if f'data-testtoolid="{tid}"' in valor:
                return _Campo(conteudo)
        raise Exception(f"no such element: {valor}")


def test_transacao_e_campos_do_formulario():
    assert dmod.TRANSACAO == "CDCOPSBENE"
    assert dmod.CAMPOS_FORMULARIO["nome"] == "w_tl_no_benef"
    assert set(dmod.CAMPOS_FORMULARIO) == {
        "nome", "cpf", "data_nascimento", "email", "logradouro", "numero",
        "complemento", "bairro", "municipio", "uf", "cep"}


# ------------------------------------------------------------- leitura
def test_ler_campos_le_os_11_do_formulario():
    c = dmod.ler_campos(_DriverCampos())
    assert c == {
        "nome": "FULANO DE TAL",
        "cpf": "000.000.000-00",
        "data_nascimento": "15/08/1960",
        "email": "fulano@exemplo.gov.br",
        "logradouro": "RUA EXEMPLO",
        "numero": "100",
        "complemento": "APTO 1",
        "bairro": "BAIRRO EXEMPLO",
        "municipio": "Cidade Exemplo",
        "uf": "XX",
        "cep": "00000-000",
    }


def test_ler_campos_valor_vazio_vira_none():
    valores = dict(VALORES, w_tl_complemento_endereco="", w_co_cep="   ")
    c = dmod.ler_campos(_DriverCampos(valores))
    assert c["complemento"] is None and c["cep"] is None
    assert c["nome"] == "FULANO DE TAL"


def test_ler_campos_elemento_ausente_vira_none():
    c = dmod.ler_campos(_DriverCampos(ausentes=("w_tl_ed_correio_eletronico",)))
    assert c["email"] is None
    assert c["nome"] == "FULANO DE TAL"


def test_ler_campos_formulario_vazio_tudo_none():
    c = dmod.ler_campos(_DriverCampos({tid: "" for tid in VALORES}))
    assert all(v is None for v in c.values())


@pytest.mark.parametrize("bruto, esperado", [
    ("15AGO1960", "15/08/1960"),     # forma SIAPE
    ("15/08/1960", "15/08/1960"),    # já com barras
    ("1960-08-15", None),
    ("15XYZ1960", None),
    ("", None),
    (None, None),
])
def test_data_nascimento_aceita_as_duas_formas(bruto, esperado):
    assert dmod._data_nascimento(bruto) == esperado


# --------------------------------------------------------- procuração
class _Corpo:
    def __init__(self):
        self.teclas = []

    def send_keys(self, *t):
        self.teclas.extend(t)


class _SwitchToFake:
    def default_content(self):
        pass


class _DriverFrames:
    """Driver com N frames; cada um tem um texto de corpo."""

    def __init__(self, textos):
        self.textos = list(textos)
        self.atual = 0
        self.switch_to = _SwitchToFake()
        self.corpo = _Corpo()
        self.frames_visitados = []

    def execute_script(self, script, *args):
        return self.textos[self.atual]

    def find_element(self, by, valor):
        return self.corpo


@pytest.fixture
def frames(monkeypatch):
    """Substitui a varredura de frames por uma lista fixa."""
    def instalar(driver):
        monkeypatch.setattr(dmod, "frames_visiveis",
                            lambda d: [(i,) for i in range(len(d.textos))])

        def ir(d, caminho):
            d.atual = caminho[0]
            d.frames_visitados.append(caminho[0])
            return True

        monkeypatch.setattr(dmod, "ir_para_frame", ir)
        return driver
    return instalar


def test_procuracao_ausente_devolve_false(frames):
    d = frames(_DriverFrames(["TELA NORMAL", "OUTRA TELA"]))
    assert dmod.atravessar_procuracao(d) is False
    assert d.corpo.teclas == []


def test_procuracao_presente_envia_enter_e_devolve_true(frames):
    d = frames(_DriverFrames(["TELA NORMAL", "BENEFICIARIO COM PROCURACAO"]))
    assert dmod.atravessar_procuracao(d) is True
    assert d.corpo.teclas == [Keys.ENTER]


def test_procuracao_com_enter_falhando_ainda_devolve_true(frames, caplog):
    d = frames(_DriverFrames(["BENEFICIARIO COM PROCURACAO"]))

    def explode(*_a, **_k):
        raise RuntimeError("stale")

    d.find_element = explode
    assert dmod.atravessar_procuracao(d) is True   # a tela EXISTIA
    assert any("procuração" in r.getMessage() for r in caplog.records)


# ------------------------------------------------------------- dataclass
def test_repr_nao_expoe_dados_pessoais(tmp_path):
    d = dmod.DadosPensionista(
        matricula="0000000", nome="FULANO DE TAL", cpf="000.000.000-00",
        data_nascimento="15/08/1960", email="fulano@exemplo.gov.br",
        logradouro="RUA EXEMPLO", numero="100", complemento="APTO 1",
        bairro="BAIRRO EXEMPLO", municipio="Cidade Exemplo", uf="XX",
        cep="00000-000", com_procuracao=True,
        pdf=tmp_path / "dados_pensionista_0000000.pdf")
    r = repr(d)
    for proibido in ("FULANO", "000.000.000-00", "15/08/1960",
                     "fulano@exemplo", "RUA EXEMPLO", "BAIRRO", "00000-000",
                     "0000000"):
        assert proibido not in r, proibido
    assert "*****00" in r
    assert "com_procuracao=True" in r
    assert "Cidade Exemplo" in r and "XX" in r


def test_repr_sem_pdf():
    d = dmod.DadosPensionista(
        matricula="0000000", nome=None, cpf=None, data_nascimento=None,
        email=None, logradouro=None, numero=None, complemento=None,
        bairro=None, municipio=None, uf=None, cep=None)
    assert "pdf=None" in repr(d)
    assert d.com_procuracao is False
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_dados_pensionista.py -q
```

Esperado: falha na coleta, `ImportError: cannot import name 'dados_pensionista'`.

- [ ] **Step 3: Escrever o módulo (só a leitura)**

Criar `integra_gov/esiape/dados_pensionista.py`:

```python
"""Dados pessoais do pensionista (CDCOPSBENE): campos do formulário + PDF.

A CDCOPSBENE é um **formulário**: os valores chegam dentro de elementos de
entrada, e é de lá que saem os campos. Diferente da CDCOINDPES
(:mod:`~integra_gov.esiape.dados_pessoais`), que é um **relatório** e cujos
campos saem da camada de texto do PDF impresso. Cada leitura casa com a
natureza da sua tela: ler este formulário pelo impresso seria apostar que o
PDF carrega os valores digitados, o que ninguém mediu.

Campo vazio vira ``None``: ausência é informação, não falha. O PDF continua
sendo gerado, porque é o documento que se anexa ao processo.

Nada pessoal neste arquivo — matrícula, nome e CPF são sempre parâmetro.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from ._campos import data_siape, mascarar_digitos, mascarar_matricula
from .navegacao import frames_visiveis, ir_para_frame

_log = logging.getLogger(__name__)

TRANSACAO = "CDCOPSBENE"

#: Campos do formulário por ``data-testtoolid`` — fatos da tela CDCOPSBENE,
#: validados em produção pelo módulo privado que este porta.
CAMPOS_FORMULARIO = {
    "nome": "w_tl_no_benef",
    "cpf": "w_tl_nu_cpf",
    "data_nascimento": "w_da_nascimento",
    "email": "w_tl_ed_correio_eletronico",
    "logradouro": "w_tl_no_logradouro",
    "numero": "w_nu_end",
    "complemento": "w_tl_complemento_endereco",
    "bairro": "w_tl_no_bairro_novo",
    "municipio": "w_tl_no_municipio",
    "uf": "w_tl_uf_end",
    "cep": "w_co_cep",
}

#: Texto que identifica a tela intermediária de procuração. No privado ela
#: vive num iframe cujo ``id`` contém ``SUBPAGE``; aqui o marcador textual
#: basta, e a varredura de frames da lib faz o resto.
TEXTO_PROCURACAO = "BENEFICIARIO COM PROCURACAO"


@dataclass(repr=False)
class DadosPensionista:
    """Os campos cadastrais do pensionista (ausente = ``None``).

    ``repr()`` omite nome, CPF, nascimento, e-mail e o endereço inteiro; só
    município, UF, ``com_procuracao`` e a matrícula mascarada aparecem, para
    não vazar dados pessoais em log ou traceback. Os ``field(repr=False)``
    documentam a intenção; quem a garante é o ``__repr__`` abaixo.
    """

    matricula: str | None
    nome: str | None = field(repr=False)
    cpf: str | None = field(repr=False)
    data_nascimento: str | None = field(repr=False)
    email: str | None = field(repr=False)
    logradouro: str | None = field(repr=False)
    numero: str | None = field(repr=False)
    complemento: str | None = field(repr=False)
    bairro: str | None = field(repr=False)
    municipio: str | None
    uf: str | None
    cep: str | None = field(repr=False)
    com_procuracao: bool = False
    pdf: Path | None = None

    def __repr__(self) -> str:
        if self.pdf is not None:
            pdf_repr = repr(f"{self.pdf.parent}/{mascarar_digitos(self.pdf.name)}")
        else:
            pdf_repr = "None"
        return (
            f"DadosPensionista("
            f"matricula={mascarar_matricula(self.matricula or '')!r}, "
            f"municipio={self.municipio!r}, uf={self.uf!r}, "
            f"com_procuracao={self.com_procuracao!r}, pdf={pdf_repr})"
        )


# ------------------------------------------------------------- leitura
def _data_nascimento(bruto: str | None) -> str | None:
    """``15AGO1960`` → ``15/08/1960``; ``15/08/1960`` mantido; resto ``None``.

    PENDÊNCIA (gate ao vivo): qual das duas formas a CDCOPSBENE devolve não
    foi medido. Depois do gate, a que não ocorrer sai daqui.
    """
    convertida = data_siape(bruto)
    if convertida is not None:
        return convertida
    texto = (bruto or "").strip()
    return texto if re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto) else None


def _valor(driver, testtoolid: str) -> str | None:
    """Valor de um campo de entrada do formulário (ausente/vazio → ``None``).

    O driver precisa estar NO FRAME do formulário; quem chama posiciona.
    """
    seletor = f'input[data-testtoolid="{testtoolid}"]'
    try:
        bruto = driver.find_element(By.CSS_SELECTOR, seletor).get_attribute("value")
    except Exception:  # noqa: BLE001 — campo ausente é informação, não falha
        return None
    valor = (bruto or "").strip()
    return valor or None


def ler_campos(driver) -> dict[str, str | None]:
    """Os 11 campos do formulário da CDCOPSBENE, normalizados.

    O driver precisa estar no frame do formulário; ``consultar`` posiciona
    com ``esperar_seletor`` antes de chamar.
    """
    cru = {chave: _valor(driver, tid)
           for chave, tid in CAMPOS_FORMULARIO.items()}
    return {
        "nome": cru["nome"],
        "cpf": cru["cpf"],
        "data_nascimento": _data_nascimento(cru["data_nascimento"]),
        "email": (cru["email"] or "").lower() or None,
        "logradouro": cru["logradouro"],
        "numero": cru["numero"],
        "complemento": cru["complemento"],
        "bairro": cru["bairro"],
        "municipio": (cru["municipio"] or "").title() or None,
        "uf": cru["uf"],
        "cep": cru["cep"],
    }


# --------------------------------------------------------- procuração
def atravessar_procuracao(driver) -> bool:
    """Fecha a tela intermediária de procuração, se ela estiver presente.

    Devolve ``True`` quando a tela EXISTIA — inclusive quando o ENTER falha,
    porque o fato relevante para quem instrui o processo é haver procuração;
    se ela tiver ficado presa, os campos seguintes não preenchem e
    ``consultar`` acusa. A tela é OPCIONAL (só aparece com procurador
    cadastrado), então não encontrá-la é o caso normal e devolve ``False``.
    """
    try:
        driver.switch_to.default_content()
    except Exception:  # noqa: BLE001 — sem contexto raiz não há o que varrer
        return False
    for caminho in frames_visiveis(driver):
        if not ir_para_frame(driver, caminho):
            continue
        try:
            texto = driver.execute_script(
                "return document.body ? document.body.innerText : ''") or ""
        except Exception:  # noqa: BLE001 — frame que não responde não é a tela
            continue
        if TEXTO_PROCURACAO not in texto.upper():
            continue
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ENTER)
            _log.info("%s: tela de procuração atravessada", TRANSACAO)
        except Exception as exc:  # noqa: BLE001 — a tela existia mesmo assim
            _log.warning("%s: tela de procuração não fechou (%s); os campos "
                         "seguintes vão acusar se ela ficou presa",
                         TRANSACAO, exc)
        return True
    return False
```

- [ ] **Step 4: Rodar os testes**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_dados_pensionista.py -q
```

Esperado: todos passam (16 testes). Depois:

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m ruff check integra_gov tests
```

Esperado: `All checks passed!`

- [ ] **Step 5: Commit**

Mensagem em `$env:TEMP\msg_p2.txt`:

```
feat(esiape): leitura do formulario da CDCOPSBENE e travessia da procuracao

ler_campos() devolve os 11 campos do formulario normalizados (vazio vira
None); atravessar_procuracao() fecha a tela intermediaria e diz se ela
existia. Data de nascimento aceita as duas formas ate o gate medir qual e.
A classe que dirige a transacao vem no commit seguinte; nada exportado.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

```bash
git add integra_gov/esiape/dados_pensionista.py tests/test_esiape_dados_pensionista.py
git commit -F "$env:TEMP\msg_p2.txt"
```

---

### Task 3: `DadosPessoaisPensionista.consultar`

**Files:**
- Modify: `integra_gov/esiape/dados_pensionista.py` (acrescentar imports e a classe)
- Modify: `tests/test_esiape_dados_pensionista.py` (acrescentar os testes)

**Interfaces:**
- Consumes, de `integra_gov.esiape.navegacao`: `navegar_para_transacao(driver, transacao, seletor_confirmacao, timeout=30) -> bool`, `esperar_seletor(driver, seletor_css, timeout=20) -> tuple | None`, `procurar_em_frames(driver, seletor_css) -> tuple | None`, `fechar_janelas_extras(driver, handle_principal=None)`, `fechar_popups_cis(driver) -> int`, `limpar_overlay(driver, timeout=10) -> bool`, `relogin_pendente(driver) -> bool`, `limpar_flag_relogin(driver)`. De `integra_gov.esiape.impressao`: `imprimir_via_popup(driver, clicar_imprimir, pasta_download, *, timeout_popup=20, timeout_download=60, delay=1.0) -> Path`. De `integra_gov.ficha_financeira`: `tem_camada_de_texto(origem) -> bool`, `PdfIlegivelError`. De `.exceptions`: `DadosPessoaisIndisponiveis`, `PdfImpressoIlegivel`, `TransacaoNaoAbriu`. Da Task 2: `TRANSACAO`, `CAMPOS_FORMULARIO`, `DadosPensionista`, `ler_campos`, `atravessar_procuracao`.
- Produces: `DadosPessoaisPensionista(driver, pasta_saida: Path, pasta_download: Path | None = None)` com `consultar(matricula: str) -> DadosPensionista` e os atributos de classe `TRANSACAO`, `SEL_MATRICULA`, `SEL_CONSULTAR`, `SEL_NOME`, `SEL_IMPRIMIR`, `SEL_GERAR_PDF`, `SEL_SAIR`, `TIMEOUT_TELA`, `TIMEOUT_CAMPOS`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao final de `tests/test_esiape_dados_pensionista.py`:

```python
# ------------------------------------------------ DadosPessoaisPensionista
from unittest.mock import patch  # noqa: E402

from integra_gov.esiape.exceptions import (  # noqa: E402
    DadosPessoaisIndisponiveis,
    PdfImpressoIlegivel,
    TransacaoNaoAbriu,
)
from tests._pdf_sintetico import pdf_bytes  # noqa: E402

P = dmod.DadosPessoaisPensionista
BOTOES = (P.SEL_MATRICULA, P.SEL_CONSULTAR, P.SEL_IMPRIMIR, P.SEL_GERAR_PDF,
          P.SEL_SAIR)


class _Botao:
    def __init__(self, seletor, ordem):
        self.seletor = seletor
        self.ordem = ordem
        self.cliques = 0
        self.teclas = []
        self.eco = ""
        #: Quando != None, e o que o CIS "devolve" no campo, independente do
        #: que foi digitado. E assim que os testes de eco divergente e de eco
        #: vazio se escrevem: ``consultar`` chama ``clear()`` antes de
        #: digitar, entao mexer so em ``eco`` nao sobreviveria.
        self.eco_forcado = None

    def click(self):
        self.cliques += 1
        self.ordem.append(self.seletor)

    def clear(self):
        self.eco = ""

    def send_keys(self, *t):
        self.teclas.extend(t)
        for k in t:
            if isinstance(k, str) and k != Keys.ENTER:
                self.eco += k

    def get_attribute(self, nome):
        if nome != "value":
            return None
        return self.eco if self.eco_forcado is None else self.eco_forcado


class _DriverConsulta:
    """Botões por seletor CSS e campos do formulário por data-testtoolid."""

    def __init__(self, valores=None):
        self.ordem: list[str] = []
        self.el = {s: _Botao(s, self.ordem) for s in BOTOES}
        self.valores = dict(valores if valores is not None else VALORES)
        self._esiape_relogin_pendente = False
        self.switch_to = _SwitchToFake()

    def find_element(self, by, valor):
        if valor in self.el:
            return self.el[valor]
        for tid, conteudo in self.valores.items():
            if f'data-testtoolid="{tid}"' in valor:
                return _Campo(conteudo)
        raise Exception(f"no such element: {valor}")

    def find_elements(self, by, valor):
        return []


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """Navegação, procuração e impressão substituídas.

    Devolve ``(driver, servidor, chamadas)``.
    """
    monkeypatch.setattr(dmod.time, "sleep", lambda *_a, **_k: None)
    driver = _DriverConsulta()
    chamadas = {"navegar": [], "limpar_flag": 0, "imprimir": 0,
                "fechar_popups": 0, "limpar_overlay": 0,
                "fechar_janelas_extras": 0, "procuracao": 0}

    def navegar(d, transacao, seletor, timeout=30):
        chamadas["navegar"].append(transacao)
        return True

    def imprimir(d, clicar, pasta_download, **kw):
        chamadas["imprimir"] += 1
        clicar()
        bruto = Path(pasta_download) / "cis_bruto.pdf"
        bruto.write_bytes(pdf_bytes([["RELATORIO CDCOPSBENE"]]))
        return bruto

    def conta(chave, retorno):
        def _f(*_a, **_k):
            chamadas[chave] += 1
            return retorno
        return _f

    monkeypatch.setattr(dmod, "navegar_para_transacao", navegar)
    monkeypatch.setattr(dmod, "esperar_seletor",
                        lambda d, s, timeout=20: (0,))
    monkeypatch.setattr(dmod, "procurar_em_frames", lambda d, s: (0,))
    monkeypatch.setattr(dmod, "fechar_janelas_extras",
                        conta("fechar_janelas_extras", None))
    monkeypatch.setattr(dmod, "limpar_overlay", conta("limpar_overlay", True))
    monkeypatch.setattr(dmod, "fechar_popups_cis", conta("fechar_popups", 0))
    monkeypatch.setattr(dmod, "atravessar_procuracao",
                        conta("procuracao", False))
    monkeypatch.setattr(dmod, "limpar_flag_relogin",
                        lambda d: chamadas.__setitem__(
                            "limpar_flag", chamadas["limpar_flag"] + 1))
    monkeypatch.setattr(dmod, "imprimir_via_popup", imprimir)
    servidor = P(driver, pasta_saida=tmp_path / "saida")
    return driver, servidor, chamadas


def test_pastas_default_como_o_modulo_de_servidor(tmp_path):
    s = P(object(), pasta_saida=tmp_path / "s")
    assert s.pasta_saida == tmp_path / "s"
    assert s.pasta_download == tmp_path / "s" / "_download_esiape"
    assert s.pasta_saida.is_dir() and s.pasta_download.is_dir()


def test_matricula_vazia_levanta_value_error(ambiente):
    _, servidor, _ = ambiente
    with pytest.raises(ValueError):
        servidor.consultar("   ")


def test_consultar_caminho_feliz(ambiente):
    driver, servidor, chamadas = ambiente
    d = servidor.consultar(" 000.000-0 ")
    assert chamadas["navegar"] == ["CDCOPSBENE"]
    assert driver.el[P.SEL_MATRICULA].teclas == ["0000000", Keys.ENTER]
    assert driver.ordem == [P.SEL_CONSULTAR, P.SEL_IMPRIMIR, P.SEL_GERAR_PDF,
                            P.SEL_SAIR]
    assert chamadas["fechar_janelas_extras"] == 1
    assert chamadas["fechar_popups"] == 1
    assert chamadas["limpar_overlay"] == 1
    assert chamadas["procuracao"] == 1
    assert chamadas["imprimir"] == 1
    assert d.matricula == "0000000"
    assert d.nome == "FULANO DE TAL" and d.cep == "00000-000"
    assert d.com_procuracao is False
    assert d.pdf == servidor.pasta_saida / "dados_pensionista_0000000.pdf"
    assert d.pdf.exists()
    assert not (servidor.pasta_download / "cis_bruto.pdf").exists()


def test_com_procuracao_vai_para_o_resultado(ambiente, monkeypatch):
    _, servidor, _ = ambiente
    monkeypatch.setattr(dmod, "atravessar_procuracao", lambda d: True)
    assert servidor.consultar("0000000").com_procuracao is True


def test_campos_do_formulario_nao_aparecem_levanta(ambiente, monkeypatch):
    _, servidor, chamadas = ambiente
    monkeypatch.setattr(dmod, "esperar_seletor",
                        lambda d, s, timeout=20: None if s == P.SEL_NOME else (0,))
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("0000000")
    assert "não trouxe dados" in str(exc.value)
    assert chamadas["imprimir"] == 0            # nada foi impresso
    assert chamadas["fechar_popups"] == 2       # início + recuperação


def test_todos_os_campos_vazios_levanta_sem_imprimir(ambiente, monkeypatch):
    driver, servidor, chamadas = ambiente
    driver.valores = {tid: "" for tid in VALORES}
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("0000000")
    assert "todos os campos vazios" in str(exc.value)
    assert chamadas["imprimir"] == 0
    assert chamadas["limpar_overlay"] == 2      # início + recuperação


def test_procuracao_presa_entra_no_motivo(ambiente, monkeypatch):
    driver, servidor, _ = ambiente
    driver.valores = {tid: "" for tid in VALORES}
    monkeypatch.setattr(dmod, "atravessar_procuracao", lambda d: True)
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("0000000")
    assert "procuração" in str(exc.value)


def test_eco_divergente_levanta(ambiente):
    driver, servidor, _ = ambiente
    driver.el[P.SEL_MATRICULA].eco_forcado = "1111111"
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("0000000")
    assert "*****11" in str(exc.value) and "*****00" in str(exc.value)
    assert "1111111" not in str(exc.value)


def test_eco_vazio_apenas_avisa(ambiente, caplog):
    import logging

    driver, servidor, _ = ambiente
    driver.el[P.SEL_MATRICULA].eco_forcado = ""      # o CIS nao ecoa
    with caplog.at_level(logging.WARNING,
                         logger="integra_gov.esiape.dados_pensionista"):
        d = servidor.consultar("0000000")
    assert d.nome == "FULANO DE TAL"
    assert any("conferência de identidade" in r.getMessage()
               for r in caplog.records)


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
    assert len(tentativas) == 2 and chamadas["limpar_flag"] == 1
    assert d.matricula == "0000000"


def test_falha_sem_relogin_nao_repete(ambiente):
    _, servidor, chamadas = ambiente
    with patch.object(dmod, "navegar_para_transacao", lambda *a, **k: False):
        with pytest.raises(TransacaoNaoAbriu):
            servidor.consultar("0000000")
    assert chamadas["limpar_flag"] == 0


def test_botao_consultar_ausente_levanta(ambiente, monkeypatch):
    _, servidor, _ = ambiente
    monkeypatch.setattr(
        dmod, "esperar_seletor",
        lambda d, s, timeout=20: None if s == P.SEL_CONSULTAR else (0,))
    with pytest.raises(DadosPessoaisIndisponiveis) as exc:
        servidor.consultar("0000000")
    assert "Consultar" in str(exc.value)


def test_impressao_sem_pdf_levanta(ambiente):
    _, servidor, _ = ambiente

    def imprimir(*a, **k):
        raise TimeoutError("nenhum PDF apareceu")

    with patch.object(dmod, "imprimir_via_popup", imprimir):
        with pytest.raises(DadosPessoaisIndisponiveis) as exc:
            servidor.consultar("0000000")
    assert "nenhum PDF apareceu" in str(exc.value)


def test_pdf_sem_camada_de_texto_levanta_e_mantem_arquivo(ambiente):
    _, servidor, chamadas = ambiente

    def imprimir(d, clicar, pasta_download, **kw):
        bruto = Path(pasta_download) / "cis_bruto.pdf"
        bruto.write_bytes(pdf_bytes([None], com_fonte=False))
        return bruto

    with patch.object(dmod, "imprimir_via_popup", imprimir):
        with pytest.raises(PdfImpressoIlegivel) as exc:
            servidor.consultar("0000000")
    assert Path(exc.value.caminho).exists()
    assert chamadas["fechar_popups"] == 2


def test_sobrescreve_pdf_anterior(ambiente):
    _, servidor, _ = ambiente
    destino = servidor.pasta_saida / "dados_pensionista_0000000.pdf"
    destino.write_bytes(b"velho")
    d = servidor.consultar("0000000")
    assert d.pdf == destino and destino.read_bytes() != b"velho"


def test_recuperacao_falhando_nao_mascara_a_excecao_original(ambiente,
                                                            monkeypatch,
                                                            caplog):
    driver, servidor, _ = ambiente
    driver.valores = {tid: "" for tid in VALORES}
    chamadas_overlay = []

    def limpar(*_a, **_k):
        chamadas_overlay.append(1)
        if len(chamadas_overlay) > 1:      # a chamada da recuperação
            raise RuntimeError("cortina explodiu")
        return True

    monkeypatch.setattr(dmod, "limpar_overlay", limpar)
    with pytest.raises(DadosPessoaisIndisponiveis):
        servidor.consultar("0000000")
    assert any("recuperação" in r.getMessage() for r in caplog.records)


def test_sair_falhando_nao_derruba(ambiente):
    driver, servidor, _ = ambiente

    def explode():
        raise RuntimeError("stale")

    driver.el[P.SEL_SAIR].click = explode
    assert servidor.consultar("0000000").nome == "FULANO DE TAL"


def test_log_nao_expoe_a_matricula_inteira(ambiente, caplog):
    import logging

    _, servidor, _ = ambiente
    with caplog.at_level(logging.INFO,
                         logger="integra_gov.esiape.dados_pensionista"):
        servidor.consultar("1234567")
    texto = "\n".join(r.getMessage() for r in caplog.records)
    assert "1234567" not in texto and "*****67" in texto
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_dados_pensionista.py -q
```

Esperado: os testes novos falham com `AttributeError: module ... has no attribute 'DadosPessoaisPensionista'`; os da Task 2 seguem passando.

- [ ] **Step 3: Implementar a classe**

Em `integra_gov/esiape/dados_pensionista.py`, acrescentar aos imports (depois de `from pathlib import Path`):

```python
import time
```

e aos imports relativos:

```python
from ..ficha_financeira import PdfIlegivelError, tem_camada_de_texto
from .exceptions import (
    DadosPessoaisIndisponiveis,
    PdfImpressoIlegivel,
    TransacaoNaoAbriu,
)
from .impressao import imprimir_via_popup
from .navegacao import (
    esperar_seletor,
    fechar_janelas_extras,
    fechar_popups_cis,
    frames_visiveis,
    ir_para_frame,
    limpar_flag_relogin,
    limpar_overlay,
    navegar_para_transacao,
    procurar_em_frames,
    relogin_pendente,
)
```

(o import de `frames_visiveis` e `ir_para_frame` da Task 2 passa a fazer parte deste bloco; não deixe os dois blocos duplicados)

E ao final do arquivo:

```python
# --------------------------------------------------------- com navegador
class DadosPessoaisPensionista:
    """Consulta a CDCOPSBENE, lê o formulário e imprime o PDF da tela.

    Args:
        driver: WebDriver com a sessão do e-SIAPE autenticada e o Chrome
            configurado para "Salvar como PDF" (``docs/uso-basico.md``).
        pasta_saida: onde fica ``dados_pensionista_<matricula>.pdf``.
        pasta_download: pasta de download do Chrome (default: subpasta
            ``_download_esiape`` de ``pasta_saida``). Tem de ser DEDICADA:
            :func:`~integra_gov.esiape.impressao.imprimir_via_popup` apaga
            todos os PDFs dela antes de imprimir.
    """

    TRANSACAO = TRANSACAO
    SEL_MATRICULA = '[data-testtoolid="w_matr_infor_alfa"]'
    SEL_CONSULTAR = '[data-testtoolid="onClickbtnConsulta"]'
    SEL_NOME = f'input[data-testtoolid="{CAMPOS_FORMULARIO["nome"]}"]'
    SEL_IMPRIMIR = '[data-testtoolid="onPrintPDF"]'
    SEL_GERAR_PDF = '[data-testtoolid="w_report.onGeneratePrintVersion"]'
    SEL_SAIR = '[data-testtoolid="onClickBtnSair"]'

    TIMEOUT_TELA = 30
    #: Os campos já vêm renderizados com a consulta; esperar 30s por eles
    #: atrasaria toda matrícula inexistente em meio minuto.
    TIMEOUT_CAMPOS = 10
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
        """Abre a CDCOPSBENE; se a lib abortou por relogin atravessado,
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

    def _recuperar_tela(self) -> None:
        """Recuperação best-effort após falha dentro da transação: fecha
        popups, limpa a cortina e clica Sair — para a PRÓXIMA consulta
        começar limpa. O try/except garante que a recuperação NUNCA mascare
        a exceção original que está propagando."""
        try:
            fechar_popups_cis(self.driver)
            limpar_overlay(self.driver)
            self._sair()
        except Exception as exc:  # noqa: BLE001 — recuperação é best-effort
            _log.warning("%s: recuperação da tela falhou (ignorado): %s",
                         self.TRANSACAO, exc)

    def _conferir_identidade(self, matricula: str) -> None:
        """Confere a matrícula que ficou no campo de busca contra a pedida.

        A tela do pensionista NÃO devolve a matrícula junto dos dados, então
        este eco é a única conferência possível, e ela é mais fraca que a do
        módulo de servidor (que compara a matrícula impressa no PDF). A
        proteção estrutural é que cada ``consultar`` navega para a transação
        do zero, com o formulário em branco.

        PENDÊNCIA (gate ao vivo): não se sabe se o campo ecoa o valor depois
        da consulta. Eco vazio registra um aviso e a consulta segue; eco
        divergente levanta. Medido o comportamento real, a tolerância sai.
        """
        try:
            eco = self.driver.find_element(
                By.CSS_SELECTOR, self.SEL_MATRICULA).get_attribute("value")
            eco = re.sub(r"\D", "", eco or "")
        except Exception as exc:  # noqa: BLE001
            _log.warning("%s: conferência de identidade impossível (%s)",
                         self.TRANSACAO, exc)
            return
        if not eco:
            _log.warning("%s: conferência de identidade impossível (o campo "
                         "de busca ficou vazio após a consulta)",
                         self.TRANSACAO)
            return
        if eco != matricula:
            raise DadosPessoaisIndisponiveis(
                matricula, f"o campo de busca traz a matrícula "
                           f"{mascarar_matricula(eco)}, não a pedida")

    def _imprimir(self, matricula: str) -> Path:
        """Imprime a tela e devolve o PDF BRUTO, ainda em pasta_download."""
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
        except PdfIlegivelError as exc:
            raise PdfImpressoIlegivel(
                bruto, None, "o PDF não abriu") from exc
        if not legivel:
            # fica com o nome bruto, na pasta de download, para inspeção
            raise PdfImpressoIlegivel(
                bruto, None, "o PDF não tem camada de texto")
        return bruto

    # ----- API -----

    def consultar(self, matricula: str) -> DadosPensionista:
        """Lê os dados do pensionista e imprime o PDF da tela.

        Raises:
            ValueError: matrícula vazia depois de normalizada a dígitos.
            TransacaoNaoAbriu: a tela não montou (mesmo após a repetição
                por relogin).
            DadosPessoaisIndisponiveis: botão ausente no prazo; os campos do
                formulário não apareceram ou vieram todos vazios (o sinal
                provável de matrícula inexistente); eco de matrícula
                divergente; a impressão não produziu PDF.
            PdfImpressoIlegivel: o impresso saiu sem camada de texto; o
                arquivo fica na pasta de download, sob o nome bruto, até a
                próxima impressão.

        Em falha dentro da transação, o módulo fecha popups, limpa a cortina
        e clica Sair (melhor esforço) antes de propagar, para a PRÓXIMA
        consulta começar com a tela limpa. Nada é impresso antes de os
        campos serem lidos e conferidos.
        """
        matricula = re.sub(r"\D", "", str(matricula).strip())
        if not matricula:
            raise ValueError("matricula é obrigatória")
        mascarada = mascarar_matricula(matricula)
        _log.info("%s: consultando a matrícula %s", self.TRANSACAO, mascarada)

        fechar_janelas_extras(self.driver)
        fechar_popups_cis(self.driver)
        limpar_overlay(self.driver)
        self._abrir_transacao()

        try:
            campo = self.driver.find_element(By.CSS_SELECTOR, self.SEL_MATRICULA)
            campo.clear()
            campo.send_keys(matricula)
            campo.send_keys(Keys.ENTER)
            time.sleep(self.DELAY_APOS_ENTER)
            self._clicar(self.SEL_CONSULTAR, matricula, "Consultar")
            time.sleep(self.DELAY_APOS_CONSULTAR)

            com_procuracao = atravessar_procuracao(self.driver)
            if com_procuracao:
                time.sleep(self.DELAY_APOS_CONSULTAR)
            ressalva = ("; a tela de procuração pode ter ficado presa"
                        if com_procuracao else "")

            if esperar_seletor(self.driver, self.SEL_NOME,
                               timeout=self.TIMEOUT_CAMPOS) is None:
                raise DadosPessoaisIndisponiveis(
                    matricula, "a consulta não trouxe dados (os campos do "
                               f"formulário não apareceram{ressalva})")

            campos = ler_campos(self.driver)
            self._conferir_identidade(matricula)
            if not any(campos.values()):
                raise DadosPessoaisIndisponiveis(
                    matricula, "a consulta não trouxe dados (todos os campos "
                               f"vazios{ressalva})")

            bruto = self._imprimir(matricula)
        except (DadosPessoaisIndisponiveis, PdfImpressoIlegivel):
            self._recuperar_tela()
            raise

        destino = self.pasta_saida / f"dados_pensionista_{matricula}.pdf"
        if destino.exists():
            destino.unlink()
        bruto.rename(destino)
        self._sair()

        dados = DadosPensionista(matricula=matricula, **campos,
                                 com_procuracao=com_procuracao, pdf=destino)
        _log.info("%s: %s lida, %d/11 campos%s", self.TRANSACAO, mascarada,
                  sum(1 for v in campos.values() if v),
                  " (com procuração)" if com_procuracao else "")
        return dados
```

- [ ] **Step 4: Rodar os testes**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_dados_pensionista.py tests/test_esiape_dados_pessoais.py -q
```

Esperado: todos passam. Depois a suíte inteira e o lint:

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest -q
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m ruff check .
```

Esperado: `860 + (testes novos) passed` e `All checks passed!`

- [ ] **Step 5: Commit**

Mensagem em `$env:TEMP\msg_p3.txt`:

```
feat(esiape): DadosPessoaisPensionista.consultar le a CDCOPSBENE e imprime o PDF

Navega (uma repeticao se um relogin atravessou), digita a matricula,
atravessa a tela de procuracao quando existe, le os 11 campos do formulario,
confere o eco do campo de busca e so entao imprime. Formulario ausente ou
todo vazio e o sinal provavel de matricula inexistente e levanta ANTES de
imprimir. Em falha, recupera a tela sem mascarar a excecao original.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

```bash
git add integra_gov/esiape/dados_pensionista.py tests/test_esiape_dados_pensionista.py
git commit -F "$env:TEMP\msg_p3.txt"
```

---

### Task 4: exportação, documentação e script do gate

**Files:**
- Modify: `integra_gov/esiape/__init__.py`
- Modify: `README.md` (exemplo após o bloco de `dados_pessoais`; linha na tabela após `integra_gov.esiape.dados_pessoais`)
- Modify: `CHANGELOG.md` (topo de `### Adicionado` em `## [Não publicado]`)
- Modify: `docs/uso-basico.md` (nova seção logo após `## Dados pessoais de uma matrícula (e-SIAPE)`)
- Modify: `tests/test_esiape_dados_pensionista.py` (teste de exportação)
- Create: `dados_reais/esiape_dados_pensionista_gate.py` (pasta gitignored; NÃO entra no commit)

**Interfaces:**
- Consumes: tudo das Tasks 2 e 3.
- Produces: `from integra_gov.esiape import DadosPensionista, DadosPessoaisPensionista`.

- [ ] **Step 1: Teste de exportação (falha)**

Acrescentar ao final de `tests/test_esiape_dados_pensionista.py`:

```python
def test_exportado_no_subpacote():
    import integra_gov.esiape as pkg

    for nome in ("DadosPensionista", "DadosPessoaisPensionista"):
        assert hasattr(pkg, nome), nome
        assert nome in pkg.__all__, nome
```

Rodar:

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_esiape_dados_pensionista.py::test_exportado_no_subpacote -q
```

Esperado: `AssertionError: DadosPensionista`.

- [ ] **Step 2: Exportar**

Em `integra_gov/esiape/__init__.py`, inserir após a linha `from .dados_pessoais import ...`:

```python
from .dados_pensionista import DadosPensionista, DadosPessoaisPensionista
```

Em `__all__`, inserir em ordem alfabética `"DadosPensionista"` e `"DadosPessoaisPensionista"` (vêm logo depois de `"DadosFuncionaisOrgao"` e antes de `"DadosPessoais"`, porque `Pen` < `Pes`).

No docstring do pacote, na frase que hoje termina com "e dados pessoais (CDCOINDPES) lidos do PDF impresso.", trocar por: "dados pessoais de servidor (CDCOINDPES, lidos do PDF impresso) e de pensionista (CDCOPSBENE, lidos do formulário)."

Rodar o teste de exportação: PASS.

- [ ] **Step 3: README**

Após o bloco de código do exemplo de `dados_pessoais` e o parágrafo que o segue, inserir:

````markdown
**Pensionista** tem transação própria (`CDCOPSBENE`), que é um formulário e
não um relatório: os campos saem da tela, e o PDF impresso vai junto como
documento. Além dos dados da pessoa, o resultado diz se há procuração
cadastrada:

```python
from pathlib import Path
from integra_gov.esiape import DadosPessoaisPensionista

cad = DadosPessoaisPensionista(driver, pasta_saida=Path("cadastrais/"))
dados = cad.consultar("0000000")                 # matrícula fictícia
print(dados.pdf, dados.municipio, dados.com_procuracao)
```

Os campos são nome, CPF, nascimento, e-mail, o endereço completo (logradouro,
número, complemento, bairro, município, UF e CEP) e a matrícula. Campo vazio
fica `None`.
````

Na tabela de módulos, após a linha de `integra_gov.esiape.dados_pessoais`:

```markdown
| `integra_gov.esiape.dados_pensionista` | `CDCOPSBENE`: 12 campos do pensionista lidos do formulário + PDF da tela; atravessa e registra a tela de procuração | ✅ |
```

- [ ] **Step 4: CHANGELOG**

No topo de `### Adicionado` em `## [Não publicado]`:

```markdown
- **`integra_gov.esiape.dados_pensionista`** (`CDCOPSBENE`): `DadosPessoaisPensionista.consultar(matricula)`
  devolve `DadosPensionista` com doze campos (matrícula, nome, CPF,
  nascimento, e-mail e o endereço completo) mais `com_procuracao`, e o PDF
  impresso da tela como documento. Os campos saem do **formulário**, não do
  PDF: a CDCOPSBENE é uma tela de entrada, ao contrário da CDCOINDPES, que é
  relatório. Campo vazio vira `None`, nunca exceção. A tela intermediária de
  procuração é atravessada e registrada no resultado. Formulário ausente ou
  todo vazio levanta `DadosPessoaisIndisponiveis` **antes de imprimir**.
  `repr(DadosPensionista)` omite nome, CPF, nascimento, e-mail e endereço.
  Porte do módulo privado, com a impressão trocada pela mecânica de
  `esiape.impressao`. **Ainda não verificado ao vivo** (o gate está
  planejado); até lá a data de nascimento aceita as duas formas plausíveis e
  a conferência de identidade tolera o campo de busca vazio.
- **`integra_gov.esiape._campos`** (interno): a máscara de dígitos, a máscara
  de matrícula e a conversão de data do SIAPE saíram de `dados_pessoais` para
  serem compartilhadas com o módulo de pensionista. Sem mudança de
  comportamento.
```

- [ ] **Step 5: uso-basico**

Logo após o fim da seção `## Dados pessoais de uma matrícula (e-SIAPE)` e antes da próxima seção de nível dois, inserir:

````markdown
## Dados pessoais de um pensionista (e-SIAPE)

A `CDCOPSBENE` é a transação do pensionista. Ela é um **formulário**, não um
relatório: os valores chegam dentro dos campos da tela, e é de lá que o
módulo os lê. O PDF impresso continua sendo gerado, porque é o documento que
se anexa ao processo.

```python
from pathlib import Path
from integra_gov.esiape import AcessoEsiape, DadosPessoaisPensionista

AcessoEsiape(driver).executar()                  # você confirma no app
cad = DadosPessoaisPensionista(driver, pasta_saida=Path("cadastrais/"))
dados = cad.consultar("0000000")                 # matrícula fictícia
dados.pdf                 # cadastrais/dados_pensionista_0000000.pdf
dados.nome, dados.cpf, dados.data_nascimento, dados.email
dados.logradouro, dados.numero, dados.complemento, dados.bairro
dados.municipio, dados.uf, dados.cep
dados.com_procuracao      # True quando há procurador cadastrado
```

O Chrome precisa das prefs de impressão da seção "Configuração do Chrome"
(acima), e `pasta_download` (default `cadastrais/_download_esiape`) tem de
ser **dedicada**: a impressão apaga todos os PDFs dela antes de começar.

Regras de honestidade do módulo:

- campo vazio fica `None`; não é erro;
- formulário que não aparece, ou que vem todo vazio, é o sinal provável de
  matrícula inexistente e levanta `DadosPessoaisIndisponiveis` **antes de
  imprimir** (nenhum PDF é produzido);
- a tela de procuração é atravessada quando existe, e o resultado registra
  isso em `com_procuracao`;
- PDF sem camada de texto levanta `PdfImpressoIlegivel`, com o arquivo
  mantido na pasta de download, sob o nome bruto, até a próxima impressão;
- se um relogin do SERPRO atravessar entre duas consultas, a navegação é
  repetida uma vez; persistindo, `TransacaoNaoAbriu`.

Duas limitações declaradas, e as duas diferem do módulo de servidor:

1. **A conferência de identidade é mais fraca.** A tela não devolve a
   matrícula junto dos dados, então o módulo compara apenas o que ficou no
   campo de busca. Se esse campo vier vazio, um aviso registra que a
   conferência não foi possível e a consulta segue. A proteção estrutural é
   que cada consulta navega para a transação do zero.
2. **Não há releitura sem navegador.** Os campos vêm do DOM, não do PDF, de
   modo que um PDF de pensionista já no disco não pode ser relido como
   dados. Para servidor isso existe, em `ler_dados_pessoais`.

Nos logs só aparecem os dois últimos dígitos da matrícula; nome, CPF,
e-mail e endereço nunca são logados.
````

- [ ] **Step 6: Script do gate (gitignored)**

Criar `dados_reais/esiape_dados_pensionista_gate.py`:

```python
"""Gate ao vivo do modulo esiape.dados_pensionista (CDCOPSBENE).

    python dados_reais/esiape_dados_pensionista_gate.py [m1 m2 inexistente]

Sem argumentos, pede as matriculas. Use duas REAIS de pensionista nas duas
primeiras posicoes (de preferencia uma COM procuracao) e uma INEXISTENTE na
ultima. Chrome com as prefs de impressao de docs/uso-basico.md; Serpro ID
confirmado pelo usuario.

Verifica FORMA, nunca valor: imprime PASS/FAIL por campo e nada mais.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

from selenium.webdriver.chrome.options import Options as ChromeOptions

from integra_gov.esiape import AcessoEsiape, DadosPessoaisPensionista, EsiapeError
from integra_gov.sei import criar_driver_chrome

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
SAIDA = Path(__file__).parent / "_gate_dados_pensionista"
DOWNLOAD = SAIDA / "_download_esiape"

REGRAS = {
    "cpf": (r"\d{3}\.\d{3}\.\d{3}-\d{2}", "ddd.ddd.ddd-dd"),
    "data_nascimento": (r"\d{2}/\d{2}/\d{4}", "dd/mm/aaaa"),
    "uf": (r"[A-Z]{2}", "2 letras maiusculas"),
    "cep": (r"\d{5}-?\d{3}", "8 digitos"),
}
TEXTO_LIVRE = ("nome", "logradouro", "bairro", "municipio", "complemento",
               "numero")


def _mascarar(texto: str) -> str:
    return re.sub(r"\d(?:[.\-/ ]?\d){2,}",
                  lambda m: "*****" + re.sub(r"\D", "", m.group(0))[-2:], texto)


def verificar_forma(d, pedida: str) -> bool:
    ok = True
    for campo, (padrao, regra) in REGRAS.items():
        valor = getattr(d, campo)
        passou = bool(valor) and re.fullmatch(padrao, valor) is not None
        ok = ok and passou
        print(f"   {campo}: {'PASS' if passou else 'FAIL (' + regra + ')'}")
    email = d.email or ""
    passou = email.count("@") == 1 and " " not in email and email == email.lower()
    ok = ok and passou
    print(f"   email: {'PASS' if passou else 'FAIL (um @, sem espaco, minusculo)'}")
    for campo in TEXTO_LIVRE:
        valor = getattr(d, campo)
        passou = bool(valor) and ":" not in valor
        ok = ok and passou
        print(f"   {campo}: {'PASS' if passou else 'FAIL (vazio ou com :)'}")
    passou = d.matricula == pedida
    ok = ok and passou
    print(f"   matricula: {'PASS' if passou else 'FAIL (difere da pedida)'}")
    print(f"   com_procuracao: {d.com_procuracao}")
    print(f"   repr sem digitos longos: {re.search(r'[0-9]{3,}', repr(d)) is None}")
    return ok


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
    matriculas = [a for a in sys.argv[1:] if a.strip()]
    if not matriculas:
        print("Digite as matriculas de PENSIONISTA (so digitos), separadas por espaco.")
        print("Duas REAIS primeiro (se possivel uma COM procuracao); a ultima INEXISTENTE.")
        matriculas = input("> ").split()
    matriculas = [re.sub(r"\D", "", m) for m in matriculas]
    matriculas = [m for m in matriculas if m]
    if len(matriculas) < 2:
        print("preciso de pelo menos duas matriculas.")
        return 2

    SAIDA.mkdir(parents=True, exist_ok=True)
    DOWNLOAD.mkdir(parents=True, exist_ok=True)
    driver = abrir_chrome()
    falhou = False
    try:
        print("== Login SERPRO ID: CONFIRME NO APP ==")
        AcessoEsiape(driver).executar()
        cad = DadosPessoaisPensionista(driver, pasta_saida=SAIDA,
                                       pasta_download=DOWNLOAD)
        for m in matriculas:
            print(f"== matricula *****{m[-2:]} ==")
            try:
                d = cad.consultar(m)
                print(f"   {_mascarar(d.pdf.name)}")
                if not verificar_forma(d, m):
                    falhou = True
                    print("   FALHOU")
                else:
                    print("   OK")
            except EsiapeError as exc:
                esperada = m == matriculas[-1] and len(matriculas) >= 3
                if not esperada:
                    falhou = True
                print(f"   EXC {type(exc).__name__}: {_mascarar(str(exc))}")
                print("   (esperada: matricula inexistente; anote o que a tela mostrou)"
                      if esperada else "   (NAO esperada)")
    finally:
        input(">> ENTER para fechar o Chrome da automacao... ")
        driver.quit()
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
```

Confirmar que a pasta é ignorada:

```bash
git check-ignore dados_reais/esiape_dados_pensionista_gate.py
```

Esperado: o caminho é impresso (está ignorado).

- [ ] **Step 7: Suíte inteira e lint**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest -q
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m ruff check .
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m py_compile dados_reais/esiape_dados_pensionista_gate.py
```

Esperado: tudo passa; `git status --short` não mostra `dados_reais/`.

- [ ] **Step 8: Commit**

Mensagem em `$env:TEMP\msg_p4.txt`:

```
feat(esiape): exporta dados_pensionista e documenta (README, CHANGELOG, uso-basico)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

```bash
git add integra_gov/esiape/__init__.py README.md CHANGELOG.md docs/uso-basico.md tests/test_esiape_dados_pensionista.py
git commit -F "$env:TEMP\msg_p4.txt"
```

---

## Depois das quatro tarefas (fora do plano de código)

1. Review final da branch com o modelo mais capaz, e onda única de correções.
2. Gate ao vivo pelo usuário, com o comando sem argumentos (o script pede as matrículas). Registrar na spec a seção "Verificado ao vivo" com as quatro medições: forma da data, eco do campo de busca, comportamento com matrícula inexistente e se o PDF impresso tem camada de texto e carrega os campos.
3. Encolher o código à medida: a forma de data que não ocorrer sai de `_data_nascimento`; se o eco existir sempre, a tolerância sai de `_conferir_identidade`.
4. Trocar no CHANGELOG a nota "Ainda não verificado ao vivo" pela data do gate.
5. Merge em `main`; push só com ordem do usuário.
