# Fundação e-SIAPE (navegação CIS + acesso + habilitação) — design

**Data:** 2026-08-05
**Subpacote alvo:** `integra_gov/esiape/` (novo)
**Estratégia:** reescrita guiada — módulos novos no padrão do integra-gov,
usando os módulos privados validados ao vivo (03-04/08/2026, lote real de 14
extrações sem falha) apenas como referência de comportamento. Nenhum dado
pessoal ou default de órgão embutido.

Este é o **ciclo E1 (fundação)** do e-SIAPE. O ciclo E2 (ficha anual
FPEMFICHAF + CDCOINDFUN + encadeamento multi-órgão) virá em spec própria,
em cima desta fundação.

## Contexto

O e-SIAPE web (`esiape.sigepe.gov.br`) é um front CIS (Software AG) de
mainframe: iframes que se revezam, popups modais próprios, cortina de
transição, sessão que renasce na tela de aviso do SERPRO. Automatizá-lo sem
conhecer essas mecânicas produz falhas silenciosas e lotes abortados. A
fundação empacota essas mecânicas de forma reutilizável: com ela, QUALQUER
transação e-SIAPE fica automatizável (valor entregável por si só).

Diferencial vs. o subpacote `siape` (3270): Selenium puro — multiplataforma,
sem pywinauto, sem extra de instalação além do núcleo.

## Escopo

**Entra (4 módulos):** `navegacao.py`, `acesso.py`, `habilitacao.py`,
`exceptions.py` — detalhados abaixo.

**Fica fora (decisões explícitas):**
- Ficha anual, CDCOINDFUN, multi-órgão → ciclo E2.
- Lote/checkpoint/disjuntor → orquestrador (integra-flow).
- Download de PDF via fetch→base64 → ciclo E2 (é da ficha).
- Digitação de PIN/senha do certificado — princípio "você autentica": a lib
  espera a confirmação, nunca toca credencial.

## API pública

```python
from integra_gov.sei import criar_driver_chrome   # factory reusado (DRY)
from integra_gov.esiape import AcessoEsiape, TrocaHabilitacaoEsiape

driver = criar_driver_chrome()
AcessoEsiape(driver).executar()                 # VOCÊ confirma no app SERPRO ID
TrocaHabilitacaoEsiape(driver, orgao="00000").trocar()
```

O driver Chrome vem de `integra_gov.sei.navegador` (retry + limpeza de
órfãos) — dependência declarada entre subpacotes em vez de duplicação.

### `navegacao.py` — alicerce CIS

Funções módulo-nível (driver como 1º argumento, sem estado de classe):

| função | contrato |
|---|---|
| `frames_visiveis(driver)` | caminhos de todos os frames `is_displayed()`, em profundidade (máx. 4) |
| `ir_para_frame(driver, caminho)` | posiciona no frame; `False` se sumiu |
| `procurar_em_frames(driver, seletor)` | 1º frame VISÍVEL com o seletor (deixa o driver nele) ou `None`; sempre re-enumera do topo |
| `esperar_seletor(driver, seletor, timeout)` | poll de `procurar_em_frames` |
| `overlay_presente(driver)` / `limpar_overlay(driver, timeout)` | cortina `#OPA`/`.FLASHPageSwitch` presa: espera sumir; persistindo, esconde via JS (decorativa) |
| `fechar_janelas_extras(driver, principal)` | fecha toda janela além da principal, devolve o foco; retorna o handle principal |
| `fechar_popups_cis(driver)` | fecha page-popups modais pelo X do TOPO (`td[id^='TITLEBAR'][id$='CLOSE']`); retorna quantos fechou |
| `garantir_menu(driver, timeout=60)` | máquina de estados até a lupa: fecha popup modal → clica Pular → clica AVANÇAR (aí seta flag de relogin) → repete; `False` no timeout |
| `navegar_para_transacao(driver, transacao, seletor_confirmacao, timeout)` | lupa → campo `w_transacao` → Ir; `True` SOMENTE se `seletor_confirmacao` apareceu; sem lupa → `garantir_menu` e, se relogin pendente, falha a tentativa de propósito |
| `relogin_pendente(driver)` / `limpar_flag_relogin(driver)` | flag: sessão renasceu (AVANÇAR clicado) e a habilitação voltou ao padrão do usuário — quem conhece o órgão re-habilita e limpa |

Seletores como constantes de módulo (valores observados ao vivo):
`SELETOR_LUPA='[data-testtoolid="onMenuClickPesqTrans"]'`,
`SELETOR_CAMPO_TRANSACAO='[data-testtoolid="w_transacao"]'`,
`SELETOR_BTN_IR='[data-testtoolid="onMenuClickBtnIr"]'`,
`SELETOR_HOME='[data-testtoolid="onMenuClickHome"]'`,
`SELETOR_OVERLAY="#OPA, .FLASHPageSwitch"`,
`SELETOR_BTN_AVANCAR='[data-testtoolid="meucert.onCheck"]'`,
`SELETOR_BTN_PULAR='[data-testtoolid="onClickBtnPular"]'`,
`SELETOR_POPUP_FECHAR="td[id^='TITLEBAR'][id$='CLOSE']"`.

### `acesso.py` — login SERPRO ID

`AcessoEsiape(driver, timeout_confirmacao=180)`:
- `executar()`: navega à URL do e-SIAPE (constante de classe), aciona o botão
  de certificado, **espera VOCÊ confirmar no app SERPRO ID** (poll de página
  pós-login até `timeout_confirmacao`), e atravessa as telas de entrada
  (Avançar → eventual aviso UORG → Pular) delegando a `garantir_menu`.
  Termina com a lupa acessível ou levanta `AutenticacaoNaoConfirmada` /
  `MenuInacessivel`.
- A lib NUNCA digita PIN/senha; logs não registram credenciais.

### `habilitacao.py` — TROCAHAB web

`TrocaHabilitacaoEsiape(driver, orgao)`:
- `trocar()`: idempotente pelo cabeçalho (`orgao_atual()` ==
  destino → não faz nada e **limpa a flag de relogin**); senão
  `navegar_para_transacao("TROCAHAB", ...)` → grade `table.TEXTGRIDTable`
  (linha 0 = cabeçalho; código do órgão na célula 1) → clique na linha →
  modal "Confirma ?" em frame próprio → `[data-testtoolid="onClickBtnSim"]`
  → confirmação REAL pelo cabeçalho `[data-testtoolid="w_menu_orgao_usu"]`
  refletir o novo órgão → volta ao menu (`SELETOR_HOME`) → **limpa a flag
  de relogin** (pendência sanada).
- `orgao_atual()`: órgão ativo lido do cabeçalho (ex.: `"40805"`), `None` se
  ilegível.
- Sem habilitação no destino → `HabilitacaoNaoEncontrada` (lista o que a
  grade mostrou).

### `exceptions.py`

`EsiapeError` (base) e filhas: `MenuInacessivel` (lupa não voltou nem após a
máquina de estados; mensagem inclui a dica do PIN do certificado),
`AutenticacaoNaoConfirmada` (timeout do app), `TransacaoNaoAbriu` (carrega a
transação e o `seletor_confirmacao` esperado), `HabilitacaoNaoEncontrada`
(carrega o órgão pedido e os códigos visíveis na grade). Mensagens dizem o
que o CIS mostrou, não o que o código esperava.

## Mecânicas CIS embutidas (comportamento validado ao vivo)

1. **Frames ocultos guardam telas ANTIGAS** — WA0/WA1/WA2 se revezam em ordem
   imprevisível; só o iframe visível é a tela atual. Buscar "em todos" acha
   elemento de tela morta. Toda busca re-enumera do topo.
2. **Popups modais fecham pelo X do TOPO** — o aviso "UORG DO CORREIO DO
   USUARIO DESATIVADA" é um page-popup (`pagepopupN`) cujo X
   (`onclick=closePageN_M()`) fica no documento raiz; esconder via CSS NÃO
   libera a navegação — é preciso CLICAR.
3. **Relogin derruba a habilitação** — a tela "REDE DE COMUNICAÇÃO SERPRO"
   (AVANÇAR) significa sessão nova com habilitação padrão. Sequência real:
   AVANÇAR → popup UORG (fechar pelo X) → Pular → lupa. `garantir_menu` só
   seta a flag quando clicou AVANÇAR; `navegar_para_transacao` com flag
   pendente falha a tentativa de propósito (consulta no órgão errado devolve
   "sem dados" FALSO = lacuna silenciosa); `trocar()` limpa a flag.
4. **Cortina presa** — `#OPA`/`.FLASHPageSwitch` (z-index 1000) fica presa
   quando uma operação morre no meio; todo clique seguinte falha com
   "element click intercepted". Esperar; persistindo, `display:none` via JS.
5. **Lupa, não menu** — navegação por transação só funciona pela lupa do
   cabeçalho; o campo `w_transacao` nasce oculto. Sucesso = o seletor
   exclusivo da tela-destino apareceu num frame visível (nunca falso
   positivo).
6. **TROCAHAB efetiva no "Sim"** — selecionar a linha da grade não basta; o
   modal "Confirma ?" em frame próprio é quem efetiva; e a troca só é
   declarada quando o CABEÇALHO reflete o novo órgão.

## Testes

Mockados (padrão da suíte): `MagicMock(spec=WebDriver)` com DOM roteirizado
(side effects de `find_elements`/`execute_script`/`switch_to`). Cenários
mínimos:

1. `procurar_em_frames` ignora iframe oculto que contém o seletor e acha o
   visível;
2. `garantir_menu`: popup modal fechado pelo X → Pular → lupa (sem AVANÇAR →
   flag NÃO setada);
3. `garantir_menu` com relogin completo: AVANÇAR → popup UORG → Pular → lupa,
   flag setada; popup respawnando N vezes converge;
4. `garantir_menu` timeout → `False` (e `MenuInacessivel` onde o chamador
   exigir);
5. `navegar_para_transacao`: sucesso confirmado pelo seletor da tela;
   tela não abriu → `False` com log; sem lupa + relogin atravessado → falha
   a tentativa e flag fica pendente; sem lupa + só popup perdido → segue e
   navega;
6. `limpar_overlay`: some sozinha; presa → escondida via JS;
7. `fechar_janelas_extras`: fecha extras e devolve o foco;
8. `TrocaHabilitacaoEsiape`: idempotente (cabeçalho já no destino) limpa a
   flag; troca completa com modal Confirma e confirmação pelo cabeçalho;
   órgão ausente na grade → `HabilitacaoNaoEncontrada`; cabeçalho não
   refletiu → erro honesto (não declara sucesso);
9. `AcessoEsiape`: confirmação detectada → atravessa entrada e termina na
   lupa; timeout do app → `AutenticacaoNaoConfirmada`.

## Verificação ao vivo (gate antes do merge)

Login real via SERPRO ID (você no app) → `garantir_menu` → troca de
habilitação ida-e-volta entre dois órgãos que você possui →
`navegar_para_transacao` numa transação de consulta inócua → leitura do
cabeçalho. Script em `dados_reais/` (gitignored). CHANGELOG registra
"Verificado ao vivo" com o que a verificação corrigiu.

## Documentação (junto com o módulo)

- README: seção nova `integra_gov.esiape` (tabela + exemplo).
- `docs/uso-basico.md`: seção com o fluxo, as 6 mecânicas CIS resumidas e a
  semântica da flag de relogin.
- CHANGELOG.

## Riscos e mitigação

- **Seletores `data-testtoolid` mudarem com versão do e-SIAPE:** constantes
  de módulo, ajustáveis sem fork; verificação ao vivo detecta.
- **Relogin pedindo PIN na janela do Windows:** fora do alcance do Selenium —
  `garantir_menu` expira com mensagem citando essa hipótese
  (`MenuInacessivel`).
- **Dependência de `integra_gov.sei.navegador`:** import no exemplo/docs,
  não no código do esiape (os módulos recebem o driver pronto) — o
  acoplamento fica só na conveniência documentada.
