# Karl Learning System — Phase 1: Org-Kontext & Quellanzeige

## Ziel

KI-Vorschläge (DoD, Testfälle, Features, Story-Verbesserungen) werden mit Wissen aus der eigenen Organisation angereichert. Jeder Vorschlag zeigt seine Herkunft — entweder als verlinkbare Org-Quelle (Story, Nextcloud-Dokument) oder als `✦ KI`-Badge wenn kein Org-Kontext verfügbar war.

## Architektur

Bestehende RAG-Infrastruktur (pgvector, `DocumentChunk`, LiteLLM-Embeddings) wird erweitert statt ersetzt. Zwei neue Felder und ein umbenanntes Feld in `DocumentChunk` tragen Provenienz-Metadaten. Alle vier Vorschlagstypen nutzen dasselbe Retrieval. Phase 2 (Jira) und Phase 3 (Confluence) fügen nur neue `source_type`-Werte hinzu — kein weiterer Schemachange.

**Tech Stack:** FastAPI, SQLAlchemy async, pgvector, Celery, LiteLLM, Next.js 14, TypeScript

---

## 1. Datenschema

### Migration 0025 — `document_chunks`

```sql
-- Umbenennen
ALTER TABLE document_chunks RENAME COLUMN file_path TO source_ref;

-- Neue Spalten
ALTER TABLE document_chunks ADD COLUMN source_type VARCHAR(32) NOT NULL DEFAULT 'nextcloud';
ALTER TABLE document_chunks ADD COLUMN source_url  TEXT;
ALTER TABLE document_chunks ADD COLUMN source_title TEXT;

-- Enum-Werte: 'nextcloud', 'karl_story'
-- Phase 2/3 fügt 'jira', 'confluence' hinzu — kein weiterer Schemachange
```

### Erweitertes ORM-Modell

```python
class SourceType(str, enum.Enum):
    nextcloud  = "nextcloud"
    karl_story = "karl_story"
    # Phase 2/3: jira = "jira", confluence = "confluence"

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id:           Mapped[uuid.UUID]
    org_id:       Mapped[uuid.UUID]
    source_ref:   Mapped[str]          # war: file_path — Nextcloud-Pfad ODER "story:{uuid}"
    source_type:  Mapped[SourceType]   # neu
    source_url:   Mapped[str | None]   # neu — interner Pfad oder externer Link
    source_title: Mapped[str | None]   # neu — Anzeigename für Badge
    file_hash:    Mapped[str]
    chunk_index:  Mapped[int]
    chunk_text:   Mapped[str]
    embedding:    Mapped[str | None]   # vector(1536)
    created_at:   Mapped[datetime]
```

---

## 2. Indexierungs-Pipeline

### Was wird indexiert

| Quelle | Chunk-Inhalt | Trigger |
|--------|-------------|---------|
| Story (title + description + AC) | Volltext | Status → `ready` oder `done` |
| DoD-Items | Jedes Item einzeln | Story-Status → `ready` oder `done` |
| Features | title + description | Feature-Status → `done` |
| Testfälle | title + steps + expected_result | result → `passed` |

### Celery Task: `index_story_knowledge`

**Datei:** `backend/app/tasks/rag_tasks.py`

```python
@celery_app.task
def index_story_knowledge(story_id: str, org_id: str, org_slug: str) -> None:
    """Indexiert Story + zugehörige DoD-Items, Features (done), Testfälle (passed)."""
    # 1. Lade Story + DoD-Items + Features (done) + Testfälle (passed) aus DB
    # 2. Baue Chunks:
    #    - Story: ein Chunk mit Volltext
    #    - DoD: je Item ein Chunk
    #    - Feature: je Feature ein Chunk
    #    - Testfall: je Testfall ein Chunk
    #    Alle mit:
    #      source_type  = "karl_story"
    #      source_ref   = f"story:{story_id}"
    #      source_url   = f"/{org_slug}/stories/{story_id}"
    #      source_title = f"Story: {story.title}"
    # 3. Lösche alle bestehenden Chunks mit source_ref = f"story:{story_id}"
    # 4. Embed alle Chunks via LiteLLM (batch, identisch zur Nextcloud-Indexierung)
    # 5. Persistiere neue Chunks
```

### Trigger-Punkte

**`PATCH /api/v1/user-stories/{id}`** — nach erfolgreichem Status-Wechsel:
```python
if new_status in ("ready", "done"):
    index_story_knowledge.delay(str(story.id), str(story.organization_id), org_slug)
```

**`PATCH /api/v1/test-cases/{id}`** — nach result → `passed`:
```python
if data.result == "passed":
    index_story_knowledge.delay(str(tc.story_id), str(tc.organization_id), org_slug)
```

---

## 3. Retrieval & Provenienz

### Erweitertes `RagChunk`

```python
@dataclass
class RagChunk:
    text:         str
    score:        float
    source_type:  str         # "karl_story" | "nextcloud"
    source_url:   str | None
    source_title: str | None

@dataclass
class RagResult:
    mode:    Literal["direct", "context", "none"]
    chunks:  list[RagChunk]
    context: str              # Prompt-Text unverändert
```

### Retrieval-Query pro Vorschlagstyp

| Vorschlagstyp | RAG-Query |
|---------------|-----------|
| Story-Suggest | `f"{title} {description}"` (bereits vorhanden) |
| DoD           | `f"{title} {description}"` |
| Testfälle     | `f"{title} {acceptance_criteria}"` |
| Features      | `f"{title} {description} {acceptance_criteria}"` |

### Prompt-Injektion (alle Typen identisch)

```
--- Org-Wissen (aus Karl / Nextcloud) ---
{chunk_text}
-----------------------------------------
```

### API-Response: `sources`-Feld

Jeder Vorschlag in der Response trägt Provenienz:

```json
{
  "suggestions": [
    {
      "text": "Unit Tests für alle API-Endpunkte",
      "sources": [
        {
          "title": "Story: Auth-Login",
          "url": "/acme/stories/abc-123",
          "type": "karl_story"
        }
      ]
    },
    {
      "text": "Dokumentation aktualisieren",
      "sources": []
    }
  ]
}
```

`sources: []` = pure KI, kein Org-Kontext gefunden.

---

## 4. Frontend — Quellanzeige

### `AISuggestionItem` — neue Props

```typescript
interface Source {
  title: string;
  url:   string;
  type:  "karl_story" | "nextcloud";
}

interface AISuggestionItemProps {
  text:     string;
  sources?: Source[];   // neu — von API mitgeliefert
  dragType?: string;
  // ...bestehende Props
}
```

### Badge-Rendering

```
Org-Quelle:   📄 Story: Auth-Login         (klickbar, Link zur Story)
Nextcloud:    📄 Architektur.pdf           (klickbar, öffnet in neuem Tab)
Pure KI:      ✦ KI                         (nicht klickbar, gedimmtes Grau)
```

**Regel:**
- `sources.length > 0` → Org-Quell-Badges mit Links
- `sources.length === 0` → `✦ KI`-Badge (kein Link)

```tsx
<div className="flex flex-wrap items-center gap-1 mt-1">
  {sources && sources.length > 0 ? (
    sources.map((s, i) => (
      <a
        key={i}
        href={s.url}
        target={s.type === "nextcloud" ? "_blank" : "_self"}
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="inline-flex items-center gap-1 text-[10px] text-[var(--ink-faint)]
                   hover:text-[var(--accent-red)] border border-[var(--paper-rule)]
                   rounded-sm px-1.5 py-0.5 transition-colors"
      >
        <FileText size={9} />
        {s.title}
      </a>
    ))
  ) : (
    <span className="inline-flex items-center gap-1 text-[10px] text-[var(--ink-faintest)]
                     border border-[var(--paper-rule)] rounded-sm px-1.5 py-0.5">
      <Sparkles size={9} />
      KI
    </span>
  )}
</div>
```

---

## Dateien — Übersicht

### Backend (erstellen / ändern)

| Datei | Änderung |
|-------|----------|
| `backend/migrations/versions/0025_knowledge_chunks.py` | Neu: source_ref, source_type, source_url, source_title |
| `backend/app/models/document_chunk.py` | file_path → source_ref, SourceType-Enum, neue Felder |
| `backend/app/services/rag_service.py` | RagChunk + RagResult um Provenienz erweitern |
| `backend/app/tasks/rag_tasks.py` | Neuer Task `index_story_knowledge` |
| `backend/app/services/ai_story_service.py` | RAG-Aufruf in DoD/Testfall/Feature-Funktionen ergänzen; `sources` in Response |
| `backend/app/routers/user_stories.py` | Task-Dispatch bei Status-Wechsel |
| `backend/app/routers/test_cases.py` | Task-Dispatch bei result → passed |
| `backend/app/schemas/user_stories.py` | `Source`-Schema, `sources`-Feld in Suggestion-Responses |

### Frontend (ändern)

| Datei | Änderung |
|-------|----------|
| `frontend/components/stories/AISuggestionItem.tsx` | `Source`-Interface, Badge-Rendering |
| `frontend/app/[org]/stories/[id]/page.tsx` | `sources` aus API-Response an `AISuggestionItem` weitergeben |

---

---

## 5. Feedback-Loop — abgelehnte Vorschläge

### Ziel

Vorschläge die der Nutzer explizit ablehnt, sollen bei künftigen Generierungen für diese Org nicht mehr erscheinen.

### Schema — neue Tabelle `suggestion_feedback`

```python
class SuggestionFeedback(Base):
    __tablename__ = "suggestion_feedback"
    id:              Mapped[uuid.UUID]   # PK
    organization_id: Mapped[uuid.UUID]   # Index — org-spezifisch
    suggestion_type: Mapped[str]         # "dod" | "test_case" | "feature" | "story"
    suggestion_text: Mapped[str]         # Text des abgelehnten Vorschlags (max 1000 Zeichen)
    feedback:        Mapped[str]         # "rejected" (Phase 1 nur Negativ-Signal)
    created_at:      Mapped[datetime]
```

Migration 0026.

### Backend — Endpoint

```
POST /api/v1/suggestions/feedback
Body: { suggestion_type, suggestion_text, feedback: "rejected" }
```

Speichert den Eintrag — kein Rückgabewert außer 204.

### Nutzung bei Generierung

Beim Aufbau jedes Suggestion-Prompts werden die letzten 20 abgelehnten Texte dieser Org geladen und als Negativliste injiziert:

```
--- Von der Organisation abgelehnte Vorschläge (nicht wiederholen) ---
- Unit Tests für alle Endpunkte
- Dokumentation auf Confluence veröffentlichen
----------------------------------------------------------------------
```

Die Abfrage ist lightweight (kein Embedding, kein Vektor-Lookup) — ein einfaches `SELECT ... WHERE organization_id = :org_id AND suggestion_type = :type ORDER BY created_at DESC LIMIT 20`.

### Frontend — Ablehnen-Button

`AISuggestionItem` bekommt ein `onReject?: () => void`-Prop. Bei Klick:
1. Lokale Optimistic-Entfernung aus der Liste
2. `POST /api/v1/suggestions/feedback` im Hintergrund

```
┌─────────────────────────────────────────────────────┐
│ ≡  Unit Tests für alle API-Endpunkte          [✕]  │
│    📄 Story: Auth-Login                             │
└─────────────────────────────────────────────────────┘
```

`✕`-Button (klein, nur bei Hover sichtbar) — gleiche Hover-Reveal-Logik wie der bestehende ExternalLink-Button.

---

## Dateien — Übersicht


---

---

## 6. Phase 2 — Jira-Tickets indexieren

### Ziel

Beim Import eines Jira-Tickets (`POST /jira/ai`) wird das Ticket in den Wissens-Index aufgenommen. Vorschläge können damit auf historische Jira-Tickets verweisen mit direktem Link zum Ticket.

### Abbruchbedingung

```python
jira_cfg = org.metadata_.get("integrations", {}).get("jira", {})
if not jira_cfg.get("base_url") or not jira_cfg.get("api_token_enc"):
    return  # Jira nicht konfiguriert — kein Index-Versuch
```

Kein Fehler, kein Log-Spam — stiller Abbruch.

### Was wird indexiert

| Quelle | Chunk-Inhalt |
|--------|-------------|
| Jira-Ticket | `f"{ticket_key}: {summary}\n{description_plaintext}"` |

```python
DocumentChunk(
    source_type  = "jira",
    source_ref   = f"jira:{ticket_key}",
    source_url   = f"{jira_base_url}/browse/{ticket_key}",
    source_title = f"Jira: {ticket_key} — {summary[:60]}",
    chunk_text   = f"{ticket_key}: {summary}\n{description}",
    ...
)
```

### Trigger

In `POST /jira/ai` (nach erfolgreicher Transformation zu User Story):
```python
index_jira_ticket.delay(ticket_key, org_id)
```

Celery Task `index_jira_ticket` in `rag_tasks.py` — lädt Ticket-Text aus `jira_story`-Tabelle, baut einen Chunk, embedded und persistiert.

### Frontend-Badge

```
🔗 Jira: ABC-123 — Login-Feature    (öffnet Jira-Ticket in neuem Tab)
```

---

## 7. Phase 3 — Confluence-Seiten indexieren

### Ziel

Confluence-Seiten aus konfigurierten Spaces werden indexiert und stehen als Wissensquelle für Vorschläge zur Verfügung — mit direktem Link zur Confluence-Seite.

### Abbruchbedingung

```python
conf_cfg = org.metadata_.get("integrations", {}).get("confluence", {})
if not conf_cfg.get("base_url") or not conf_cfg.get("api_token_enc"):
    return  # Confluence nicht konfiguriert — kein Index-Versuch
```

Stiller Abbruch in jedem Trigger-Punkt und Task.

### Was wird indexiert

Alle Seiten aus den in den Org-Einstellungen hinterlegten Confluence-Spaces. Pro Seite: Titel + Plaintext-Body in 2000-Zeichen-Chunks (identisch zur Nextcloud-Logik).

```python
DocumentChunk(
    source_type  = "confluence",
    source_ref   = f"confluence:{page_id}",
    source_url   = f"{confluence_base_url}/wiki/spaces/{space_key}/pages/{page_id}",
    source_title = f"Confluence: {page_title}",
    chunk_text   = f"{page_title}\n{page_body_plaintext}",
    ...
)
```

### Trigger

**Manuell on-demand** (Settings → Confluence → "Jetzt indexieren"-Button):
```
POST /api/v1/confluence/index
```
Startet Celery Task `index_confluence_space(org_id)`.

**Automatisch** bei erfolgreichem Confluence-Publish (`POST /confluence/publish`): Re-indexiert die betroffene Seite.

### Task: `index_confluence_space`

```python
@celery_app.task
def index_confluence_space(org_id: str) -> None:
    cfg = get_confluence_config(org_id)
    if not cfg:
        return  # Abbruchpunkt

    for space_key in cfg.space_keys:
        pages = confluence_service.list_pages(space_key)
        for page in pages:
            body = confluence_service.get_page_body_plaintext(page.id)
            chunks = chunk_text(f"{page.title}\n{body}")
            # Embed + persistiere (identisch zu Nextcloud-Logik)
```

### Frontend-Badge

```
📘 Confluence: Architektur-Übersicht    (öffnet Confluence-Seite in neuem Tab)
```

---

## Dateien — Übersicht

### Backend (erstellen / ändern)

| Datei | Änderung |
|-------|----------|
| `backend/migrations/versions/0025_knowledge_chunks.py` | Neu: source_ref, source_type, source_url, source_title |
| `backend/migrations/versions/0026_suggestion_feedback.py` | Neue Tabelle `suggestion_feedback` |
| `backend/app/models/document_chunk.py` | file_path → source_ref, SourceType-Enum (inkl. jira, confluence), neue Felder |
| `backend/app/models/suggestion_feedback.py` | Neues ORM-Modell |
| `backend/app/services/rag_service.py` | RagChunk + RagResult um Provenienz erweitern |
| `backend/app/tasks/rag_tasks.py` | `index_story_knowledge`, `index_jira_ticket`, `index_confluence_space` |
| `backend/app/services/ai_story_service.py` | RAG + Negativliste in allen Suggestion-Prompts |
| `backend/app/routers/user_stories.py` | Task-Dispatch bei Status-Wechsel |
| `backend/app/routers/test_cases.py` | Task-Dispatch bei result → passed |
| `backend/app/routers/jira.py` | Task-Dispatch nach Ticket-Import |
| `backend/app/routers/confluence.py` | Neuer Endpoint POST /confluence/index; Task-Dispatch nach Publish |
| `backend/app/routers/suggestions.py` | Neuer Router: POST /suggestions/feedback |
| `backend/app/schemas/user_stories.py` | `Source`-Schema, `sources`-Feld in Suggestion-Responses |

### Frontend (ändern)

| Datei | Änderung |
|-------|----------|
| `frontend/components/stories/AISuggestionItem.tsx` | `Source`-Interface, Badge-Rendering, `onReject`-Prop |
| `frontend/app/[org]/stories/[id]/page.tsx` | `sources` + `onReject` an `AISuggestionItem` weitergeben |
| `frontend/app/[org]/settings/page.tsx` | "Jetzt indexieren"-Button im Confluence-Tab |

---

## Nicht in Scope

- Embedding-Modell wechseln
- Automatischer Confluence-Sync-Scheduler (Phase 4)
