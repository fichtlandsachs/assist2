# Design: Nextcloud RAG — Org-sensitives Wissenssystem

**Datum:** 2026-03-26
**Status:** Approved
**Scope:** pgvector-basiertes RAG mit LiteLLM-Embeddings, Nextcloud als Wissensquelle, Direktantwort bei hoher Ähnlichkeit

---

## 1. Überblick

Dateien in der Nextcloud-Org-Ablage (`Organizations/{org_slug}/`) werden automatisch indexiert und als Wissensquelle für KI-Anfragen bei der User-Story-Erstellung genutzt. Jede Org sieht nur ihr eigenes Wissen. Bei sehr hoher Ähnlichkeit wird die Antwort direkt aus dem gespeicherten Chunk zurückgegeben — kein LLM-Call nötig.

---

## 2. Architektur

```
Nextcloud (WebDAV)
    ↓ Celery Task: index_org_documents
Text-Extraktion (pdfplumber / python-docx / plaintext)
    ↓
LiteLLM /embeddings  →  document_chunks (pgvector, org_id)
                                ↓
User Story AI-Suggest
    ↓
1. Query-Embedding via LiteLLM
2. Cosine-Similarity gegen document_chunks WHERE org_id = ?
3a. Score ≥ 0.92 → Direktantwort aus Chunk (kein LLM-Call)
3b. Score 0.50–0.92 → Top-3 Chunks als Kontext in Prompt
3c. Score < 0.50 → kein RAG-Kontext
```

---

## 3. Neue Dateien

| Datei | Zweck |
|---|---|
| `backend/migrations/versions/0019_document_chunks.py` | pgvector-Extension + `document_chunks`-Tabelle |
| `backend/app/models/document_chunk.py` | SQLAlchemy ORM-Model |
| `backend/app/services/rag_service.py` | Embedding, Retrieval, Schwellwert-Logik |
| `backend/app/tasks/rag_tasks.py` | Celery-Task `index_org_documents` |
| `backend/tests/unit/test_rag_service.py` | Unit-Tests RAG-Logik |
| `backend/tests/unit/test_rag_tasks.py` | Unit-Tests Index-Task |

## 4. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `backend/app/services/ai_story_service.py` | RAG-Kontext vor LLM-Call einfügen |
| `backend/app/routers/nextcloud.py` | Nach Upload `index_org_documents.delay(...)` auslösen |
| `backend/app/celery_app.py` | `app.tasks.rag_tasks` in `include` |
| `backend/requirements.txt` | `pdfplumber`, `python-docx`, `pgvector` |
| `infra/docker-compose.yml` | PostgreSQL-Image auf `pgvector/pgvector:pg16` wechseln |

---

## 5. Datenmodell

### `document_chunks`-Tabelle

```sql
id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
org_id       UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE
file_path    TEXT NOT NULL          -- "Organizations/acme/Handbuch.pdf"
file_hash    TEXT NOT NULL          -- SHA256, für Change-Detection
chunk_index  INTEGER NOT NULL       -- Position im Dokument
chunk_text   TEXT NOT NULL          -- max. 512 Tokens
embedding    vector(1536)           -- text-embedding-3-small via LiteLLM
created_at   TIMESTAMPTZ DEFAULT now()
```

**Indizes:**
- `ivfflat (embedding vector_cosine_ops)` — schnelle Nearest-Neighbor-Suche
- `(org_id, file_path)` — schnelle Invalidierung bei Dateiänderung

### Migration 0019

```python
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table("document_chunks", ...)
    op.execute("CREATE INDEX ... USING ivfflat (embedding vector_cosine_ops) WITH (lists=100)")
```

---

## 6. Indexierungs-Task

**Task:** `rag_tasks.index_org_documents(org_id: str, org_slug: str)`

**Flow:**
1. PROPFIND auf `Organizations/{org_slug}/` — Dateiliste holen
2. SHA256 jeder Datei gegen `file_hash` in DB prüfen — unveränderte überspringen
3. Datei via WebDAV herunterladen
4. Text extrahieren:
   - `.pdf` → pdfplumber (seitenweise)
   - `.docx` → python-docx
   - `.txt`, `.md` → direkt
   - Andere Typen → überspringen (WARNING-Log)
5. Text in Chunks aufteilen: 512 Tokens, 50 Token Overlap
6. Embedding via `POST {LITELLM_URL}/embeddings` (model: `text-embedding-3-small`)
7. Alte Chunks für `(org_id, file_path)` löschen, neue einfügen

**Trigger:**
- Direkt nach jedem Datei-Upload im Nextcloud-Router
- Celery-Beat täglich als Fallback (für extern hochgeladene Dateien)

---

## 7. RAG Service

### `rag_service.retrieve(query: str, org_id: UUID, db) -> RagResult`

```python
@dataclass
class RagResult:
    mode: Literal["direct", "context", "none"]
    chunks: list[str]        # leere Liste wenn mode=none
    direct_answer: str | None  # gesetzter Text wenn mode=direct
```

**Logik:**
1. Embedding des Query-Texts via LiteLLM
2. SQL: `SELECT chunk_text, 1-(embedding <=> $1) AS score FROM document_chunks WHERE org_id=$2 ORDER BY score DESC LIMIT 5`
3. Höchster Score entscheidet den Modus (Schwellwerte aus org-Config oder Defaults)

### Fehlerbehandlung

- LiteLLM nicht erreichbar → `RagResult(mode="none")` — RAG wird übersprungen
- DB-Query schlägt fehl → `RagResult(mode="none")`
- Datei-Extraktion fehlerhaft → Datei überspringen, Task läuft weiter

---

## 8. Prompt-Injection

In `ai_story_service.get_story_suggestions`, vor dem LLM-Call:

```python
rag = await rag_service.retrieve(f"{data.title} {data.description}", org_id, db)

if rag.mode == "direct":
    # Direktantwort — kein LLM-Call
    return AISuggestion(
        explanation=f"Aus Org-Wissensbank: {rag.direct_answer}",
        quality_score=None, dor_issues=[], ...
    )

if rag.mode == "context":
    context_block = "\n".join([f"[Kontext]\n{c}" for c in rag.chunks])
    # context_block wird in den System-Prompt eingefügt
```

**Prompt-Format bei Kontext:**
```
[Bestehender System-Prompt]

--- Org-Wissen (aus Nextcloud) ---
[Kontext 1]
"..."
[Kontext 2]
"..."
---------------------------------

[User-Prompt mit Story-Daten]
```

---

## 9. Konfiguration

Schwellwerte sind per Org im bestehenden `admin_config`-System konfigurierbar:

```json
{
  "section": "rag",
  "config_payload": {
    "rag_enabled": true,
    "rag_direct_threshold": 0.92,
    "rag_context_threshold": 0.50,
    "rag_max_chunks": 3,
    "embedding_model": "text-embedding-3-small"
  }
}
```

Defaults gelten wenn keine Org-Konfiguration vorhanden.

---

## 10. Umgebungsvariablen

```
LITELLM_URL=http://litellm:4000   # interner Docker-Hostname
LITELLM_API_KEY=...               # optional, falls LiteLLM Auth aktiviert
```

---

## 11. Tests

| Datei | Tests |
|---|---|
| `test_rag_service.py` | Retrieval-Modi (direct/context/none), Schwellwert-Logik, LiteLLM-Fehler-Fallback |
| `test_rag_tasks.py` | Index-Task: SHA256-Skip, PDF/DOCX/TXT-Extraktion, Chunk-Splitting, alte Chunks löschen |

---

## 12. Nicht in diesem Scope

- UI für "Welche Dokumente wurden als Kontext verwendet" (spätere Wave)
- Re-Ranking oder Hybrid-Search (BM25 + Vector)
- Indexierung von Mail-Anhängen
- Unterstützung von `.pptx`, `.xlsx` o.ä.
