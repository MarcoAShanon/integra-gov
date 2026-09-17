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
    texto_popup_cis,
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
            # mascarar_digitos roda no CAMINHO INTEIRO, não só no nome do
            # arquivo: quem organiza a saída por matrícula (ex.:
            # cadastrais/<matricula>/) não pode ver a matrícula vazar pela
            # pasta. str(Path) já usa o separador correto do SO.
            pdf_repr = repr(mascarar_digitos(str(self.pdf)))
        else:
            pdf_repr = "None"
        return (
            f"DadosPensionista("
            f"matricula={mascarar_matricula(self.matricula or '')!r}, "
            f"municipio={self.municipio!r}, uf={self.uf!r}, "
            f"com_procuracao={self.com_procuracao!r}, pdf={pdf_repr})"
        )


# ------------------------------------------------------------- leitura
def forma_da_data(bruto: str | None) -> str:
    """Qual forma a tela usou para a data: ``DDMMMAAAA``, ``dd/mm/aaaa``,
    ``outra`` ou ``ausente``. Serve à medição do gate — o nome da forma não
    é dado pessoal, o valor é."""
    texto = (bruto or "").strip()
    if not texto:
        return "ausente"
    if re.fullmatch(r"\d{2}[A-Z]{3}\d{4}", texto.upper()):
        return "DDMMMAAAA"
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto):
        return "dd/mm/aaaa"
    return "outra"


def _data_nascimento(bruto: str | None) -> str | None:
    """``15AGO1960`` → ``15/08/1960``; ``15/08/1960`` mantido; resto ``None``.

    PENDÊNCIA (gate ao vivo): qual das duas formas a CDCOPSBENE devolve não
    foi medido. Depois do gate, a que não ocorrer sai daqui.
    """
    forma = forma_da_data(bruto)
    if forma == "DDMMMAAAA":
        return data_siape(bruto)
    if forma == "dd/mm/aaaa":
        return (bruto or "").strip()
    return None


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
    _log.debug("%s: data de nascimento na forma %s", TRANSACAO,
               forma_da_data(cru["data_nascimento"]))
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
    SEL_NOME = f'input[data-testtoolid="{CAMPOS_FORMULARIO["nome"]}"]'
    #: Na CDCOPSBENE este ÚNICO clique já abre a janela que traz o PDF —
    #: medido no gate ao vivo de 16/09: o clique em onPrintPDF tinha sucesso
    #: e a consulta SEGUINTE fechava "1 janela extra", prova de que uma
    #: janela nova havia sido aberta ali. Não existe aqui um segundo passo
    #: "gerar versão para impressão"; esse botão
    #: (``w_report.onGeneratePrintVersion``) é das telas de RELATÓRIO
    #: (CDCOINDPES, FPEMFICHAF), que oferecem um link "versão para
    #: impressão" — a CDCOPSBENE é formulário, não relatório. Consistente
    #: com o módulo privado, validado em produção, que também clica só este
    #: botão e passa a trabalhar sobre a janela que ele abre.
    SEL_IMPRIMIR = '[data-testtoolid="onPrintPDF"]'
    SEL_SAIR = '[data-testtoolid="onClickBtnSair"]'

    TIMEOUT_TELA = 30
    #: Os campos já vêm renderizados com a consulta; esperar 30s por eles
    #: atrasaria toda matrícula inexistente em meio minuto.
    TIMEOUT_CAMPOS = 10
    #: Medido no gate ao vivo de 16/09: a primeira impressão da sessão
    #: excedeu os 60s default de ``imprimir_via_popup`` enquanto as duas
    #: seguintes, na mesma sessão, não excederam. A causa não foi
    #: estabelecida, então o orçamento fica generoso, e a falha por timeout
    #: passa a listar o que há na pasta de download (ver ``_imprimir``).
    TIMEOUT_DOWNLOAD = 120
    DELAY_APOS_CONSULTA = 1.5
    DELAY_APOS_SAIR = 1.0

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
            motivo = (f"o botão {rotulo} ({seletor}) não apareceu em "
                      f"{self.TIMEOUT_TELA}s")
            texto_popup = texto_popup_cis(self.driver)
            if texto_popup is not None:
                motivo += f"; a tela mostrou: {texto_popup}"
            raise DadosPessoaisIndisponiveis(matricula, motivo)
        self.driver.find_element(By.CSS_SELECTOR, seletor).click()

    def _sair(self) -> None:
        try:
            if procurar_em_frames(self.driver, self.SEL_SAIR) is not None:
                self.driver.find_element(By.CSS_SELECTOR, self.SEL_SAIR).click()
                time.sleep(self.DELAY_APOS_SAIR)
        except Exception as exc:  # noqa: BLE001 — Sair é cortesia, não etapa
            _log.warning("%s: Sair falhou (ignorado): %s", self.TRANSACAO,
                         mascarar_digitos(str(exc)))

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
                         self.TRANSACAO, mascarar_digitos(str(exc)))

    def _conferir_identidade(self, matricula: str) -> None:
        """Confere a matrícula que ficou no campo de busca contra a pedida.

        A tela do pensionista NÃO devolve a matrícula junto dos dados, então
        este eco é a única conferência possível, e ela é mais fraca que a do
        módulo de servidor (que compara a matrícula impressa no PDF). A
        proteção estrutural é que cada ``consultar`` navega para a transação
        do zero, com o formulário em branco.

        O campo de busca é localizado entre os frames visíveis: por este
        ponto, ``esperar_seletor`` já deixou o driver no frame dos campos do
        formulário, que não é necessariamente o do campo de busca. Ler com
        ``find_element`` direto arriscaria degradar a conferência para
        "impossível" em TODA consulta caso os dois frames sejam diferentes.

        MEDIDO no gate ao vivo de 16/09, nas duas matrículas reais: depois da
        consulta, ``w_matr_infor_alfa`` não está em NENHUM frame visível —
        não é um caso raro, é o comportamento normal desta tela. Na prática,
        hoje, a única proteção é a estrutural (cada ``consultar`` navega para
        a transação do zero, com o formulário em branco); por isso os
        caminhos "impossível" logam em ``debug``, não em ``warning`` — uma
        condição que ocorre em toda consulta não pode gritar toda consulta.
        O caminho de eco DIVERGENTE continua levantando, sem mudança: se o
        campo por acaso vier preenchido com outra matrícula, isso ainda é
        sinal forte de erro. Uma conferência real pode voltar a existir se o
        PDF impresso carregar a matrícula — o que o gate mede à parte.
        """
        try:
            if procurar_em_frames(self.driver, self.SEL_MATRICULA) is None:
                _log.debug(
                    "%s: conferência de identidade impossível (o campo de "
                    "busca não foi encontrado em nenhum frame visível)",
                    self.TRANSACAO)
                return
            eco = self.driver.find_element(
                By.CSS_SELECTOR, self.SEL_MATRICULA).get_attribute("value")
            eco = re.sub(r"\D", "", eco or "")
        except Exception as exc:  # noqa: BLE001
            _log.debug("%s: conferência de identidade impossível (%s)",
                       self.TRANSACAO, mascarar_digitos(str(exc)))
            return
        if not eco:
            _log.debug("%s: conferência de identidade impossível (o campo "
                       "de busca ficou vazio após a consulta)",
                       self.TRANSACAO)
            return
        if eco != matricula:
            raise DadosPessoaisIndisponiveis(
                matricula, f"o campo de busca traz a matrícula "
                           f"{mascarar_matricula(eco)}, não a pedida")

    def _imprimir(self, matricula: str) -> Path:
        """Imprime a tela e devolve o PDF BRUTO, ainda em pasta_download.

        O clique em Imprimir É o disparo da impressão nesta tela (ver o
        comentário em ``SEL_IMPRIMIR``): por isso ele entra como o próprio
        ``clicar_imprimir`` de :func:`imprimir_via_popup`, em vez de um
        clique solto seguido de um segundo botão que não existe aqui.
        """
        try:
            bruto = imprimir_via_popup(
                self.driver,
                lambda: self._clicar(self.SEL_IMPRIMIR, matricula, "Imprimir"),
                self.pasta_download, timeout_download=self.TIMEOUT_DOWNLOAD)
        except DadosPessoaisIndisponiveis:
            raise
        except Exception as exc:  # noqa: BLE001 — timeout de popup/download
            motivo = ("a impressão não produziu PDF: "
                      f"{mascarar_digitos(str(exc))}")
            try:
                arquivos = list(self.pasta_download.iterdir())
                sufixos = sorted({p.suffix or "(sem extensão)"
                                  for p in arquivos})
                motivo += (f"; {len(arquivos)} arquivo(s) na pasta: "
                           f"{', '.join(sufixos)}")
            except Exception:  # noqa: BLE001 — listar a pasta é best-effort
                motivo += "; a pasta de download não pôde ser listada"
            raise DadosPessoaisIndisponiveis(matricula, motivo) from exc

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
            # A CDCOPSBENE não tem botão Consultar (medido no gate ao vivo de
            # 16/09: as duas matrículas falharam porque o módulo esperava um
            # botão que não existe nesta tela; o módulo privado, validado em
            # produção, declara o seletor onClickbtnConsulta mas nunca o
            # clica). O ENTER no campo da matrícula envia a consulta sozinho.
            campo.send_keys(Keys.ENTER)
            time.sleep(self.DELAY_APOS_CONSULTA)

            com_procuracao = atravessar_procuracao(self.driver)
            if com_procuracao:
                time.sleep(self.DELAY_APOS_CONSULTA)

            if esperar_seletor(self.driver, self.SEL_NOME,
                               timeout=self.TIMEOUT_CAMPOS) is None:
                # segunda chance: a tela de procuração pode ter renderizado
                # tarde e a primeira varredura ter passado batido por ela.
                achou = False
                if atravessar_procuracao(self.driver):
                    com_procuracao = True
                    time.sleep(self.DELAY_APOS_CONSULTA)
                    achou = esperar_seletor(
                        self.driver, self.SEL_NOME,
                        timeout=self.TIMEOUT_CAMPOS) is not None
                if not achou:
                    motivo = ("a consulta não trouxe dados (os campos "
                               "do formulário não apareceram; considere "
                               "a hipótese de procuração — com ou sem "
                               "tela intermediária detectada)")
                    texto_popup = texto_popup_cis(self.driver)
                    if texto_popup is not None:
                        motivo += f"; a tela mostrou: {texto_popup}"
                    raise DadosPessoaisIndisponiveis(matricula, motivo)

            campos = ler_campos(self.driver)
            # O formulário já foi lido, então _conferir_identidade pode
            # reposicionar o driver por outros frames sem risco de perder
            # os campos.
            self._conferir_identidade(matricula)
            if not any(campos.values()):
                # ressalva derivada de com_procuracao NESTE ponto (não
                # congelada na 1a varredura): a 2a chance acima pode tê-lo
                # virado True depois do cálculo inicial.
                ressalva = ("; a tela de procuração pode ter ficado presa"
                            if com_procuracao else "")
                motivo = ("a consulta não trouxe dados (todos os campos "
                          f"vazios{ressalva})")
                texto_popup = texto_popup_cis(self.driver)
                if texto_popup is not None:
                    motivo += f"; a tela mostrou: {texto_popup}"
                raise DadosPessoaisIndisponiveis(matricula, motivo)

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
