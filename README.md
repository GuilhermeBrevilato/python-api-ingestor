# python-api-ingestor

## O que é
Cliente que busca dados de uma API e lida com falhas: erro de status HTTP,
falha de conexão e resposta em formato inválido.

Diante de uma falha, o cliente decide:
- se vale tentar de novo;
- quanto tempo esperar antes da nova tentativa;
- quando desistir.## O que é

## Como rodar
Requer Python 3.11 ou superior.

```bash
git clone https://github.com/GuilhermeBrevilato/python-api-ingestor.git
cd python-api-ingestor
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m ingestor.demo_http_retry
```

A demo roda quatro cenários de falha simulada e confere, em cada um, quantas chamadas
foram feitas e quanto tempo o cliente esperou.

## O que já funciona

- Nova tentativa para erros temporários: status 429 e 503, timeout de conexão e de leitura.
- Sem nova tentativa para erros permanentes (como 401 e 404) e para resposta em formato inválido.
- Espera entre tentativas com backoff exponencial, teto máximo e jitter, para evitar que vários
  clientes tentem de novo ao mesmo tempo.
- Respeito ao header `Retry-After`, em segundos ou em data HTTP. Se o header estiver ausente,
  inválido ou com uma data que já passou, o cliente volta ao backoff.
- Testes que simulam a API, o relógio e a espera, sem depender da internet e sem esperar
  tempo real.
- Limite de espera: se o servidor pedir para esperar mais que o orçamento (600 segundos
  por padrão), o cliente interrompe a extração com um erro claro, em vez de ficar parado.

## Documentação

- [Fluxo de decisão do cliente HTTP](docs/fluxo-retry.md): quando repetir, quanto esperar
  e quando desistir.

## Como o trabalho é organizado

As tarefas são planejadas em sprints de uma semana no Jira (projeto ING).
Toda mudança segue o mesmo caminho: card no Jira → branch → commits → pull request → merge no main.

A chave do card aparece em cada etapa, e o Jira liga tudo automaticamente ao card:

| Onde | Padrão | Exemplo |
|---|---|---|
| Branch | `tipo/CHAVE-descricao` | `docs/ING-6-convencao-jira` |
| Commit | `tipo(CHAVE): descrição` | `docs(ING-6): registra a convenção de nomes` |
| Pull request | `CHAVE: descrição` | `ING-6: registra a convenção de nomes` |

Tipos usados: `feat`, `fix`, `refactor`, `docs`, `chore`, `build` e `test`.