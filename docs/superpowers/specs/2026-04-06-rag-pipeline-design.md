# RAG Pipeline Design

> **For agentic workers:** Use superpowers:writing-plans to create the implementation plan from this spec.

**Goal:** Confluence, Jira und User Actions als persistente Wissensbasis in assist2 integrieren, um KI-Chat und Story-Generierung mit org-spezifischem Kontextwissen anzureichern.

**Architecture:** Option A — inkrementell auf bestehendem Stack. Kein neuer Microservice. pgvector (HNSW), Celery für Ingestion, async RAG-Injection mit Timeout in Chat und Story-Generierung.

**Tech Stack:** FastAPI, pgvector (PostgreSQL), Celery + Celery Beat, LiteLLM (`ionos-embed` / BAAI/bge-m3), Confluence REST API, Jira REST API v3, Redis

---

## 1. Datenschicht

### 1.1 Schema-Migration

Die bestehende Tabelle `document_chunks` muss auf `vector(1024)` migriert werden (bge-m3 liefert 1024 Dimensionen statt OpenAI's 1536).

- Neue Alembic-Migration: `DROP INDEX` auf altem IVFFlat-Index, `ALTER COLUMN embedding TYPE vector(1024)`, neuen HNSW-Index anlegen.
- HNSW-Parameter: `m=16, ef_construction=64` — guter Default für kontinuierliches Schreiben ohne Rebuild.

### 1.2 Neuer Source-Type

`source_type` Enum erhält den Wert `user_action`. Bestehende Werte bleiben: `nextcloud`, `karl_story`, `jira`, `confluence`.

### 1.3 Embedding-Modell

`rag_service.py` und `rag_tasks.py` werden von `text-embedding-3-small` auf `ionos-embed` umgestellt. Das Modell wird über LiteLLM aufgerufen (`POST /v1/embeddings`, model=`ionos-embed`). Alle Daten bleiben auf EU-Servern (IONOS Berlin).

---

## 2. Ingestion-Pipeline

### 2.1 Nachtlicher Sync (Celery Beat)

Täglich um 02:00 Uhr werden für alle aktiven Orgs folgende Tasks ausgeführt:
- `index_confluence_space(org_id)` — alle konfigurierten Space-Keys der Org
- `index_jira_tickets(org_id)` — alle offenen und kürzlich geänderten Issues

Bestehende Hash-Deduplizierung in `rag_tasks.py` verhindert unnötige Re-Embeddings für unveränderte Inhalte.

### 2.2 Webhook-Endpoints

Zwei neue FastAPI-Endpunkte in einem neuen Router `backend/app/routers/webhooks.py`:

**`POST /api/v1/webhooks/confluence`**
- Authentifizierung: Shared Secret im Header (`X-Webhook-Secret`)
- Payload: Confluence Page-Event (`page_created`, `page_updated`, `page_deleted`)
- Aktion: Löst `index_confluence_page.delay(org_id, page_id)` aus — nur die betroffene Seite, nicht den ganzen Space

**`POST /api/v1/webhooks/jira`**
- Authentifizierung: Shared Secret im Header (`X-Webhook-Secret`)
- Payload: Jira Issue-Event (`issue_created`, `issue_updated`, `issue_deleted`)
- Aktion: Löst `index_jira_ticket.delay(org_id, issue_key)` aus

Webhook-Secrets werden pro Org in der `organizations`-Tabelle als JSON-Feld `webhook_secrets` gespeichert (`{"confluence": "...", "jira": "..."`}). Beim Webhook-Empfang wird anhand des Secrets die Org ermittelt.

### 2.3 User Action Tracking

Drei Trigger-Punkte im bestehenden Backend:

**Story-Feedback:** In `backend/app/routers/stories.py` (oder dem Feedback-Endpoint) — bei Accept/Reject einer AI-Suggestion wird `index_user_action.delay(org_id, action_type, content)` aufgerufen. Content = Summary der akzeptierten/abgelehnten Story.

**Chat-Auszüge:** In `/ai/compact-chat` — nach der Zusammenfassung wird das Summary als `user_action`-Chunk indexiert, wenn die Zusammenfassung länger als 100 Zeichen ist.

**Workflow-Entscheidungen:** In `backend/app/routers/stories.py` bei Status-Änderungen (`status_update`) — Entscheidung (wer, was, wann) als Chunk gespeichert.

Alle User-Action-Chunks bekommen `source_type=user_action`, `source_ref=user_id`, `source_title="User Action: {action_type}"`.

---

## 3. RAG-Injection

### 3.1 Chat (`/ai/chat`)

In `backend/app/routers/ai.py` wird vor dem LLM-Call ein RAG-Retrieval eingefügt:

```
async def retrieve_with_timeout(query, org_id, db):
    try:
        return await asyncio.wait_for(rag_service.retrieve(query, org_id, db), timeout=0.8)
    except asyncio.TimeoutError:
        return None
```

- Bei Ergebnis (Score ≥ 0.50): Chunks werden als Kontext-Block **vor** die letzte User-Message injiziert.
- Format: `[Kontext aus {source_type}]\n{chunk_text}\n\n`
- Source-Labels: `[Confluence]`, `[Jira]`, `[Karl Story]`, `[Team-Wissen]`
- Bei Timeout oder kein Ergebnis: Chat läuft ohne Kontext — kein Fehler, kein Fallback nötig.
- Kein Frontend-Umbau nötig.

### 3.2 Story-Generierung (`ai_story_service.py`)

In `backend/app/services/ai_story_service.py` wird vor dem Story-Prompt ein RAG-Retrieval für ähnliche Stories, Jira-Tickets und Confluence-Doku eingefügt:

- Schwellwert: nur direkte Treffer (Score ≥ 0.75) um Halluzinationen zu vermeiden
- Abgerufen werden: bis zu 3 Chunks aus `source_type IN (jira, confluence, karl_story)`
- Kontext-Injection in den Prompt: `"Ähnliche Stories/Tickets in eurem System:\n{context}"`
- Kein Timeout-Pattern nötig hier (synchroner Flow, Nutzer wartet ohnehin auf Story-Generierung)

---

## 4. Konfiguration

Neue Env-Variablen in `infra/.env`:

```
CONFLUENCE_WEBHOOK_SECRET=<secret>
JIRA_WEBHOOK_SECRET=<secret>
RAG_CHAT_TIMEOUT_MS=800
RAG_STORY_SCORE_THRESHOLD=0.75
RAG_CHAT_SCORE_THRESHOLD=0.50
```

Celery Beat Schedule (in `backend/app/celery_app.py` oder `tasks/schedule.py`):

```python
"rag-nightly-sync": {
    "task": "app.tasks.rag_tasks.nightly_rag_sync",
    "schedule": crontab(hour=2, minute=0),
}
```

---

## 5. Nicht im Scope

- Admin-UI für Embedding-Management (separates Feature)
- Hybrid-Search (Keyword + Semantic) — kann später ergänzt werden
- Chunk-Reranking — HNSW + Score-Threshold reicht für Phase 1
- Multi-Org Webhook-Routing (jede Org registriert eigene Webhooks bei Confluence/Jira)
