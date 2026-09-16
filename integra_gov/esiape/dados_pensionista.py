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
import time
from dataclasses import dataclass, field
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from ..ficha_financeira import PdfIlegivelError, tem_camada_de_texto
from ._campos import data_siape, mascarar_digitos, mascarar_matricula
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
