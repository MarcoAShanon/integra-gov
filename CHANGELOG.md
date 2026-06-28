# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado
- `integra.sei.navegador`: helper opcional `criar_driver_chrome()` que abre o
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
  `driver` segue funcionando.
- Guia de uso passo a passo: `docs/uso-basico.md` (sequência navegador → login →
  tela de aviso → unidade → processo e o porquê de cada passo).
- `integra.sei.selecao_unidade`: `SelecaoUnidade.selecionar(sigla)` troca a
  unidade de trabalho (idempotente) e `listar_unidades()` devolve as unidades
  disponíveis como dados (`Unidade`: sigla, descrição, órgão, id) — para uma
  interface LOCAL oferecer a escolha (a biblioteca não inclui GUI). Seletores verificados ao vivo no SEI
  4.1.5: abre via `a#lnkInfraUnidade` e seleciona pelo radio cujo `title` é a
  sigla (que dispara `selecionarUnidade(id)` — sem botão de confirmar). Exceção
  `UnidadeNaoEncontrada`.
- `integra.sei.tela_aviso`: `fechar_tela_aviso()` fecha o aviso que o SEI exibe
  após o login (e que bloqueia os demais campos). Chamado automaticamente por
  `LoginSei.logar()`. Idempotente; um seletor combinado evita esperas longas
  quando não há aviso.
- `integra.sei.login`: autenticação no SEI (`LoginSei.logar()` e
  `montar_url_login()`), com **URL base e órgão parametrizáveis** (serve a
  qualquer órgão, não só ao MGI) e exceções `SeiLoginError` /
  `CredenciaisInvalidas`. Verificado ao vivo no SEI 4.1.5 (ColaboraGov/MGI):
  login + fechamento automático da tela de aviso confirmados.
- `integra.sei.processo`: acesso a um processo existente via pesquisa rápida
  (`ProcessoSei.acessar()` e `.ir_para_raiz()`), com **validação real** do
  acesso (substitui o antigo stub que sempre retornava `True`) e reúso de
  `IframesSei` para navegar a árvore.
- `integra.sei.exceptions`: hierarquia de exceções tipadas (`SeiError`,
  `SeiNavegacaoError`, `ProcessoNaoEncontrado`).
- Documentação de uso: quickstart no README e
  `examples/exemplo_abrir_processo.py`.
- `integra.sei.iframes`: navegação entre os iframes do SEI, tolerante às
  estruturas do SEI 3.x e 4.x — `switch_to_iframe_visualizacao()` e a classe
  `IframesSei` (destinos `ARVORE`, `VISUALIZACAO`, `DOCUMENTO_HTML`), com retry
  para falhas transitórias e testes (Selenium mockado).
- Esqueleto inicial do pacote: estrutura, empacotamento (`pyproject.toml`),
  licença MIT, CI (GitHub Actions), `.gitignore` com proteção de dados pessoais
  e testes de fumaça.
