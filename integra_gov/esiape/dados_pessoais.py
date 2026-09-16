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
import time
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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
    limpar_flag_relogin,
    limpar_overlay,
    navegar_para_transacao,
    procurar_em_frames,
    relogin_pendente,
)

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
