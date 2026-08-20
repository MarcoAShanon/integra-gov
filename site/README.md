# site/ — a landing de divulgação

No ar em <https://projeto.govintegra.com.br>.

## O que é cada coisa

| | |
|---|---|
| `index.html` | **o artefato servido**. Gerado, não editado à mão. |
| `parts/` | as partes. É aqui que se altera a página. |
| `parts/contrato.md` | o contrato de design. É lei para quem mexer em qualquer fatia. |
| `parts/00-sistema.css` | tokens e primitivas. Nenhuma fatia redefine token daqui. |
| `montar.py` | concatena `parts/` → `index.html`. |
| `verificar.py` | checagens estáticas: acessibilidade, privacidade, fontes vetadas, vazamento de seletor. |
| `auditar_contrato.py` | recalcula 236 razões de contraste do próprio CSS e cobra lastro de cada número afirmado no contrato. |
| `assets/` | imagens, nomeadas por hash do conteúdo. Ver `assets/MAPA.md`. |
| `media/` | o vídeo (5,9 MB). **Não versionado** — vive na VPS. |
| `original/index-slim.html` | a página anterior, congelada como referência de texto. |

## Como alterar

1. Edite o arquivo da fatia em `parts/`.
2. `python site/montar.py`
3. `python site/verificar.py`
4. `python site/auditar_contrato.py` — **obrigatório se mexeu em qualquer cor**.
5. `python -m pytest tests/test_site.py`

Os quatro precisam passar. O `verificar.py` roda em modo fatia quando o alvo se
chama `preview-<fatia>.html` — `python site/montar.py --so 02-prova` gera essa
prévia.

**Nunca edite `index.html` direto.** Ele é regenerado, e a edição se perde na
próxima montagem.

## Regra de cache

Os assets são nomeados por **hash do conteúdo** (`img-03-eb0db43e.jpg`), então
um asset que muda de conteúdo muda de nome e o navegador nunca serve o antigo.
Se você acrescentar um asset com nome fixo, essa garantia deixa de valer para ele.

## Redeploy

**Publicação externa. Só com ordem explícita.**

Guarde a versão que está no ar antes de sobrescrever:

```bash
ssh -i ~/.ssh/integra_deploy root@145.223.95.35 "cp /var/www/projeto.govintegra.com.br/index.html /var/www/projeto.govintegra.com.br/index.prev.html"
```

Suba **os assets primeiro** — se a página subir antes, ela pede imagens que
ainda não existem:

```bash
scp -i ~/.ssh/integra_deploy -r site/assets root@145.223.95.35:/var/www/projeto.govintegra.com.br/
scp -i ~/.ssh/integra_deploy site/assets/og-image.png root@145.223.95.35:/var/www/projeto.govintegra.com.br/og-image.png
scp -i ~/.ssh/integra_deploy site/index.html root@145.223.95.35:/var/www/projeto.govintegra.com.br/index.html
```

Confira que o que está no ar é o que você subiu:

```bash
curl -sS https://projeto.govintegra.com.br/ | sha256sum
sha256sum site/index.html
```

**Voltar atrás:**

```bash
ssh -i ~/.ssh/integra_deploy root@145.223.95.35 "cp /var/www/projeto.govintegra.com.br/index.prev.html /var/www/projeto.govintegra.com.br/index.html"
```

## Prévia antes do deploy

`python site/montar.py --previa` gera `previa.html`, idêntica à produção exceto
por um `<meta name="robots" content="noindex,nofollow">`. Publique em
`/previa/` para ver em dispositivo real sem tocar na produção — e **remova
depois**: cópia velha esquecida num caminho público é pior que nenhuma prévia.

## O `og-image`

`parts/og.html` é a fonte; `gerar_og.py` a fotografa em 1200×630 com Selenium.
**Se o contrato mudar a fonte de display, regere** — senão o cartão do link
mostra uma marca diferente da página. O gerador se recusa a gravar se alguma
fonte cair em fallback.
