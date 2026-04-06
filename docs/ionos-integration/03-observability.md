# IONOS AI Integration — Observability-Konzept

## Strukturierte Log-Zeilen

Alle AI-Aufrufe emittieren eine maschinenlesbare Log-Zeile:

```
provider_call request_id=<8-char-uuid> provider=<ionos|anthropic|openai>
  model=<alias> task=<suggest|docs> pipeline=<single|multi>
  latency_ms=<int> in_tokens=<int> out_tokens=<int>
  fallback=<True|False> status=<ok|error> [error=<ExceptionType>]
```

Rate-Limit-Events:
```
rate_limit provider=ionos attempt=2 delay_s=5.0 source=Retry-After request_id=abc
```

Fallback-Events:
```
provider_fallback from=openai to=anthropic reason=RateLimitError request_id=abc
```

## Request-ID-Korrelation

Jeder HTTP-Request bekommt eine 8-Zeichen-UUID in `X-Request-ID`.
Die ID wird in `ContextVar` gespeichert und in alle Log-Zeilen injiziert.

Middleware-Snippet (in `main.py` ergänzen):
```python
from app.core.observability import set_request_id
import uuid

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    set_request_id(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response
```

## LiteLLM-Metriken

LiteLLM loggt nativ als JSON (`json_logs: true`):
- Model, provider, latency, tokens, status

## Metriken-Dashboard (vorbereitet)

Grafana-Panels (via Loki log aggregation):
- Requests/min pro Provider
- P50/P95 Latenz pro Modell
- Token-Verbrauch kumuliert (Kosten-Proxy)
- Rate-Limit-Events / Fallback-Rate
- Error-Rate nach Provider

## Health-Check-Endpunkte

| Endpunkt | Service | Zweck |
|---------|---------|-------|
| GET /health | Backend | FastAPI liveness |
| GET /metrics | LiteLLM | Token/latency metrics |
| GET /v1/models | LiteLLM | Provider-Verfügbarkeit testen |
