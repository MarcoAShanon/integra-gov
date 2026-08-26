# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado
- **A landing de divulgação passa a viver no repositório, em `site/`** —
  publicada em <https://projeto.govintegra.com.br>. Antes ela existia apenas no
  ar e num diretório temporário que já não existia: o ponto de partida deste
  trabalho foi baixar de volta a própria página com `curl`, porque não havia
  fonte. Agora há histórico, diff e rollback junto do pacote que ela anuncia.
  - **A página é montada, não editada.** `site/parts/` tem uma fatia por seção;
    `montar.py` concatena em `index.html`. Alterar a página é alterar uma
    fatia — não é caçar dentro de um arquivo de centenas de linhas. O nginx
    continua servindo HTML puro: o montador é ferramenta local, não build.
  - **`site/parts/contrato.md` é o sistema de design, e é lei.** Tokens, escala
    tipográfica, grid, primitivas e as regras que as fatias não podem
    renegociar. Ele existe porque cinco seções foram construídas em paralelo
    por agentes que não se viam: congelar o contrato antes de paralelizar é o
    que faz cinco autores produzirem uma página em vez de cinco coladas.
  - **Dois portões automáticos, versionados.** `verificar.py` reprova
    acessibilidade (hierarquia de títulos, `alt`, foco, `prefers-reduced-motion`,
    skip link, âncora quebrada, `id` duplicado), privacidade (CPF por dígito
    verificador) e violação de contrato (fonte vetada, seletor vazando entre
    fatias, recurso de terceiro por host exato). `auditar_contrato.py`
    recalcula **236 razões de contraste a partir do próprio CSS** e exige que
    todo número afirmado no contrato tenha lastro — inclusive resolvendo
    `var()` e checando cascata, porque a conta pode estar certa sobre um CSS
    que não faz o que a conta supõe.
  - **Medido, na página montada, nos dois temas:** zero contrastes reprovados e
    **zero elementos não mensuráveis** — a versão anterior tinha 18, por pôr
    texto sobre gradiente. Todo texto está sobre fundo sólido, e por isso todo
    contraste dela é verificável por máquina em vez de opinável.
  - **De 648,7 KB para 123,3 KB.** As nove imagens embutidas em base64 saíram
    para `site/assets/`, nomeadas por hash do conteúdo — asset que muda de
    conteúdo muda de nome, e o navegador nunca serve o antigo.
  - Acessibilidade que a versão anterior não tinha: os três landmarks
    (`header`, `main`, `nav`), skip link que **de fato pula** a navegação (o
    montador emite o `<header>` antes do `<main>`), 14 alvos de toque todos com
    44px, e nenhum conteúdo dependente de JavaScript — sem script, nada some.
  - **Seção nova para a conversa** (chamada de "piloto assistido" à época),
    com a promessa delimitada por escrito:
    conversa inicial e orientação pontual, sem acompanhamento de implantação. A
    página anterior terminava num `mailto:` solto.
  - **−90% virou −89%**: a conta dá −89,06%, e arredondar **para cima** numa
    página cujo argumento é que os números são medidos custa mais que o ponto
    percentual. Pela mesma razão, uma série anual saiu da página — a soma dava
    763 a mais que o total publicado, e enquanto não se souber qual dos dois
    está certo, publica-se só o que tem lastro.

- **Novo subpacote `integra_gov.ficha_financeira`** — leitura de ficha
  financeira em PDF **como dados**. Recebe o arquivo (servidor, aposentado,
  pensionista ou instituidor) e devolve os lançamentos estruturados: rubrica,
  descrição, competência, valor e natureza (rendimento/desconto), num formato
  neutro que qualquer script consome. Fecha o outro lado do ciclo: os módulos
  `siape.ficha_pensionista`, `esiape.ficha_anual` e `esiape.ficha_multi_orgao`
  **produzem** o PDF; este o lê de volta.
  - API: `ler_fichas_financeiras(pdf)` devolve **uma ficha por identidade e
    exercício** — um PDF mesclado (até 15 anos, vários órgãos) contém várias.
    `ler_ficha_financeira(pdf)` atende o caso simples e levanta
    `MultiplasFichasError` em vez de escolher uma em silêncio.
  - **A leitura se autoconfere.** A soma dos lançamentos de cada mês é
    comparada com o `TOTAL BRUTO`/`TOTAL DESCONTOS`/`TOTAL LÍQUIDO` impressos:
    mês que não fecha volta com `confere=False` e `Aviso` de código estável,
    e `FichaFinanceira.consistente` é o gate de uma checagem só. Divergência
    aritmética é aviso (ou exceção, com `strict=True`); **perda de dado**
    (linha da tabela não reconhecida) levanta sempre.
  - A coluna `R/D` não é impressa em toda linha: o marcador aparece onde o
    grupo começa e as seguintes o herdam. A resolução é determinística, na
    ordem impressa, e a conferência contra os totais é que a **valida** — se a
    herança estiver errada, o mês não fecha em vez de devolver um valor com o
    sinal trocado. A mesma rubrica pode ter naturezas opostas em meses
    diferentes (adiantamento da gratificação natalina é crédito em junho e
    débito em novembro), então a natureza é do **lançamento**, não da rubrica.
  - Valores em `Decimal`, sempre positivos, com o sinal na `Natureza` — sem
    convenção contábil embutida e sem erro de arredondamento binário.
  - `tem_camada_de_texto(pdf)` é público e reutilizável: distingue um PDF
    legível por máquina de um impresso com as fontes convertidas em curva
    vetorial (o caso conhecido é a impressora virtual `Microsoft Print to PDF`
    do Windows). Sem esse guard, um PDF assim atravessa qualquer pipeline em
    silêncio e produz uma ficha vazia que parece legítima. A biblioteca **não
    faz OCR**: reconhecer dígito em valor monetário troca centavos sem avisar.
  - **Dois layouts** são lidos: o relatório do **SIAPE mainframe**
    (`L.A54120.DE`, monoespaçado, largura fixa) e a **impressão web do
    e-SIAPE** (tabela por `|`, dois semestres por página). Cada página é
    classificada pelo seu próprio detector, então um PDF mesclado pode
    misturar os dois; `origem.layout` registra de onde cada ficha veio.
  - Verificado contra fichas reais: a de pensionista (mainframe) fecha os 12
    meses contra os totais impressos, e a de instituidor (e-SIAPE) fecha os 7
    meses com lançamento — as duas sem aviso.
  - Ambos validados contra PDFs reais, inclusive o **round-trip** da
    impressão do e-SIAPE: a estrutura por `|` sobrevive à extração e o ruído
    da impressão (cabeçalho com data/hora, rodapé com a URL) é descartado sem
    virar lançamento.

### Alterado
- `pyproject.toml`: piso do `pypdf` subiu de `>=3.0` para `>=4.0`. O modo de
  extração `layout` — de que a leitura da ficha depende, porque no relatório
  do SIAPE a informação está na **posição** do caractere — só existe a partir
  do 4.0. Com o piso antigo o pacote instalava e quebrava em runtime.
- **A landing para de barrar o gestor não-técnico na porta.** A fatia do gestor
  existia para derrubar "isso é coisa de TI, eu não tenho equipe" e, no mesmo
  bloco, reintroduzia a objeção como requisito: exigia alguém que lesse Python e
  uma máquina Windows, e mandava o leitor para uma seção que pedia a versão do
  SEI e se havia quem programasse. A página se desmentia no clique que ela mesma
  pedia.
  - **Sai a exigência técnica das três fatias que o leitor percorre** (`01b`,
    `03` e `05`). O custo continua dito — a automação exige alguém por perto, e
    o roteiro quebra se a tela mudar —, mas como preço à vista, não como
    condição de entrada. A `04-oferta` não muda: lá é catálogo técnico.
  - **O contato deixa de ser só o e-mail.** Entra `(24) 98849-3257`, no WhatsApp
    e por ligação, ao lado do endereço institucional. O número foi conferido
    contra o portão de privacidade antes de entrar.
  - **O limite continua dito, sem fechar a porta.** Some o "Termina aí" e a
    negação em série; fica a divisão de trabalho — quem implanta e opera é a
    equipe do órgão — e a conversa segue se fizer sentido para os dois lados.
  - **A seção da conversa perdeu o nome de plano de serviço.** Chamava-se
    "Piloto assistido" na navegação, no mapa, na pílula e no `h2` — e a lede
    existia para definir o que "assistido" queria dizer. Passou a se chamar
    **Conversa**, palavra que a própria página já usava. Junto com isso, a
    porta do gestor deixou de repetir a promessa da seção seguinte e passa a
    convidar a conversar pelo meio que o leitor preferir; o limite continua
    dito três vezes na seção da conversa, que é para onde o botão leva.
  - **A entrada do gestor parou de falar de preço e de exigir decisão.** Saiu
    o cartão "O que não dá para prometer" — falar de custo na seção que existe
    para abrir uma porta é receber o visitante com uma fatura na mão. A
    comparação honesta continua no contexto, com os dois preços à vista. A
    abertura passou a falar da demanda que cresce, e não da equipe que
    encolhe: assim enquadrada, a queda de `8` para `4` técnicos lia como
    precedente de corte de pessoal — achado de um crítico que leu a página sem
    acesso ao raciocínio por trás dela.
  - **"Licença MIT" vem explicada onde o leitor encontra o termo**, e não três
    seções adiante: qualquer órgão pode baixar, usar e adaptar, sem pagar nada
    e sem pedir autorização, mantendo o aviso de autoria e o texto da licença.
  - **Doze testes novos em `tests/test_site.py`** cobram cada uma dessas
    decisões no texto publicado, lendo a fatia sem os comentários de projeto —
    inclusive um para a palavra "solução", vetada por implicar transação e que
    nenhum portão cobrava.
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

### Alterado
- `integra_gov.siape.TrocaHabilitacao`: **`upag` vira opcional** — o módulo
  passou a contemplar as **duas formas** de escolher o órgão de trabalho na
  tela TROCAHAB. Conforme o **perfil de acesso** de cada pessoa, a habilitação
  pode vir vinculada ao par ÓRGÃO+UPAG (formato clássico, com a coluna
  UNIDADE preenchida) ou concedida a **nível de ÓRGÃO** (categoria OPERAC):
  aí a linha vem com a coluna UNIDADE vazia e o nível de acesso `ORGAO`. A
  busca agora testa candidatos em ordem de preferência, em cada página: com
  `upag` informada, primeiro o padrão exato ÓRGÃO+UPAG (comportamento
  clássico, intacto); sempre, por último, o padrão de nível ÓRGÃO (`orgao`
  seguido de `ORGAO` após os brancos) como fallback. Quem tem acesso por
  unidade não muda de comportamento; quem tem no nível do órgão cai no
  fallback automaticamente, sem mudar chamadores. Sem `upag`, busca direto a
  habilitação de nível ÓRGÃO. A exceção `HabilitacaoNaoEncontrada` agora
  lista os candidatos tentados.
- **BREAKING — namespace renomeado para `integra_gov`.** O pacote passou a
  importar como `integra_gov` (antes `integra`) e o nome de distribuição é
  `integra-gov` (`pip install integra-gov`). **Atualize os imports:**
  `from integra.sei import X` → `from integra_gov.sei import X`. Isso alinha o
  nome de instalação e o de importação (antes divergiam) e, principalmente,
  evita a colisão com o pacote interno `integra` — permitindo que ele passe a
  **consumir este como dependência** em vez de manter cópias divergentes.

### Corrigido
- `integra_gov.sei.iniciar_processo` em **lote/sequência**: após criar um
  processo, o SEI fica na página do processo (a árvore ocupa o lugar do menu) e
  a criação SEGUINTE falhava com `IniciarProcessoError` ("menu não encontrado").
  Agora o módulo volta à tela inicial pelo ícone "Controle de Processos" da
  barra superior (sempre presente) e aciona o menu — criação única segue
  intocada (o desvio só ocorre quando o menu não está na tela). **Verificado ao
  vivo** no SEI 4.1.5 (MGI): 7 criações em sequência num lote real do
  orquestrador, incluindo retomadas. Achado da
  verificação ao vivo do orquestrador (integra-flow, plano 5a): itens 2–3 de um
  lote de 3 quarentenavam.
- `IframesSei.DOCUMENTO_HTML` (`integra_gov.sei.iframes`) não alcançava o
  `ifrArvoreHtml` no SEI 4.0: ele fica no `ifrVisualizacao` **aninhado** dentro do
  wrapper `ifrConteudoVisualizacao`, e a navegação não descia essa camada (só
  funcionava em SEI < 4.0). A descida virou o helper compartilhado
  `descer_para_conteudo_documento`, reusado também pelo `download_documento` (que
  já aplicava a correção inline) — DRY. Nenhum caller de produção era afetado (o
  destino `DOCUMENTO_HTML` só era usado em teste); a mesma navegação foi
  verificada ao vivo pelo `download_documento`.

### Adicionado
- `integra_gov.esiape.ficha_anual`, `integra_gov.esiape.dados_funcionais` e
  `integra_gov.esiape.ficha_multi_orgao`: extração da **ficha financeira
  anual** (`FPEMFICHAF`) pela web, num único órgão ou encadeada por todos os
  órgãos do servidor. `FichaAnualServidor` divide a faixa pedida em blocos de
  até 15 anos (limite do e-SIAPE), imprime cada um e mescla tudo num único
  PDF em ordem cronológica (`pypdf`, já dependência do **núcleo** desde a
  criação do subpacote — sem extra dedicado); decide por **evidência**
  (botão "Gerar Relatório" ou a mensagem de "sem dados" do CIS), nunca por
  timeout silencioso — bloco sem dados entra em `blocos_sem_dados` (não é
  erro), enquanto um erro de verdade no meio de um bloco aborta a pessoa
  inteira (`ExtracaoFichaEsiapeInterrompida`, com `blocos_processados` e
  `causa` — os PDFs já salvos permanecem em disco). `DadosFuncionaisOrgao`
  consulta o `CDCOINDFUN` para descobrir deterministicamente o órgão
  anterior e o ano de ingresso de quem migrou (sem sondar ficha mês a mês).
  `FichaMultiOrgao` encadeia os dois: extrai a faixa do órgão ativo, troca a
  habilitação para o órgão anterior e repete, respeitando a regra de que o
  **ano da virada pertence aos dois órgãos**; devolve um PDF único mesclado,
  a `trilha` percorrida, `lacunas`/`falhas_tecnicas` sempre declaradas (nunca
  levanta por uma lacuna legítima) e `voltou_ao_orgao_inicial` (a próxima
  matrícula do lote não pode ser consultada no órgão errado). Comportamento
  portado do extrator validado em produção, com o lote multi-órgão real
  **14/14** confirmando o encadeamento e o retorno ao órgão inicial.
  **Verificado ao vivo em 2026-08-06** contra o e-SIAPE real: militar
  reformado multi-órgão real, faixa 2008–2026, trilha de dois órgãos
  (`[('99995', ..., 2014, 2026), ('77000', ..., 2008, 2014)]`) com o ano da
  virada (2014) presente nos DOIS órgãos, `lacunas == []` e
  `voltou_ao_orgao_inicial=True`; PDF final mesclado com 22 páginas
  (13 + 9) cobrindo 2008–2026 (conferido com `pypdf`) em 108 s, atravessando
  ao vivo DOIS relogins do SERPRO no meio do fluxo — inclusive um relogin
  transitório durante o salto de órgão, sem perder a faixa do órgão anterior
  graças ao retry adicionado pela verificação. A verificação corrigiu quatro
  defeitos reais antes de passar: a sequência da tela FPEMFICHAF (ENTER
  após a matrícula, com os anos como dropdowns `Select`, não campos de
  texto); a consulta passou a disparar pelo botão `onClickBtnAvanca` (o
  `w_opc_cons` é só o radio de opção, não o gatilho); a configuração do
  Chrome exigida para a impressão realmente salvar o PDF, agora documentada
  em `docs/uso-basico.md`; e o retry do salto de órgão após relogin
  transitório (sem ele, a faixa do órgão anterior se perdia).
- **Subpacote `integra_gov.esiape`** — automação do e-SIAPE **web**
  (CIS/Software AG), **multiplataforma** (roda no mesmo `driver` Selenium do
  SEI, sem `pywinauto`/extra dedicado). Camadas: `navegacao` (frames
  visíveis, popups modais, cortina de transição, travessia de
  relogin/máquina de estados do menu, atalho de transação pela lupa),
  `acesso` (`AcessoEsiape` — SERPRO ID, você confirma no app, a lib nunca
  digita PIN/senha) e `habilitacao` (`TrocaHabilitacaoEsiape` — troca de
  ÓRGÃO via `TROCAHAB`, só efetiva no "Sim" do modal e só confirma pelo
  cabeçalho refletindo o destino). Exceções tipadas (`EsiapeError` e
  subclasses). A flag de relogin pendente (`relogin_pendente`/
  `limpar_flag_relogin`) evita a lacuna silenciosa de consultar o órgão
  errado após uma sessão renascer. **Mecânicas validadas ao vivo em lote
  real** (14 extrações) no pacote **privado** que originou este subpacote.
  **Verificado ao vivo em 2026-08-05** (e-SIAPE real): login SERPRO ID caiu
  na tela de relogin do SERPRO e a travessia automática (AVANÇAR → Pular)
  funcionou; leitura do órgão ativo; troca de habilitação nos DOIS caminhos
  (idempotente — cabeçalho já no destino — e completa, com modal "Sim" e
  confirmação pelo cabeçalho); `navegar_para_transacao` confirmou a tela do
  FPEMFICHAF pelo seletor exclusivo; flag de relogin limpa ao final. A
  verificação não exigiu correções.
- `integra_gov.siape.ficha_pensionista`: **`FichaAnualPensionista`** — ficha
  financeira anual do pensionista (`>FPEMPSFICF`), um PDF por ano com
  confirmação em disco, seleção de instituidor em pensão múltipla (nunca
  escolhe sozinha — `InstituidorObrigatorio` lista as opções da tela) e aborto
  honesto (`ExtracaoFichaInterrompida`, com `anos_processados`). Comportamento
  portado do extrator validado em produção (649 fichas). **Verificado ao vivo
  em 2026-08-05** (SIAPE real, órgão de teste): pensão única com 2 anos com
  dados (PDFs confirmados em disco, ~15 s/ano) e faixa com 2 anos vazios —
  ambos em `anos_sem_dados`, com o `(0034)` tratado duas vezes seguidas
  provando a recuperação do cursor via F2 (o ano seguinte foi digitado nos
  campos certos); ao final de cada extração o F12 devolveu o terminal ao
  prompt de matrícula, utilizável. A verificação não exigiu correções.
- `integra_gov.sei.sessao`: **detecção de sessão caída** (página de login no
  meio do fluxo) — `sessao_expirada(driver)` (a página atual é a de login?) e
  `levantar_se_sessao_expirada(driver, causa)`; nova exceção
  `SessaoExpiradaError` (subclasse direta de `SeiError` — deliberadamente NÃO
  de `SeiNavegacaoError`, para atravessar os módulos sem ser embrulhada).
  **Comportamento novo no funil de navegação:** falhas em
  `IframesSei.navegar`/`switch_to_iframe_visualizacao` e em
  `ProcessoSei.acessar` com a página de login presente levantam
  `SessaoExpiradaError` (fail-fast, sem esgotar retries contra a página de
  login) em vez de `TimeoutException`/`SeiNavegacaoError`. Quem captura
  `SeiError` não sente diferença. Motivação: orquestradores (integra-flow)
  distinguirem "sessão caiu" (recuperável: logar de novo) de falha ambígua.
  **Verificado ao vivo** no SEI 4.1.5 (MGI): sem falso positivo com sessão
  viva; após `delete_all_cookies()` (simulação fiel da expiração),
  `ProcessoSei.acessar` levantou `SessaoExpiradaError` e `sessao_expirada(driver)`
  confirmou a página de login. A verificação **corrigiu o funil**: a expiração
  real deixa a página anterior renderizada (o campo de pesquisa ainda existe) e
  a falha só aparece depois do round-trip ao servidor (ENTER → redirect ao
  login), na **confirmação** do acesso — o guard entrou também no
  `_validar_acesso`, além do caminho do campo ausente.
- `integra_gov.sei.incluir_documento_bloco`: **inclui documento(s) em um bloco de
  assinatura** (mecanismo do SEI para assinatura em lote) —
  `IncluirDocumentoBloco(driver, bloco, protocolos).incluir()`. Requer o documento
  **selecionado na árvore**; `bloco` casa por value (id) ou texto (erro lista os
  disponíveis); `protocolos` são numéricos (validados). Estrito: se algum
  protocolo não estiver na tela, **nada é incluído** (tudo-ou-nada);
  `BlocoAssinaturaError` em qualquer falha. Portado do `incluir_documento_bloco`
  do pacote privado, generalizado: exceção tipada no lugar do `bool` silencioso,
  sem `callback_log`, reúso de `barra_icones`/`iframes`. **Verificado ao vivo** no
  SEI 4.1.5 (MGI): documento incluído em bloco real. A verificação corrigiu a
  **confirmação**: ao incluir com sucesso, a tela do bloco **não muda** (sem
  mensagem, formulário permanece) — então a confirmação é pela **ausência de
  recusa** (o submit recarrega o iframe = ação processada; sem alerta imediato,
  alerta tardio ou erro inline `#divInfraExcecoes` = aceito), e o diálogo
  pós-Incluir é **dispensado** (`dismiss`), nunca aceito.
- `integra_gov.sei.download_documento`: **baixa o documento selecionado** na
  árvore — `DownloadDocumento(driver).baixar()` → `DocumentoBaixado` (bytes +
  `content_type` + `extensao` + `nome_sugerido`). **Headless:** busca o arquivo
  com `fetch()` **dentro da sessão logada** (reusa cookies/SSL — o que também
  resolve os certificados `.gov.br`), sem a janela nativa "Salvar como" nem a
  pasta de download do Chrome; a lib devolve **dado**, não escreve em disco por
  si (`DocumentoBaixado.salvar(pasta, nome=...)` grava quando você quiser). Vale
  para documentos **externos/enviados**; documento interno é HTML e não tem anexo
  para baixar. Portado do `download_documento` do pacote privado, generalizado:
  `DownloadDocumentoError` no lugar do `None` silencioso, sem `callback_log`,
  extração de nome/extensão do `Content-Disposition`. **Verificado ao vivo** no
  SEI 4.1.5 (MGI): baixou um comprovante externo de 86 KB (`application/pdf`,
  nome do `Content-Disposition`). A verificação corrigiu a navegação de iframes:
  no SEI 4.0 o `ifrArvoreHtml` (cujo `src` é a URL `documento_download_anexo`)
  fica no `ifrVisualizacao` **aninhado**, então `_extrair_url` desce essa camada
  extra além do wrapper `ifrConteudoVisualizacao` (em SEI < 4.0, sem wrapper, é
  no-op).
- `integra_gov.sei.enviar_processo`: **envia (tramita)** o processo aberto a outra
  unidade — `EnviarProcesso(driver, unidade_destino, *, orgao=None,
  manter_aberto=False).enviar()`. Preenche a unidade no autocomplete do SEI,
  **confirma que a unidade exata entrou em `selUnidades`** antes de enviar (casa a
  sigla distinguindo a unidade-pai de sub-unidades, para não mandar ao lugar
  errado) e checa o alerta de erro depois; `EnviarProcessoError` em qualquer
  falha. Portado do `enviar_processo` do pacote privado, generalizado: **removida
  a dependência de GUI `PrimeiroPlanoNavegador`** (fere o princípio headless),
  sleeps aleatórios e `callback_log` fora, exceções tipadas no lugar de `bool`,
  reúso de `barra_icones`/`switch_to_iframe_visualizacao`. **Verificado ao vivo**
  no SEI 4.1.5 (MGI): processo criado e enviado à unidade destino com
  `manter_aberto` (após enviar, a visualização mostrou "Processo aberto nas
  unidades: destino + origem"). Detalhes de DOM fixados na verificação: o
  autocomplete é `div.infraAjaxAutoCompletar > … > a`, e o checkbox/Enviar são
  clicados via JS (o SEI cobre o `<input>` com o `<label>` do infraCheckbox).
- `integra_gov.sei.concluir_processo`: **conclui (encerra)** um processo aberto —
  `ConcluirProcesso(driver).concluir()`. Trata os caminhos que o SEI apresenta: o
  formulário "Conclusão de Processo" (SEI 4.x → botão Salvar), o *alert* de
  confirmação legado (< 4.0), e o **bloqueio** por documento com hipótese legal
  pendente (via *alert* ou `div.alert-danger`), que levanta a subclasse
  `ProcessoBloqueadoError` — para quem conclui em lote distinguir "bloqueado" de
  uma falha técnica (`ConcluirProcessoError`). Portado do `concluir_processo` do
  pacote privado, generalizado: exceções tipadas no lugar do `dict {sucesso,
  motivo}`, logging stdlib, reúso de `barra_icones` (com a estabilização
  anti-corrida do clique), comentário de fluxo de órgão removido. **Verificado ao
  vivo** no SEI 4.1.5 (MGI): processo público criado e concluído pelo formulário
  (após Salvar, a visualização passou a "Processo não possui andamentos abertos").
- `integra_gov.sei.marcador`: marcadores do SEI em **dois contextos** (duas
  classes). `Marcadores` (tela Controle de Processos) lista os marcadores da
  unidade como **dados** (`Marcador`: id/nome/quantidade/cor), filtra a lista por
  marcador (`selecionar`, por nome exato ou id), desfaz o filtro
  (`remover_filtro`) e lê o filtro ativo (`filtro_ativo`). `MarcadorProcesso`
  (processo aberto, modal "Gerenciar Marcador") **inclui** (`incluir`, com
  mensagem opcional ≤ 250), **remove** (`remover`) e **lista** (`listar`) o
  marcador **daquele** processo. Portado de `seletor_marcadores`/`marcador`/
  `troca_marcador` do pacote privado, generalizado: exceções tipadas
  (`MarcadorError`), reúso de `barra_icones`/`iframes`, sem DevTools/`input()`/
  GUI/`bs4`/`tenacity` e sem valores de órgão embutidos. **Verificado ao vivo** no
  SEI 4.1.5 (MGI): listar (12 marcadores), filtrar + relistar com filtro ativo, e
  incluir/remover num processo (ciclo reversível). A verificação corrigiu o sinal
  de "filtro aplicado": `filtrarMarcador(id)` **navega** e o resultado aparece em
  `tblProcessosRecebidos`/`tblProcessosGerados` (não há `tblProcessosDetalhado`),
  então `selecionar` espera o chip `divFiltroMarcador` e a volta à visão de
  marcadores é via `filtrarMarcador(null)`.
- `integra_gov.sei.controle_prazo`: define/exclui o **prazo em dias** de um
  processo aberto — `ControlePrazo(driver).definir(dias)` (valida `1..9999`) e
  `.excluir()`. **Melhoria sobre a fonte:** o valor mágico `prazo="0"` (=excluir)
  virou dois métodos distintos, sem mágica. Exceções tipadas (`ControlePrazoError`,
  `ValueError`), reúso de `barra_icones` com a estabilização anti-corrida do clique
  ("ícone pressionado sem navegar"). **Verificado ao vivo** no SEI 4.1.5 (MGI):
  definir 30 dias + excluir.
- **Link entre documentos** no editor: `montar_link_documento(id_documento,
  protocolo)` monta a **âncora nativa** do SEI (classe `ancora_sei`, id
  `lnkSei<id_documento>`, sem `href` — o SEI a resolve na visualização), e o novo
  parâmetro `chaves_html` de `EditarConteudo` injeta esse HTML **cru** apenas em
  placeholders escolhidos (sem escape), junto dos campos de texto escapados, numa
  **única** passada. Para isso, `documentos_arvore` passou a capturar o
  `id_documento` (id **interno**, distinto do protocolo visível): `DocumentoNo`
  ganhou o campo `id_documento`, extraído do `href` do nó (`&id_documento=…`).
  **Verificado ao vivo** no SEI 4.1.5 (MGI): a âncora gerada saiu **idêntica** à
  que o SEI grava para um link feito à mão, e o round-trip (injetar → salvar →
  reabrir) preservou o link funcional **sem sanitização** do CKEditor; a tripla
  `href id_documento == lnkSei id == anchor id` foi confirmada — o protocolo (nº
  visível) e o `id_documento` são números diferentes, e o link usa o interno.
- `integra_gov.sei.documentos_arvore`: consulta e **seleção** de documentos na
  árvore do processo. `DocumentosArvore.selecionar(texto)` clica o nó do
  documento (aponta um documento existente para `assinar`/`editar_conteudo`, que
  agem sobre o selecionado); `listar()/contar()/existe()` devolvem a árvore como
  **dados** — cada item é um `DocumentoNo` (`texto`, `numero`, `tipo`, `id`) com
  o tipo (`TipoDocumento`: PDF/interno) identificado pelo ícone e o protocolo
  extraído do rótulo. **Expande as pastas automaticamente** (`expandir()`, via
  "Abrir todas as Pastas") antes de ler/selecionar — o SEI agrupa os documentos
  em pastas colapsadas quando passam de ~20, e sem expandir eles não entram no
  DOM; use `expandir=False` para desligar. Seleção com **desambiguação segura**:
  vários nós casando sem `indice` → `SelecaoDocumentoError` (não escolhe em
  silêncio). Portado dos módulos `documentos_arvore` + `expandir_pastas` do
  pacote privado, generalizado (logging, exceções tipadas, sem simulação de
  tempo). **Verificado ao vivo** no SEI 4.1.5 (MGI): a expansão revelou uma
  pasta colapsada (23 → 42 documentos), com tipo/número corretos e seleção pelo
  protocolo.
- `integra_gov.sei.assinar_documento`: **assinatura eletrônica** do documento
  selecionado (`AssinarDocumento(driver, senha).assinar()`) — aciona "Assinar
  Documento", preenche a senha no modal e confirma. A senha é **parâmetro** do
  chamador (via `getpass`/cofre), **nunca embutida, nunca registrada em log**
  nem persistida (mesmo princípio do SIAPE: você é quem autoriza). **Não reporta
  "assinado" por suposição**: confirma pela verdade — o documento passar a
  exibir os marcadores reais de assinatura do SEI ("assinado eletronicamente
  por"/"código CRC"/"código verificador"), impossíveis num documento não
  assinado; senha recusada (alerta ou mensagem no modal) levanta
  `AssinaturaError`. Doc traz o caveat de governança (assinar em lote = assinar
  sem revisar; a conferência é da aplicação). **Verificado ao vivo** no SEI 4.1.5
  (MGI): despacho clonado de modelo, preenchido e assinado (nova versão com o
  bloco de assinatura oficial). A confirmação via documento foi necessária
  porque o SEI mantém o iframe do modal no DOM após assinar (checar o modal dava
  falso negativo).
- `integra_gov.sei.editar_conteudo`: substitui **placeholders** no conteúdo de um
  documento (`EditarConteudo(driver, {"{{NOME}}": ...}).editar()`, devolve
  `placeholder → nº de ocorrências`). Injeta direto na **API do CKEditor**
  (`getData`/`setData` em todas as instâncias editáveis — cabeçalho, corpo,
  rodapé) em vez de simular teclado/"localizar e substituir" na tela:
  determinístico, rápido e **sem exigir habilitação institucional** (só a
  sessão logada). Par natural do `documento_modelo=` do
  `incluir_documento_interno` (clona o modelo → preenche os campos). Rede de
  segurança: placeholder não encontrado → **fecha o editor sem salvar** e
  falha listando os faltantes; valores escapados por padrão
  (`escapar_html=False` para HTML cru); confirmação do save pela
  desabilitação do botão Salvar (comportamento real do editor). Inclui o
  helper `data_por_extenso()` (data pt-BR sem depender de locale).
  **Verificado ao vivo** no SEI 4.1.5 (MGI): clone de modelo (`documento_modelo`)
  + substituição de `{{PROCESSO}}`/`{{NOME}}`/`{{CPF}}`/`{{DATA}}`/`{{SERVIDOR}}`/
  `{{CARGO}}` gravada como nova versão. Ao **reabrir** um documento já salvo, o
  editor nasce "limpo" e o Salvar desabilitado; o módulo dispara o evento
  `change` do CKEditor para o SEI reconhecer a alteração e habilitar o Salvar.
- `integra_gov.sei.incluir_documento_interno`: inclui um **documento interno**
  (Despacho, Nota Técnica, …) num processo aberto
  (`IncluirDocumentoInterno.incluir()`, **devolve o rótulo na árvore**, ex.:
  `"Despacho 12345678"`). Suporta o texto inicial **"Documento Modelo"**
  (`documento_modelo=` protocolo do documento base — os modelos pré-definidos)
  ou nenhum; `nome_arvore` opcional; nível de acesso e hipótese legal reusam
  `nivel_acesso`. Após salvar, **confirma a criação pela abertura do editor**
  (janela nova), fecha-o e devolve o driver à janela principal — a edição de
  conteúdo será um módulo próprio. **Verificado ao vivo** no SEI 4.1.5 (MGI) —
  o que também valida o `gerar_documento` extraído (mesmo caminho de código).
- `integra_gov.sei.gerar_documento`: componente **reutilizável** com o preâmbulo da
  tela "Gerar Documento" (`abrir_gerar_documento(driver, tipo)`) — aciona
  "Incluir Documento", espera a tela carregar e seleciona o tipo pelo texto
  exato, com as robustezes verificadas ao vivo (reentrada no iframe na corrida
  do AJAX; reclique do ícone que não navega). **Extraído do
  `inserir_documento_externo`** (que agora o consome, sem mudança de
  comportamento) e usado também pelo `incluir_documento_interno`. Em caso de
  tipo não encontrado, a mensagem de erro **lista os tipos visíveis**.
- `integra_gov.sei.inserir_documento_externo`: inclui um **documento externo**
  (upload de arquivo) num processo aberto (`InserirDocumentoExterno.inserir()`,
  **devolve o `nome_arvore`** confirmado). O upload vai direto ao
  `<input type=file>` via Selenium — **sem `pywinauto`/janela nativa**, mantendo
  o subpacote SEI livre de dependências de desktop. Generaliza o módulo original:
  `tipo_serie` e `nome_arvore` obrigatórios (sem default), nível de acesso e
  hipótese legal reusam `nivel_acesso`; sem valores de órgão embutidos. Escopo
  atual: formato **nato-digital**. **Verificado ao vivo** no SEI 4.1.5 (MGI):
  série "Ficha", restrito + hipótese "Informação Pessoal", upload de PDF e save
  confirmados. Robusto à corrida do AJAX após "Incluir Documento" (reentra no
  iframe até a tela abrir) e ao clique que não navega (reclica o ícone).
- `integra_gov.sei.barra_icones`: componente **reutilizável** para clicar em ícones
  da barra do documento (`clicar_icone_barra(driver, titulo)`) — seleciona o nó
  na árvore, entra no iframe de visualização e clica no ícone pelo `title`.
  Usado pelo `inserir_documento_externo` e pelos futuros módulos de documento
  (Editar Conteúdo, Enviar Processo…). **Verificado ao vivo** no SEI 4.1.5.
- `integra_gov.sei.iniciar_processo`: criação de um novo processo
  (`IniciarProcesso.iniciar()`), **verificado ao vivo** no SEI 4.1.5
  (público e restrito + hipótese legal). **Devolve o número (NUP)** do processo
  criado, lido do título da aba — que também confirma a criação. Generaliza o
  que era específico de órgão: `tipo` obrigatório (sem default), nível de acesso
  e hipótese legal são parâmetros; especificação/assunto/interessado/observação
  opcionais. Retornos `bool` viraram exceção tipada `IniciarProcessoError`;
  detecta o alerta de validação do SEI (ex.: "Informe o nível de acesso") em vez
  de mentir "salvo".
- `integra_gov.sei.nivel_acesso`: componente **reutilizável** para o nível de acesso
  (Público/Restrito + hipótese legal), usado pelo `iniciar_processo` e pelos
  futuros módulos de documento — o nível é parâmetro e a hipótese é obrigatória
  no restrito (`configurar_nivel_acesso()`, exceção `NivelAcessoError`). A
  seleção da hipótese legal espera o dropdown (populado via AJAX) até o `timeout`,
  reconsultando o `<select>` a cada tentativa, tolera diferença de espaçamento/NBSP
  no texto e, se falhar, **lista as opções disponíveis** na mensagem de erro.
- **Subpacote `integra_gov.siape`** — automação do SIAPE pelo **terminal 3270**
  (emulador IBM HOD), como extra opcional Windows-only (`pip install
  integra-gov[siape]`, instala `pywinauto`); o `pywinauto` é importado de forma
  protegida, então o núcleo e a CI Linux seguem intactos. Camadas (sala limpa,
  exceções tipadas, **OTP/credencial nunca digitados pela lib — você autentica**):
  `acesso_web` (Selenium: SIAPENet → certificado → captura do OTP),
  `lancador` (executa o `hodcivws*.jsp` e abre o terminal),
  `controle` (ler tela via clipboard / enviar teclas),
  `conexao` (acesso/login com OTP + `acessar_transacao(">COMANDO")`),
  `habilitacao` (troca de habilitação ÓRGÃO/UPAG via `TROCAHAB`).
  **Verificado ao vivo** de ponta a ponta (web → OTP → HOD → terminal →
  trocahab → transação `>GRCOSITPRO`).
- `integra_gov.sei.navegador`: helper opcional `criar_driver_chrome()` que abre o
  Chrome já com os ajustes de ambiente gerenciado/gov (`--no-sandbox`,
  `--disable-dev-shm-usage`) e trata o erro "Chrome instance exited" / navegador
  que não abre por duas frentes: (a) **retry automático** (`tentativas=3`,
  `intervalo=1.0`) para a falha transitória de *cold start* (antivírus/EDR no
  primeiro launch) — verificado ao vivo: a 1ª tentativa falhou e a 2ª subiu; e
  (b) encerramento de `chromedriver` órfãos **antes de cada tentativa**. A
  limpeza padrão é segura (`encerrar_chromedriver_orfaos()`, não toca nas janelas
  pessoais); há a opção destrutiva opt-in `encerrar_chrome()` /
  `encerrar_todo_chrome=True`. Esgotadas as tentativas, levanta `NavegadorError`
  (encadeando a causa do Selenium). A lib continua headless: passar o seu próprio
  `driver` segue funcionando. Abre a janela **maximizada por padrão**
  (`maximizar=True`) — o SEI é responsivo e, em janela estreita, colapsa a barra
  de ícones e alguns elementos somem do DOM, quebrando a automação; no headless
  usa uma viewport larga (`--window-size=1920,1080`) pelo mesmo motivo.
- Guia de uso passo a passo: `docs/uso-basico.md` (sequência navegador → login →
  tela de aviso → unidade → processo e o porquê de cada passo).
- `integra_gov.sei.selecao_unidade`: `SelecaoUnidade.selecionar(sigla)` troca a
  unidade de trabalho (idempotente) e `listar_unidades()` devolve as unidades
  disponíveis como dados (`Unidade`: sigla, descrição, órgão, id) — para uma
  interface LOCAL oferecer a escolha (a biblioteca não inclui GUI). Seletores verificados ao vivo no SEI
  4.1.5: abre via `a#lnkInfraUnidade` e seleciona pelo radio cujo `title` é a
  sigla (que dispara `selecionarUnidade(id)` — sem botão de confirmar). Exceção
  `UnidadeNaoEncontrada`.
- `integra_gov.sei.tela_aviso`: `fechar_tela_aviso()` fecha o aviso que o SEI exibe
  após o login (e que bloqueia os demais campos). Chamado automaticamente por
  `LoginSei.logar()`. Idempotente; um seletor combinado evita esperas longas
  quando não há aviso.
- `integra_gov.sei.login`: autenticação no SEI (`LoginSei.logar()` e
  `montar_url_login()`), com **URL base e órgão parametrizáveis** (serve a
  qualquer órgão, não só ao MGI) e exceções `SeiLoginError` /
  `CredenciaisInvalidas`. Verificado ao vivo no SEI 4.1.5 (ColaboraGov/MGI):
  login + fechamento automático da tela de aviso confirmados.
- `integra_gov.sei.processo`: acesso a um processo existente via pesquisa rápida
  (`ProcessoSei.acessar()` e `.ir_para_raiz()`), com **validação real** do
  acesso (substitui o antigo stub que sempre retornava `True`) e reúso de
  `IframesSei` para navegar a árvore.
- `integra_gov.sei.exceptions`: hierarquia de exceções tipadas (`SeiError`,
  `SeiNavegacaoError`, `ProcessoNaoEncontrado`).
- Documentação de uso: quickstart no README e
  `examples/exemplo_abrir_processo.py`.
- `integra_gov.sei.iframes`: navegação entre os iframes do SEI, tolerante às
  estruturas do SEI 3.x e 4.x — `switch_to_iframe_visualizacao()` e a classe
  `IframesSei` (destinos `ARVORE`, `VISUALIZACAO`, `DOCUMENTO_HTML`), com retry
  para falhas transitórias e testes (Selenium mockado).
- Esqueleto inicial do pacote: estrutura, empacotamento (`pyproject.toml`),
  licença MIT, CI (GitHub Actions), `.gitignore` com proteção de dados pessoais
  e testes de fumaça.
