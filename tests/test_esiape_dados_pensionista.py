"""Testes de ``integra_gov.esiape.dados_pensionista`` (CDCOPSBENE)."""

from __future__ import annotations

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
