# IONOS AI Integration — Security-Konzept

## Secrets-Management

| Secret | Speicherort | Niemals in |
|--------|------------|------------|
| IONOS_API_KEY | infra/.env | Code, Frontend, Logs, Images |
| ANTHROPIC_API_KEY | infra/.env | — |
| LITELLM_MASTER_KEY | infra/.env | — |

Rotation: `.env` aktualisieren → Container neu starten. Kein Build nötig.

## API-Key-Sicherheit

- Keys werden per `os.environ/KEY_NAME` in LiteLLM-Config referenziert (nie im YAML-Text)
- Backend liest Keys nur via `pydantic-settings` (`get_settings()`) zur Laufzeit
- LiteLLM-Config: `log_raw_request_response: false` — keine Prompts in Logs
- `return_response_headers: false` — keine internen Modell-IDs nach außen

## Request-Authentifizierung

```
Browser  →  JWT Bearer  →  Traefik  →  Backend
                                         │
                                         └─ get_current_user() dependency
                                            (JWT validation + org-scope check)
```

LiteLLM-Endpunkt ist nicht direkt aus dem Internet erreichbar (internes Docker-Netz).
Nur der Backend-Container darf LiteLLM erreichen.

## Rate-Limit-Schutz (intern)

- Traefik: InFlightReq-Middleware begrenzt gleichzeitige Anfragen pro IP
- Backend: Redis-basiertes per-Org Limit (vorbereitet via AI_USAGE_LIMIT_PER_ORG)
- LiteLLM: `allowed_fails: 2` + `cooldown_time: 60s` pro Modell

## Eingaben

- Strenge Pydantic-Validierung aller Request-Bodies (FastAPI dependency)
- System-Prompt ist immer der erste Nachrichteneintrag und klar vom User-Input getrennt
- Keine direkte SQL-Interpolation von Nutzereingaben (SQLAlchemy ORM)

## Audit-Logging

Jeder Provider-Aufruf loggt:
```
provider_call request_id=abc123 provider=ionos model=ionos-quality
  task=suggest pipeline=single latency_ms=842
  in_tokens=312 out_tokens=198 fallback=False status=ok
```

Kein Prompt-Text, keine API-Keys in diesen Log-Zeilen.

## Admin-Endpunkte

- `/api/v1/admin/*` → `is_superuser` Dependency (FastAPI)
- LiteLLM-UI → Traefik BasicAuth Middleware
- pgAdmin → intern, nicht über Traefik exponiert in Production
