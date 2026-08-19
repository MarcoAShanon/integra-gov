"""Gerador de PDFs mínimos para os testes de leitura.

Monta os bytes do PDF diretamente, sem depender de API interna do pypdf: um
helper de teste que usasse `PdfWriter._add_object` quebraria a cada mudança de
versão da dependência, e o que se quer testar aqui é a nossa leitura, não a
escrita de terceiros.

Serve só à camada de leitura (M2), que não conhece ficha financeira — para os
parsers de layout as fixtures são *scrub* geométrico do PDF real, porque uma
tabela escrita à mão pode codificar colunas que não existem.
"""

from __future__ import annotations

from typing import Optional, Sequence

__all__ = ["pdf_bytes"]


def _stream(dados: bytes) -> bytes:
    return (b"<< /Length " + str(len(dados)).encode() + b" >>\nstream\n"
            + dados + b"\nendstream")


def _montar(objetos: Sequence[bytes]) -> bytes:
    """Concatena os objetos e escreve a tabela xref com os offsets reais."""
    saida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for indice, corpo in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida += f"{indice} 0 obj\n".encode() + corpo + b"\nendobj\n"

    inicio_xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n".encode()
    saida += b"0000000000 65535 f \n"
    for offset in offsets:
        saida += f"{offset:010d} 00000 n \n".encode()
    saida += (f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
              f"startxref\n{inicio_xref}\n%%EOF\n").encode()
    return bytes(saida)


def pdf_bytes(paginas: Sequence[Optional[Sequence[str]]], *,
              com_fonte: bool = True) -> bytes:
    """Monta um PDF de teste.

    Args:
        paginas: uma entrada por página. Uma sequência de strings vira texto
            (uma linha por string); ``None`` vira uma página **sem texto** —
            só um retângulo desenhado, que é o que sobra quando a impressão
            converte os glifos em curva vetorial.
        com_fonte: quando ``False``, as páginas não declaram ``/Font``,
            reproduzindo o PDF vetorizado da impressora do Windows.

    Returns:
        Os bytes de um PDF válido.
    """
    objetos: list[bytes] = [b"", b""]  # 1 = catálogo, 2 = árvore de páginas
    kids: list[str] = []
    numero = 3

    for linhas in paginas:
        if linhas is None:
            conteudo = b"0 0 0 rg\n36 700 100 20 re f\n"
        else:
            ops = ["BT", "/F1 10 Tf", "12 TL", "36 750 Td"]
            for linha in linhas:
                escapada = (linha.replace("\\", r"\\")
                                 .replace("(", r"\(")
                                 .replace(")", r"\)"))
                ops.append(f"({escapada}) Tj T*")
            ops.append("ET")
            # A fonte Type1 padrão só cobre latin-1, e o texto real traz
            # caracteres fora dela (reticências, por exemplo). `replace` troca
            # cada um por "?", preservando o comprimento — e é o comprimento,
            # não o glifo, que os testes de layout exercitam.
            conteudo = "\n".join(ops).encode("latin-1", errors="replace")

        recursos = (b"<< /Font << /F1 << /Type /Font /Subtype /Type1 "
                    b"/BaseFont /Courier >> >> >>") if com_fonte else b"<< >>"
        objetos.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources " + recursos + f" /Contents {numero + 1} 0 R >>".encode()
        )
        objetos.append(_stream(conteudo))
        kids.append(f"{numero} 0 R")
        numero += 2

    objetos[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objetos[1] = (b"<< /Type /Pages /Kids [" + " ".join(kids).encode()
                  + b"] /Count " + str(len(kids)).encode() + b" >>")
    return _montar(objetos)
