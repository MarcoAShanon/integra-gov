# Design — `integra_gov.sei.acesso_externo` (acesso externo a processo)

*28/08/2026. Porte em sala limpa do `AcessoExterno` do projeto INTEGRA_3_5_PSS
(`SEI_Geral.py:5029`), ampliado para o ciclo completo da tela.*

## 1. Objetivo

Dar à lib pública o que a tela **"Gerenciar Disponibilizações de Acesso
Externo"** do SEI faz: conceder a uma pessoa de fora o acompanhamento de um
processo, listar as concessões ativas e cancelar uma concessão. O caso de uso
é real e está em produção no PSS (`integrador_mensageria_pss.py:375`): dar ao
interessado o acompanhamento do próprio processo.

**Fora de escopo:** a modalidade "Disponibilização de documentos" (acesso
parcial, com escolha de documentos por protocolo) — o PSS só usa a integral e
não há consumidor para a parcial; entra depois se aparecer demanda.

## 2. A fonte, e o que o porte corrige

A fonte preenche: `selEmailUnidade` (dropdown) → `txtDestinatario`
(autocomplete + ENTER na primeira sugestão) → `txtEmailDestinatario` →
`txaMotivo` → rádio `lblIntegral` → `txtDias` → `pwdSenha` →
`btnDisponibilizar`.

Correções do porte, além da parametrização:

- **Todo passo da fonte é `try/except` que loga o erro e SEGUE EM FRENTE** —
  ela "conclui" com campo não preenchido e sem clicar o botão. No porte, cada
  falha levanta `AcessoExternoError` com o campo no texto (princípio 4:
  mensagens honestas).
- A fonte confirma o autocomplete com **ENTER na primeira sugestão que vier**
  — pode selecionar o contato errado. O porte casa a sugestão **exata** (a
  lição do autocomplete do `enviar_processo`); sem sugestão → erro tipado
  dizendo que o contato não existe no SEI.
- A fonte **guarda a senha em `self.senha`**. No porte a senha é argumento do
  método, usada e descartada; nunca em atributo, log ou repr (princípio 2).
- A fonte não confirma o sucesso. O porte tem **confirmação positiva** (§5).

## 3. API

Módulo novo `integra_gov/sei/acesso_externo.py`:

```python
@dataclass(frozen=True)
class Disponibilizacao:
    destinatario: str
    email: str
    # As demais colunas (validade, situação, …) são FIXADAS PELO GATE ao vivo
    # (§9) — a fonte não lê a tabela e o layout dela não está registrado.

class AcessoExterno:
    """Pré-condição (igual aos irmãos): SEI autenticado e um processo aberto."""

    def __init__(self, driver, *, timeout: float = 10): ...

    def conceder(
        self,
        destinatario: str,
        email: str,
        motivo: str,
        validade_dias: int,
        senha: str,
        *,
        email_unidade: str | None = None,
    ) -> None: ...

    def listar(self) -> list[Disponibilizacao]: ...

    def cancelar(self, email: str) -> None: ...
```

Decisões de assinatura:

- **`email_unidade=None`:** se o dropdown tiver **uma** opção, usa-a; se tiver
  várias e o argumento for `None`, levanta `AcessoExternoError` com a lista
  das opções na mensagem (para o chamador copiar o texto exato). Explícito
  que não está no dropdown → mesmo erro.
- **`validade_dias: int`** — a fonte passava string; dias são um número.
- **`cancelar(email)`** mira pelo e-mail, único na tabela (destinatário
  homônimo não desambigua).
- **`listar()` devolve lista vazia** quando não há concessões — estado
  legítimo, não erro.
- **`senha` não é validada pela lib** (formato é problema do SEI); a recusa
  do SEI (alerta) vira erro tipado com o texto dele.

Nova exceção em `exceptions.py`, no padrão da casa:

```python
class AcessoExternoError(SeiError):
    """Falha ao conceder/listar/cancelar disponibilização de acesso externo:
    o ícone/formulário/campo não foi encontrado, o contato não existe no
    autocomplete, o SEI recusou a operação (alerta), a concessão pedida não
    está na lista, ou a confirmação pós-clique não pôde ser lida."""
```

Uma classe só, sem subclasses — nenhum consumidor precisa distinguir hoje;
se o integra-flow um dia ganhar um descritor disto, a granularidade se decide
lá (`excecoes_pre_efeito` etc.).

## 4. Navegação (pré-efeito — o funil já cobre)

Preâmbulo dos três verbos, compartilhado:

1. `ProcessoSei(driver).ir_para_raiz()` — o ícone pertence à barra do nó do
   **processo**; com um documento selecionado, a barra é outra.
2. Pausa de estabilização (`SETTLE_APOS_NO = 1.2`, a mesma constante e razão
   dos irmãos: o clique no nó dispara reload AJAX que "engole" o clique
   seguinte).
3. `clicar_icone_barra(ICONE, selecionar_no=False)` — o nó já está
   selecionado pelo passo 1; re-selecionar dispararia outro reload.
4. `switch_to_iframe_visualizacao` até o formulário/tabela.

Sessão caída em qualquer ponto daqui sai `SessaoExpiradaError` de graça — é o
funil instrumentado pela fatia `2026-08-27-sessao-caida-fora-do-funil`. O
módulo **não** adiciona sondas próprias (mesma decisão do §9 daquela spec:
campos de formulário não são instrumentados).

`ICONE = "Gerenciar Disponibilizações de Acesso Externo"` vem da fonte, que é
de SEI antigo — **o título exato no SEI 4.1.5 é fixado pelo gate** (§9).

## 5. `conceder` — a fronteira do efeito é o clique em Disponibilizar

**Pré-efeito** (falha → `AcessoExternoError` nomeando o campo):

1. dropdown `selEmailUnidade` (regra do §3);
2. `txtDestinatario` + autocomplete: espera a sugestão cujo texto casa o
   destinatário **exato**; clica-a; sem sugestão em tempo → erro "o contato
   {nome!r} não existe no SEI (cadastre-o ou confira a grafia)";
3. `txtEmailDestinatario`, `txaMotivo`, rádio `lblIntegral` (via JS se o
   label interceptar, como nos irmãos), `txtDias`, `pwdSenha`.

**Efeito:** clique em `btnDisponibilizar`.

**Pós-efeito** (a regra da fatia anterior, aplicada desde o nascimento):

- Alerta presente → recusa do SEI (senha errada, campo inválido): aceita o
  alerta e levanta `AcessoExternoError` com o texto do SEI. (Recusa = o SEI
  **não** registrou; o erro diz isso.)
- Sem alerta → **confirmação positiva**: relê a tela e exige a concessão
  (e-mail do destinatário) na lista de disponibilizações.
- **A releitura pós-clique NÃO usa o funil de iframes** — usa re-navegação
  local (`switch_to.default_content()` + switch cru para o frame, sem
  `levantar_se_sessao_expirada`). Motivo, gravado na spec
  `2026-08-27` e nos comentários de `enviar_processo`/`concluir_processo`:
  uma `SessaoExpiradaError` nascida DEPOIS do efeito faria um orquestrador
  repetir a operação. Falha na releitura → `AcessoExternoError` **ambígua**,
  com "a concessão pode ter sido registrada — confira a tela" na mensagem.

Este é o primeiro módulo da família com confirmação positiva de nascença —
`concluir_processo` e `enviar_processo` têm a sua anotada como endurecimento
futuro.

## 6. `listar`

Só leitura, sem efeito — usa o funil normalmente (sessão caída → tipada, sem
risco). Lê a tabela de disponibilizações e devolve `list[Disponibilizacao]`.
Tabela ausente ou vazia → `[]`. Linha que não puder ser interpretada →
`AcessoExternoError` (perda de dado nunca é silenciosa — mesmo princípio do
`ficha_financeira`).

## 7. `cancelar`

1. **Pré-efeito:** `listar()` internamente; e-mail ausente da lista → erro
   tipado "não há disponibilização ativa para {email!r}" (nada foi tocado).
2. **Efeito:** aciona o cancelamento da linha (ícone/link da própria linha) e
   trata a confirmação — alert e/ou senha, **o gate fixa qual** (§9).
3. **Pós-efeito:** releitura local (mesma regra do §5): o e-mail tem de ter
   sumido da lista; falha na releitura → erro ambíguo com "o cancelamento
   pode ter sido efetivado — confira a tela".

## 8. Testes (mockados, TDD)

Arquivo novo `tests/test_acesso_externo.py`, no idioma da casa (`_FakeWait`,
`EC` substituído, driver fake com roteamento por id). **Todo driver fake
nasce com `find_elements` explícito devolvendo `[]` por padrão** — a
armadilha do MagicMock verdadeiro está documentada no plano da fatia
anterior e não será paga de novo.

| # | Teste | Trava |
|---|---|---|
| 1 | caminho feliz do `conceder` (preenche tudo, clica, lista confirma) | §5 |
| 2 | dropdown com UMA opção e `email_unidade=None` → usa-a | §3 |
| 3 | dropdown com várias e `None` → erro com as opções na mensagem | §3 |
| 4 | `email_unidade` explícito ausente do dropdown → erro | §3 |
| 5 | autocomplete sem sugestão → "o contato não existe no SEI" | §5 |
| 6 | sugestão exata vence sugestão-prefixo | §5 |
| 7 | campo do formulário ausente → erro nomeando o campo | §5 |
| 8 | alerta pós-clique → erro com o texto do SEI | §5 |
| 9 | lista não confirma a concessão → erro ambíguo "pode ter sido registrada" | §5 |
| 10 | **a releitura pós-clique não chama o funil** (mock do funil grita se chamado após o clique) | §5 |
| 11 | caminho feliz do `listar` + tabela vazia → `[]` | §6 |
| 12 | linha ininterpretável → erro (não silencia) | §6 |
| 13 | caminho feliz do `cancelar` (some da lista) | §7 |
| 14 | `cancelar` de e-mail sem concessão → erro pré-efeito | §7 |
| 15 | `AcessoExternoError` herda de `SeiError`; exports no `__init__` | §3 |

O **teste 10 é o guardião da regra da fatia anterior** — é ele que impede
alguém de "simplificar" a releitura usando `switch_to_iframe_visualizacao` e
reintroduzir a `SessaoExpiradaError` pós-efeito.

Suíte completa + `ruff check .` na lib. O flow não é tocado por esta fatia
— nenhum descritor novo entra agora.

## 9. Gate ao vivo — se limpa sozinho

Script em `dados_reais/` (gitignored), processo de teste da
`MGI-SGP-DECIPEX-CGPAG-NUTEC`, o operador digita a senha. Roteiro:

1. `conceder` para **o e-mail do próprio operador** (o e-mail de
   disponibilização chega a ele mesmo; ninguém de fora é envolvido);
2. `listar` → a concessão está lá (confirma o §5 e fixa as **colunas reais**
   da tabela → campos do `Disponibilizacao`);
3. `cancelar` → fixa se o SEI pede senha ou só confirmação;
4. `listar` → a concessão sumiu. O gate termina sem estado pendurado.

O gate também fixa: o **título exato do ícone** no SEI 4.1.5 (a fonte é de
versão antiga); e **confere se o formulário tem `txtUsuario`** além do
`pwdSenha` — terceira tela com esse id; alimenta a pendência da sonda anotada
na spec `2026-08-27` §11 (a expectativa é que NÃO tenha: o campo de nome é
`txtDestinatario`).

Achados do gate → registro na própria spec (§ de registro), como sempre.

## 10. Convenções do commit

Doc no MESMO commit (memória `doc-ao-adicionar-modulo`): README (tabela de
módulos + exemplo), `CHANGELOG.md` (*Adicionado*), `docs/uso-basico.md`
(seção nova com o ciclo conceder → listar → cancelar). Nota "Verificado ao
vivo" após o gate. Branch própria, review final da branch antes do gate,
merge ff na main.
