# Design: User Story — Prompt-Tab & Scoring-Button

**Datum:** 2026-03-29
**Status:** Approved

---

## Überblick

Zwei unabhängige Erweiterungen der `StoryDetail`-Ansicht:

1. **Prompt-Tab** — gespeichertes, KI-generiertes Prompt-Feld für Implementierungs-KIs
2. **Scoring-Button** — heuristisches Qualitäts-Scoring der Story (kein LLM)

---

## Feature 1: Prompt-Tab

### Datenbank

Neue Spalte in `user_stories`:

```sql
ALTER TABLE user_stories ADD COLUMN prompt TEXT NULL;
```

Alembic-Migration im Plugin (`plugins/user-story/backend/migrations/`), neue Datei `0002_story_prompt.py`.

### Backend

**Schema-Änderungen** (`plugins/user-story/backend/schemas.py`):
- `StoryRead`: neues Feld `prompt: Optional[str]`
- `StoryUpdate`: neues Feld `prompt: Optional[str]`

**Neuer Endpoint:**

```
POST /api/v1/organizations/{org_id}/stories/{story_id}/generate-prompt
```

- Permission: `story:update`
- Kein Request-Body nötig
- Lädt die Story, baut einen System-Prompt, ruft die bestehende AI-Pipeline auf (Task `suggest`, Komplexität aus `context_analyzer`)
- Speichert das Ergebnis in `story.prompt` (DB-Commit)
- Gibt `StoryRead` zurück

**Prompt-Template für die KI** (in `service.py`):

```
Du bist ein technischer Schreiber. Wandle die folgende User Story in einen präzisen,
vollständigen Implementierungs-Prompt um, den eine Coding-KI direkt verwenden kann.
Enthalt: Titel, Kontext, genaue Anforderungen, Acceptance Criteria, technische Hinweise.
Antworte nur mit dem Prompt-Text, keine Einleitung.

Story: {title}
Beschreibung: {description}
Acceptance Criteria: {acceptance_criteria}
```

### Frontend (`StoryDetail.tsx`)

**Tab-Navigation** im Hauptbereich (linke Spalte, 2/3-Breite):
- Tab "Details" — bisheriger Inhalt (Beschreibung, AC, Test Cases)
- Tab "Prompt" — neuer Inhalt

**Prompt-Tab-Inhalt:**
- Anzeige des `story.prompt`-Textes in einer `<pre>`-ähnlichen Box
- Button "Generieren" → `POST .../generate-prompt`, Ladezustand, aktualisiert story via `mutate`
- Button "Kopieren" (Clipboard-API) — nur sichtbar wenn Prompt vorhanden
- Im Edit-Modus: `<textarea>` statt read-only Anzeige, Feld wird mit `PATCH /stories/{id}` gespeichert

---

## Feature 2: Scoring-Button

### Backend

**Neuer Endpoint:**

```
POST /api/v1/organizations/{org_id}/stories/{story_id}/score
```

- Permission: `story:read`
- Kein Request-Body
- Lädt die Story, ruft `analyze_context(title, description, ac_string)` auf
- Ruft `score_complexity(context)` auf
- Gibt `StoryScoreResponse` zurück (kein DB-Write)

**Neues Schema** (`schemas.py`):

```python
class StoryScoreResponse(BaseModel):
    level: str          # "low" | "medium" | "high"
    confidence: float   # 0.0–1.0
    clarity: float      # 0.0–1.0
    complexity: float   # 0.0–1.0
    risk: float         # 0.0–1.0
    domain: str         # "technical" | "business" | "security" | "generic"
```

### Frontend (`StoryDetail.tsx`)

**Button im Header:**
- "Prüfen" neben dem "Bearbeiten"-Button (nicht-destruktiv, immer sichtbar)
- Im Edit-Modus: neben "Speichern" und "Abbrechen"
- Ladezustand während des API-Calls

**Score-Panel:**
- Erscheint inline unterhalb des Headers, über den Fehler/Erfolgs-Meldungen
- Zeigt: Complexity-Badge (`low`/`medium`/`high` farbig), drei horizontale Balken für Clarity / Complexity / Risk (0–100%), Domain-Label
- Verschwindet wenn "×" geklickt oder beim nächsten Speichern

---

## Komponenten-Übersicht

| Datei | Änderung |
|---|---|
| `plugins/user-story/backend/migrations/0002_story_prompt.py` | Neu: Migration |
| `plugins/user-story/backend/models.py` | +`prompt` Spalte |
| `plugins/user-story/backend/schemas.py` | +`prompt` in Read/Update, +`StoryScoreResponse` |
| `plugins/user-story/backend/service.py` | +`generate_prompt()`, +`score()` |
| `plugins/user-story/backend/routes.py` | +2 Endpoints |
| `plugins/user-story/frontend/components/StoryDetail.tsx` | Tab-Navigation, Prompt-Tab, Scoring-Button + Panel |

---

## Nicht in Scope

- Scoring-Ergebnisse werden nicht gespeichert
- Kein AI-Review (LLM-basiertes inhaltliches Feedback)
- Keine Änderung an bestehenden Status-Übergängen
