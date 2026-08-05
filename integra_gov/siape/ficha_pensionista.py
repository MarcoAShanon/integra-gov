"""Ficha financeira anual do pensionista no SIAPE 3270 (``>FPEMPSFICF``).

Extrai a ficha de UMA pensionista para uma faixa de anos: um PDF por ano com
dados, salvo em ``pasta_saida``. Ano sem dados (código ``(0034)`` do SIAPE)
não é erro — entra em ``anos_sem_dados`` no resultado.

Requer terminal já conectado/autenticado (:class:`ControleTerminal3270`) e a
habilitação correta já ativa (:class:`TrocaHabilitacao`). A impressão usa a
impressora de PDF configurada no ambiente (ver ``docs/uso-basico.md``).

Restrições herdadas do 3270: sessão Windows GUI interativa; clipboard e foco
são globais — execução estritamente serial.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from ._dependencias import Desktop, exigir_pywinauto
from ._menu import garantir_menu_principal
from .controle import ControleTerminal3270
from .exceptions import (
    ExtracaoFichaInterrompida,
    FichaIndisponivel,
    InstituidorObrigatorio,
    TransacaoError,
)

_log = logging.getLogger(__name__)


@dataclass
class ResultadoFichaAnual:
    """Resultado da extração de uma pensionista em uma faixa de anos."""

    pdfs: list[Path] = field(default_factory=list)
    anos_com_dados: list[int] = field(default_factory=list)
    anos_sem_dados: list[int] = field(default_factory=list)
    duracao_s: float = 0.0


class FichaAnualPensionista:
    """Extrai a ficha financeira anual de uma pensionista (``>FPEMPSFICF``).

    Args:
        controle: :class:`ControleTerminal3270` conectado.
        pasta_saida: pasta onde os PDFs anuais são salvos (criada se preciso).
        impressora: nome da impressora de PDF esperada no ambiente — usada em
            mensagens de erro quando a janela de salvar não aparece (o módulo
            NÃO configura a impressora).
    """

    COMANDO_FICHA = ">FPEMPSFICF"
    TEXTO_SELECAO_INSTITUIDOR = "SELECIONE O INSTITUIDOR DO PENSIONISTA"
    CODIGO_SEM_DADOS = "(0034)"
    TEXTO_SEM_DADOS = "NAO EXISTEM DADOS"
    TITULO_JANELA_SALVAR = "Salvar Saída de Impressão como"
    # Qualquer código (0NNN) fora do fluxo do ano indica problema no acesso
    # (matrícula inexistente, sem habilitação, etc.).
    PADRAO_CODIGO_ERRO = re.compile(r"\(0\d{3}\)")

    # Geometria da tela de seleção de instituidores (validada em produção).
    LINHA_INICIO_LISTA_INSTITUIDORES = 7
    LINHA_FIM_LISTA_INSTITUIDORES = 18

    # Esperas (valores otimizados validados; máquinas lentas podem folgar).
    DELAY_PADRAO = 0.5
    DELAY_CURTO = 0.15
    ESPERA_MSG_IMPRESSAO = 1.0   # após S+ENTER, mensagem de impressão
    ESPERA_POS_CONFIRMACAO = 2.2  # janela de salvar OU (0034) surgirem
    TIMEOUT_JANELA_SALVAR = 15.0
    TIMEOUT_ARQUIVO = 10.0

    def __init__(
        self,
        controle: ControleTerminal3270,
        pasta_saida: Path,
        impressora: str = "Microsoft Print to PDF",
    ):
        self.controle = controle
        self.pasta_saida = Path(pasta_saida)
        self.pasta_saida.mkdir(parents=True, exist_ok=True)
        self.impressora = impressora

    def extrair(
        self,
        matricula_pensionista: str,
        ano_inicial: int,
        ano_final: int,
        matricula_instituidor: str | None = None,
    ) -> ResultadoFichaAnual:
        """Extrai a ficha anual da pensionista na faixa ``[ano_inicial, ano_final]``.

        Raises:
            ValueError: parâmetros inválidos.
            InstituidorObrigatorio: pensão múltipla sem ``matricula_instituidor``.
            FichaIndisponivel: matrícula inexistente/sem acesso.
            ExtracaoFichaInterrompida: falha no meio da faixa (carrega
                ``anos_processados`` e ``causa``).
        """
        matricula = str(matricula_pensionista).strip()
        if not matricula:
            raise ValueError("matricula_pensionista é obrigatória")
        if int(ano_inicial) > int(ano_final):
            raise ValueError(
                f"faixa invertida: ano_inicial={ano_inicial} > ano_final={ano_final}"
            )
        inicio = time.monotonic()
        resultado = ResultadoFichaAnual()
        self._posicionar(matricula, matricula_instituidor)
        try:
            for ano in range(int(ano_inicial), int(ano_final) + 1):
                caminho = self._processar_ano(matricula, ano)
                if caminho is None:
                    resultado.anos_sem_dados.append(ano)
                else:
                    resultado.anos_com_dados.append(ano)
                    resultado.pdfs.append(caminho)
        except Exception as exc:
            anos = resultado.anos_com_dados + resultado.anos_sem_dados
            raise ExtracaoFichaInterrompida(sorted(anos), exc) from exc
        finally:
            self._finalizar()
        resultado.duracao_s = time.monotonic() - inicio
        _log.info(
            "Matrícula %s: %d anos com dados, %d sem dados, %.1fs",
            matricula, len(resultado.anos_com_dados),
            len(resultado.anos_sem_dados), resultado.duracao_s,
        )
        return resultado

    def _finalizar(self) -> None:
        """F12: devolve o terminal ao prompt de matrícula (o chamador pode
        emendar a próxima pensionista). Falha aqui não mascara o resultado."""
        try:
            self.controle.enviar_teclas("{F12}")
            time.sleep(self.DELAY_PADRAO)
        except Exception:
            _log.warning("F12 de finalização falhou; terminal pode exigir menu")

    # ----- posicionamento -----

    def _posicionar(self, matricula: str, matricula_instituidor: str | None) -> None:
        """Menu → ``>FPEMPSFICF`` → matrícula; trata a tela de seleção de
        instituidores; deixa o terminal no prompt de ano (EXERCÍCIO)."""
        garantir_menu_principal(self.controle)
        self.controle.enviar_teclas(self.COMANDO_FICHA)
        self.controle.enviar_teclas("{ENTER}")
        time.sleep(self.DELAY_PADRAO)

        self.controle.enviar_teclas(matricula)
        self.controle.enviar_teclas("{ENTER}")
        time.sleep(self.DELAY_PADRAO)

        tela = self._normalizar(self.controle.copiar_tela() or "")
        if self._tela_de_selecao(tela):
            self._selecionar_instituidor(tela, matricula_instituidor)
            return
        codigo = self.PADRAO_CODIGO_ERRO.search(tela)
        if codigo and codigo.group(0) != self.CODIGO_SEM_DADOS:
            linha_erro = self._linha_do_codigo(tela, codigo.start())
            raise FichaIndisponivel(
                f"matrícula {matricula} indisponível na habilitação ativa: "
                f"{linha_erro}"
            )
        _log.info("Posicionado na ficha da matrícula %s", matricula)

    def _tela_de_selecao(self, tela: str) -> bool:
        return self.TEXTO_SELECAO_INSTITUIDOR in tela

    def _selecionar_instituidor(
        self, tela: str, matricula_instituidor: str | None
    ) -> None:
        """Seleciona a linha do instituidor na tela de pensão múltipla.

        Comparação NUMÉRICA (tolerante a zeros à esquerda): a tela mostra
        ``146605`` enquanto planilhas costumam trazer ``0146605``.
        """
        opcoes = self._matriculas_da_selecao(tela)
        if matricula_instituidor is None:
            raise InstituidorObrigatorio(opcoes)
        alvo = int(str(matricula_instituidor).lstrip("0") or "0")
        posicao = next(
            (i for i, m in enumerate(opcoes) if int(m.lstrip("0") or "0") == alvo),
            None,
        )
        if posicao is None:
            raise InstituidorObrigatorio(opcoes)
        for _ in range(posicao):
            self.controle.enviar_teclas("{TAB}")
            time.sleep(self.DELAY_CURTO)
        self.controle.enviar_teclas("X")
        self.controle.enviar_teclas("{ENTER}")
        time.sleep(self.DELAY_PADRAO)
        _log.info(
            "Instituidor %s selecionado (opção %d de %d)",
            matricula_instituidor, posicao + 1, len(opcoes),
        )

    def _matriculas_da_selecao(self, tela: str) -> list[str]:
        """Matrículas das linhas de opção (com parênteses), na ordem da tela."""
        largura = ControleTerminal3270.CARACTERES_POR_LINHA
        matriculas: list[str] = []
        for n_linha in range(
            self.LINHA_INICIO_LISTA_INSTITUIDORES,
            self.LINHA_FIM_LISTA_INSTITUIDORES + 1,
        ):
            linha = tela[(n_linha - 1) * largura : n_linha * largura]
            if "(" not in linha or ")" not in linha:
                continue
            numeros = re.findall(r"\d{6,9}", linha)
            if numeros:
                matriculas.append(numeros[0])
        return matriculas

    # ----- processamento de um ano -----

    def _processar_ano(self, matricula: str, ano: int) -> Path | None:
        """Emite e salva a ficha de um ano. ``None`` = ano sem dados (0034).

        Sequência validada em produção: ano → X → ENTER (tela "CONFIRMA
        EMISSÃO? S/N") → S + ENTER → mensagem de impressão (ENTER) → então a
        janela de salvar surge (há dados) OU o (0034) aparece no terminal.
        A decisão é pelo que EXISTE, não por timeout cego.
        """
        self.controle.enviar_teclas(str(ano))
        time.sleep(self.DELAY_CURTO)
        self.controle.enviar_teclas("X")
        time.sleep(self.DELAY_CURTO)
        self.controle.enviar_teclas("{ENTER}")
        time.sleep(self.DELAY_PADRAO)
        self.controle.enviar_teclas("S")
        self.controle.enviar_teclas("{ENTER}")
        time.sleep(self.ESPERA_MSG_IMPRESSAO)
        self.controle.enviar_teclas("{ENTER}")  # fecha a mensagem de impressão
        time.sleep(self.ESPERA_POS_CONFIRMACAO)

        leu_tela = False
        limite = time.monotonic() + self.TIMEOUT_JANELA_SALVAR
        while True:
            if self._janela_salvar_existe():
                break
            sem_dados = self._sem_dados_no_terminal()
            leu_tela = True
            if sem_dados:
                _log.info("Ano %d sem dados (0034)", ano)
                self._recuperar_cursor_apos_sem_dados()
                return None
            if time.monotonic() >= limite:
                raise TransacaoError(
                    f"ano {ano}: nem a janela '{self.TITULO_JANELA_SALVAR}' nem "
                    f"o {self.CODIGO_SEM_DADOS} apareceram em "
                    f"{self.TIMEOUT_JANELA_SALVAR}s — confira se a impressora "
                    f"ativa do SIAPE é '{self.impressora}'"
                )
            time.sleep(self.DELAY_CURTO)

        caminho = self.pasta_saida / f"ficha_{matricula}_{ano}.pdf"
        self._salvar_via_dialogo(caminho)
        self._confirmar_arquivo(caminho)
        if leu_tela:
            # _sem_dados_no_terminal() rodou pelo menos uma vez antes da janela
            # de salvar aparecer (copiar_tela desalinha o cursor) — recupera
            # antes de seguir para o próximo ano.
            self._recuperar_cursor_apos_sem_dados()
        _log.info("Ano %d salvo em %s", ano, caminho)
        return caminho

    def _sem_dados_no_terminal(self) -> bool:
        """True se o terminal mostra o código ``(0034)`` (ano sem dados)."""
        tela = self._normalizar(self.controle.copiar_tela() or "")
        return self.CODIGO_SEM_DADOS in tela or self.TEXTO_SEM_DADOS in tela

    def _recuperar_cursor_apos_sem_dados(self) -> None:
        """Qualquer leitura de tela (``copiar_tela``, via
        ``_sem_dados_no_terminal``) desalinha o cursor; F2 o devolve ao campo
        EXERCÍCIO — sem isso os dígitos do próximo ano caem em campos errados."""
        self.controle.enviar_teclas("{F2}")
        time.sleep(self.DELAY_PADRAO)

    def _confirmar_arquivo(self, caminho: Path) -> None:
        """Só declara o ano salvo quando o arquivo EXISTE com tamanho > 0."""
        limite = time.monotonic() + self.TIMEOUT_ARQUIVO
        while time.monotonic() < limite:
            if caminho.exists() and caminho.stat().st_size > 0:
                return
            time.sleep(self.DELAY_CURTO)
        raise TransacaoError(
            f"o PDF não se materializou em {caminho} "
            f"(timeout {self.TIMEOUT_ARQUIVO}s)"
        )

    # ----- pontos de contato com o pywinauto (mockados nos testes) -----

    def _janela_salvar_existe(self) -> bool:
        """True se a janela nativa de salvar impressão está aberta."""
        exigir_pywinauto()
        try:
            return Desktop(backend="win32").window(
                title=self.TITULO_JANELA_SALVAR
            ).exists()
        except Exception:  # janela sumiu entre o find e o exists
            return False

    def _salvar_via_dialogo(self, caminho: Path) -> None:
        """Preenche a janela de salvar de forma ATÔMICA (``set_edit_text``,
        imune a interferência de clipboard) e confirma."""
        exigir_pywinauto()
        dlg = Desktop(backend="win32").window(title=self.TITULO_JANELA_SALVAR)
        dlg.wait("ready", timeout=self.TIMEOUT_JANELA_SALVAR)
        escreveu = False
        for classe in ("Edit", "ComboBox"):
            try:
                dlg.child_window(class_name=classe, found_index=0).set_edit_text(
                    str(caminho)
                )
                escreveu = True
                break
            except Exception:
                continue
        if not escreveu:  # fallback: digitação direta
            dlg.type_keys(str(caminho), with_spaces=True)
        time.sleep(self.DELAY_CURTO)
        try:
            dlg.child_window(title_re="Salvar.*", class_name="Button").click_input()
        except Exception:
            dlg.type_keys("{ENTER}")

    # ----- utilitários de tela -----

    @staticmethod
    def _normalizar(tela: str) -> str:
        return tela.replace("\xa0", " ")

    def _linha_do_codigo(self, tela: str, posicao: int) -> str:
        largura = ControleTerminal3270.CARACTERES_POR_LINHA
        inicio = (posicao // largura) * largura
        return tela[inicio : inicio + largura].strip()
