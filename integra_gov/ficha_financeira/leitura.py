"""Leitura bruta do PDF: abre o arquivo e devolve o texto de cada página.

Camada mais baixa do módulo. Ela **não** conhece ficha financeira nenhuma —
não sabe o que é rubrica, competência ou total. Faz três coisas e para:

1. abre o PDF (ou falha dizendo por quê);
2. detecta se ele tem **camada de texto**;
3. devolve o texto por página, preservando o alinhamento das colunas.

O ponto 2 é o que evita o modo de falha mais traiçoeiro deste domínio. Uma
ficha impressa por um driver que converte fonte em contorno vetorial (o caso
conhecido é a impressora ``Microsoft Print to PDF`` do Windows) fica visualmente
perfeita e completamente ilegível por máquina: `extract_text` devolve string
vazia. Sem essa checagem, o pipeline inteiro atravessaria em silêncio e
entregaria uma ficha sem lançamento nenhum como se fosse uma ficha vazia
legítima.

A biblioteca **não faz OCR** e isso é deliberado: reconhecer dígito por dígito
em valor monetário troca centavos sem avisar. Diante de um PDF sem texto, o
caminho honesto é falhar dizendo como reemitir o arquivo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Union

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .exceptions import PdfIlegivelError, PdfSemTextoError

_log = logging.getLogger(__name__)

#: O que a leitura aceita como entrada: caminho, bytes ou arquivo aberto.
OrigemPdf = Union[str, Path, bytes, IO[bytes]]

__all__ = ["OrigemPdf", "PaginaTexto", "abrir_pdf", "extrair_paginas",
           "tem_camada_de_texto"]

#: Orientação repetida nas mensagens de erro de PDF sem texto.
#:
#: Deliberadamente **não** prescreve uma ferramenta: qualquer PDF que preserve
#: a camada de texto serve, e a biblioteca não sabe nem precisa saber como o
#: arquivo foi produzido. O que se nomeia é a causa conhecida do problema.
_COMO_REEMITIR = (
    "o PDF não tem camada de texto (os caracteres viraram curvas vetoriais). "
    "Qualquer PDF que preserve o texto serve, não importa a origem: se o "
    "sistema oferecer download direto do arquivo, ele é a via mais segura; se "
    "for impressão, use um destino que preserve o texto (o 'Salvar como PDF' "
    "nativo do navegador). O caso conhecido que destrói o texto é a impressora "
    "virtual 'Microsoft Print to PDF' do Windows, que converte as fontes em "
    "contorno"
)


@dataclass(frozen=True)
class PaginaTexto:
    """O texto de uma página, com o número dela.

    O número é **1-based**, como o usuário vê no leitor de PDF, e é o que
    alimenta :attr:`~integra_gov.ficha_financeira.modelo.Origem.paginas` —
    num PDF mesclado é ele que diz de onde cada ficha saiu.

    Attributes:
        numero: número da página no PDF, começando em 1.
        texto: texto extraído em modo *layout* (colunas preservadas). Vazio
            quando a extração da página falhou.
        erro: mensagem da falha, quando a página não pôde ser extraída.
            ``None`` no caso normal.

            Uma página que estoura **não derruba o documento** — mas a falha
            precisa viajar no dado, não só no log. No layout do e-SIAPE uma
            ficha inteira cabe em uma página; se ela sumisse em silêncio, o
            retorno traria uma ficha a menos sem nada que denunciasse a perda.
            Log não é contrato.
    """

    numero: int
    texto: str
    erro: str | None = None

    @property
    def vazia(self) -> bool:
        """``True`` quando a página não tem nenhum caractere não-branco.

        Uma página legítima em branco e uma página que falhou são as duas
        vazias — o que as distingue é :attr:`legivel`.
        """
        return not self.texto.strip()

    @property
    def legivel(self) -> bool:
        """``False`` quando a extração desta página falhou."""
        return self.erro is None


def abrir_pdf(origem: OrigemPdf) -> PdfReader:
    """Abre o PDF e devolve o leitor do pypdf.

    Args:
        origem: caminho, ``bytes`` ou arquivo binário já aberto.

    Returns:
        O :class:`~pypdf.PdfReader` posicionado no documento.

    Raises:
        PdfIlegivelError: arquivo ausente, ilegível, corrompido ou protegido
            por senha.
    """
    alvo: object = origem
    if isinstance(origem, bytes):
        import io
        alvo = io.BytesIO(origem)

    try:
        leitor = PdfReader(alvo)  # type: ignore[arg-type]
    except FileNotFoundError as exc:
        raise PdfIlegivelError(f"arquivo não encontrado: {origem!r}") from exc
    except (PdfReadError, OSError, ValueError) as exc:
        raise PdfIlegivelError(f"não foi possível abrir o PDF: {exc}") from exc

    if leitor.is_encrypted:
        # Senha vazia resolve o caso comum de PDF só com dono; se não resolver,
        # a biblioteca não pede senha ao usuário — quem chama decide.
        try:
            if not leitor.decrypt(""):
                raise PdfIlegivelError(
                    "o PDF está protegido por senha; a biblioteca não solicita "
                    "senha — abra e salve uma cópia sem proteção antes de ler")
        except PdfIlegivelError:
            raise
        except Exception as exc:
            raise PdfIlegivelError(
                f"o PDF está protegido e não pôde ser aberto: {exc}") from exc

    return leitor


def tem_camada_de_texto(origem: OrigemPdf) -> bool:
    """Diz se o PDF tem texto extraível — sem levantar por ausência de texto.

    É o guard barato para quem acabou de **gerar** um PDF e quer confirmar que
    ele saiu legível antes de seguir adiante. O caso de uso que motivou expor
    isto como função pública é o download da ficha no e-SIAPE: sem essa
    verificação, um PDF impresso pela impressora errada é aceito em silêncio.

    Para de varrer assim que encontra a primeira página com texto, então o
    custo é desprezível no caso bom; o caso ruim (nenhum texto) é justamente o
    que precisa ser varrido por inteiro para ter certeza.

    Args:
        origem: caminho, ``bytes`` ou arquivo binário já aberto.

    Returns:
        ``True`` se ao menos uma página tem caractere não-branco.

    Raises:
        PdfIlegivelError: se o arquivo sequer abre. Não é confundido com
            "abriu e não tem texto" de propósito — são problemas diferentes,
            com soluções diferentes.
    """
    leitor = abrir_pdf(origem)
    for pagina in leitor.pages:
        try:
            texto = pagina.extract_text() or ""
        except Exception:  # página quebrada não invalida o documento inteiro
            continue
        if texto.strip():
            return True
    return False


def extrair_paginas(origem: OrigemPdf) -> tuple[PaginaTexto, ...]:
    """Devolve o texto de cada página, com as colunas preservadas.

    Usa o modo ``layout`` do pypdf, que reconstrói o espaçamento horizontal —
    indispensável aqui, porque no relatório do SIAPE mainframe a informação
    está na **posição** do caractere (a coluna 33 diz se o lançamento é
    rendimento ou desconto).

    Args:
        origem: caminho, ``bytes`` ou arquivo binário já aberto.

    Returns:
        Uma tupla de :class:`PaginaTexto`, na ordem do documento. Páginas em
        branco são mantidas, para que a numeração continue batendo com o PDF.
        Página cuja extração falhou vem com :attr:`PaginaTexto.erro` preenchido
        em vez de derrubar o documento inteiro — a falha fica no dado, para
        quem monta a ficha decidir.

    Raises:
        PdfIlegivelError: o arquivo não abre.
        PdfSemTextoError: o arquivo abre mas **nenhuma** página tem texto.
    """
    leitor = abrir_pdf(origem)
    paginas: list[PaginaTexto] = []

    for indice, pagina in enumerate(leitor.pages, start=1):
        try:
            texto = pagina.extract_text(extraction_mode="layout") or ""
        except Exception as exc:
            _log.warning("página %d não pôde ser extraída (%s)", indice, exc)
            paginas.append(PaginaTexto(numero=indice, texto="", erro=str(exc)))
            continue
        paginas.append(PaginaTexto(numero=indice, texto=texto))

    if not paginas:
        raise PdfIlegivelError("o PDF não tem páginas")

    if all(pagina.vazia for pagina in paginas):
        # Duas causas diferentes produzem o mesmo "tudo vazio", e o conselho de
        # cada uma é outro. Se houve falha de extração, o PDF pode muito bem ter
        # camada de texto — mandar reemitir o arquivo seria afirmar uma causa
        # que os próprios erros em mãos desmentem, e ainda descartaria as
        # mensagens que dizem o que de fato houve.
        falhas = [pagina for pagina in paginas if pagina.erro]
        if falhas:
            detalhe = "; ".join(f"p{p.numero}: {p.erro}" for p in falhas)
            raise PdfIlegivelError(
                f"nenhuma das {len(paginas)} página(s) pôde ser extraída; "
                f"falhas: {detalhe}")
        raise PdfSemTextoError(
            f"{len(paginas)} página(s) lida(s) e nenhuma tem texto: "
            f"{_COMO_REEMITIR}")

    return tuple(paginas)
