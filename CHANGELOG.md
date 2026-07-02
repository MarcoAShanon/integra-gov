# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Alterado
- **BREAKING — namespace renomeado para `integra_gov`.** O pacote passou a
  importar como `integra_gov` (antes `integra`) e o nome de distribuição é
  `integra-gov` (`pip install integra-gov`). **Atualize os imports:**
  `from integra.sei import X` → `from integra_gov.sei import X`. Isso alinha o
  nome de instalação e o de importação (antes divergiam) e, principalmente,
  evita a colisão com o pacote interno `integra` — permitindo que ele passe a
  **consumir este como dependência** em vez de manter cópias divergentes.

### Adicionado
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
