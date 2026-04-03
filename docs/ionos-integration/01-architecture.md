# IONOS AI Integration — Zielarchitektur

## Überblick

IONOS AI wird als externer Provider über die OpenAI-kompatible API eingebunden.
Alle Modellanfragen laufen über LiteLLM als zentrales Gateway — das Backend spricht
nie direkt mit IONOS, Anthropic oder OpenAI.

## Komponentendiagramm

```
Internet
  │
  ▼
Traefik (TLS, Routing, Rate-Limit)
  │
  ├──► Frontend (Next.js :3000)     ← never touches AI APIs
  │
  └──► Backend API (FastAPI :8000)
         │
         ├──► LiteLLM Gateway (:4000)  ← ALL model traffic
         │      ├── IONOS (ionos-fast, ionos-quality, ionos-reasoning)
         │      ├── Anthropic (claude-sonnet-4-6, claude-haiku-4-5)
         │      └── OpenAI (fallback)
         │
         ├──► PostgreSQL (pgvector) ← internal RAG embeddings
         ├──► Redis           ← session, cache, Celery broker
         └──► n8n             ← workflow orchestration
```

## Request-Fluss (Chat Completion)

```
Frontend
  → POST /api/v1/ai/chat (JWT auth required)
  → Backend routers/ai.py
  → ai_story_service._make_client()
  → routing_matrix.resolve_model()   ← picks ionos-quality / claude-sonnet etc.
  → ProviderClient.call()
  → LiteLLM :4000  POST /v1/chat/completions
  → IONOS openai.ionos.com/openai/v1/chat/completions
  ← response + usage metrics logged
  ← SSE stream to Frontend (if streaming=true)
```

## Docker Compose Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| traefik | traefik:v3 | 80/443 | TLS termination, routing |
| frontend | custom Next.js | 3000 | UI |
| backend | custom FastAPI | 8000 | Business logic, AI orchestration |
| litellm | ghcr.io/berriai/litellm | 4000 | LLM gateway |
| litellm-postgres | postgres:16 | — | LiteLLM state |
| postgres | pgvector/pgvector:pg16 | — | Main DB + vectors |
| redis | redis:7 | — | Cache, broker |
| n8n | n8n | 5678 | Workflows |

## Provider-Logik

IONOS ist der primäre Provider wenn `IONOS_API_KEY` gesetzt ist.
Anthropic ist der primäre Provider für Dokumentationsgenerierung.
Jeder Provider ist über `PROVIDER_ROUTING_*`-Variablen konfigurierbar.
