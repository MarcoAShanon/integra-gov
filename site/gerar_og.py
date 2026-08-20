#!/usr/bin/env python3
"""Fotografa site/parts/og.html em 1200x630 -> site/assets/og-image.png.

Pillow nao esta no venv; Selenium esta. Compor a imagem em HTML tem a
vantagem de ela usar exatamente os mesmos tokens e as mesmas fontes do
contrato de design — a marca que aparece no cartao de compartilhamento
fica igual a marca da pagina, e nao parecida.

QUANDO RODAR DE NOVO: sempre que `--font-display` mudar no
`parts/00-sistema.css`, ou quando o texto da proposicao mudar. A pagina
compoe o wordmark em texto; o compartilhamento social exige a marca como
IMAGEM, e e este arquivo que a produz. Sem regerar, a marca do link fica
diferente da marca da pagina.

Uso:
    python site/gerar_og.py
"""
from __future__ import annotations

import pathlib
import struct
import sys
import tempfile

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

RAIZ = pathlib.Path(__file__).resolve().parent
ORIGEM = RAIZ / "parts" / "og.html"
DESTINO = RAIZ / "assets" / "og-image.png"

LARGURA, ALTURA = 1200, 630
FAMILIAS = ("Bricolage Grotesque", "IBM Plex Mono")

_ASSINATURA_PNG = b"\x89PNG\r\n\x1a\n"

# Espera a promessa TERMINAR. `execute_script("return document.fonts.ready")`
# devolve a Promise e segue em frente sem esperar nada — e a foto sai no
# fallback, silenciosamente.
_JS_ESPERAR_FONTES = """
const pronto = arguments[arguments.length - 1];
document.fonts.ready.then(() => pronto(document.fonts.status));
"""

# `document.fonts.check()` devolve true para familia que caiu em fallback,
# entao nao serve de prova. Este mede a MESMA familia com dois fallbacks
# genericos diferentes: se a familia carregou, ela e usada nos dois casos e
# as larguras batem; se nao carregou, um cai em monospace e o outro em
# serif, e as larguras divergem.
_JS_CONFERIR_FONTES = """
const familias = arguments[0];
function largura(pilha, peso) {
  const s = document.createElement('span');
  s.textContent = 'PROJETO INTEGRA 1234567890 automacao';
  s.style.cssText = 'position:absolute;left:-9999px;top:0;white-space:nowrap;'
                  + 'font-size:100px;font-weight:' + peso + ';font-family:' + pilha;
  document.body.appendChild(s);
  const w = s.getBoundingClientRect().width;
  s.remove();
  return w;
}
const saida = {};
for (const familia of familias) {
  const com_mono  = largura('"' + familia + '", monospace', 600);
  const com_serif = largura('"' + familia + '", serif', 600);
  saida[familia] = {
    com_mono: Math.round(com_mono * 100) / 100,
    com_serif: Math.round(com_serif * 100) / 100,
    carregou: Math.abs(com_mono - com_serif) < 0.5,
  };
}
return saida;
"""


def _ajustar_viewport(navegador: webdriver.Chrome) -> tuple[int, int]:
    """Faz a AREA VISIVEL medir 1200x630, nao a janela.

    `--window-size` dimensiona a janela; conforme a versao do Chrome sobra
    ou falta alguns pixels de cromo, e a foto sai fora de medida. As redes
    cortam qualquer coisa que nao seja 1200x630, entao vale corrigir.
    """
    for _ in range(4):
        atual = navegador.execute_script("return [window.innerWidth, window.innerHeight];")
        if atual == [LARGURA, ALTURA]:
            return LARGURA, ALTURA
        janela = navegador.get_window_size()
        navegador.set_window_size(
            janela["width"] + (LARGURA - atual[0]),
            janela["height"] + (ALTURA - atual[1]),
        )
    return tuple(navegador.execute_script("return [window.innerWidth, window.innerHeight];"))


def dimensoes_png(caminho: pathlib.Path) -> tuple[int, int]:
    """Largura e altura lidas do cabecalho IHDR, sem depender de Pillow."""
    dados = caminho.read_bytes()
    if dados[:8] != _ASSINATURA_PNG:
        raise ValueError(f"{caminho} nao e um PNG")
    return struct.unpack(">II", dados[16:24])


def main() -> int:
    opcoes = Options()
    opcoes.add_argument("--headless=new")
    opcoes.add_argument(f"--window-size={LARGURA},{ALTURA}")
    opcoes.add_argument("--hide-scrollbars")
    opcoes.add_argument("--force-device-scale-factor=1")
    opcoes.add_argument("--no-sandbox")
    opcoes.add_argument("--disable-gpu")
    opcoes.add_argument("--disable-dev-shm-usage")
    # perfil proprio e descartavel: sem isto o Chrome recusa a sessao quando
    # ja ha uma instancia do usuario aberta com o perfil padrao.
    opcoes.add_argument(f"--user-data-dir={tempfile.mkdtemp(prefix='og-integra-')}")

    navegador = webdriver.Chrome(options=opcoes)
    try:
        navegador.set_script_timeout(30)
        navegador.get(ORIGEM.as_uri())

        visivel = _ajustar_viewport(navegador)
        if tuple(visivel) != (LARGURA, ALTURA):
            print(f"aviso: area visivel em {visivel}, nao em ({LARGURA}, {ALTURA})")

        estado = navegador.execute_async_script(_JS_ESPERAR_FONTES)
        conferencia = navegador.execute_script(_JS_CONFERIR_FONTES, list(FAMILIAS))

        print(f"document.fonts.status: {estado}")
        faltando = []
        for familia, medida in conferencia.items():
            marca = "ok" if medida["carregou"] else "FALLBACK"
            print(
                f"  {marca:9s} {familia:22s} "
                f"mono={medida['com_mono']:.1f} serif={medida['com_serif']:.1f}"
            )
            if not medida["carregou"]:
                faltando.append(familia)
        if faltando:
            print(
                "erro: as familias acima cairam em fallback — a imagem sairia com "
                "a marca diferente da marca da pagina. Nada foi gravado."
            )
            return 1

        corpo = navegador.find_element("tag name", "body")
        corpo.screenshot(str(DESTINO))
    finally:
        navegador.quit()

    largura, altura = dimensoes_png(DESTINO)
    tamanho = DESTINO.stat().st_size / 1024
    print(f"{DESTINO} — {largura}x{altura}, {tamanho:.1f} KB")
    if (largura, altura) != (LARGURA, ALTURA):
        print(f"erro: as redes cortam o que nao for {LARGURA}x{ALTURA}; conserte o og.html")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
