# Governance: Zwei-Ebenen-Kontrollmodell – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing `Control` model with a plain-language user layer (visible to all users) alongside the governance layer (admin-only), update the admin editor and story compliance panel accordingly.

**Architecture:** Additive migration on `controls` table adds 5 user-layer fields. Schema/model updated. `relevant-controls` endpoint serializes using a user-view schema. New `ControlEditor` admin component shows both panels side-by-side. `StoryCompliancePanel` shows only user-layer fields.

**Tech Stack:** FastAPI, Alembic, SQLAlchemy async, Pydantic v2, Next.js 14, SWR, Tailwind CSS, lucide-react.

---

### Task 1: Migration 0061 – User-Layer-Felder auf controls

**Files:**
- Create: `backend/migrations/versions/0061_control_user_layer.py`

- [ ] **Step 1: Migration schreiben**

```python
"""add user layer fields to controls

Revision ID: 0061
Revises: 0060
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("controls", sa.Column("user_title", sa.String(500), nullable=True))
    op.add_column("controls", sa.Column("user_explanation", sa.Text(), nullable=True))
    op.add_column("controls", sa.Column("user_action", sa.Text(), nullable=True))
    op.add_column(
        "controls",
        sa.Column(
            "user_guiding_questions",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="'[]'::jsonb",
        ),
    )
    op.add_column(
        "controls",
        sa.Column(
            "user_evidence_needed",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="'[]'::jsonb",
        ),
    )


def downgrade() -> None:
    op.drop_column("controls", "user_evidence_needed")
    op.drop_column("controls", "user_guiding_questions")
    op.drop_column("controls", "user_action")
    op.drop_column("controls", "user_explanation")
    op.drop_column("controls", "user_title")
```

- [ ] **Step 2: Migration ausführen**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend alembic upgrade head
```

Expected: `Running upgrade 0060 -> 0061, add user layer fields to controls`

- [ ] **Step 3: Columns prüfen**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec db psql -U assist2 -c "\d controls" | grep user_
```

Expected: 5 Zeilen (user_title, user_explanation, user_action, user_guiding_questions, user_evidence_needed)

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/versions/0061_control_user_layer.py
git commit -m "feat: migration 0061 – add user layer fields to controls"
```

---

### Task 2: Model + Schema – User-Layer-Felder integrieren

**Files:**
- Modify: `backend/app/models/control.py`
- Modify: `backend/app/schemas/control.py`

- [ ] **Step 1: Model erweitern**

In `backend/app/models/control.py` nach `framework_refs` einfügen:

```python
    user_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    user_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_guiding_questions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    user_evidence_needed: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 2: Schemas erweitern**

In `backend/app/schemas/control.py`:

`ControlCreate` um diese Felder erweitern:
```python
    user_title: Optional[str] = None
    user_explanation: Optional[str] = None
    user_action: Optional[str] = None
    user_guiding_questions: Optional[list[str]] = []
    user_evidence_needed: Optional[list[str]] = []
```

`ControlUpdate` um dieselben Felder erweitern (alle Optional).

`ControlRead` um dieselben Felder erweitern.

Neues Schema `ControlUserView` hinzufügen (nach `ControlRead`):

```python
class ControlUserView(BaseModel):
    """User-facing view: only plain-language fields, no governance data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_title: Optional[str] = None
    title: str  # fallback if user_title is empty
    user_explanation: Optional[str] = None
    user_action: Optional[str] = None
    user_guiding_questions: Optional[list[str]] = None
    user_evidence_needed: Optional[list[str]] = None
    is_inherited: bool = False
    applies_via_node_id: Optional[uuid.UUID] = None
```

- [ ] **Step 3: Backend neu starten und prüfen**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml restart backend
docker logs assist2-backend --tail 20
```

Expected: kein Fehler, Backend startet.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/control.py backend/app/schemas/control.py
git commit -m "feat: control model and schemas – add user layer fields"
```

---

### Task 3: relevant-controls Endpoint – ControlUserView zurückgeben

**Files:**
- Modify: `backend/app/routers/user_stories.py` (Zeilen 1486–1503)

- [ ] **Step 1: Import hinzufügen**

Am Anfang der Datei (bei anderen schema-imports) oder lokal im Endpoint:
```python
from app.schemas.control import ControlUserView
```

- [ ] **Step 2: Endpoint anpassen**

Den bestehenden `get_relevant_controls` Endpoint ersetzen:

```python
@router.get("/user-stories/{story_id}/relevant-controls")
async def get_relevant_controls(
    story_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return user-layer compliance controls relevant to this story's capability."""
    from app.services import control_service as control_svc
    rows = await control_svc.get_controls_for_story(db, org_id, story_id)
    result = []
    for row in rows:
        ctrl = row["control"]
        assessment = row["assessment"]
        result.append({
            "id": str(ctrl.id),
            "user_title": ctrl.user_title or ctrl.title,
            "user_explanation": ctrl.user_explanation,
            "user_action": ctrl.user_action,
            "user_guiding_questions": ctrl.user_guiding_questions or [],
            "user_evidence_needed": ctrl.user_evidence_needed or [],
            "is_inherited": assessment.is_inherited,
            "applies_via_node_id": str(row["applies_via_node_id"]),
        })
    return result
```

- [ ] **Step 3: Testen**

```bash
# In einem Story mit Capability-Zuweisung und Controls:
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/user-stories/<story_id>/relevant-controls?org_id=<org_id>" | python3 -m json.tool
```

Expected: Liste mit user_title, user_explanation usw.; keine governance-Felder (kein framework_refs, kein control_type).

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/user_stories.py
git commit -m "feat: relevant-controls endpoint returns user-layer view only"
```

---

### Task 4: Frontend-Typen erweitern

**Files:**
- Modify: `frontend/types/index.ts`

- [ ] **Step 1: Control-Typ erweitern**

In `frontend/types/index.ts` im `Control`-Interface folgende Felder hinzufügen:

```typescript
  user_title?: string | null;
  user_explanation?: string | null;
  user_action?: string | null;
  user_guiding_questions?: string[] | null;
  user_evidence_needed?: string[] | null;
```

- [ ] **Step 2: ControlUserView Typ hinzufügen**

```typescript
export interface ControlUserView {
  id: string;
  user_title: string;
  user_explanation?: string | null;
  user_action?: string | null;
  user_guiding_questions?: string[];
  user_evidence_needed?: string[];
  is_inherited: boolean;
  applies_via_node_id: string;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/types/index.ts
git commit -m "feat: frontend types – ControlUserView and user layer fields"
```

---

### Task 5: StoryCompliancePanel – User-Layer anzeigen

**Files:**
- Modify: `frontend/components/governance/StoryCompliancePanel.tsx`

- [ ] **Step 1: Bestehende Datei lesen und verstehen**

Lese `frontend/components/governance/StoryCompliancePanel.tsx` komplett.

- [ ] **Step 2: Komponente umschreiben**

Die Komponente soll `ControlUserView` rendern. Vollständige Implementierung:

```tsx
"use client";

import useSWR from "swr";
import { ShieldCheck, HelpCircle, CheckSquare, FileText } from "lucide-react";
import { fetcher } from "@/lib/api/client";
import type { ControlUserView } from "@/types";

interface Props {
  storyId: string;
  orgId: string;
}

function UserHintCard({ control }: { control: ControlUserView }) {
  return (
    <div className="rounded-lg border border-[var(--paper-rule)] bg-[var(--card)] overflow-hidden">
      <div className="px-4 py-3 bg-[var(--paper-warm)] border-b border-[var(--paper-rule)] flex items-center gap-2">
        <ShieldCheck size={14} className="text-[var(--green,#527b5e)] shrink-0" />
        <span className="text-sm font-semibold text-[var(--ink)]">{control.user_title}</span>
        {control.is_inherited && (
          <span className="ml-auto text-[10px] text-[var(--ink-faint)] italic">(vererbt)</span>
        )}
      </div>

      <div className="px-4 py-3 space-y-4">
        {control.user_explanation && (
          <p className="text-sm text-[var(--ink-mid)]">{control.user_explanation}</p>
        )}

        {control.user_action && (
          <div className="rounded-md bg-[rgba(82,123,94,.08)] border border-[var(--green,#527b5e)] px-3 py-2.5">
            <p className="text-xs font-semibold text-[var(--green,#527b5e)] uppercase tracking-wide mb-1">
              Was zu tun ist
            </p>
            <p className="text-sm text-[var(--ink)]">{control.user_action}</p>
          </div>
        )}

        {control.user_guiding_questions && control.user_guiding_questions.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <HelpCircle size={12} className="text-[var(--ink-faint)]" />
              <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">
                Leitfragen
              </p>
            </div>
            <ol className="space-y-1">
              {control.user_guiding_questions.map((q, i) => (
                <li key={i} className="text-sm text-[var(--ink-mid)] flex gap-2">
                  <span className="text-[var(--ink-faint)] shrink-0">{i + 1}.</span>
                  <span>{q}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {control.user_evidence_needed && control.user_evidence_needed.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <FileText size={12} className="text-[var(--ink-faint)]" />
              <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">
                Benötigte Nachweise
              </p>
            </div>
            <ul className="space-y-1">
              {control.user_evidence_needed.map((e, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-[var(--ink-mid)]">
                  <CheckSquare size={13} className="text-[var(--green,#527b5e)] shrink-0 mt-0.5" />
                  <span>{e}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export function StoryCompliancePanel({ storyId, orgId }: Props) {
  const { data, isLoading } = useSWR<ControlUserView[]>(
    `/api/v1/user-stories/${storyId}/relevant-controls?org_id=${orgId}`,
    fetcher,
    { revalidateOnFocus: false },
  );

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs text-[var(--ink-faint)] py-4">
        <div className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
        Lade Hinweise…
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--paper-rule)] bg-[var(--paper-warm)] px-4 py-6 text-center">
        <ShieldCheck size={20} className="mx-auto mb-2 text-[var(--ink-faintest)]" />
        <p className="text-sm text-[var(--ink-faint)]">
          Keine Hinweise für diese Story.
        </p>
        <p className="text-xs text-[var(--ink-faintest)] mt-1">
          Weise zuerst eine Business Capability im Prozesse-Tab zu.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-[var(--ink-faint)]">
        {data.length} {data.length === 1 ? "Hinweis" : "Hinweise"} für diese Story
      </p>
      {data.map((control) => (
        <UserHintCard key={control.id} control={control} />
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Im Browser prüfen**

Story mit Capability-Zuweisung und Controls öffnen → Compliance-Tab → User-Layer-Felder erscheinen, kein ISO-Kürzel.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/governance/StoryCompliancePanel.tsx
git commit -m "feat: story compliance panel shows user-layer fields only"
```

---

### Task 6: ControlEditor – Admin-Two-Panel-Komponente

**Files:**
- Create: `frontend/components/governance/ControlEditor.tsx`

- [ ] **Step 1: Komponente implementieren**

```tsx
"use client";

import { useState } from "react";
import { Save, X, Plus, Trash2 } from "lucide-react";
import { apiRequest } from "@/lib/api/client";
import type { Control } from "@/types";

interface Props {
  control: Control;
  orgId: string;
  onSaved: (updated: Control) => void;
  onClose: () => void;
}

function StringListEditor({
  label,
  items,
  onChange,
}: {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
}) {
  const add = () => onChange([...items, ""]);
  const remove = (i: number) => onChange(items.filter((_, idx) => idx !== i));
  const update = (i: number, v: string) =>
    onChange(items.map((item, idx) => (idx === i ? v : item)));

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">
          {label}
        </label>
        <button
          onClick={add}
          className="text-xs text-[var(--btn-primary)] hover:underline flex items-center gap-0.5"
        >
          <Plus size={11} /> Hinzufügen
        </button>
      </div>
      <div className="space-y-1.5">
        {items.map((item, i) => (
          <div key={i} className="flex gap-1.5">
            <input
              value={item}
              onChange={(e) => update(i, e.target.value)}
              className="flex-1 text-sm border border-[var(--paper-rule)] rounded px-2 py-1 bg-[var(--card)] text-[var(--ink)] focus:outline-none focus:border-[var(--btn-primary)]"
            />
            <button
              onClick={() => remove(i)}
              className="p-1 text-[var(--ink-faint)] hover:text-red-500 transition-colors"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-xs text-[var(--ink-faintest)] italic">Noch keine Einträge</p>
        )}
      </div>
    </div>
  );
}

export function ControlEditor({ control, orgId, onSaved, onClose }: Props) {
  const [saving, setSaving] = useState(false);

  // User layer state
  const [userTitle, setUserTitle] = useState(control.user_title ?? "");
  const [userExplanation, setUserExplanation] = useState(control.user_explanation ?? "");
  const [userAction, setUserAction] = useState(control.user_action ?? "");
  const [userQuestions, setUserQuestions] = useState<string[]>(
    control.user_guiding_questions ?? [],
  );
  const [userEvidence, setUserEvidence] = useState<string[]>(
    control.user_evidence_needed ?? [],
  );

  // Governance layer state
  const [govTitle, setGovTitle] = useState(control.title);
  const [govDescription, setGovDescription] = useState(control.description ?? "");
  const [govType, setGovType] = useState(control.control_type);
  const [govStatus, setGovStatus] = useState(control.implementation_status);
  const [govInterval, setGovInterval] = useState(control.review_interval_days);
  const [govRefs, setGovRefs] = useState<string[]>(control.framework_refs ?? []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await apiRequest(
        `/api/v1/controls/orgs/${orgId}/${control.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            title: govTitle,
            description: govDescription,
            control_type: govType,
            implementation_status: govStatus,
            review_interval_days: govInterval,
            framework_refs: govRefs,
            user_title: userTitle,
            user_explanation: userExplanation,
            user_action: userAction,
            user_guiding_questions: userQuestions,
            user_evidence_needed: userEvidence,
          }),
        },
      );
      onSaved(updated);
    } finally {
      setSaving(false);
    }
  };

  const inputCls =
    "w-full text-sm border border-[var(--paper-rule)] rounded px-2.5 py-1.5 bg-[var(--card)] text-[var(--ink)] focus:outline-none focus:border-[var(--btn-primary)]";
  const labelCls = "block text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide mb-1";
  const textareaCls = inputCls + " resize-none";

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--paper-rule)]">
        <h3 className="text-sm font-semibold text-[var(--ink)] truncate flex-1 mr-4">
          Control bearbeiten
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-[var(--btn-primary)] text-white hover:opacity-90 transition-opacity disabled:opacity-60"
          >
            <Save size={12} />
            {saving ? "Speichern…" : "Speichern"}
          </button>
          <button onClick={onClose} className="p-1.5 text-[var(--ink-faint)] hover:text-[var(--ink)]">
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Two-panel body */}
      <div className="flex-1 overflow-auto grid grid-cols-2 divide-x divide-[var(--paper-rule)]">
        {/* Left: User Layer */}
        <div className="px-4 py-4 space-y-4 overflow-auto">
          <div className="flex items-center gap-2 mb-2 pb-2 border-b border-[var(--paper-rule)]">
            <div className="w-2 h-2 rounded-full bg-[var(--green,#527b5e)]" />
            <span className="text-xs font-bold text-[var(--green,#527b5e)] uppercase tracking-wide">
              Nutzer-Ebene
            </span>
            <span className="text-[10px] text-[var(--ink-faintest)]">(sichtbar für alle)</span>
          </div>

          <div>
            <label className={labelCls}>Titel (verständlich)</label>
            <input
              value={userTitle}
              onChange={(e) => setUserTitle(e.target.value)}
              placeholder={govTitle}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls}>Warum wichtig?</label>
            <textarea
              value={userExplanation}
              onChange={(e) => setUserExplanation(e.target.value)}
              rows={3}
              className={textareaCls}
            />
          </div>

          <div>
            <label className={labelCls}>Was zu tun ist</label>
            <textarea
              value={userAction}
              onChange={(e) => setUserAction(e.target.value)}
              rows={3}
              className={textareaCls}
            />
          </div>

          <StringListEditor
            label="Leitfragen"
            items={userQuestions}
            onChange={setUserQuestions}
          />

          <StringListEditor
            label="Benötigte Nachweise"
            items={userEvidence}
            onChange={setUserEvidence}
          />
        </div>

        {/* Right: Governance Layer */}
        <div className="px-4 py-4 space-y-4 overflow-auto">
          <div className="flex items-center gap-2 mb-2 pb-2 border-b border-[var(--paper-rule)]">
            <div className="w-2 h-2 rounded-full bg-[var(--navy,#2d3a8c)]" />
            <span className="text-xs font-bold text-[var(--navy,#2d3a8c)] uppercase tracking-wide">
              Governance-Ebene
            </span>
            <span className="text-[10px] text-[var(--ink-faintest)]">(nur Admins)</span>
          </div>

          <div>
            <label className={labelCls}>Technischer Titel</label>
            <input
              value={govTitle}
              onChange={(e) => setGovTitle(e.target.value)}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls}>Beschreibung</label>
            <textarea
              value={govDescription}
              onChange={(e) => setGovDescription(e.target.value)}
              rows={3}
              className={textareaCls}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Typ</label>
              <select
                value={govType}
                onChange={(e) => setGovType(e.target.value)}
                className={inputCls}
              >
                <option value="preventive">Preventive</option>
                <option value="detective">Detective</option>
                <option value="corrective">Corrective</option>
                <option value="compensating">Compensating</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Status</label>
              <select
                value={govStatus}
                onChange={(e) => setGovStatus(e.target.value)}
                className={inputCls}
              >
                <option value="not_started">Nicht gestartet</option>
                <option value="in_progress">In Arbeit</option>
                <option value="implemented">Implementiert</option>
                <option value="verified">Verifiziert</option>
              </select>
            </div>
          </div>

          <div>
            <label className={labelCls}>Prüfintervall (Tage)</label>
            <input
              type="number"
              value={govInterval}
              onChange={(e) => setGovInterval(Number(e.target.value))}
              min={1}
              className={inputCls}
            />
          </div>

          <StringListEditor
            label="Framework-Referenzen (ISO 27001:A.x, NIS2:Art.x …)"
            items={govRefs}
            onChange={setGovRefs}
          />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/governance/ControlEditor.tsx
git commit -m "feat: ControlEditor two-panel admin component (user + governance layer)"
```

---

### Task 7: ControlCapabilityMap – ControlEditor integrieren

**Files:**
- Modify: `frontend/components/governance/ControlCapabilityMap.tsx`

- [ ] **Step 1: Bestehende Datei lesen**

Lese `frontend/components/governance/ControlCapabilityMap.tsx` komplett.

- [ ] **Step 2: ControlEditor einbinden**

Die rechte Spalte (Control-Liste) soll beim Klick auf einen Control den `ControlEditor` anzeigen. Änderungen:

1. Import hinzufügen: `import { ControlEditor } from "./ControlEditor";`
2. State hinzufügen: `const [editingControl, setEditingControl] = useState<Control | null>(null);`
3. In der rechten Spalte: Wenn `editingControl !== null`, `<ControlEditor>` rendern, sonst Control-Liste.
4. Jeder Control-Eintrag bekommt einen "Bearbeiten"-Button, der `setEditingControl(control)` aufruft.
5. `ControlEditor.onSaved`: mutate SWR, `setEditingControl(null)`.
6. `ControlEditor.onClose`: `setEditingControl(null)`.

Konkretes Diff — in der rechten Spalte, wo Controls gelistet werden, die `map`-Schleife anpassen:

```tsx
// Vor jedem Control-Card-div:
<button
  onClick={() => setEditingControl(control.control)}
  className="text-xs text-[var(--btn-primary)] hover:underline"
>
  Bearbeiten
</button>
```

Und im rechten Spalten-Container conditionally rendern:

```tsx
{editingControl ? (
  <ControlEditor
    control={editingControl}
    orgId={orgId}
    onSaved={(updated) => {
      setEditingControl(null);
      mutate(); // refresh controls list
    }}
    onClose={() => setEditingControl(null)}
  />
) : (
  /* existing control list JSX */
)}
```

- [ ] **Step 3: Im Browser testen**

Compliance-Seite öffnen → Controls & Capabilities Tab → Control anklicken → Bearbeiten → Zwei-Panel-Editor erscheint → user_title und Leitfragen eintragen → Speichern → Story-Compliance-Panel zeigt user_title.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/governance/ControlCapabilityMap.tsx
git commit -m "feat: ControlCapabilityMap integrates ControlEditor for two-panel editing"
```

---

### Task 8: Backend restart + end-to-end smoke test

- [ ] **Step 1: Backend und Frontend neu starten**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml restart backend frontend
```

- [ ] **Step 2: Smoke-Test-Ablauf**

1. Admin öffnet `/[org]/compliance` → Controls & Capabilities → wählt Capability-Node
2. Klickt auf einen Control → "Bearbeiten"
3. Trägt user_title, user_explanation, user_action, 2 Leitfragen, 2 Nachweise ein → Speichern
4. Öffnet eine Story, die dieser Capability zugewiesen ist → Compliance-Tab
5. Sieht user_title als Überschrift, Leitfragen, Nachweise — kein ISO-Kürzel

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: two-level governance controls – user layer visible, governance layer admin-only"
```
