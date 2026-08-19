"""Exceções tipadas do subpacote ``integra_gov.ficha_financeira``."""

from __future__ import annotations


class FichaFinanceiraError(Exception):
    """Erro base da leitura de ficha financeira em PDF."""


class PdfIlegivelError(FichaFinanceiraError):
    """O arquivo não pôde ser aberto como PDF (ausente, corrompido ou cifrado)."""


class PdfSemTextoError(FichaFinanceiraError):
    """O PDF abriu, mas não tem **camada de texto** — nada a extrair.

    Acontece quando a ficha é impressa por um driver que converte a fonte em
    contorno vetorial (o caso conhecido é a impressora ``Microsoft Print to
    PDF`` do Windows): o arquivo fica com aparência correta na tela, mas sem
    um único caractere legível por máquina.

    A biblioteca **não** faz OCR: reconhecer dígito por dígito em valor
    monetário troca centavos em silêncio. O caminho é obter o PDF preservando
    o texto — e a biblioteca aceita **qualquer** PDF assim, seja ele baixado
    direto do sistema ou impresso por um destino que não vetorize as fontes.
    """


class LayoutNaoReconhecidoError(FichaFinanceiraError):
    """O PDF tem texto, mas não corresponde a nenhum layout conhecido.

    Layouts suportados: o relatório do SIAPE mainframe (``L.A54120.DE``) e a
    impressão web do e-SIAPE.

    Também é levantada quando uma página é reconhecida como de um layout mas
    lhe falta um elemento estrutural que o parser precisa. Descartar a página
    seria perder as rubricas dela sem deixar rastro no retorno.

    Attributes:
        pagina: número da página no PDF (1-based), quando conhecido.
    """

    def __init__(self, mensagem: str, *, pagina: int | None = None) -> None:
        super().__init__(mensagem)
        self.pagina = pagina


class MultiplasFichasError(FichaFinanceiraError):
    """Pediu-se **uma** ficha, mas o PDF contém mais de uma.

    Acontece com os PDFs mesclados que o próprio pacote produz (vários anos,
    vários órgãos). Devolver a primeira seria escolher em silêncio por quem
    chamou; a saída é usar a API plural.

    Attributes:
        quantidade: quantas fichas o PDF continha.
    """

    def __init__(self, mensagem: str, *, quantidade: int = 0) -> None:
        super().__init__(mensagem)
        self.quantidade = quantidade


class LinhaNaoReconhecidaError(FichaFinanceiraError):
    """Uma linha não vazia da tabela não casou com nenhum padrão conhecido.

    Levantada **sempre**, mesmo fora do modo estrito, e a distinção é
    deliberada: total que não fecha é uma divergência *visível* — o consumidor
    vê ``confere=False`` e decide. Já uma linha descartada em silêncio some
    sem deixar rastro, e a ficha resultante parece íntegra estando incompleta.
    Perder dado calado é a violação real de "mensagens honestas".

    Carrega a linha ofensora e a página, e não só a mensagem: quem recebe o
    erro precisa conseguir olhar o PDF no ponto certo sem reabrir a leitura.

    Attributes:
        linha: o texto da linha que não foi reconhecida.
        pagina: número da página no PDF (1-based), quando conhecido.
    """

    def __init__(self, mensagem: str, *, linha: str | None = None,
                 pagina: int | None = None) -> None:
        super().__init__(mensagem)
        self.linha = linha
        self.pagina = pagina


class FichaInconsistenteError(FichaFinanceiraError):
    """Os lançamentos lidos não fecham com os totais impressos na ficha.

    Só é levantada quando a leitura é feita em modo estrito; por padrão a
    divergência vira aviso e ``TotaisMes.confere`` fica ``False``, para que o
    consumidor decida o que fazer.
    """
