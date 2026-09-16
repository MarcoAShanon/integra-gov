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
