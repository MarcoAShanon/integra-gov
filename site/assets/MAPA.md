# Mapa dos assets extraidos

As 9 imagens abaixo (`img-01`..`img-09`) foram extraidas do base64 embutido
no `index.html` publicado em projeto.govintegra.com.br, capturado em
18/07/2026, pelo `site/extrair_assets.py`. `og-image.png` foi baixada a
parte (Step 3 da task), direto de `/og-image.png` da pagina no ar — nao veio
de um base64 do HTML, entao nao tem card no showcase.

| arquivo | KB | origem |
|---|---|---|
| `img-01-fe4b5613.png` | 8.7 | Favicon do site — cubo mágico colorido em miniatura (`<link rel="icon">`, `<head>`, fora de qualquer `<section>`). |
| `img-02-69ed929c.png` | 32.9 | Logo do cabeçalho — cubo mágico 3D com as letras "CGPAG" nas faces, marcado no HTML como "LOGO PROVISÓRIA — trocar pela logo oficial do INTEGRA". Aparece no `<header class="hero">`, dentro do link `.logo` da navegação (topo da página, antes de qualquer `<section>`). |
| `img-03-eb0db43e.jpg` | 33.0 | Foto da cerimônia de premiação — equipe da DECIPEX no palco recebendo o prêmio de 1º lugar em Experiências Inspiradoras em Gestão de Pessoas (MGI/SGP, 2025), com telão mostrando o logo do cubo "CGPAG" ao fundo. Seção `#premio`. |
| `img-04-615283e8.jpg` | 55.3 | Captura de tela do "Painel SEI" — dashboard web com indicadores agregados (ativos na unidade, novos no período, concluídos, passivo > 90 dias) e gráfico de evolução no período; dados fictícios de demonstração (nenhum CPF/nome/matrícula/processo individual visível). Seção `#feito-com`, primeiro card do showcase de projetos. |
| `img-05-0ad33b0c.jpg` | 62.7 | Captura de tela do "Extrator SEI" — janela de desktop do aplicativo Extrator sobreposta à tela de unidades do SEI (login e senha borrados/redigidos na imagem); botões de coleta de movimentações e marcadores. Seção `#feito-com`, segundo card do showcase. |
| `img-06-487d112d.jpg` | 42.0 | Captura de tela do "INTEGRA Mensageria" — janela de desktop "INTEGRA - Sistema de Mensageria" (abas Status/Ações/Log, fases da automação) sobreposta à Central de Mensagens do Sigepe; campos de destinatário e mensagem vazios. Seção `#feito-com`, terceiro card do showcase. |
| `img-07-c7db0106.jpg` | 44.8 | Captura de tela do "INTEGRA PSS — Reposição ao Erário" — janela de desktop do launcher "INTEGRA PSS" com campos de login/token mascarados (borrado/pontos) e log de execução da automação. Seção `#feito-com`, quarto card do showcase. |
| `img-08-6ad7082f.jpg` | 114.3 | Frame-poster do vídeo de execução do "INTEGRA Exante" (`data-video="/media/exante.mp4"`) — janela "INTEGRA EXANTE" sobreposta ao SEI (colaboragov), com a árvore de processos e os números de processo do SEI borrados/pixelizados de propósito (alt: "dados pessoais ocultados"); o e-mail de login exibido é do autor do projeto, já público no `<meta name="author">` da página, não de um servidor/processo real. Seção `#feito-com`, quinto e último card do showcase. |
| `img-09-4d87ec95.png` | 53.5 | Logo de rodapé — variante clara do cubo "CGPAG" com a marca "PROJETO INTEGRA — I.A. & Automação" abaixo, sobre fundo escuro. Aparece no `.foot .note` ao final da seção `#feito-com` (rodapé da página). |
| `og-image.png` | 149.1 | Imagem de compartilhamento social (`og:image`/`twitter:image`) baixada de `https://projeto.govintegra.com.br/og-image.png` (Step 3). Sera refeita na Task 9 — mantida aqui so para nao perder a versao atual. |
