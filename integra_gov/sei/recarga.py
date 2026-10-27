"""Troca de página dentro de um frame do SEI (componente compartilhado).

Vários cliques do SEI trocam a página de um frame: o nó da árvore recarrega a
visualização, o tipo "Externo" abre o formulário, a série reenvia o formulário
(``trocarSerie()`` → ``submit()``). Conferido ao vivo no SEI 5.0.4 (Chrome 156,
27/10/2026), duas armadilhas:

  - quando a página nova chega durante um comando, o ChromeDriver perde o frame
    e passa a responder pelo **documento de cima** — buscas no formulário falham
    e um elemento da página velha nem sempre fica "stale";
  - até a página nova chegar, a velha continua na tela e aceita cliques (que se
    perdem).

Por isso a troca é reconhecida por uma **marca** posta na página velha (a nova
não a tem) e o driver **reentra no frame** a cada consulta, pelo caminho de
nomes de frames anotado antes do clique.
"""

from __future__ import annotations

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait

# Nomes dos frames, do topo até o frame atual.
JS_CAMINHO_FRAMES = (
    "var nomes = [], w = window;"
    " while (w.frameElement) { nomes.unshift(w.frameElement.name || w.frameElement.id);"
    " w = w.parent; } return nomes;"
)
JS_MARCAR_PAGINA = "window.__integraGovPagina = true;"
JS_PAGINA_NOVA = (
    "return !window.__integraGovPagina && document.readyState === 'complete';"
)


def caminho_do_frame(driver) -> list[str]:
    """Nomes dos frames do topo até o frame em que o driver está."""
    return list(driver.execute_script(JS_CAMINHO_FRAMES) or [])


def entrar_no_frame(driver, caminho) -> None:
    """Posiciona o driver no frame do ``caminho``, partindo do topo."""
    driver.switch_to.default_content()
    for nome in caminho:
        driver.switch_to.frame(nome)


def marcar_pagina(driver) -> None:
    """Marca a página do frame atual (a que vier no lugar dela não terá a marca)."""
    driver.execute_script(JS_MARCAR_PAGINA)


def aguardar_pagina_nova(driver, caminho, timeout: float) -> bool:
    """Espera a página marcada do frame ser trocada por uma nova já carregada.

    Reentra no frame a cada consulta. Ao terminar, o driver fica no frame.

    Returns:
        ``True`` se a página foi trocada; ``False`` se não houve troca no prazo.
    """

    def pagina_nova(d) -> bool:
        try:
            entrar_no_frame(d, caminho)
            return bool(d.execute_script(JS_PAGINA_NOVA))
        except WebDriverException:
            return False  # frame no meio da navegação; consulta de novo

    try:
        WebDriverWait(driver, timeout).until(pagina_nova)
        return True
    except TimeoutException:
        try:
            entrar_no_frame(driver, caminho)
        except WebDriverException:
            pass
        return False
