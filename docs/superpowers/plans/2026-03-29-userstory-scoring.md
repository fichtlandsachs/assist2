# User Story Scoring-Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Einen "Prüfen"-Button in der StoryDetail-Ansicht hinzufügen, der heuristisches Scoring (Clarity / Complexity / Risk) anzeigt — ohne LLM, ohne DB-Write.

**Architecture:** Neuer `POST /score`-Endpoint im Plugin ruft deterministisch `analyze_context` + `score_complexity` auf und gibt ein `StoryScoreResponse` zurück. Das Frontend zeigt das Ergebnis als kleines Panel direkt unterhalb des Headers.

**Tech Stack:** FastAPI, Pydantic v2, Python 3.12, Next.js 14, TypeScript, Tailwind CSS, SWR

---

## File Map

| Datei | Aktion |
|---|---|
| `plugins/user-story/backend/schemas.py` | Modify — `StoryScoreResponse` hinzufügen |
| `plugins/user-story/backend/service.py` | Modify — `score()` Methode in `StoryService` |
| `plugins/user-story/backend/routes.py` | Modify — `POST /{story_id}/score` Endpoint |
| `backend/tests/unit/test_story_score.py` | Create — Unit Tests für Scoring-Logik |
| `plugins/user-story/frontend/components/StoryDetail.tsx` | Modify — Button + Score-Panel |

---

## Task 1: StoryScoreResponse Schema

**Files:**
- Modify: `plugins/user-story/backend/schemas.py`

- [ ] **Step 1: `StoryScoreResponse` ans Ende der Datei anhängen**

Direkt nach dem `TestCaseRead`-Block in `schemas.py` einfügen:

```python
# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class StoryScoreResponse(BaseModel):
    level: str       # "low" | "medium" | "high"
    confidence: float
    clarity: float
    complexity: float
    risk: float
    domain: str      # "technical" | "business" | "security" | "generic"
```

- [ ] **Step 2: Commit**

```bash
git add plugins/user-story/backend/schemas.py
git commit -m "feat(user-story): add StoryScoreResponse schema"
```

---

## Task 2: score() Service-Methode

**Files:**
- Modify: `plugins/user-story/backend/service.py`

- [ ] **Step 1: Imports ergänzen**

Am Anfang von `service.py` die bestehende Import-Sektion erweitern:

```python
from app.ai.context_analyzer import analyze_context
from app.ai.complexity_scorer import score_complexity
```

Und in den Schema-Imports `StoryScoreResponse` hinzufügen:

```python
from .schemas import (
    AIDeliveryResponse,
    StoryCreate,
    StoryFilter,
    StoryScoreResponse,
    StoryUpdate,
    TestCaseCreate,
    TestCaseUpdate,
)
```

- [ ] **Step 2: `score()` Methode in `StoryService` hinzufügen**

Direkt nach `trigger_ai_delivery()`, noch innerhalb der `StoryService`-Klasse:

```python
async def score(
    self,
    db: AsyncSession,
    org_id: uuid.UUID,
    story_id: uuid.UUID,
) -> StoryScoreResponse:
    """Run heuristic scoring on a story. No DB write, no LLM."""
    story = await self.get(db, org_id, story_id)

    ac_string = "\n".join(story.acceptance_criteria or [])
    context = analyze_context(story.title, story.description, ac_string)
    complexity = score_complexity(context)

    return StoryScoreResponse(
        level=complexity.level,
        confidence=complexity.confidence,
        clarity=context.clarity,
        complexity=context.complexity,
        risk=context.risk,
        domain=context.domain,
    )
```

- [ ] **Step 3: Commit**

```bash
git add plugins/user-story/backend/service.py
git commit -m "feat(user-story): add score() to StoryService"
```

---

## Task 3: Unit Tests für Scoring-Logik

**Files:**
- Create: `backend/tests/unit/test_story_score.py`

- [ ] **Step 1: Test-Datei anlegen**

```python
"""Unit tests for story scoring logic (deterministic, no DB, no LLM)."""
import pytest

from app.ai.context_analyzer import analyze_context
from app.ai.complexity_scorer import score_complexity


def test_score_well_specified_story_is_low_or_medium():
    """A clear, simple story should not score high."""
    ctx = analyze_context(
        title="Button Farbe ändern",
        description="Der primäre Button soll blau statt grün sein.",
        acceptance_criteria="1. Button ist blau\n2. Hover-Effekt bleibt erhalten",
    )
    score = score_complexity(ctx)
    assert score.level in ("low", "medium")
    assert 0.0 <= score.confidence <= 1.0
    assert 0.0 <= ctx.clarity <= 1.0
    assert 0.0 <= ctx.complexity <= 1.0
    assert 0.0 <= ctx.risk <= 1.0
    assert ctx.domain in ("technical", "business", "security", "generic")


def test_score_security_story_scores_high():
    """A story with security keywords and risk terms should score high."""
    ctx = analyze_context(
        title="Passwort Reset mit Token Validierung",
        description=(
            "Nutzer können ihr Passwort zurücksetzen. "
            "Ein sicherer Token wird per Email verschickt. "
            "DSGVO-konforme Speicherung. Admin-Permission erforderlich."
        ),
        acceptance_criteria=(
            "1. Token ist 24h gültig\n"
            "2. Token wird nach Verwendung invalidiert\n"
            "3. Compliance-Log wird geschrieben"
        ),
    )
    score = score_complexity(ctx)
    assert score.level == "high"
    assert ctx.domain == "security"


def test_score_empty_story_fields():
    """Empty fields should not raise — and should produce valid output."""
    ctx = analyze_context(title="", description=None, acceptance_criteria=None)
    score = score_complexity(ctx)
    assert score.level in ("low", "medium", "high")
    assert ctx.domain in ("technical", "business", "security", "generic")


def test_score_response_fields_are_floats():
    """All score fields must be floats in 0.0–1.0 range."""
    ctx = analyze_context(
        title="API Endpoint für Dateiupload",
        description="REST-Endpoint der Dateien via Multipart akzeptiert und in S3 speichert.",
        acceptance_criteria="1. Max 10MB\n2. Nur PDF und PNG",
    )
    score = score_complexity(ctx)
    for val in (ctx.clarity, ctx.complexity, ctx.risk, score.confidence):
        assert isinstance(val, float)
        assert 0.0 <= val <= 1.0
```

- [ ] **Step 2: Tests ausführen und sicherstellen dass sie bestehen**

```bash
cd /opt/assist2 && docker exec assist2-backend pytest backend/tests/unit/test_story_score.py -v
```

Erwartete Ausgabe: 4 passed

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_story_score.py
git commit -m "test(user-story): add unit tests for story scoring logic"
```

---

## Task 4: Score-Endpoint in routes.py

**Files:**
- Modify: `plugins/user-story/backend/routes.py`

- [ ] **Step 1: `StoryScoreResponse` zu den Schema-Imports hinzufügen**

Den bestehenden Import-Block anpassen:

```python
from .schemas import (
    AIDeliveryRequest,
    AIDeliveryResponse,
    PaginatedResponse,
    StatusTransitionRequest,
    StoryCreate,
    StoryFilter,
    StoryList,
    StoryPriority,
    StoryRead,
    StoryScoreResponse,
    StoryStatus,
    StoryUpdate,
    TestCaseCreate,
    TestCaseRead,
    TestCaseUpdate,
)
```

- [ ] **Step 2: Score-Endpoint nach `trigger_ai_delivery` einfügen**

Direkt nach dem `ai-delivery`-Endpoint, vor dem `# Test Cases`-Kommentar:

```python
@router.post(
    "/{story_id}/score",
    response_model=StoryScoreResponse,
    summary="Score Story Quality (Heuristic)",
)
async def score_story(
    org_id: uuid.UUID,
    story_id: uuid.UUID,
    current_user: User = Depends(require_permission("story:read")),
    db: AsyncSession = Depends(get_db),
) -> StoryScoreResponse:
    return await story_service.score(db, org_id, story_id)
```

- [ ] **Step 3: Backend neu starten und Endpoint manuell testen**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
```

Dann mit einer vorhandenen Story-ID testen:
```bash
curl -s -X POST \
  "http://localhost:8000/api/v1/organizations/<org_id>/stories/<story_id>/score" \
  -H "Authorization: Bearer <token>" | python3 -m json.tool
```

Erwartete Ausgabe:
```json
{
  "level": "low",
  "confidence": 0.45,
  "clarity": 0.35,
  "complexity": 0.12,
  "risk": 0.0,
  "domain": "business"
}
```

- [ ] **Step 4: Commit**

```bash
git add plugins/user-story/backend/routes.py
git commit -m "feat(user-story): add POST /score endpoint"
```

---

## Task 5: Frontend — Scoring-Button und Score-Panel

**Files:**
- Modify: `plugins/user-story/frontend/components/StoryDetail.tsx`

- [ ] **Step 1: `StoryScoreResponse` Typ und neuen State oben in der Datei ergänzen**

Den bestehenden Type-Block erweitern (nach `StoryDetailProps`):

```typescript
interface StoryScoreResponse {
  level: "low" | "medium" | "high";
  confidence: number;
  clarity: number;
  complexity: number;
  risk: number;
  domain: string;
}
```

Innerhalb von `StoryDetail`, nach den bestehenden State-Deklarationen (`isAIDeliveryPending`, `actionError`, `actionSuccess`):

```typescript
const [score, setScore] = useState<StoryScoreResponse | null>(null);
const [isScoring, setIsScoring] = useState(false);
```

- [ ] **Step 2: `handleScore` Handler hinzufügen**

Direkt nach `handleAIDelivery`:

```typescript
const handleScore = async () => {
  setIsScoring(true);
  setScore(null);
  try {
    const result = await apiRequest<StoryScoreResponse>(
      `/api/v1/organizations/${orgSlug}/stories/${storyId}/score`,
      { method: "POST" }
    );
    setScore(result);
  } catch (err) {
    setActionError(err instanceof Error ? err.message : "Scoring fehlgeschlagen");
  } finally {
    setIsScoring(false);
  }
};
```

- [ ] **Step 3: "Prüfen"-Button im Header ergänzen**

Den bestehenden Button-Block im Header (`<div className="flex gap-2 shrink-0">`) anpassen:

```tsx
<div className="flex gap-2 shrink-0">
  <button
    onClick={handleScore}
    disabled={isScoring}
    className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 text-gray-700 disabled:opacity-50"
  >
    {isScoring ? "Prüfe…" : "Prüfen"}
  </button>
  {isEditing ? (
    <>
      <button
        onClick={() => setIsEditing(false)}
        className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50"
      >
        Abbrechen
      </button>
      <button
        onClick={handleSave}
        disabled={isSaving}
        className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
      >
        {isSaving ? "Speichern..." : "Speichern"}
      </button>
    </>
  ) : (
    <button
      onClick={startEditing}
      className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 text-gray-700"
    >
      Bearbeiten
    </button>
  )}
</div>
```

- [ ] **Step 4: Score-Panel nach den Error/Success-Meldungen einfügen**

Direkt nach `{actionSuccess && (...)}` und vor `<div className="grid grid-cols-3 gap-6">`:

```tsx
{score && (
  <div className="mb-4 rounded border border-gray-200 bg-gray-50 px-4 py-3">
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
          Story Scoring
        </span>
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
          score.level === "low"
            ? "bg-green-100 text-green-700"
            : score.level === "medium"
            ? "bg-yellow-100 text-yellow-800"
            : "bg-red-100 text-red-700"
        }`}>
          {score.level === "low" ? "Niedrig" : score.level === "medium" ? "Mittel" : "Hoch"}
        </span>
        <span className="text-xs text-gray-400 capitalize">{score.domain}</span>
      </div>
      <button
        onClick={() => setScore(null)}
        className="text-gray-400 hover:text-gray-600 text-xs"
      >
        ×
      </button>
    </div>
    <div className="space-y-2">
      {(
        [
          { label: "Klarheit", value: score.clarity },
          { label: "Komplexität", value: score.complexity },
          { label: "Risiko", value: score.risk },
        ] as { label: string; value: number }[]
      ).map(({ label, value }) => (
        <div key={label} className="flex items-center gap-3">
          <span className="text-xs text-gray-500 w-20 shrink-0">{label}</span>
          <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-blue-500"
              style={{ width: `${Math.round(value * 100)}%` }}
            />
          </div>
          <span className="text-xs text-gray-500 w-8 text-right">
            {Math.round(value * 100)}%
          </span>
        </div>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 5: Im Browser testen**

1. Story öffnen
2. "Prüfen"-Button klicken
3. Score-Panel erscheint mit Complexity-Badge, Domain, drei Balken
4. "×" schließt das Panel
5. Bearbeiten-Modus öffnen — "Prüfen"-Button bleibt sichtbar

- [ ] **Step 6: Commit**

```bash
git add plugins/user-story/frontend/components/StoryDetail.tsx
git commit -m "feat(user-story): add scoring button and score panel to StoryDetail"
```
