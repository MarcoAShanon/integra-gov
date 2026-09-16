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
