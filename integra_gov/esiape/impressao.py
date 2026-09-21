"""Impressão via popup no e-SIAPE: a sequência estabilizada em produção.

O CIS imprime abrindo um popup que dispara um download (com o Chrome
configurado para "Save as PDF", ver ``docs/uso-basico.md``). A sequência
que funciona, e que já rendeu quatro defeitos só no gate ao vivo até ficar
assim, é:

1. limpar PDFs órfãos da pasta de download (o "mais recente" confundiria);
2. guardar os handles de janela ANTES do clique;
3. clicar em imprimir;
4. esperar o popup (pode não abrir; o download dispara mesmo assim);
5. esperar UM PDF aparecer e ficar estável (tamanho constante em 2 leituras);
6. fechar o popup por handle Selenium, com JS como fallback;
7. voltar à janela principal com ``refresh`` (sem ele a página fica em
   carregamento eterno) e ``default_content``.

Nasceu como cinco métodos privados de :mod:`ficha_anual`; virou módulo para
que a extração de dados cadastrais (e qualquer outra tela que imprime) não
duplique um trecho tão sensível. :func:`imprimir_via_popup` é a composição;
as funções soltas ficam para quem precisa intercalar algo (a ficha anual
confere a camada de texto ANTES de fechar o popup).

Uma segunda mecânica vive aqui também: :func:`imprimir_pagina_para_pdf`, para
telas cujo próprio arquivo a automação não consegue capturar (medido no
pensionista/CDCOPSBENE) — em vez de perseguir um download, pede ao Chrome
que imprima a página atual via DevTools e recebe os bytes direto.
"""

from __future__ import annotations

import base64
import logging
import time
from collections.abc import Callable
from pathlib import Path

_log = logging.getLogger(__name__)


def aguardar_popup(driver, handles_antes: list[str], *, timeout: float = 20,
                   intervalo: float = 0.3) -> str | None:
    """Handle da janela nova (``None`` se não abriu — o download pode
    disparar mesmo assim; quem decide é o PDF no disco)."""
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        novos = [h for h in driver.window_handles if h not in handles_antes]
        if novos:
            return novos[0]
        time.sleep(intervalo)
    _log.warning("Popup de impressão não detectado em %.0fs", timeout)
    return None


def aguardar_pdf_estavel(pasta_download: Path, *, timeout: float = 60,
                         intervalo: float = 0.3) -> Path:
    """Espera UM PDF aparecer em ``pasta_download`` e ficar estável (tamanho
    constante em 2 leituras). Erro honesto no timeout."""
    pasta_download = Path(pasta_download)
    limite = time.monotonic() + timeout
    tamanho_anterior: dict[Path, int] = {}
    while time.monotonic() < limite:
        pdfs = sorted(pasta_download.glob("*.pdf"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        if pdfs:
            atual = pdfs[0]
            tamanho = atual.stat().st_size
            if tamanho > 0 and tamanho_anterior.get(atual) == tamanho:
                return atual
            tamanho_anterior[atual] = tamanho
        time.sleep(intervalo)
    raise TimeoutError(
        f"o PDF não apareceu em {pasta_download} em {timeout}s — a pasta de "
        f"download do driver coincide com pasta_download?")


def fechar_popup(driver, popup_handle: str, *, intervalo: float = 0.3) -> None:
    """Fecha o popup por handle Selenium (retry); JS como fallback."""
    for _tentativa in range(2):
        try:
            if popup_handle not in driver.window_handles:
                return
            driver.switch_to.window(popup_handle)
            driver.close()
            time.sleep(intervalo)
            if popup_handle not in driver.window_handles:
                return
        except Exception:
            pass
    try:  # fallback JS
        if popup_handle in driver.window_handles:
            driver.switch_to.window(popup_handle)
            driver.execute_script("window.close();")
    except Exception:
        pass
    if popup_handle in driver.window_handles:
        _log.warning("Popup de impressão resistiu — janela órfã será "
                     "varrida por fechar_janelas_extras")


def retornar_apos_impressao(driver, handle_principal: str, *, delay: float = 1.0) -> None:
    """Volta à janela principal, refresh e contexto raiz (a página fica em
    carregamento eterno sem o refresh — comportamento real do CIS)."""
    try:
        if handle_principal in driver.window_handles:
            driver.switch_to.window(handle_principal)
        elif driver.window_handles:
            driver.switch_to.window(driver.window_handles[0])
        driver.refresh()
        driver.switch_to.default_content()
        time.sleep(delay)
    except Exception as exc:
        _log.warning("Retorno pós-impressão com falha (%s)", exc)


def limpar_downloads_orfaos(pasta_download: Path) -> None:
    """Remove PDFs de tentativas anteriores da pasta de download.

    Remove TODOS os ``*.pdf`` que já estiverem em ``pasta_download`` — sem
    filtro de idade ou origem. Por isso ``pasta_download`` precisa ser uma
    pasta de download DEDICADA a esta automação (ex.: ``_download_esiape``),
    nunca uma pasta compartilhada como ``Downloads`` do usuário — apontar
    para lá apaga, silenciosamente (log em nível debug), todo PDF que
    estiver ali."""
    for pdf in Path(pasta_download).glob("*.pdf"):
        try:
            pdf.unlink()
            _log.debug("Órfão removido: %s", pdf.name)
        except OSError as exc:
            _log.warning(
                "Órfão %s não pôde ser removido (%s) — a impressão seguinte "
                "pode devolvê-lo no lugar do PDF novo", pdf.name, exc)


def imprimir_via_popup(driver, clicar_imprimir: Callable[[], None],
                       pasta_download: Path, *, timeout_popup: float = 20,
                       timeout_download: float = 60, delay: float = 1.0) -> Path:
    """A sequência inteira. Devolve o PDF BRUTO na pasta de download; quem
    chama renomeia (e, se quiser conferir o conteúdo antes de fechar o popup,
    use as funções soltas, como ``ficha_anual`` faz).

    Começa chamando :func:`limpar_downloads_orfaos`, que apaga TODOS os
    ``*.pdf`` de ``pasta_download`` — use uma pasta dedicada à automação,
    nunca uma pasta compartilhada como ``Downloads``.

    NÃO varre janelas de impressão órfãs entre chamadas — entre impressões,
    chame ``fechar_janelas_extras(driver, handle_principal)`` de
    :mod:`integra_gov.esiape.navegacao`, como ``ficha_anual`` faz."""
    limpar_downloads_orfaos(pasta_download)
    handle_principal = driver.current_window_handle
    handles_antes = list(driver.window_handles)
    clicar_imprimir()
    popup = aguardar_popup(driver, handles_antes, timeout=timeout_popup)
    pdf = aguardar_pdf_estavel(pasta_download, timeout=timeout_download)
    if popup is not None:
        fechar_popup(driver, popup)
    retornar_apos_impressao(driver, handle_principal, delay=delay)
    return pdf


def imprimir_pagina_para_pdf(driver, destino: Path, *,
                             paisagem: bool = False) -> Path:
    """Imprime a página ATUAL via DevTools e devolve os bytes direto.

    Ao lado de :func:`imprimir_via_popup` (que captura o PDF que uma tela de
    RELATÓRIO produz via kiosk printing, pousando na pasta de download), esta
    função pede ao próprio navegador que imprima a página corrente, pelo
    comando do DevTools ``Page.printToPDF``, e recebe os bytes de volta sem
    tocar a máquina de downloads nem depender de popup nenhum.

    Use-a quando a tela entrega o próprio arquivo de um jeito que a automação
    não consegue capturar — o caso medido é a CDCOPSBENE, onde cinco rotas de
    captura foram descartadas ao vivo: esperar o download na pasta configurada (pasta vazia
    em 120s, com o popup aberto); forçar a pasta via
    ``Browser.setDownloadBehavior`` do CDP (o comando teve sucesso e não
    mudou nada); buscar a URL do popup pela sessão (devolve a casca do CIS em
    HTML, ~2646 bytes, nunca o PDF); vigiar toda janela e todo frame por dois
    minutos (nenhum jamais carrega uma URL de PDF, o que é consistente,
    porque um download não navega); e remover
    ``plugins.always_open_pdf_externally`` do perfil, a hipótese mais forte
    (o arquivo já havia sido encontrado assim num perfil sem essa preferência)
    — o gate falhou de novo, identicamente.

    O resultado é a impressão da TELA que o operador vê, não o relatório
    próprio do CIS — uma diferença real para quem anexa o documento a um
    processo, e por isso não pode ficar implícita em lugar nenhum que usa
    esta função.

    LIMITAÇÃO MEDIDA (gate do pensionista, 17/09): a impressão só cobre a
    região VISÍVEL da tela. Uma tela cujo conteúdo relevante rola dentro de
    um frame sai incompleta — a CDCOPSBENE mediu isso ao vivo (uma página,
    429 caracteres, com endereço e telefone mas sem matrícula, nome, CPF nem
    nascimento) e por isso o módulo `dados_pensionista` não usa esta função.

    Papel A4 em polegadas (``paperWidth`` 8.27, ``paperHeight`` 11.69),
    dimensões trocadas com ``paisagem=True``; margens de 0.4 polegada nos
    quatro lados; ``printBackground=True``.

    Raises:
        RuntimeError: o driver não tem ``execute_cdp_cmd`` (não suporta
            DevTools), o comando falha (a causa original fica em
            ``__cause__``), ou o conteúdo devolvido não começa em ``%PDF``
            (o motivo cita o prefixo em hexadecimal, nunca o conteúdo).
    """
    destino = Path(destino)
    largura, altura = (11.69, 8.27) if paisagem else (8.27, 11.69)
    params = {
        "printBackground": True,
        "paperWidth": largura,
        "paperHeight": altura,
        "marginTop": 0.4,
        "marginBottom": 0.4,
        "marginLeft": 0.4,
        "marginRight": 0.4,
    }
    executar = getattr(driver, "execute_cdp_cmd", None)
    if executar is None:
        raise RuntimeError(
            "impressão via DevTools indisponível: o driver não tem "
            "execute_cdp_cmd")
    try:
        resultado = executar("Page.printToPDF", params)
    except Exception as exc:
        raise RuntimeError(
            "impressão via DevTools indisponível: Page.printToPDF "
            "falhou") from exc
    bruto = base64.b64decode(resultado["data"])
    if not bruto.startswith(b"%PDF"):
        prefixo = bruto[:8].hex()
        raise RuntimeError(
            f"o conteúdo devolvido pela impressão via DevTools não é um "
            f"PDF (começa em {prefixo})")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(bruto)
    return destino
