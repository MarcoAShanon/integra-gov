# Como contribuir

Obrigado por ajudar! Este projeto nasceu para apoiar servidores públicos.

## Antes de tudo: dados sensíveis

- **Nunca** inclua dados reais (CPF, nomes, números de processo, e-mails de terceiros) em código, exemplos, testes ou mensagens de commit.
- Use sempre valores fictícios:
  - CPF: `111.111.111-11`
  - E-mail: `fulano@example.com`
  - Processo SEI: `00000.000000/0000-00`

## Ambiente

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```

## Padrões

- Código e docstrings em **português** (domínio público brasileiro).
- _Type hints_ onde fizer sentido.
- Todo novo comportamento acompanha **teste** (mockando o Selenium quando envolver navegador).
- **Parametrize** o que for específico de um órgão/unidade — nada embutido no código.

## Fluxo

1. Abra uma _issue_ descrevendo o que pretende fazer.
2. Faça um _fork_ e um _branch_.
3. Garanta `pytest` e `ruff` verdes.
4. Abra um _Pull Request_.
