"""Testes de ``integra_gov.siape.ficha_pensionista`` — terminal mockado."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from integra_gov.siape import _menu
from integra_gov.siape.controle import ControleTerminal3270
from integra_gov.siape.exceptions import (
    ExtracaoFichaInterrompida,
    FichaIndisponivel,
    InstituidorObrigatorio,
    SiapeError,
)
from integra_gov.siape.ficha_pensionista import (
    FichaAnualPensionista,
    ResultadoFichaAnual,
)


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    from integra_gov.siape import ficha_pensionista as fmod

    monkeypatch.setattr(fmod.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(_menu.time, "sleep", lambda *_a, **_k: None)


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


def test_janela_aparece_apos_checagem_de_0034_ainda_recupera_com_f2(tmp_path):
    """F2 pós-leitura no caminho "com dados": a janela de salvar só aparece na
    2ª checagem do poll — a 1ª já rodou _sem_dados_no_terminal() (copiar_tela,
    que desalinha o cursor). O F2 de recuperação deve ser enviado mesmo assim,
    para o próximo ano não cair com os dígitos em campos errados."""
    ficha, c = _ficha_ano(tmp_path, "tela sem 0034 nem texto reconhecivel")
    destino_esperado = tmp_path / "ficha_0000001_2024.pdf"

    def _salva(caminho):
        caminho.write_bytes(b"%PDF-conteudo")

    with patch.object(
        ficha, "_janela_salvar_existe", side_effect=[False, True]
    ), patch.object(ficha, "_salvar_via_dialogo", side_effect=_salva):
        resultado = ficha._processar_ano("0000001", 2024)
    assert resultado == destino_esperado
    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert "{F2}" in enviados


def test_janela_aparece_na_1a_checagem_nao_envia_f2(tmp_path):
    """Espelho do teste acima: quando a janela já existe na 1ª checagem do
    poll, _sem_dados_no_terminal() nunca roda — a sequência de produção do
    caminho rápido fica intocada e o F2 de recuperação NÃO é enviado."""
    ficha, c = _ficha_ano(tmp_path)
    destino_esperado = tmp_path / "ficha_0000001_2024.pdf"

    def _salva(caminho):
        caminho.write_bytes(b"%PDF-conteudo")

    with patch.object(ficha, "_janela_salvar_existe", return_value=True), \
         patch.object(ficha, "_salvar_via_dialogo", side_effect=_salva):
        resultado = ficha._processar_ano("0000001", 2024)
    assert resultado == destino_esperado
    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert "{F2}" not in enviados


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


def test_extrair_ponta_a_ponta_pensao_multipla(tmp_path):
    """Costura de ponta a ponta: ``extrair()`` roda de verdade — sem mockar
    ``_posicionar``/``_processar_ano`` — cobrindo menu → comando → matrícula →
    seleção de instituidor → ano sem dados (0034) → ano com dados → F12. Só os
    dois pontos de contato com o pywinauto (``_janela_salvar_existe`` e
    ``_salvar_via_dialogo``) são mockados."""
    telas = [
        "",  # checagem do menu (conteúdo irrelevante; extrair_texto é mockado)
        _tela_selecao("( ) 1111111 FULANO", "( ) 2222222 BELTRANO"),
        "TELA DA FICHA (0034) NAO EXISTEM DADOS PARA ESTA CONSULTA",  # ano 2023
    ]
    estado = {"i": 0}

    def _copiar_tela(*_a, **_k):
        # Função com estado em vez de lista fixa: chamadas extras (ex.: um
        # retry no menu) repetem a última tela em vez de estourar o índice.
        i = estado["i"]
        estado["i"] += 1
        return telas[i] if i < len(telas) else telas[-1]

    c = MagicMock(spec=ControleTerminal3270)
    c.extrair_texto.return_value = _menu.TEXTO_LINHA_COMANDO  # menu já alcançado
    c.copiar_tela.side_effect = _copiar_tela

    ficha = FichaAnualPensionista(c, pasta_saida=tmp_path)

    def _salva(caminho):
        caminho.write_bytes(b"%PDF-conteudo")

    with patch.object(
        ficha, "_janela_salvar_existe", side_effect=[False, True]
    ), patch.object(ficha, "_salvar_via_dialogo", side_effect=_salva):
        resultado = ficha.extrair(
            "0000002", 2023, 2024, matricula_instituidor="2222222"
        )

    assert resultado.anos_sem_dados == [2023]
    assert resultado.anos_com_dados == [2024]
    destino = tmp_path / "ficha_0000002_2024.pdf"
    assert resultado.pdfs == [destino]
    assert destino.exists()

    enviados = [ch.args[0] for ch in c.enviar_teclas.call_args_list if ch.args]
    assert "X" in enviados      # marca o instituidor selecionado (e X do ano)
    assert "{TAB}" in enviados  # navega até a 2ª opção da tela de seleção
    assert "{F12}" in enviados  # finalização


def test_exports_do_pacote():
    from integra_gov.siape import FichaAnualPensionista as F
    from integra_gov.siape import ResultadoFichaAnual as R

    assert F is FichaAnualPensionista
    assert R is ResultadoFichaAnual
