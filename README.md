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

A demo simula uma API que responde com erro 429 e depois com sucesso, e confere
se o cliente esperou o tempo certo antes de tentar de novo.

## O que já funciona

- Nova tentativa para erros temporários: status 429 e 503, timeout de conexão e de leitura.
- Sem nova tentativa para erros permanentes (como 401 e 404) e para resposta em formato inválido.
- Espera entre tentativas com backoff exponencial, teto máximo e jitter, para evitar que vários
  clientes tentem de novo ao mesmo tempo.
- Respeito ao header `Retry-After`, em segundos ou em data HTTP. Se o header estiver ausente
  ou inválido, o cliente volta ao backoff.
- Testes que simulam a API, o relógio e a espera, sem depender da internet e sem esperar
  tempo real.

## Documentação

- [Fluxo de decisão do cliente HTTP](docs/fluxo-retry.md): quando repetir, quanto esperar
  e quando desistir.