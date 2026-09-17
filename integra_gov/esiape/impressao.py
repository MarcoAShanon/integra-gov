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
"""

from __future__ import annotations

import base64
import logging
import time
from collections.abc import Callable
from pathlib import Path

_log = logging.getLogger(__name__)

# fetch(url) reusando cookies/SSL da sessão → base64 em fatias + content-type.
# String.fromCharCode.apply sobre o array INTEIRO estoura a pilha em arquivos
# grandes; por isso a conversão roda em fatias de 0x8000 bytes (mesma técnica
# de integra_gov.sei.download_documento, adaptada de dataURL para base64 puro
# porque aqui o conteúdo já é sabidamente binário — não há nome de arquivo a
# extrair de um Content-Disposition).
_JS_FETCH_POPUP = """
var url = arguments[0];
var callback = arguments[arguments.length - 1];
fetch(url, {credentials: 'include'})
    .then(function (r) {
        var tipo = r.headers.get('Content-Type') || '';
        if (!r.ok) {
            callback({ok: false, erro: 'HTTP ' + r.status + ' ' + r.statusText,
                      tipo: tipo});
            return null;
        }
        return r.arrayBuffer().then(function (buf) {
            var bytes = new Uint8Array(buf);
            var CHUNK = 0x8000;
            var partes = [];
            for (var i = 0; i < bytes.length; i += CHUNK) {
                partes.push(String.fromCharCode.apply(
                    null, bytes.subarray(i, i + CHUNK)));
            }
            callback({ok: true, b64: btoa(partes.join('')), tipo: tipo});
        });
    })
    .catch(function (err) {
        callback({ok: false, erro: err.toString(), tipo: ''});
    });
"""


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


def baixar_pdf_do_popup(driver, clicar_imprimir: Callable[[], None], destino: Path, *,
                        timeout_popup: float = 20, timeout_fetch: float = 60) -> Path:
    """A OUTRA mecânica de entrega do CIS: o popup RETORNA o PDF como arquivo
    na resposta HTTP, em vez de disparar um download do Chrome.

    :func:`imprimir_via_popup` serve as telas de RELATÓRIO (CDCOINDPES,
    FPEMFICHAF): o navegador imprime o HTML em PDF por *kiosk printing* e o
    arquivo aparece sozinho na pasta de download configurada no perfil. Esta
    função serve as telas em que o CIS devolve o PDF como FILE dentro do
    popup — o Chrome mostra o próprio cartão de download ("Abrir" para
    ``StartDynamicContent.pdf``), que é interface do navegador, não DOM da
    página, e não dispara arquivo nenhum sem um clique humano.

    MEDIDO no gate ao vivo de 16/09, quinta rodada, nas duas matrículas reais
    do módulo de pensionista: o popup abria (2 janelas), a pasta de download
    ficava vazia depois de 120s, e fixar a pasta via CDP
    (``Browser.setDownloadBehavior``) não mudou nada — a causa não era a
    pasta, era o cartão do Chrome esperando um clique que o Selenium não
    consegue dar. A saída foi trocar de estrada: a URL para a qual o popup
    navega DEVOLVE o PDF, então o arquivo pode ser buscado pela própria
    sessão (``fetch`` com ``credentials: 'include'``), como
    :mod:`integra_gov.sei.download_documento` já faz para documentos do SEI.

    Sequência:

    1. guarda os handles de janela ANTES do clique, clica, espera o popup
       (:func:`aguardar_popup`) — sem popup, ``RuntimeError``;
    2. troca para o popup e lê ``driver.current_url``;
    3. ``set_script_timeout(timeout_fetch)`` e um script assíncrono busca essa
       URL com ``credentials: 'include'``, convertendo o corpo para base64 em
       fatias de 0x8000 bytes (um único ``String.fromCharCode.apply`` sobre o
       array inteiro estoura a pilha);
    4. resposta não-OK ou erro no fetch → ``RuntimeError`` com o erro relatado
       e o content-type — NUNCA a URL, que carrega um id de sessão;
    5. bytes decodificados que não começam com ``%PDF`` → ``RuntimeError``
       citando os primeiros bytes (hex, no máximo 8) e o content-type — é essa
       checagem que impede uma página de erro em HTML de ser arquivada como
       documento cadastral;
    6. grava em ``destino`` (cria o pai), fecha o popup
       (:func:`fechar_popup`), volta à janela principal
       (:func:`retornar_apos_impressao`) e devolve ``destino``.

    Sem qualquer conhecimento de matrícula ou dado pessoal — isso é do
    chamador.
    """
    handle_principal = driver.current_window_handle
    handles_antes = list(driver.window_handles)
    clicar_imprimir()
    popup = aguardar_popup(driver, handles_antes, timeout=timeout_popup)
    if popup is None:
        raise RuntimeError(
            f"popup do PDF não abriu em {timeout_popup}s")
    driver.switch_to.window(popup)
    url = driver.current_url
    driver.set_script_timeout(timeout_fetch)
    resultado = driver.execute_async_script(_JS_FETCH_POPUP, url)

    if not isinstance(resultado, dict) or not resultado.get("ok"):
        erro = resultado.get("erro") if isinstance(resultado, dict) else resultado
        tipo = resultado.get("tipo", "") if isinstance(resultado, dict) else ""
        raise RuntimeError(
            f"não foi possível buscar o PDF do popup: {erro} "
            f"(content-type: {tipo!r})")

    tipo = resultado.get("tipo", "")
    conteudo = base64.b64decode(resultado.get("b64") or "")
    if not conteudo.startswith(b"%PDF"):
        prefixo = conteudo[:8].hex()
        raise RuntimeError(
            f"o conteúdo buscado não começa com %PDF (primeiros bytes: "
            f"{prefixo!r}; content-type: {tipo!r})")

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)
    fechar_popup(driver, popup)
    retornar_apos_impressao(driver, handle_principal)
    return destino
