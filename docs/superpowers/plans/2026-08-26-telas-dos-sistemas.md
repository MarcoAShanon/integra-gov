# As telas dos sistemas — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** pôr na fatia `03-contexto` da landing as cinco capturas reais das telas
por onde o trabalho manual passa, na ordem de uma tarefa de verdade, para que o
gestor **reconheça** o próprio dia em vez de ler que os sistemas não se falam.

**Architecture:** um bloco novo dentro da fatia 03, feito de uma `<ol>` de cinco
`.figura` (primitiva que já existe, com legenda fora da imagem) e fechado por um
link para o vídeo. As imagens são preparadas fora da página por um script local
que reduz e renomeia por hash do conteúdo. Nenhuma primitiva do sistema é criada
ou alterada.

**Tech Stack:** HTML/CSS estáticos; Python 3 (montador, verificador e auditor do
próprio repo); Pillow como ferramenta **local** de preparo de imagem; pytest.

## Global Constraints

Valores copiados da spec `docs/superpowers/specs/2026-08-26-telas-dos-sistemas-design.md`.

1. **Nunca editar `site/index.html` à mão** — ele é gerado por `site/montar.py`.
   Só a Task 5 o regenera.
2. **`site/parts/contrato.md` é lei** — nenhum token, primitiva, breakpoint ou
   regra criado ou alterado. **Nenhuma regra sai de `#oferta` para o sistema.**
3. **Palavras vetadas no texto visível:** `completo`, `pronto`, `finalizado`,
   `fecha o ciclo`. E o vocabulário de transação do § 0 (`solução`, `cliente`,
   `atendimento`, `oferta`, `proposta de valor`).
4. **Zero exclamações.** A página inteira não tem nenhuma; os cinco `h2` são
   declarativos.
5. **Todo número visível vai em `.num`** (contrato § 5.4). Exceção única:
   número dentro de `.pill`. Há portão automático:
   `test_nenhum_numero_visivel_escapa_do_mono`.
6. **"Três" do fecho vai por extenso e SEM `.num`** — o § 5.4 cobra dígito.
7. **`.figura` (contrato § 8.3-g): legenda FORA da imagem.** Nunca sobreposta —
   é o caso que o § 6.4 proíbe.
8. **`loading="lazy"` e `width`/`height` explícitos** em toda imagem nova.
9. **Nenhuma publicação.** Nenhum `scp`, `ssh` ou deploy.
10. **NUNCA invoque `convert` para imagem nesta máquina.** O que está no `PATH`
    é `C:\Windows\system32\convert.exe`, o utilitário que converte volume de FAT
    para NTFS.
11. Python do venv, sempre absoluto:
    `C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe`

## Onde este plano SUPERA a spec — duas decisões posteriores a ela

A spec foi escrita antes destas duas decisões. Onde eles divergirem, **vale o
plano**, e o motivo está aqui para o revisor não ler contradição:

**1. As imagens são PNG, não JPEG.** A spec § 8 diz "JPEG redimensionado", no
padrão das nove imagens já publicadas. Mas aquelas são **fotos e capturas de
dashboard**; estas são **telas de interface** — cor chapada, texto de 11px, e a
do terminal é preto com verde. JPEG produz chiado em volta da letra, que é
exatamente o que apaga o reconhecimento — o único objetivo do bloco. PNG é
lossless e comprime bem área chapada. Decisão do controlador, com a medida no
Step 3 da Task 1 (se o total passar de 400 KB, o implementador para e reporta).

**2. O vídeo abre por link comum, não pelo lightbox.** A spec § 5 mandava reusar
o gancho `.proj` + `data-video` + `.poster` + `<button>` do contrato § 9.3. Ao
escrever o plano descobriu-se que **`.poster` e `.play` só têm estilo sob
`#oferta`**: no `#contexto` o botão nasceria sem os 56×56 do alvo de toque, sem
o fundo sólido que o § 6.4 exige e sem o raio corrigido pelo achado A9.3. As
saídas eram duplicar ~40 linhas com decisões documentadas, ou promover as
classes ao sistema — que a própria spec § 9.8 proíbe. **O usuário escolheu o
link comum com `.btn`**, primitiva que já existe e já é estilizada: funciona com
e sem JavaScript, não duplica nada, não toca no sistema nem no contrato. O
lightbox continua existindo na vitrine da fatia 04, onde o gancho mora.

## File Structure

| arquivo | responsabilidade | tarefas |
|---|---|---|
| `site/preparar_telas.py` | **criar** — reduz as capturas e grava em `assets/` com nome por hash | 1 |
| `site/assets/tela-01..05-<hash>.png` | **criar** — os cinco assets servidos | 1 |
| `site/assets/MAPA.md` | registro de origem de cada asset | 1 |
| `site/parts/03-contexto.html` | a abertura, o bloco das paradas, o bloco do vídeo | 2, 3, 4 |
| `site/parts/03-contexto.css` | só o que a `.figura` não dá: a `<ol>` e o bloco do vídeo | 3, 4 |
| `tests/test_site.py` | portões de conteúdo e dos assets | 1, 2, 3, 4 |
| `CHANGELOG.md` | registro | 5 |

---

### Task 1: O preparo das imagens

**Files:**
- Create: `site/preparar_telas.py`
- Create: `site/assets/tela-01..05-<hash>.png` (gerados)
- Modify: `site/assets/MAPA.md`
- Modify: `tests/test_site.py`

**Interfaces:**
- Produces: cinco arquivos em `site/assets/` cujos nomes as Tasks 3 e 4 vão
  referenciar. **Os nomes só se conhecem depois de rodar o script** (o hash vem
  do conteúdo gravado). O relatório do implementador tem de listar os cinco
  nomes exatos, com largura e altura de cada um — as tarefas seguintes precisam
  deles para o `src`, o `width` e o `height`.

- [ ] **Step 1: Instalar o Pillow no venv**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pip install Pillow
```

Esperado: `Successfully installed pillow-...`

**Não** acrescente Pillow ao `pyproject.toml`. É ferramenta local de preparo de
asset, no mesmo estatuto de `site/extrair_assets.py` e `site/gerar_og.py` — não
é dependência do pacote `integra-gov` publicado.

- [ ] **Step 2: Escrever o script**

Crie `site/preparar_telas.py`:

```python
"""Prepara as capturas de tela de site/media/ para publicacao em site/assets/.

Le os PNG originais, reduz a largura maxima para 1000px (NUNCA amplia), grava
PNG otimizado com nome por hash do CONTEUDO GRAVADO — a regra de cache do
site/README.md, que garante que um asset alterado muda de nome e o navegador
nunca serve o antigo.

POR QUE PNG, E NAO JPEG: sao capturas de INTERFACE — cor chapada, texto de
11px, e a do terminal e preto com verde. JPEG produz chiado em volta da letra,
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
    ("SIAPE_TERMINAL.png", "Terminal 3270 do SIAPE: menu inicial, tela preta e verde"),
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
            imagem.save(temporario, format="PNG", optimize=True)
        dados = temporario.read_bytes()
        temporario.unlink()
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
```

- [ ] **Step 3: Rodar e registrar o resultado**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/preparar_telas.py
```

Esperado: cinco linhas `tela-NN-<hash>.png  <largura>x<altura>  <n> KB (era <m> KB)`,
mais o total.

**Anote os cinco nomes, larguras e alturas — as Tasks 3 e 4 dependem deles.**

**Se o total passar de 400 KB**, pare e reporte antes de seguir: a spec § 8
projetou ~1,3 MB de assets no total da página (eram 701 KB), e um total muito
acima disso é sinal de que o `optimize` não rendeu nesta máquina. **Não resolva
baixando qualidade por conta própria** — a spec § 8 diz que comprimir até borrar
o desenho dos menus destrói o objetivo do bloco, e que na dúvida vale mais
qualidade.

- [ ] **Step 4: Escrever o teste dos assets**

Acrescente no fim de `tests/test_site.py`, **substituindo os cinco nomes pelos
que o Step 3 imprimiu**:

```python
def test_as_cinco_telas_estao_nos_assets():
    """As capturas dos sistemas sao servidas de site/assets/ com nome por hash
    do conteudo (regra de cache do site/README.md), e nao de site/media/, que e
    gitignored e nao vai para a VPS junto com a pagina.

    A largura maxima e 1000px: e a mesma da maior imagem ja publicada
    (img-08, 1000x541). Mais que isso e peso sem ganho — a coluna de texto da
    pagina nao passa disso."""
    import gerar_og

    for nome in (
        "tela-01-XXXXXXXX.png",
        "tela-02-XXXXXXXX.png",
        "tela-03-XXXXXXXX.png",
        "tela-04-XXXXXXXX.png",
        "tela-05-XXXXXXXX.png",
    ):
        caminho = SITE / "assets" / nome
        assert caminho.exists(), f"{nome} — rode: python site/preparar_telas.py"
        largura, _ = gerar_og.dimensoes_png(caminho)
        assert largura <= 1000, f"{nome} tem {largura}px de largura"
```

- [ ] **Step 5: Rodar o teste**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q -k cinco_telas
```

Esperado: `1 passed`.

- [ ] **Step 6: Registrar no MAPA.md**

Acrescente ao fim de `site/assets/MAPA.md`, com os nomes e KB reais:

```markdown

## As cinco telas dos sistemas (26/08/2026)

Capturas de tela feitas pelo autor, preparadas por `site/preparar_telas.py` a
partir de `site/media/` (gitignored). Servem ao bloco das cinco paradas da fatia
`03-contexto`, e a ordem do nome é a ordem das paradas.

**Auditadas:** nenhuma tem CPF, matrícula, nome de servidor ou dado de terceiro.
As três do SEI são da unidade de testes `MGI-SGP-DECIPEX-CGPAG-NUTEC`, com
processos que o autor confirmou serem fictícios. Nas duas do SIAPE aparece o
primeiro nome do próprio autor, já publicado no rodapé da página como contato.

| arquivo | KB | origem |
|---|---|---|
| `tela-01-<hash>.png` | ... | SEI — árvore do processo, três documentos de teste. Parada 1. |
| `tela-02-<hash>.png` | ... | e-SIAPE (Sigepe) — menu da folha, com "EMITE INFORMACOES FINANCEIRAS". Parada 2. |
| `tela-03-<hash>.png` | ... | SEI — formulário "Registrar Documento Externo" com todos os campos vazios. Parada 3. |
| `tela-04-<hash>.png` | ... | Terminal 3270 do SIAPE — menu inicial, tela preta com texto verde. Parada 4. |
| `tela-05-<hash>.png` | ... | SEI — tela "Conclusão de Processo", opção "Somente concluir". Parada 5. |
```

- [ ] **Step 7: Commit**

```bash
git add site/preparar_telas.py site/assets/tela-*.png site/assets/MAPA.md tests/test_site.py
git commit -m "feat(site): prepara as cinco capturas dos sistemas para os assets"
```

---

### Task 2: A abertura da fatia 03

**Files:**
- Modify: `site/parts/03-contexto.html` (linhas 19-20)
- Modify: `tests/test_site.py`

**Interfaces:**
- Consumes: o helper `_fatia(nome: str) -> str` já existente em
  `tests/test_site.py` (lê `site/parts/<nome>.html` sem os comentários).
  Reuse-o; não redefina.

- [ ] **Step 1: Escrever o teste que falha**

Acrescente no fim de `tests/test_site.py`:

```python
def test_a_abertura_do_contexto_conta_as_paradas():
    """O h2 dizia "Dois sistemas que nao se falam". Abaixo dele passou a haver
    um bloco com CINCO capturas de TRES telas — e o leitor que conta as telas e
    le "dois" tropeca. "Dois sistemas. Tres telas. Cinco paradas." diz a mesma
    coisa e prepara o que vem abaixo: e-SIAPE e terminal 3270 sao o MESMO
    SIAPE, em duas caras.

    O 1989 NAO PODE SUMIR: ele aparecia uma unica vez na fatia, nesse h2, e e o
    fato que da o soco — um dos dois sistemas e mais velho que a web. Migrou
    para a lede."""
    texto = _fatia("03-contexto")
    assert "Dois sistemas. Três telas. Cinco paradas." in texto
    assert "Dois sistemas que não se falam" not in texto
    assert "1989" in texto
    assert "que existe desde <span class=\"num\">1989</span>" in texto
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q -k conta_as_paradas
```

Esperado: **1 failed**, em `assert "Dois sistemas. Três telas. Cinco paradas." in texto`.

- [ ] **Step 3: Trocar o h2 e a lede**

Em `site/parts/03-contexto.html`, troque estas duas linhas:

```html
      <h2>Dois sistemas que não se falam — e um deles nasceu em <span class="num">1989</span>.</h2>
      <p class="lede">O SEI tramita documentos na web desde <span class="num">2009</span>. O SIAPE guarda os dados funcionais numa emulação de terminal de mainframe — a tela preta <span class="num">3270</span>. Entre os dois fica o servidor: copiando, digitando e conferindo matrícula por matrícula.</p>
```

por:

```html
      <h2>Dois sistemas. Três telas. Cinco paradas.</h2>
      <p class="lede">O SEI tramita documentos na web desde <span class="num">2009</span>. O SIAPE guarda os dados funcionais numa emulação de terminal de mainframe — a tela preta <span class="num">3270</span>, que existe desde <span class="num">1989</span>. Entre os dois fica o servidor: copiando, digitando e conferindo matrícula por matrícula.</p>
```

O `2009`, o `3270` e o `1989` continuam em `.num`. **"Três" e "Cinco" do `h2`
vão por extenso e sem `.num`** — o § 5.4 cobra dígito (Global Constraint 6).

- [ ] **Step 4: Rodar e ver passar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q
```

Esperado: todos passam.

- [ ] **Step 5: Commit**

```bash
git add site/parts/03-contexto.html tests/test_site.py
git commit -m "feat(site): a abertura do contexto conta as telas e as paradas"
```

---

### Task 3: O bloco das cinco paradas

**Files:**
- Modify: `site/parts/03-contexto.html`
- Modify: `site/parts/03-contexto.css`
- Modify: `tests/test_site.py`

**Interfaces:**
- Consumes: os cinco nomes de arquivo, larguras e alturas que a Task 1 imprimiu;
  e o helper `_fatia(nome)`.

- [ ] **Step 1: Escrever o teste que falha**

Acrescente no fim de `tests/test_site.py`:

```python
def test_as_cinco_paradas_contam_a_ida_e_a_volta():
    """O bloco existe para RECONHECIMENTO, nao para comparacao: o gestor tem de
    ver as telas do proprio dia. A sequencia e a real, dada pelo usuario — SEI,
    e-SIAPE, SEI, terminal, SEI — e o vaivem E o argumento: tres voltas ao mesmo
    lugar, com o dado carregado na mao.

    <ol> e nao <ul>: a ordem e semantica. Quem usa leitor de tela precisa saber
    que a parada 3 vem depois da 2."""
    texto = _fatia("03-contexto")
    assert '<ol class="paradas"' in texto
    assert texto.count("<figure class=\"figura parada\">") == 5
    assert "O processo chega. Você abre a árvore para ver o que ele pede." in texto
    assert "Volta ao processo e redigita, à mão, o que leu na outra tela." in texto
    assert "Volta de novo, para fechar." in texto
    assert "Três voltas ao mesmo lugar. Nenhum dado passou sozinho." in texto
    # toda imagem nova entra preguicosa e com dimensao declarada — sem isso a
    # pagina pula quando elas chegam
    bloco = texto[texto.index('<ol class="paradas"'):texto.index("</ol>")]
    assert bloco.count('loading="lazy"') == 5
    assert bloco.count("width=") == 5 and bloco.count("height=") == 5
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q -k cinco_paradas
```

Esperado: **1 failed**, em `assert '<ol class="paradas"' in texto`.

- [ ] **Step 3: O HTML do bloco**

Em `site/parts/03-contexto.html`, **logo depois de `</div>` que fecha a
`.abertura`** (linha 21) e **antes** do `<div class="bloco rise">` que abre "Os
dois caminhos cobram alguma coisa", insira:

```html
    <!-- ---------- as cinco paradas: o percurso a mao ----------
         RECONHECIMENTO, nao comparacao. O objetivo nao e o leitor comparar as
         telas — e ele RECONHECER o proprio dia. Por isso cada tela vem grande,
         uma por vez, na rolagem, e nao em grade de miniaturas: miniatura a 25%
         da largura nao dispara memoria nenhuma. Decisao do usuario em
         26/08/2026, corrigindo o controlador, que havia proposto a grade.

         A SEQUENCIA E REAL, dada pelo usuario: SEI (verificar), e-SIAPE
         (emitir a ficha), SEI (instruir), terminal 3270 (lancar), SEI (fechar).
         O SEI aparece TRES VEZES porque o trabalho volta a ele tres vezes — e o
         vaivem e o argumento inteiro. O leitor conta nos dedos; a pagina so diz
         a frase do fecho.

         O SIAPEnet ficou de fora: nao esta na sequencia, e entrar so porque a
         captura existe seria decoracao.

         <ol> e nao <ul>: a ordem e semantica, e quem usa leitor de tela precisa
         dela. .figura e a primitiva do contrato 8.3-g — legenda FORA da imagem,
         que e o que o 6.4 exige. -->
    <ol class="paradas rise" role="list">
      <li>
        <figure class="figura parada">
          <img src="assets/tela-01-XXXXXXXX.png"
               alt="Tela do SEI: barra azul no topo, árvore do processo à esquerda com três documentos, e a barra de ícones de ações."
               loading="lazy" width="1000" height="470">
          <figcaption><span class="num">1</span> O processo chega. Você abre a árvore para ver o que ele pede.</figcaption>
        </figure>
      </li>
      <li>
        <figure class="figura parada">
          <img src="assets/tela-02-XXXXXXXX.png"
               alt="Tela do Sigepe: barra azul e laranja, e seis ícones de opções da folha, entre eles Emite Informações Financeiras."
               loading="lazy" width="1000" height="628">
          <figcaption><span class="num">2</span> Para responder, você emite a ficha financeira em outro sistema.</figcaption>
        </figure>
      </li>
      <li>
        <figure class="figura parada">
          <img src="assets/tela-03-XXXXXXXX.png"
               alt="Tela do SEI: formulário Registrar Documento Externo, com os campos Tipo do Documento, Número, Nome na Árvore, Remetente, Interessados e Nível de Acesso, todos vazios."
               loading="lazy" width="1000" height="479">
          <figcaption><span class="num">3</span> Volta ao processo e redigita, à mão, o que leu na outra tela.</figcaption>
        </figure>
      </li>
      <li>
        <figure class="figura parada">
          <img src="assets/tela-04-XXXXXXXX.png"
               alt="Terminal 3270 do SIAPE: tela preta com texto verde e um menu em caixa alta — ADMINIST, CADSIAPE, CONSULTAS, FOLHA."
               loading="lazy" width="960" height="893">
          <figcaption><span class="num">4</span> O lançamento é numa terceira tela, que não conversa com nenhuma das duas.</figcaption>
        </figure>
      </li>
      <li>
        <figure class="figura parada">
          <img src="assets/tela-05-XXXXXXXX.png"
               alt="Tela do SEI: Conclusão de Processo, com o número do processo listado e a opção Somente concluir marcada."
               loading="lazy" width="1000" height="471">
          <figcaption><span class="num">5</span> Volta de novo, para fechar.</figcaption>
        </figure>
      </li>
    </ol>

    <p class="fecho-paradas rise">Três voltas ao mesmo lugar. Nenhum dado passou sozinho.</p>
```

**Troque os cinco `tela-NN-XXXXXXXX.png` pelos nomes reais** que a Task 1
imprimiu, e **confira `width`/`height` contra as dimensões que ela reportou** —
os valores acima são a projeção da spec, não medição.

- [ ] **Step 4: O CSS, só o que a `.figura` não dá**

Acrescente ao fim de `site/parts/03-contexto.css`:

```css
/* --- as cinco paradas -------------------------------------------------
   A .figura do sistema ja da o fundo, a borda, o raio e a legenda em bloco
   separado por fio (contrato 8.3-g). Falta so a lista: tirar o marcador do
   <ol> e por o ritmo vertical entre as paradas.

   As cinco capturas tem proporcoes muito diferentes (de 1,08 na tela do
   terminal a 2,13 na do SEI). NAO se impoe proporcao unica aqui: recortar
   para alinhar mataria justamente o que faz a tela ser reconhecida. Cada uma
   guarda a sua, e a largura e que e comum. */
#contexto .paradas{
  list-style:none;
  margin:var(--e-6) 0 0;
  padding:0;
  display:flex;
  flex-direction:column;
  gap:var(--e-5);
}
/* o numero da parada, na legenda: mono pelo .num do sistema, e so precisa do
   respiro ate o texto. */
#contexto .paradas figcaption .num{margin-right:var(--e-2)}

/* o fecho e a UNICA frase em que a pagina fala aqui — o leitor ja contou as
   tres voltas sozinho. Fica com a medida de leitura da .sub. */
#contexto .fecho-paradas{
  margin:var(--e-5) 0 0;
  max-width:62ch;
  font-size:var(--t-4);
}
```

**Não escreva mais nada.** Se você se pegar declarando cor, fonte, borda ou
raio, pare: a `.figura` já traz tudo isso, e redeclarar é como um token some de
vista.

- [ ] **Step 5: Rodar os testes e o portão da fatia**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q
```

Esperado: todos passam — inclusive
`test_nenhum_numero_visivel_escapa_do_mono`, que vai cobrar os cinco números
novos das legendas automaticamente.

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/montar.py --so 03-contexto
```

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/verificar.py site/preview-03-contexto.html
```

Esperado: `verificar: sem achados (preview-03-contexto.html)`. Este portão cobra
`alt` em toda imagem — se acusar, é porque um `alt` ficou vazio ou faltando.

- [ ] **Step 6: Commit**

```bash
git add site/parts/03-contexto.html site/parts/03-contexto.css tests/test_site.py
git commit -m "feat(site): as cinco paradas do percurso a mao, tela por tela"
```

---

### Task 4: O bloco do vídeo

**Files:**
- Modify: `site/parts/03-contexto.html`
- Modify: `site/parts/03-contexto.css`
- Modify: `tests/test_site.py`

**Interfaces:**
- Consumes: `_fatia(nome)`; e o asset `assets/img-08-6ad7082f.jpg`, que **já
  existe** (é o pôster do vídeo na vitrine da fatia 04). Não gere asset novo.

- [ ] **Step 1: Escrever o teste que falha**

Acrescente no fim de `tests/test_site.py`:

```python
def test_o_video_fecha_o_percurso_com_a_duracao_a_vista():
    """Depois de percorrer as cinco paradas a mao, o leitor ve a mesma coisa
    feita pela automacao — e "o mesmo percurso" e o que amarra as duas cenas.

    A DURACAO E OBRIGATORIA: o critico cego apontou, sobre a vitrine da fatia
    04, que "o gestor decide clicar pelo tamanho; sem ele, nao clica". 5min28s e
    um compromisso real para quem ainda esta decidindo se escreve.

    E um link comum, com o .btn do sistema — nao o lightbox. O gancho .play/
    .poster do contrato 9.3 so tem estilo sob #oferta, e copiar as regras para
    ca seria duplicar um bloco que carrega decisoes documentadas (56x56 do alvo
    de toque, glifo sobre cor solida por causa do 6.4, raio --raio-s). Assim
    funciona com e sem JavaScript, sem tocar no sistema."""
    texto = _fatia("03-contexto")
    assert "Veja o mesmo percurso, feito pela automação" in texto
    assert '<span class="num">5 min 28 s</span>' in texto
    assert '<a class="btn btn-s" href="/media/exante.mp4">Ver o vídeo</a>' in texto
    # o gancho do lightbox NAO pode aparecer aqui: sem o CSS de #oferta o botao
    # nasceria sem tamanho, sem contraste e sem alvo de toque
    assert "data-video" not in texto
    assert "class=\"play" not in texto
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q -k video_fecha_o_percurso
```

Esperado: **1 failed**, em `assert "Veja o mesmo percurso, feito pela automação" in texto`.

- [ ] **Step 3: O HTML**

Em `site/parts/03-contexto.html`, **logo depois** do
`<p class="fecho-paradas rise">` que a Task 3 acrescentou:

```html
    <!-- ---------- o video, como resposta a cena ----------
         Fecha as cinco paradas: o leitor acabou de contar as tres voltas ao
         SEI, e ve a mesma coisa feita pela automacao. "O mesmo percurso" e o
         que amarra as duas cenas — e o que faz ele querer ver.

         A DURACAO E OBRIGATORIA. O critico cego apontou, sobre a vitrine da
         fatia 04, que "o gestor decide clicar pelo tamanho; sem ele, nao
         clica". 5min28s e compromisso real para quem ainda esta decidindo se
         escreve, e dizer o numero e a regra da pagina.

         LINK COMUM, NAO LIGHTBOX, e isto e decisao registrada: o gancho .proj/
         .poster/.play do contrato 9.3 so tem estilo sob #oferta. Reusa-lo aqui
         exigiria copiar ~40 linhas que carregam decisoes documentadas (56x56 do
         alvo de toque; glifo sobre cor SOLIDA porque o 6.4 proibe texto sobre
         imagem; --raio-s em vez de 999px, achado A9.3) — duplicacao literal de
         bloco logico. Com .btn o controle funciona com e sem JavaScript, e o
         sistema nao muda. O video continua abrindo em lightbox na vitrine da
         fatia 04, que e onde o gancho mora. -->
    <div class="ver-percurso rise">
      <p>Veja o mesmo percurso, feito pela automação — <span class="num">5 min 28 s</span> de execução real, do processo aberto ao lançamento conferido.</p>
      <div class="acoes">
        <a class="btn btn-s" href="/media/exante.mp4">Ver o vídeo</a>
      </div>
    </div>
```

**`.acoes` mesmo com um botão só:** é a primitiva do contrato § 8.3-e, e abaixo
de 768px ela garante `width:100%` e `align-self:stretch` independentemente do
alinhamento do pai. Um `<div>` avulso não faria isso.

- [ ] **Step 4: O CSS**

Acrescente ao fim de `site/parts/03-contexto.css`:

```css
/* --- o video que fecha o percurso ------------------------------------
   Sem cartao: dois fios concentricos (a .figura acima ja tem um) seriam
   ruido. So o respiro ate o bloco seguinte e a medida de leitura. */
#contexto .ver-percurso{margin:var(--e-6) 0 0}
#contexto .ver-percurso p{margin:0 0 var(--e-4);max-width:62ch}
```

- [ ] **Step 5: Rodar os testes e o portão da fatia**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q
```

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/montar.py --so 03-contexto
```

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/verificar.py site/preview-03-contexto.html
```

Esperado: todos passam; `verificar: sem achados`.

- [ ] **Step 6: Commit**

```bash
git add site/parts/03-contexto.html site/parts/03-contexto.css tests/test_site.py
git commit -m "feat(site): o video fecha o percurso, com a duracao a vista"
```

---

### Task 5: A página inteira e o registro

**Files:**
- Modify: `site/index.html` (**gerado** por `montar.py` — não editar à mão)
- Modify: `CHANGELOG.md` (primeira seção `### Alterado` de `[Não publicado]`)

**Interfaces:**
- Consumes: as Tasks 1–4.

Esta tarefa **não** faz as checagens de olho: quem lê a página no navegador e
julga se as telas disparam reconhecimento é o controlador (ver § 10 da spec).
Não as declare feitas.

- [ ] **Step 1: Remontar**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/montar.py
```

- [ ] **Step 2: Os quatro portões**

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/verificar.py
```

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe site/auditar_contrato.py
```

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest tests/test_site.py -q
```

```bash
C:\Users\Thelemarco\PycharmProjects\integra-publico\.venv\Scripts\python.exe -m pytest -q
```

**Registre a saída literal de cada um.** Se qualquer um reprovar, **pare e
reporte** — não conserte fatia por fora, as Tasks 1–4 passaram por review.

- [ ] **Step 3: O CHANGELOG**

Em `CHANGELOG.md`, na **primeira** seção `### Alterado` de `[Não publicado]`,
acrescente:

```markdown
- **A página mostra as telas por onde o trabalho manual passa.** A seção de
  contexto afirmava que o SEI e o SIAPE não se falam; agora ela mostra, na ordem
  de uma tarefa real, as cinco paradas que um servidor percorre à mão — SEI,
  e-SIAPE, SEI, terminal `3270`, SEI. O leitor conta as três voltas ao mesmo
  lugar sozinho, e a página só diz a frase do fecho.
  - **O objetivo é reconhecimento, não comparação.** Cada tela aparece grande,
    uma por vez, e não em grade de miniaturas: o gestor precisa reconhecer o
    próprio dia, e miniatura não dispara memória. A abertura da seção passou a
    "Dois sistemas. Três telas. Cinco paradas.", e o ano de `1989` migrou para a
    lede em vez de sumir com o título antigo.
  - **As capturas são PNG, não JPEG**, e por medida: são telas de interface, com
    texto de 11px e cor chapada, onde o chiado do JPEG apagaria justamente o que
    faz a tela ser reconhecida.
  - **O vídeo de execução fecha a sequência**, com a duração à vista — quem
    decide clicar decide pelo tamanho.
```

- [ ] **Step 4: Commit**

```bash
git add site/index.html CHANGELOG.md
git commit -m "docs(site): remonta a pagina e registra as telas dos sistemas"
```

- [ ] **Step 5: Reportar o que fica para o controlador**

**Não publique.** O redeploy é ordem explícita do usuário. Ao fechar, reporte:

1. os cinco nomes de asset e o peso total, contra os ~1,3 MB projetados na spec;
2. que as checagens de olho (§ 10 da spec) não foram feitas: ver as cinco
   imagens em tamanho real e julgar se dá para reconhecer a tela, e testar a
   seção com JavaScript desligado;
3. que o vídeo **não existe localmente** — `site/media/` é gitignored e o
   arquivo vive só na VPS. O link `/media/exante.mp4` só resolve em produção.
