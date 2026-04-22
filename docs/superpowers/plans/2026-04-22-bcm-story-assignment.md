# BCM Story Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capability-Knoten der BCM per Chat-Konversation einer User Story zuweisen und im "Prozesse"-Tab anzeigen.

**Architecture:** Neuer Session-Typ "capability" in der bestehenden StoryAssistantSession-Infrastruktur. Das System-Prompt erhält den vollständigen Capability-Baum der Org injiziert. Drei neue REST-Endpoints (GET/PATCH/DELETE) verwalten die Zuweisung atomar. Frontend: zwei neue Komponenten (CapabilityAssignmentSection, StoryCapabilityChatPanel) im umgeordneten Prozesse-Tab.

**Tech Stack:** FastAPI async, SQLAlchemy async, SSE-Streaming (bestehend), Next.js 14 App Router, SWR, Tailwind CSS.

---

## File Map

**Modify:**
- `backend/app/services/story_assistant_service.py` — Capability-Systemprompt hinzufügen
- `backend/app/routers/story_assistant.py` — "capability" zu _ALLOWED_TYPES + Sonderpfad im chat_stream
- `backend/app/routers/user_stories.py` — 3 neue Endpoints für Capability-Zuweisung
- `frontend/components/stories/StoryAssistantPanel.tsx` — sessionType-Typ erweitern
- `frontend/app/[org]/stories/[id]/page.tsx` — Tabs umordnen, Prozesse-Abschnitt erweitern

**Create:**
- `frontend/components/stories/CapabilityAssignmentSection.tsx`
- `frontend/components/stories/StoryCapabilityChatPanel.tsx`

---

## Task 1: Backend — Capability-Systemprompt + session_type

**Files:**
- Modify: `backend/app/services/story_assistant_service.py`
- Modify: `backend/app/routers/story_assistant.py`

- [ ] **Step 1: Capability-Systemprompt in story_assistant_service.py hinzufügen**

Füge nach `_FEATURES_SYSTEM` (Zeile ~86) folgendes ein:

```python
# ── Capability system prompt ───────────────────────────────────────────────────

_CAPABILITY_SYSTEM = """\
Du bist ein BCM-Assistent. Deine Aufgabe ist es, die folgende User Story einem \
Knoten in der Business Capability Map der Organisation zuzuordnen.

STORY-KONTEXT:
Titel: {title}
Beschreibung: {description}
Akzeptanzkriterien: {acceptance_criteria}

BUSINESS CAPABILITY MAP:
{capability_tree}

DEINE AUFGABE:
1. Stelle gezielte Rückfragen, um zu verstehen welcher Geschäftsbereich und \
   welche Capability diese Story am besten beschreibt.
2. Stelle maximal 2 Fragen gleichzeitig.
3. Sobald du dir sicher bist, schlage den passenden Knoten vor und schließe \
   deine Antwort mit einem Vorschlagsblock ab:
   <!--proposal
   [{{"node_id": "<UUID des Knotens>", "path": "<Capability> › <Level 1> › <Level 2>"}}]
   -->
4. Verwende ausschließlich node_id-Werte aus der obigen Capability Map.

VERHALTENSREGELN:
- Antworte auf Deutsch, verwende Markdown für Struktur.
- Erfinde keine Capabilities, die nicht in der Map stehen.
- Wenn die Map leer ist, teile dem Nutzer mit, dass zuerst eine Capability Map \
  eingerichtet werden muss.
"""


def build_capability_system_prompt(
    title: str,
    description: Optional[str],
    acceptance_criteria: Optional[str],
    capability_tree: str,
) -> str:
    return _CAPABILITY_SYSTEM.format(
        title=title,
        description=description or "(nicht angegeben)",
        acceptance_criteria=acceptance_criteria or "(nicht angegeben)",
        capability_tree=capability_tree or "(keine Capabilities konfiguriert)",
    )
```

Exportiere `build_capability_system_prompt` in der Datei (keine `__all__` nötig, einfach die Funktion definieren).

- [ ] **Step 2: "capability" zu _ALLOWED_TYPES + Import in story_assistant.py**

Zeile 51 in `backend/app/routers/story_assistant.py`:
```python
_ALLOWED_TYPES = {"dod", "features", "capability"}
```

Füge nach den bestehenden Imports (nach Zeile 44) hinzu:
```python
from app.models.capability_node import CapabilityNode
from app.services.story_assistant_service import (
    build_system_prompt,
    build_capability_system_prompt,
    extract_proposal,
    extract_score,
)
```

(Ersetze die bestehende Import-Zeile für `build_system_prompt` etc.)

- [ ] **Step 3: Capability-Baum-Helper in story_assistant.py**

Füge nach `_resolve_project_name` (Zeile ~91) ein:

```python
async def _build_capability_tree_text(org_id: _uuid_module.UUID, db: AsyncSession) -> str:
    result = await db.execute(
        select(CapabilityNode)
        .where(CapabilityNode.org_id == org_id, CapabilityNode.is_active == True)
        .order_by(CapabilityNode.sort_order)
    )
    nodes = result.scalars().all()
    indent = {"capability": "", "level_1": "  ", "level_2": "    ", "level_3": "      "}
    lines = []
    # Sortiere: Capabilities zuerst, dann Level 1, dann 2, dann 3
    order = {"capability": 0, "level_1": 1, "level_2": 2, "level_3": 3}
    sorted_nodes = sorted(nodes, key=lambda n: (order.get(n.node_type, 9), n.sort_order))
    for n in sorted_nodes:
        prefix = indent.get(n.node_type, "        ")
        lines.append(f"{prefix}[{n.id}] {n.title}")
    return "\n".join(lines)
```

- [ ] **Step 4: chat_stream — Capability-Sonderpfad**

Im `chat_stream`-Endpoint (ab Zeile ~203), ersetze den Block:
```python
system_prompt = build_system_prompt(
    session_type=session_type,
    ...
)
```

durch:
```python
if session_type == "capability":
    cap_tree = await _build_capability_tree_text(org_uuid, db)
    system_prompt = build_capability_system_prompt(
        title=story.title,
        description=story.description,
        acceptance_criteria=story.acceptance_criteria,
        capability_tree=cap_tree,
    )
else:
    epic_title = await _resolve_epic_title(story.epic_id, db)
    project_name = await _resolve_project_name(story.project_id, db)
    system_prompt = build_system_prompt(
        session_type=session_type,
        title=story.title,
        description=story.description,
        acceptance_criteria=story.acceptance_criteria,
        priority=story.priority.value if story.priority else "medium",
        status=story.status.value if story.status else "draft",
        epic_title=epic_title,
        project_name=project_name,
    )
```

Hinweis: Die bestehenden Zeilen `epic_title = await _resolve_epic_title(...)` und `project_name = await _resolve_project_name(...)` müssen in den `else`-Zweig verschoben werden (sie stehen aktuell vor dem `build_system_prompt`-Aufruf).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/story_assistant_service.py backend/app/routers/story_assistant.py
git commit -m "feat(bcm): add capability session type to story assistant"
```

---

## Task 2: Backend — Capability-Assignment-Endpoints

**Files:**
- Modify: `backend/app/routers/user_stories.py`

- [ ] **Step 1: Imports hinzufügen**

Am Ende der Import-Sektion in `user_stories.py` (nach Zeile ~59) hinzufügen:
```python
from app.models.artifact_assignment import ArtifactAssignment
from app.models.capability_node import CapabilityNode
```

- [ ] **Step 2: Node-Path-Helper hinzufügen**

Nach den letzten Imports, vor dem ersten `@router`-Decorator:
```python
async def _compute_node_path(node_id: uuid.UUID, org_id: uuid.UUID, db: AsyncSession) -> str:
    result = await db.execute(
        select(CapabilityNode).where(CapabilityNode.org_id == org_id)
    )
    nodes = result.scalars().all()
    by_id = {n.id: n for n in nodes}
    path: list[str] = []
    current_id: uuid.UUID | None = node_id
    while current_id and current_id in by_id:
        node = by_id[current_id]
        path.insert(0, node.title)
        current_id = node.parent_id
    return " › ".join(path)
```

- [ ] **Step 3: GET-Endpoint**

Am Ende der Datei einfügen (vor dem letzten Endpoint oder nach `ai_generate_docs`):

```python
# ── Capability Assignment ─────────────────────────────────────────────────────

class CapabilityAssignmentResponse(BaseModel):
    assignment_id: str
    node_id: str
    node_path: str


@router.get("/{story_id}/capability-assignment")
async def get_capability_assignment(
    story_id: uuid.UUID,
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Optional[CapabilityAssignmentResponse]:
    org_uuid = uuid.UUID(org_id)
    result = await db.execute(
        select(ArtifactAssignment).where(
            ArtifactAssignment.artifact_type == "user_story",
            ArtifactAssignment.artifact_id == story_id,
            ArtifactAssignment.org_id == org_uuid,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        return None
    path = await _compute_node_path(assignment.node_id, org_uuid, db)
    return CapabilityAssignmentResponse(
        assignment_id=str(assignment.id),
        node_id=str(assignment.node_id),
        node_path=path,
    )
```

- [ ] **Step 4: PATCH-Endpoint**

```python
class CapabilityAssignmentPatch(BaseModel):
    node_id: str


@router.patch("/{story_id}/capability-assignment")
async def set_capability_assignment(
    story_id: uuid.UUID,
    body: CapabilityAssignmentPatch,
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CapabilityAssignmentResponse:
    org_uuid = uuid.UUID(org_id)
    node_uuid = uuid.UUID(body.node_id)

    # Verify node belongs to org
    node_result = await db.execute(
        select(CapabilityNode).where(
            CapabilityNode.id == node_uuid,
            CapabilityNode.org_id == org_uuid,
        )
    )
    if not node_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Capability-Knoten nicht gefunden")

    # Delete existing assignments for this story
    existing = await db.execute(
        select(ArtifactAssignment).where(
            ArtifactAssignment.artifact_type == "user_story",
            ArtifactAssignment.artifact_id == story_id,
            ArtifactAssignment.org_id == org_uuid,
        )
    )
    for old in existing.scalars().all():
        await db.delete(old)

    # Create new assignment
    assignment = ArtifactAssignment(
        org_id=org_uuid,
        artifact_type="user_story",
        artifact_id=story_id,
        node_id=node_uuid,
        relation_type="primary",
        created_by_id=current_user.id,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)

    path = await _compute_node_path(node_uuid, org_uuid, db)
    return CapabilityAssignmentResponse(
        assignment_id=str(assignment.id),
        node_id=str(assignment.node_id),
        node_path=path,
    )
```

- [ ] **Step 5: DELETE-Endpoint**

```python
from fastapi.responses import Response as FastAPIResponse

@router.delete("/{story_id}/capability-assignment")
async def delete_capability_assignment(
    story_id: uuid.UUID,
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_uuid = uuid.UUID(org_id)
    existing = await db.execute(
        select(ArtifactAssignment).where(
            ArtifactAssignment.artifact_type == "user_story",
            ArtifactAssignment.artifact_id == story_id,
            ArtifactAssignment.org_id == org_uuid,
        )
    )
    for old in existing.scalars().all():
        await db.delete(old)
    await db.commit()
    return FastAPIResponse(status_code=204)
```

Hinweis: `Response` ist in `user_stories.py` ggf. schon importiert (aus FastAPI). Falls nicht, `from fastapi.responses import Response as FastAPIResponse` hinzufügen. Falls bereits `Response` importiert ist, diesen Namen verwenden.

- [ ] **Step 6: Backend neu bauen und testen**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
sleep 5 && docker logs heykarl-backend --tail 10
```

Erwartung: `Application startup complete.` — keine Fehler.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/user_stories.py backend/app/services/story_assistant_service.py
git commit -m "feat(bcm): capability assignment endpoints on user stories"
```

---

## Task 3: Frontend — StoryAssistantPanel type + CapabilityAssignmentSection

**Files:**
- Modify: `frontend/components/stories/StoryAssistantPanel.tsx`
- Create: `frontend/components/stories/CapabilityAssignmentSection.tsx`

- [ ] **Step 1: sessionType-Typ in StoryAssistantPanel.tsx erweitern**

Zeile ~22 (die Props-Interface-Definition):
```typescript
// Alt:
sessionType: "dod" | "features";
// Neu:
sessionType: "dod" | "features" | "capability";
```

- [ ] **Step 2: CapabilityAssignmentSection.tsx erstellen**

Erstelle `frontend/components/stories/CapabilityAssignmentSection.tsx`:

```typescript
"use client";

import { useState } from "react";
import useSWR from "swr";
import { MapPin, X, MessageSquare } from "lucide-react";
import { fetcher, apiRequest } from "@/lib/api/client";
import { StoryCapabilityChatPanel } from "./StoryCapabilityChatPanel";
import type { UserStory } from "@/types";

interface CapabilityAssignment {
  assignment_id: string;
  node_id: string;
  node_path: string;
}

interface Props {
  storyId: string;
  orgId: string;
  story: UserStory;
}

export function CapabilityAssignmentSection({ storyId, orgId, story }: Props) {
  const [chatOpen, setChatOpen] = useState(false);

  const { data: assignment, mutate, isLoading } = useSWR<CapabilityAssignment | null>(
    `/api/v1/user-stories/${storyId}/capability-assignment?org_id=${orgId}`,
    fetcher,
    { revalidateOnFocus: false },
  );

  const handleRemove = async () => {
    try {
      await apiRequest(`/api/v1/user-stories/${storyId}/capability-assignment?org_id=${orgId}`, {
        method: "DELETE",
      });
      await mutate(null, false);
    } catch { /* ignore */ }
  };

  const handleAssigned = async () => {
    await mutate();
    setChatOpen(false);
  };

  return (
    <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-[var(--paper-rule)]">
        <div className="flex items-center gap-2">
          <MapPin size={15} className="text-[var(--ink-mid)]" />
          <div>
            <h3 className="text-sm font-semibold text-[var(--ink)]">Business Capability</h3>
            <p className="text-xs text-[var(--ink-faint)] mt-0.5">
              Zuordnung zur Business Capability Map
            </p>
          </div>
        </div>
        {!chatOpen && (
          <button
            onClick={() => setChatOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:border-[var(--btn-primary)] hover:text-[var(--btn-primary)] transition-colors"
          >
            <MessageSquare size={12} />
            {assignment ? "Ändern" : "Via Chat zuweisen"}
          </button>
        )}
      </div>

      {/* Content */}
      <div className="px-4 sm:px-6 py-4 space-y-4">
        {/* Current assignment */}
        {isLoading ? (
          <div className="flex items-center gap-2 text-xs text-[var(--ink-faint)]">
            <div className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
            Lade…
          </div>
        ) : assignment ? (
          <div className="flex items-center justify-between gap-2 p-3 rounded-lg bg-[var(--paper-warm)] border border-[var(--paper-rule2)]">
            <div className="flex items-center gap-2 min-w-0">
              <MapPin size={13} className="text-[var(--accent-orange)] shrink-0" />
              <span className="text-sm font-medium text-[var(--ink)] truncate">
                {assignment.node_path}
              </span>
            </div>
            <button
              onClick={handleRemove}
              className="shrink-0 text-[var(--ink-faint)] hover:text-rose-500 transition-colors"
              aria-label="Zuweisung entfernen"
            >
              <X size={14} />
            </button>
          </div>
        ) : (
          <p className="text-sm text-[var(--ink-faint)]">
            Noch keine Capability zugewiesen. Nutze den Chat, um die passende Capability zu ermitteln.
          </p>
        )}

        {/* Chat panel */}
        {chatOpen && (
          <div className="mt-2">
            <StoryCapabilityChatPanel
              storyId={storyId}
              orgId={orgId}
              story={story}
              onAssigned={handleAssigned}
              onClose={() => setChatOpen(false)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/stories/StoryAssistantPanel.tsx frontend/components/stories/CapabilityAssignmentSection.tsx
git commit -m "feat(bcm): CapabilityAssignmentSection component"
```

---

## Task 4: Frontend — StoryCapabilityChatPanel

**Files:**
- Create: `frontend/components/stories/StoryCapabilityChatPanel.tsx`

- [ ] **Step 1: Datei erstellen**

```typescript
"use client";

import { MapPin } from "lucide-react";
import { apiRequest } from "@/lib/api/client";
import { StoryAssistantPanel } from "./StoryAssistantPanel";
import type { UserStory } from "@/types";

interface CapabilityProposalItem {
  node_id: string;
  path: string;
}

interface Props {
  storyId: string;
  orgId: string;
  story: UserStory;
  onAssigned: () => void;
  onClose: () => void;
}

export function StoryCapabilityChatPanel({ storyId, orgId, story, onAssigned, onClose }: Props) {
  const handleAccept = async (item: unknown) => {
    const proposal = item as CapabilityProposalItem;
    try {
      await apiRequest(`/api/v1/user-stories/${storyId}/capability-assignment?org_id=${orgId}`, {
        method: "PATCH",
        body: JSON.stringify({ node_id: proposal.node_id }),
      });
      onAssigned();
    } catch {
      // Fehler werden im Panel nicht angezeigt — Nutzer kann es erneut versuchen
    }
  };

  return (
    <StoryAssistantPanel
      storyId={storyId}
      orgId={orgId}
      story={story}
      sessionType="capability"
      panelTitle="BCM-Assistent"
      emptyTitle="Capability via Chat ermitteln"
      emptyDesc="Beschreibe kurz, was diese Story macht — der Assistent schlägt die passende Capability vor."
      startButtonLabel="Chat starten"
      consolidateMessage="Bitte mach jetzt einen konkreten Vorschlag für die passende Capability und schließe mit dem Vorschlagsblock ab."
      proposalRenderer={{
        renderItem: (item) => {
          const p = item as CapabilityProposalItem;
          return (
            <div className="flex items-center gap-1.5">
              <MapPin size={12} className="text-[var(--accent-orange)] shrink-0" />
              <span className="font-medium">{p.path}</span>
            </div>
          );
        },
        emptyLabel: "",
      }}
      onProposalItemAdd={handleAccept}
    />
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/stories/StoryCapabilityChatPanel.tsx
git commit -m "feat(bcm): StoryCapabilityChatPanel with SSE chat and proposal acceptance"
```

---

## Task 5: Frontend — page.tsx Integration

**Files:**
- Modify: `frontend/app/[org]/stories/[id]/page.tsx`

- [ ] **Step 1: Imports hinzufügen**

Am Anfang der Datei (nach den bestehenden Komponenten-Imports, ca. Zeile 11–23):
```typescript
import { CapabilityAssignmentSection } from "@/components/stories/CapabilityAssignmentSection";
```

- [ ] **Step 2: ALL_TABS umordnen**

Zeilen 2817–2825 — ersetze:
```typescript
const ALL_TABS: { id: ActiveTab; label: string }[] = [
  { id: "story",     label: t("story_detail_tab_story") },
  { id: "features",  label: t("story_detail_tab_features") },
  { id: "tests",     label: t("story_detail_tab_tests") },
  { id: "dod",       label: t("story_detail_tab_dod") },
  { id: "docs",      label: t("story_detail_tab_docs") },
  { id: "prompt",    label: t("story_detail_tab_prompt") },
  { id: "processes", label: t("process_tab") },
];
```

durch:
```typescript
const ALL_TABS: { id: ActiveTab; label: string }[] = [
  { id: "story",     label: t("story_detail_tab_story") },
  { id: "processes", label: t("process_tab") },
  { id: "features",  label: t("story_detail_tab_features") },
  { id: "tests",     label: t("story_detail_tab_tests") },
  { id: "dod",       label: t("story_detail_tab_dod") },
  { id: "docs",      label: t("story_detail_tab_docs") },
  { id: "prompt",    label: t("story_detail_tab_prompt") },
];
```

- [ ] **Step 3: ROLE_TABS anpassen**

Zeilen 2440–2447 — ersetze:
```typescript
const ROLE_TABS: Record<DemoRole, ActiveTab[]> = {
  user:      ["story", "dod", "tests", "features", "docs", "processes"],
  ba:        ["story", "dod", "tests", "features", "docs", "processes"],
  architect: ["story", "dod", "features", "docs", "prompt", "processes"],
  developer: ["story", "dod", "tests", "features", "prompt", "processes"],
  tester:    ["story", "tests"],
  release:   ["story", "tests", "features", "docs", "processes"],
};
```

durch:
```typescript
const ROLE_TABS: Record<DemoRole, ActiveTab[]> = {
  user:      ["story", "processes", "dod", "tests", "features", "docs"],
  ba:        ["story", "processes", "dod", "tests", "features", "docs"],
  architect: ["story", "processes", "dod", "features", "docs", "prompt"],
  developer: ["story", "processes", "dod", "tests", "features", "prompt"],
  tester:    ["story", "tests"],
  release:   ["story", "processes", "tests", "features", "docs"],
};
```

- [ ] **Step 4: Prozesse-Tab-Inhalt erweitern**

Zeilen 3564–3567 — ersetze:
```tsx
{/* Processes tab */}
{activeTab === "processes" && (
  <StoryProcessSection storyId={resolvedParams.id} orgId={story.organization_id} />
)}
```

durch:
```tsx
{/* Processes tab */}
{activeTab === "processes" && (
  <div className="space-y-6">
    <CapabilityAssignmentSection
      storyId={resolvedParams.id}
      orgId={story.organization_id}
      story={story}
    />
    <StoryProcessSection storyId={resolvedParams.id} orgId={story.organization_id} />
  </div>
)}
```

- [ ] **Step 5: Frontend bauen**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build frontend
sleep 10 && docker logs heykarl-frontend --tail 15
```

Erwartung: `✓ Ready` oder `compiled successfully` — keine TypeScript-Fehler.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/\[org\]/stories/\[id\]/page.tsx
git commit -m "feat(bcm): integrate CapabilityAssignmentSection in Prozesse tab, reorder tabs"
```

---

## Abschluss-Test

Nach Rebuild beider Services:
1. Story-Detailseite öffnen → Tab "Prozesse" erscheint an zweiter Stelle (nach Story)
2. Im Prozesse-Tab: "Business Capability"-Sektion oben, Prozessänderungen darunter
3. "Via Chat zuweisen" → Chat öffnet sich, AI antwortet auf Deutsch
4. "Vorschlag anfordern" / Konsolidieren → AI schlägt einen Capability-Knoten vor (Breadcrumb)
5. "+" / Übernehmen → Zuweisung erscheint als Breadcrumb in der Sektion
6. "×" → Zuweisung wird entfernt
