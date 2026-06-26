# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado
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
