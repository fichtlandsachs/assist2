# Design: User Story — Scoring-Button

**Datum:** 2026-03-29
**Status:** Approved

---

## Überblick

Heuristischer Qualitäts-Scoring-Button in der `StoryDetail`-Ansicht (kein LLM, kein DB-Write).

---

## Backend

**Neuer Endpoint:**

```
POST /api/v1/organizations/{org_id}/stories/{story_id}/score
```

- Permission: `story:read`
- Kein Request-Body
- Lädt die Story, ruft `analyze_context(title, description, ac_string)` auf
- Ruft `score_complexity(context)` auf
- Gibt `StoryScoreResponse` zurück (kein DB-Write)

**Neues Schema** (`plugins/user-story/backend/schemas.py`):

```python
class StoryScoreResponse(BaseModel):
    level: str          # "low" | "medium" | "high"
    confidence: float   # 0.0–1.0
    clarity: float      # 0.0–1.0
    complexity: float   # 0.0–1.0
    risk: float         # 0.0–1.0
    domain: str         # "technical" | "business" | "security" | "generic"
```

---

## Frontend (`StoryDetail.tsx`)

**Button im Header:**
- "Prüfen" neben dem "Bearbeiten"-Button (immer sichtbar, nicht-destruktiv)
- Im Edit-Modus: neben "Speichern" und "Abbrechen"
- Ladezustand während des API-Calls

**Score-Panel:**
- Erscheint inline unterhalb des Headers, über Fehler/Erfolgs-Meldungen
- Zeigt: Complexity-Badge (`low`/`medium`/`high` farbig), drei horizontale Balken für Clarity / Complexity / Risk (0–100%), Domain-Label
- Verschwindet bei Klick auf "×" oder beim nächsten Speichern

---

## Komponenten-Übersicht

| Datei | Änderung |
|---|---|
| `plugins/user-story/backend/schemas.py` | +`StoryScoreResponse` |
| `plugins/user-story/backend/service.py` | +`score()` Methode in `StoryService` |
| `plugins/user-story/backend/routes.py` | +`POST /{story_id}/score` Endpoint |
| `plugins/user-story/frontend/components/StoryDetail.tsx` | +Scoring-Button + Score-Panel |

---

## Nicht in Scope

- Scoring-Ergebnisse werden nicht gespeichert
- Kein AI-Review (LLM-basiertes inhaltliches Feedback)
- Keine Änderung an bestehenden Status-Übergängen
- Keine Prompt-Tab-Änderungen
