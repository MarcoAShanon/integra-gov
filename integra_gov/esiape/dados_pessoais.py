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
