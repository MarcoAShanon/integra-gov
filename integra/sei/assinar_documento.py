"""Assinatura eletrônica de um documento no SEI (ato do próprio servidor).

Aciona o ícone **"Assinar Documento"**, preenche a **senha** no modal de
assinatura e confirma. A senha é a manifestação de vontade do servidor: ela é
**parâmetro** (vem de quem chama, via ``getpass``/cofre — nunca embutida) e o
módulo **nunca a registra em log** nem a persiste além da execução. É o mesmo
princípio já adotado no SIAPE ("credencial nunca digitada pela lib — você
autentica"); aqui é você assinando **os seus próprios** documentos.

⚠️ **Governança (responsabilidade de quem usa):** assinar em lote significa
assinar **sem revisar** cada documento individualmente. Garantir a conferência
antes da assinatura é da aplicação que monta o fluxo — a biblioteca fornece o
mecanismo, não o controle editorial.

Confiabilidade: um assinador **não pode mentir**. Este módulo só retorna com
sucesso quando o modal de assinatura **fecha sem erro**; senha recusada (alerta
ou mensagem no modal) e modal que não fecha **levantam** :class:`AssinaturaError`
— nunca reporta "assinado" por suposição.
"""

from __future__ import annotations

import logging
import time

from selenium.common.exceptions import (
    NoAlertPresentException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .barra_icones import clicar_icone_barra
from .exceptions import AssinaturaError, SeiNavegacaoError

_log = logging.getLogger(__name__)


class AssinarDocumento:
    """Assina eletronicamente o documento selecionado na árvore do SEI.

    Opera sobre o documento **atualmente selecionado** (ex.: o recém-criado por
    ``IncluirDocumentoInterno``/``EditarConteudo``).

    Args:
        driver: WebDriver com o SEI autenticado e o documento selecionado na
            árvore do processo.
        senha: senha do SEI do **próprio** servidor que assina. Obrigatória;
            usada apenas para preencher o modal — **nunca** é registrada em log
            nem persistida.
        timeout: espera máxima por elemento/modal, em segundos.

    Raises:
        ValueError: se ``senha`` faltar.
    """

    ICONE = "Assinar Documento"
    ID_SENHA = "pwdSenha"
    ID_BOTAO = "btnAssinar"
    # O diálogo de assinatura abre num modal cujo iframe carrega uma URL de
    # "documento_assinar"; é assim que o localizamos entre os iframes do topo.
    MARCA_SRC_MODAL = "documento_assinar"
    XPATH_FECHAR = "//img[@title='Fechar janela (ESC)']"
    # Palavras que sinalizam senha/assinatura recusada dentro do modal.
    KEYWORDS_ERRO = ("inválid", "invalid", "incorret", "erro ao assinar")
    # Marcadores que o SEI insere num documento REALMENTE assinado (o texto
    # estático de modelo — "Documento assinado eletronicamente" — não os tem):
    # a confirmação autoritativa é o documento passar a exibi-los.
    MARCADORES_ASSINADO = (
        "assinado eletronicamente por",
        "código crc",
        "código verificador",
    )
    MAX_PROFUNDIDADE_FRAMES = 4

    INTERVALO = 0.5

    def __init__(self, driver, senha: str, *, timeout: float = 10):
        if not senha:
            raise ValueError("senha é obrigatória para assinar")
        self.driver = driver
        self._senha = senha  # nunca logar/persistir
        self.timeout = timeout

    def assinar(self) -> None:
        """Executa o fluxo de assinatura: ícone → senha → assinar → confirmar.

        Returns:
            ``None`` — o sucesso é a ausência de exceção (confirmado pelo
            fechamento do modal sem erro).

        Raises:
            AssinaturaError: se o modal não abrir, a senha for recusada, ou a
                assinatura não puder ser confirmada.
        """
        try:
            clicar_icone_barra(self.driver, self.ICONE, timeout=self.timeout)
        except SeiNavegacaoError as exc:
            raise AssinaturaError(str(exc)) from exc

        self.driver.switch_to.default_content()
        self._entrar_no_modal()
        self._preencher_senha()
        self._clicar_assinar()
        self._confirmar()
        _log.info("Documento assinado")

    # ----- passos -----

    def _entrar_no_modal(self) -> None:
        try:
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: self._iframe_modal(d) is not False
            )
        except TimeoutException as exc:
            raise AssinaturaError(
                "o modal de assinatura não abriu após 'Assinar Documento'"
            ) from exc
        self.driver.switch_to.frame(self._iframe_modal(self.driver))
        try:
            WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.ID, self.ID_SENHA))
            )
        except TimeoutException as exc:
            self.driver.switch_to.default_content()
            raise AssinaturaError(
                "campo de senha do modal de assinatura não carregou"
            ) from exc

    def _preencher_senha(self) -> None:
        campo = self.driver.find_element(By.ID, self.ID_SENHA)
        campo.click()
        campo.clear()
        campo.send_keys(self._senha)  # valor nunca registrado em log
        _log.info("Senha de assinatura preenchida")

    def _clicar_assinar(self) -> None:
        try:
            botao = WebDriverWait(self.driver, self.timeout).until(
                EC.element_to_be_clickable((By.ID, self.ID_BOTAO))
            )
        except TimeoutException as exc:
            self.driver.switch_to.default_content()
            raise AssinaturaError(
                "botão Assinar não encontrado no modal de assinatura"
            ) from exc
        botao.click()

    def _confirmar(self) -> None:
        """Confirma a assinatura sem falso positivo.

        Volta ao topo e observa o desfecho: **alerta JS** ou **mensagem de erro
        no modal** → senha recusada (levanta); **modal fecha** → assinado. Se o
        modal permanecer aberto (alguns SEI exigem fechar), tenta fechá-lo e
        reavalia. Esgotado o tempo sem fechar, levanta — nunca assume sucesso.
        """
        self.driver.switch_to.default_content()
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            # Recusa (senha inválida) vem como alerta JS ou mensagem no modal.
            alerta = self._texto_alerta_se_houver()
            if alerta is not None:
                raise AssinaturaError(f"assinatura recusada pelo SEI: {alerta}")
            if self._erro_no_modal():
                raise AssinaturaError(
                    "assinatura recusada pelo SEI (senha inválida?)"
                )
            # Sucesso autoritativo: o documento passou a exibir a assinatura.
            if self._documento_assinado():
                self._tentar_fechar_modal()  # limpa a UI se o modal permaneceu
                self.driver.switch_to.default_content()
                return
            self._tentar_fechar_modal()
            time.sleep(self.INTERVALO)
        diagnostico = self._diagnostico()
        _log.warning("Estado do modal ao falhar a confirmação: %s", diagnostico)
        raise AssinaturaError(
            "assinatura não confirmada — o modal não fechou (a senha pode ter "
            "sido recusada); verifique o documento na tela. Diagnóstico: "
            + diagnostico
        )

    def _diagnostico(self) -> str:
        """Descreve o estado do modal/iframes (best-effort) para diagnosticar por
        que a confirmação não fechou. Nunca lança; volta ao ``default_content``."""
        partes: list[str] = []
        try:
            self.driver.switch_to.default_content()
            for i, ifr in enumerate(self.driver.find_elements(By.TAG_NAME, "iframe")):
                try:
                    src = (ifr.get_attribute("src") or "")[-70:]
                    partes.append(f"iframe[{i}] vis={ifr.is_displayed()} …{src}")
                except WebDriverException:
                    partes.append(f"iframe[{i}] <ilegível>")
        except WebDriverException:
            pass
        iframe = self._iframe_modal_qualquer()
        if iframe is not False:
            try:
                self.driver.switch_to.frame(iframe)
                titulos = [
                    t
                    for img in self.driver.find_elements(By.TAG_NAME, "img")
                    if (t := (img.get_attribute("title") or "").strip())
                ]
                botoes = [
                    b
                    for el in self.driver.find_elements(
                        By.CSS_SELECTOR, "input[type=button], input[type=submit], button"
                    )
                    if (b := (el.get_attribute("value") or el.text or "").strip())
                ]
                partes.append("modal.img_titles=" + repr(titulos[:12]))
                partes.append("modal.buttons=" + repr(botoes[:12]))
            except WebDriverException:
                pass
            finally:
                self.driver.switch_to.default_content()
        try:
            partes.append(f"doc_assinado={self._documento_assinado()}")
        except WebDriverException:
            partes.append("doc_assinado=<n/d>")
        return " | ".join(partes) or "<sem iframes>"

    def _iframe_modal_qualquer(self):
        """Como :meth:`_iframe_modal`, mas **sem** exigir visibilidade — para o
        diagnóstico enxergar o modal mesmo que esteja oculto de forma atípica."""
        for ifr in self.driver.find_elements(By.TAG_NAME, "iframe"):
            try:
                if self.MARCA_SRC_MODAL in (ifr.get_attribute("src") or ""):
                    return ifr
            except (StaleElementReferenceException, WebDriverException):
                continue
        return False

    # ----- auxiliares -----

    def _documento_assinado(self) -> bool:
        """Confirma pela verdade: o conteúdo do documento passou a exibir os
        marcadores de assinatura do SEI. Varre os frames (o conteúdo mora num
        iframe aninhado); volta ao ``default_content``."""
        self.driver.switch_to.default_content()
        achou = self._varrer_frames(0)
        self.driver.switch_to.default_content()
        return achou

    def _varrer_frames(self, profundidade: int) -> bool:
        try:
            texto = (self.driver.find_element(By.TAG_NAME, "body").text or "").lower()
        except WebDriverException:
            texto = ""
        if any(m in texto for m in self.MARCADORES_ASSINADO):
            return True
        if profundidade >= self.MAX_PROFUNDIDADE_FRAMES:
            return False
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        except WebDriverException:
            return False
        for ifr in iframes:
            try:
                self.driver.switch_to.frame(ifr)
            except WebDriverException:
                continue
            achou = self._varrer_frames(profundidade + 1)
            try:
                self.driver.switch_to.parent_frame()
            except WebDriverException:
                # Não conseguiu subir; reseta e encerra a varredura.
                self.driver.switch_to.default_content()
                return achou
            if achou:
                return True
        return False

    def _iframe_modal(self, driver):
        """Devolve o iframe **visível** do modal de assinatura (por ``src``) ou
        ``False``. Assume o driver em ``default_content``.

        A visibilidade é essencial: ao assinar, o SEI **oculta** o modal
        (``display:none``) sem removê-lo do DOM. Checar só a presença acusaria o
        modal como aberto para sempre (falso negativo na confirmação) — por isso
        exigimos ``is_displayed()``.
        """
        for ifr in driver.find_elements(By.TAG_NAME, "iframe"):
            try:
                src = ifr.get_attribute("src") or ""
                if self.MARCA_SRC_MODAL in src and ifr.is_displayed():
                    return ifr
            except (StaleElementReferenceException, WebDriverException):
                continue
        return False

    def _texto_alerta_se_houver(self) -> str | None:
        try:
            alerta = self.driver.switch_to.alert
        except NoAlertPresentException:
            return None
        texto = (alerta.text or "").strip()
        alerta.accept()
        return texto

    def _erro_no_modal(self) -> bool:
        """Procura mensagem de erro (senha inválida) dentro do modal. Sempre
        retorna ao ``default_content``."""
        iframe = self._iframe_modal(self.driver)
        if iframe is False:
            return False
        try:
            self.driver.switch_to.frame(iframe)
            corpo = self.driver.find_element(By.TAG_NAME, "body").text.lower()
        except WebDriverException:
            return False
        finally:
            self.driver.switch_to.default_content()
        return any(kw in corpo for kw in self.KEYWORDS_ERRO)

    def _tentar_fechar_modal(self) -> None:
        """Fecha o modal se houver um botão de fechar (alguns SEI mantêm o modal
        aberto após assinar). Procura no topo e **dentro** do iframe. Tolerante:
        ausência não é erro."""
        if self._clicar_fechar(self.driver):
            return
        iframe = self._iframe_modal(self.driver)
        if iframe is False:
            return
        try:
            self.driver.switch_to.frame(iframe)
            self._clicar_fechar(self.driver)
        except WebDriverException:
            pass
        finally:
            self.driver.switch_to.default_content()

    def _clicar_fechar(self, ctx) -> bool:
        for elem in ctx.find_elements(By.XPATH, self.XPATH_FECHAR):
            try:
                if elem.is_displayed():
                    elem.click()
                    return True
            except WebDriverException:
                continue
        return False
