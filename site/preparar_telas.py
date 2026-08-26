"""Prepara as capturas de tela de site/media/ para publicacao em site/assets/.

Le os PNG originais, reduz a largura maxima para 1000px (NUNCA amplia), grava
PNG otimizado com nome por hash do CONTEUDO GRAVADO — a regra de cache do
site/README.md, que garante que um asset alterado muda de nome e o navegador
nunca serve o antigo.

POR QUE PNG, E NAO JPEG: sao capturas de INTERFACE — cor chapada, texto de
11px, e a do terminal e texto azul-claro e branco sobre preto. JPEG produz chiado em volta da letra,
que e exatamente o que destroi o RECONHECIMENTO — o unico objetivo do bloco que
usa estas imagens. PNG e lossless e comprime bem area chapada.

Pillow e ferramenta LOCAL: nao entra no pyproject.toml.
"""
from __future__ import annotations

import hashlib
import pathlib

from PIL import Image

RAIZ = pathlib.Path(__file__).resolve().parent
MEDIA = RAIZ / "media"
ASSETS = RAIZ / "assets"
LARGURA_MAX = 1000

# A ordem E a ordem das paradas na fatia 03: o numero do arquivo e o numero da
# parada. Nao reordene sem reordenar a secao.
TELAS = [
    ("SEI.png", "SEI: arvore do processo, tres documentos de teste"),
    ("eSIAPE.png", "e-SIAPE (Sigepe): menu da folha"),
    ("instrucao.png", "SEI: formulario Registrar Documento Externo, campos vazios"),
    ("SIAPE_TERMINAL.png", "Terminal 3270 do SIAPE: menu inicial, azul-claro e branco sobre preto"),
    ("conclusao.png", "SEI: tela Conclusao de Processo"),
]


def preparar() -> list[dict]:
    """Grava os cinco assets e devolve o relatorio de cada um."""
    ASSETS.mkdir(exist_ok=True)
    relatorio = []
    for indice, (origem, descricao) in enumerate(TELAS, start=1):
        caminho = MEDIA / origem
        bytes_antes = caminho.stat().st_size
        with Image.open(caminho) as imagem:
            imagem = imagem.convert("RGB")
            larg_antes, alt_antes = imagem.size
            if larg_antes > LARGURA_MAX:
                nova_alt = round(alt_antes * LARGURA_MAX / larg_antes)
                imagem = imagem.resize((LARGURA_MAX, nova_alt), Image.LANCZOS)
            largura, altura = imagem.size
            temporario = ASSETS / "_preparar_telas.tmp.png"
            # try/finally, e nao a sequencia direta: se o save falhar no meio
            # (disco cheio, permissao, interrupcao) o temporario ficaria para
            # tras dentro de assets/, que e o diretorio que sobe para a VPS.
            # missing_ok porque o save pode ter falhado antes de criar o arquivo.
            try:
                imagem.save(temporario, format="PNG", optimize=True)
                dados = temporario.read_bytes()
            finally:
                temporario.unlink(missing_ok=True)
        digest = hashlib.sha256(dados).hexdigest()[:8]
        nome = f"tela-{indice:02d}-{digest}.png"
        (ASSETS / nome).write_bytes(dados)
        relatorio.append(
            {
                "nome": nome,
                "descricao": descricao,
                "origem": origem,
                "largura": largura,
                "altura": altura,
                "kb": len(dados) / 1024,
                "kb_antes": bytes_antes / 1024,
            }
        )
    return relatorio


def main() -> None:
    total = 0.0
    for item in preparar():
        total += item["kb"]
        print(
            f'{item["nome"]}  {item["largura"]}x{item["altura"]}  '
            f'{item["kb"]:.0f} KB (era {item["kb_antes"]:.0f} KB)  <- {item["origem"]}'
        )
    print(f"total: {total:.0f} KB")


if __name__ == "__main__":
    main()
