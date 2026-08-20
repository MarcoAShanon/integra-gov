# Design — Redesign da landing de divulgação (projeto.govintegra.com.br)

*20/08/2026. Escopo: camada de apresentação + nova seção de conversão.*
*O texto validado das seções existentes é preservado; o que muda é a forma —
e o fim da página, que hoje não conduz a lugar nenhum.*

## 1. Objetivo

A landing existe para **convencer servidores e gestores de outros órgãos a
replicar o INTEGRA no órgão deles**, e a conduzi-los a **falar com a equipe**
para um piloto assistido.

Hoje ela não faz o segundo trabalho. Termina em dois botões — "Abrir o
repositório" (GitHub) e "Falar com a equipe" (`mailto:` cru). Para o leitor
que se convenceu, não existe resposta para "e agora, o que eu faço na
segunda-feira".

**Fora de escopo:** reescrever a narrativa das seções existentes; criar
formulário ou backend; qualquer coisa que exija Node, build servido, SPA ou
framework CSS; o deploy em si (preparado, executado só sob ordem explícita).

## 2. Estado atual (medido, não lembrado)

A fonte não existia versionada — vivia só no ar e num scratchpad de sessão
que já não existe. Foi recuperada por `curl` de <https://projeto.govintegra.com.br>.

- 750 linhas, 665 KB no ar; ~53 KB sem as imagens base64 embutidas.
- 12 seções: hero, prêmio, problema, resultados, módulos, como funciona,
  governança, replicável, ecossistema, feito-com, CTA, rodapé.
- Tokens CSS com tema claro/escuro: `--bg:#FBFAF7`, `--brand:#E7920D` (âmbar),
  `--brand2:#10A87E` (esmeralda), `--data-blue:#3B7DE0`, `--maxw:1120px`.
- **Já tem movimento**: scroll-reveal por `IntersectionObserver` (`.rise`) e
  barras que preenchem ao entrar na viewport, com `prefers-reduced-motion`
  respeitado. Movimento não é a lacuna.
- **Tipografia é a lacuna**: `--font-sans` é a pilha do sistema
  (`-apple-system, "Segoe UI", system-ui, Roboto, Arial`) — exatamente o que a
  skill `frontend-design` veta como escolha genérica.
- **Defeitos conhecidos**: um `href="#"` morto; nenhum skip link; o texto
  promete "o vídeo do Exante entra em seguida" (promessa não cumprida no ar);
  o lightbox de vídeo só faz sentido se os vídeos existirem.

## 3. Parâmetro de design (referências verificadas no código-fonte)

Cinco landings foram abertas e lidas no HTML/CSS servido, não descritas de
memória.

| Referência | O que é roubado | O que não é |
|---|---|---|
| [oxide.computer](https://oxide.computer) | Grid de 12 colunas em custom properties; rampa neutra de croma ~0 + **um** matiz de acento; regra "todo número em mono"; seção de comparação que nomeia as concessões dos dois lados; CTA consultivo + rota de fuga | Rack 3D e animação ASCII (JS pesado) |
| [cloud.gov](https://cloud.gov) | Caso gêmeo (equipe federal servindo outros órgãos): contato como "fale com uma pessoa" sem formulário; objeções removidas pelo nome ("No RFP required / No lock-in") | O skin USWDS — é o "portal de governo" a evitar |
| [tailscale.com](https://tailscale.com) | Cards em que **a métrica é o título** e o caso vem embaixo | Carrossel de logos e mural de depoimentos: não há esse volume, e fingir destrói a credibilidade |
| [navapbc.com](https://www.navapbc.com) | Contraste de escala (display grande × corpo 16px); fundo quente em vez de branco puro | Fontes comerciais; funil que termina em newsletter |
| [public.digital](https://public.digital) | Bloco de contato logo após a prova, com convite formulado como pergunta | Prova por parede de logos de clientes |

**Direção estética escolhida: rigor técnico quente.** A estrutura da Oxide
(grid, hairlines, números em mono, densidade controlada) sobre a base quente
que a página já tem: fundo ecru, âmbar como acento único, esmeralda aposentada
ou reduzida a sinal de estado. Instrumento de precisão feito por gente — nem
startup fria, nem portal.

## 4. Restrições duras (repassadas literalmente a todo subagente)

1. **HTML estático único.** Sem Node, sem build servido, sem SPA, sem
   framework CSS. CSS e JS inline. Servido por nginx.
2. **Google Fonts é a única exceção de rede.** Toda fonte precisa de stack de
   fallback real.
3. **Proibidas como escolha de display:** Inter, Roboto, Arial, `system-ui` e
   congêneres. Também proibido convergir em Space Grotesk.
4. **Nenhum dado pessoal**, nenhum órgão real identificado, nenhum código de
   órgão real, nenhuma credencial.
5. **Números só os já publicados** (§6). Nenhuma métrica nova, nenhuma
   arredondada para cima, nenhuma sem fonte.
6. **Enquadramento incremental.** Nada de "completo", "pronto", "fecha o
   ciclo". O projeto é publicado módulo a módulo.
7. **Acessibilidade não é acabamento**: contraste AA medido, foco visível,
   ordem de foco, `prefers-reduced-motion`.
8. **Deploy não é automático.** Publicação externa exige ordem explícita.

## 5. Arquitetura das fatias

Jogar N subagentes num arquivo único faz com que se atropelem. A solução é
**congelar o contrato antes de paralelizar**.

### Fatia 0 — Sistema (sequencial, bloqueante)

Um subagente, com a skill `frontend-design`, produz:

- paleta completa em custom properties, claro e escuro, derivada da direção
  "rigor técnico quente";
- escala tipográfica com número de degraus declarado, e o **par de fontes**
  (display com caráter + mono para todos os números), ambas no Google Fonts,
  com fallback;
- grid de 12 colunas em custom properties (molde Oxide);
- primitivas: botão primário/secundário, card, pill, hairline, faixa de seção;
- regras de movimento (reaproveitando o `IntersectionObserver` já existente).

Saídas: `site/parts/00-sistema.css` e `site/parts/contrato.md`.

**Nenhuma outra fatia começa antes de o contrato ser aprovado pelo usuário**,
porque todas o consomem literalmente.

### Fatias 1–5 (paralelas)

Cada subagente escreve **apenas** a sua `<section>` e o CSS dela, consumindo os
tokens do contrato e sem redefinir nenhum.

| # | Fatia | Conteúdo | Molde |
|---|---|---|---|
| 1 | Hero + navegação | proposição em uma frase, nav, âncoras | Oxide |
| 2 | Prova | prêmio, números, resultados | Tailscale: métrica-como-título |
| 3 | Contexto | problema, comparação honesta, como funciona, governança | Oxide: nomear as concessões |
| 4 | Oferta | módulos, ecossistema, feito-com | — |
| 5 | Conversão | **piloto assistido** (nova) + rodapé | cloud.gov + Public Digital |

### Fatia 5 em detalhe (é a que não existe hoje)

Promessa autorizada, e nada além dela: **conversa inicial e orientação
pontual.** Um e-mail respondido, uma reunião de diagnóstico, e a indicação do
caminho — quais módulos, o que o órgão precisa ter, onde costuma travar. **Sem
compromisso de acompanhar a implantação.** A seção não pode sugerir fila,
prazo, plantão nem acompanhamento continuado.

Deve conter:

- quem procura (perfil do interlocutor no órgão de origem);
- **o que mandar no e-mail** para a conversa render — é isso que qualifica o
  contato e substitui o formulário que não vai existir;
- o que acontece depois, honestamente delimitado;
- objeções removidas pelo nome: sem contrato, sem fornecedor, sem licitação,
  sem senha embutida no código, licença MIT, roda com o acesso que o próprio
  servidor já tem;
- rota de fuga para quem prefere autonomia: o repositório.

## 6. Provas disponíveis (as únicas citáveis)

- 1º lugar nacional, Edital nº 1/2025 "Experiências Inspiradoras em Gestão de
  Pessoas no Setor Público" (MGI/SGP), média 93,83.
- Caso publicado na revista *Gestão de Pessoas em Ação* (MGI), vol. 3,
  jun/2025.
- −90% no tempo por processo (~32 min → ~3,5 min).
- Passivo ~4.800 → ~800 processos (mai/2023 → jan/2024).
- +6.500 processos concluídos; 15.440 recebidos entre 2023 e 2026.
- Equipe de 8 → 4 técnicos; ~200 mil vidas na DECIPEX.
- R$ 12,11 mi lançados de forma controlada no SIAPE em 304 processos
  (abr–jul/2026).

Cada card de métrica **cita a fonte**. É a vantagem sobre as referências
comerciais, que não citam nada.

## 7. Ciclo de revisão

Cada fatia atravessa quatro passos, e nenhuma entra na página final sem o
quarto:

1. **Construtor** — subagente com `frontend-design`, o contrato e o texto
   atual da seção.
2. **Crítico cego** — outro subagente recebe o HTML **sem saber quem fez nem o
   que foi pedido além do contrato**. Audita: aderência ao contrato (nenhum
   token redefinido, nenhuma fonte fora do par), acessibilidade, restrição
   estática, e as regras do §4. Mesmo padrão de gauntlet usado no leitor de
   ficha financeira.
3. **Montagem e demonstração** — a fatia é montada e exibida no navegador,
   com captura em claro e escuro.
4. **Aprovação do usuário.** Reprovada, volta **ao construtor** com o parecer
   — não é reescrita por cima pelo orquestrador.

O trabalho só se encerra quando todas as fatias estiverem aprovadas.

## 8. Validação de usabilidade

Não há MCP Playwright nesta sessão. A validação usa o painel Browser, que
dirige um Chromium real — e **exige o painel visível na tela** para captura.

Bateria, por fatia aprovada e de novo na página montada:

- viewports 375 / 768 / 1280 px, em claro e escuro;
- navegação completa por teclado: ordem de foco, foco visível, skip link
  (a criar — hoje não existe);
- árvore de acessibilidade: `h1` único, `h2` sem pular degrau, `alt` em toda
  imagem informativa, landmarks;
- **contraste medido** via `getComputedStyle`, não estimado;
- console sem erro; rede sem requisição além do Google Fonts;
- `prefers-reduced-motion` respeitado;
- peso da página (a atual pesa 665 KB — a nova não deve piorar);
- todos os links resolvendo, incluindo o `href="#"` morto de hoje.

## 9. Entrega e versionamento

A fonte passa a viver **neste repositório**:

```
site/
  index.html        # artefato único servido pelo nginx
  parts/            # as fatias, para manutenção por seção
    contrato.md
    00-sistema.css
    01-hero.html … 05-conversao.html
  montar.py         # ~30 linhas: concatena parts/ → index.html
  README.md         # como alterar e como redeployar
```

O `montar.py` é ferramenta **local** — o nginx continua servindo HTML puro.
Existe para que a próxima alteração seja por seção, e não uma caçada dentro de
um arquivo de 750 linhas.

**Redeploy** (só sob ordem explícita): `scp` de `site/index.html` para
`root@145.223.95.35:/var/www/projeto.govintegra.com.br/`, com a chave
`~/.ssh/integra_deploy`. nginx e SSL já estão configurados.

## 10. Pontas soltas (registradas, decididas depois)

1. **`og-image.png`** — arquivo separado na VPS, vai destoar do novo visual.
   Precisa ser refeito; formato 1200×630.
2. **A promessa do vídeo** — o texto no ar diz "o vídeo do Exante entra em
   seguida". Promessa não cumprida: ou sai da página, ou o vídeo entra.
3. **O lightbox de vídeo** — só se sustenta se os vídeos existirem; caso
   contrário, sai junto com o JS dele.

## 11. Verificação de conclusão

O trabalho está concluído quando, e apenas quando:

- as seis fatias (0 a 5) tiverem aprovação explícita do usuário;
- a bateria do §8 rodar na página **montada** (não só nas fatias isoladas) sem
  achado aberto;
- `site/` estiver commitado com `index.html`, `parts/`, `montar.py` e
  `README.md`;
- as três pontas soltas do §10 estiverem decididas — resolvidas ou
  explicitamente adiadas;
- o comando de redeploy estiver preparado e **não executado** sem ordem.
