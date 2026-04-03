# IONOS AI Integration — Performance-Konzept

## Stateless Requests

- Jeder Request trägt seinen eigenen JWT — kein sticky-session-Bedarf
- LiteLLM als Gateway: ein einziger HTTP-Hop vor Provider

## Connection Reuse / Keep-Alive

- `openai-python` SDK verwendet intern `httpx.Client` mit Connection Pool
- IONOS-Adapter: ein `openai.OpenAI`-Instance pro Prozess (via `@lru_cache` in Registry)
- Kein neues Client-Objekt pro Request — Pool bleibt warm

## Model-List-Caching

IONOS `/v1/models` wird gecacht:
- In-Process: TTL-Dict in `ionos_adapter.py` (default 300s)
- Redis: LiteLLM cache mit `namespace: "litellm:cache"` und `ttl: 300`

## Streaming

- `/api/v1/ai/chat` verwendet SSE-Streaming für lange Antworten
- LiteLLM leitet Chunks direkt weiter — kein Buffering im Gateway
- IONOS unterstützt `stream: true` auf `/v1/chat/completions`

## Routing-Effizienz

- Kein "fan-out" zu mehreren Providern gleichzeitig
- `routing_matrix.resolve_model()` wählt deterministisch einen Provider
- Fallback nur bei belegbarem Fehler — nie spekulativ

## Timeouts

| Layer | Timeout | Konfiguriert in |
|-------|---------|----------------|
| IONOS chat (fast) | 30s | litellm/config.yaml |
| IONOS chat (quality) | 60s | litellm/config.yaml |
| IONOS reasoning | 90s | litellm/config.yaml |
| Anthropic | 90s | litellm/config.yaml |
| Retry max wait | 60s | router_settings.retry_after_max_wait |

## Queueing / Lastglättung

- Celery-Worker: `concurrency=2` (tunable via CELERY_CONCURRENCY)
- LiteLLM `allowed_fails: 2` + `cooldown_time: 60` verhindert Cascading-Failures
- Redis-Queue vor Celery-Tasks als Puffer für Burst-Szenarien
