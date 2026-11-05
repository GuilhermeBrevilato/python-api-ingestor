# Fluxo de decisão do cliente HTTP: quando repetir, quanto esperar e quando desistir.

# Caixas em âmbar = mudanças da unidade 10B (a implementar).

## Nível macro: a decisão de repetir (`extrair_com_retry`)

```mermaid
flowchart TD
    A["Início da tentativa N"] --> B["Calcula backoff<br/>min(pausa × 2^N, teto) e sorteia jitter"]
    B --> C["GET na URL"]
    C -->|"timeout de conexão ou leitura"| T{"Última tentativa?"}
    T -->|"sim"| Y(["Log e raise:<br/>tentativas esgotadas"])
    T -->|"não"| L["Espera = backoff com jitter"]
    C -->|"resposta recebida"| D{"Status de erro?<br/>raise_for_status"}
    D -->|"não"| E["resposta.json()"]
    E -->|"JSON válido"| F(["Retorna os dados"])
    E -->|"JSON inválido"| W(["Log e raise:<br/>sem retry"])
    D -->|"sim"| G{"Status em STATUS_RETRY?"}
    G -->|"não: 401, 404"| X(["Log e raise:<br/>falha permanente"])
    G -->|"sim: 429, 503"| H{"Última tentativa?"}
    H -->|"sim"| Y
    H -->|"não"| I["Lê o header Retry-After<br/>e o relógio injetado"]
    I --> J[["interpretar_retry_after<br/>devolve segundos ou None"]]
    J --> K{"segundos é None?"}
    K -->|"sim"| L
    K -->|"não"| M{"segundos ≤ orçamento?"}
    M -->|"sim"| N["Espera = segundos<br/>origem Retry-After"]
    M -->|"não"| Z(["Raise EsperaExcedeOrcamento"])
    L --> O["await aguardar(espera)"]
    N --> O
    O -->|"próxima tentativa"| A
    
```

## Nível micro: como o header vira segundos (`interpretar_retry_after`)

```mermaid
flowchart TD
    A["valor do header Retry-After"] --> B{"valor é None?"}
    B -->|"sim"| R0(["devolve None<br/>o macro usa backoff"])
    B -->|"não"| C{"int(valor) funciona?"}
    C -->|"sim"| E{"segundos < 0?"}
    E -->|"sim"| R0
    E -->|"não, inclusive 0"| R1(["devolve os segundos<br/>0 é honrado"])
    C -->|"não"| D["parsedate_to_datetime(valor)"]
    D --> F{"data válida?"}
    F -->|"não"| R0
    F -->|"sim"| G["restante = data − agora"]
    G --> H{"restante > 0?"}
    H -->|"não: data vencida"| R0
    H -->|"sim"| R2(["devolve restante<br/>em segundos, float"])
    
```

## Decisões registradas

- `Retry-After: 0` em segundos é instrução explícita do servidor: honrar.
- Data vencida não é "tente agora": é valor velho ou relógio divergente. Devolve `None` e o macro usa backoff com jitter, que evita retries sincronizados.
- Orçamento: a espera pedida pelo `Retry-After` é limitada pelo parâmetro `orcamento_espera`, com padrão de 600 segundos. Pedido acima disso interrompe a extração com `EsperaExcedeOrcamento`. O backoff tem teto próprio (`espera_maxima`).
