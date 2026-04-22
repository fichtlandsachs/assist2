# BCM Story Assignment Design

## Goal

Capability-Knoten aus der Business Capability Map (BCM) sind einer User Story zuweisbar und per Chat-Konversation ermittelbar. Die Zuweisung erscheint im "Prozesse"-Tab der Story-Detail-Seite, der Tab wird vor "Features" einsortiert.

## Architecture

Bestehende Infrastruktur wird maximal wiederverwendet:
- `ArtifactAssignment`-Modell (bereits vorhanden) speichert die Zuweisung
- `StoryAssistantSession` / `StoryAssistantPanel` erhalten einen dritten Session-Typ `"capability"`
- SSE-Streaming, Session-Persistenz und Proposal-Mechanismus bleiben unverändert
- Neuer atomarer PATCH-Endpoint ersetzt alte Zuweisung durch neue

## Tech Stack

FastAPI (Backend), Next.js 14 App Router (Frontend), SQLAlchemy async, SSE-Streaming, SWR, Tailwind CSS / bestehende Design-Tokens.

---

## Section 1: Tab-Reihenfolge

`ALL_TABS` in `frontend/app/[org]/stories/[id]/page.tsx` wird umgeordnet:

**Neu:** `Story → Prozesse → Features → Tests → DoD → Docs → KI-Prompt`

`ROLE_TABS` wird entsprechend angepasst — "processes" erscheint direkt nach "story" in allen Rollen, die es bisher enthalten.

---

## Section 2: Prozesse-Tab Layout

Der Tab enthält zwei vertikal gestapelte Bereiche:

**Oben: Business Capability (neu)**
- Zeigt aktuelle Zuweisung als Breadcrumb: `Capability › Level 1 › Level 2`
- Kein Eintrag: Placeholder-Text + "Via Chat zuweisen"-Button
- Eintrag vorhanden: Breadcrumb-Karte + "Ändern"-Button + "Entfernen"-Icon
- Chat-Panel klappt innerhalb des Tab auf (kein Modal)

**Unten: Prozessänderungen (unverändert)**
- Bestehende `StoryProcessSection`-Komponente

---

## Section 3: Backend

### 3.1 Neuer Session-Typ "capability"

`backend/app/models/story_assistant_session.py`:
- `session_type` CHECK-Constraint / Enum um `"capability"` erweitern

`backend/app/routers/story_assistant.py`:
- Überall wo `session_type` gegen `["dod", "features"]` validiert wird: `"capability"` hinzufügen
- Im Chat-Endpoint (`/chat`): wenn `session_type == "capability"`, eigenes System-Prompt laden (Section 3.2)

### 3.2 Capability-System-Prompt

Wird im Chat-Endpoint dynamisch zusammengestellt:

```
Du bist ein BCM-Assistent. Deine Aufgabe ist es, die folgende User Story
einem Knoten in der Business Capability Map zuzuordnen.

Story: {title}
Beschreibung: {description}
Acceptance Criteria: {acceptance_criteria}

Capability Map der Organisation:
{capability_tree_as_indented_text}

Führe eine kurze Konversation, um den passenden Knoten zu ermitteln.
Sobald du dir sicher bist, antworte mit deinem Vorschlag im Format:
<!--proposal:{"node_id":"<UUID>","path":"<Capability> › <L1> › <L2>"}-->

Schreibe den Vorschlag ans Ende deiner Antwort, nach einer kurzen Begründung.
```

Der Capability-Baum wird als eingerückter Text serialisiert:
```
Erzeugung & Beschaffung
  Stromerzeugung
    Konventionelle Erzeugung
    Erneuerbare Energien
  Wärmeerzeugung
...
```

### 3.3 Chat-Endpoint-Anpassung

`POST /stories/{story_id}/assistant/capability/chat`:
- Lädt Story-Felder (title, description, acceptance_criteria) aus DB
- Lädt alle `CapabilityNode` der Org (flat list, sortiert nach node_type + sort_order)
- Serialisiert Baum als eingerückten Text
- Injiziert beides ins System-Prompt
- Ansonsten identische Logik wie dod/features (SSE, message history, proposal extraction)

### 3.4 Atomarer Zuweisung-Endpoint

`PATCH /api/v1/user-stories/{story_id}/capability-assignment`

Request Body:
```json
{ "node_id": "uuid" }
```

Logik:
1. Prüfe, dass `node_id` zu einem `CapabilityNode` der Org gehört (404 sonst)
2. Lösche alle bestehenden `ArtifactAssignment` für `artifact_type="user_story"`, `artifact_id=story_id` der Org
3. Erstelle neuen `ArtifactAssignment` mit `relation_type="primary"`
4. Commit + return Assignment mit Node-Pfad

`DELETE /api/v1/user-stories/{story_id}/capability-assignment`
- Löscht alle Assignments für diese Story (kein Body)

Response für GET (bestehender Assignments-Endpoint wird genutzt):
`GET /api/v1/capabilities/orgs/{org_id}/assignments?artifact_type=user_story&artifact_id={story_id}`

### 3.5 Node-Pfad im Response

Der PATCH-Response enthält zusätzlich `node_path: str` (Breadcrumb-String), damit das Frontend keine separaten Lookups braucht.

Erweiterung `ArtifactAssignmentRead` um optionales Feld `node_path: Optional[str] = None`.

Der Pfad wird im Router aus der geladenen `CapabilityNode`-Hierarchie berechnet (rekursiver Walk über parent_id bis zur Wurzel).

---

## Section 4: Frontend

### 4.1 Neue Komponente: `CapabilityAssignmentSection`

Datei: `frontend/components/stories/CapabilityAssignmentSection.tsx`

Props:
```typescript
interface Props {
  storyId: string;
  orgId: string;
  story: UserStory;
}
```

Zustand:
- `assignment` — via SWR: `GET /api/v1/capabilities/orgs/{orgId}/assignments?artifact_type=user_story&artifact_id={storyId}`
- `chatOpen: boolean`

Render (kein Eintrag):
```
[ BCM-Icon ] Business Capability
Noch keine Zuweisung.
[ Via Chat zuweisen ]
```

Render (Eintrag vorhanden):
```
[ BCM-Icon ] Business Capability
Erzeugung & Beschaffung › Stromerzeugung › Konventionelle Erzeugung  [ × ]
[ Ändern ]
```

### 4.2 Neue Komponente: `StoryCapabilityChatPanel`

Datei: `frontend/components/stories/StoryCapabilityChatPanel.tsx`

Wrapper um `StoryAssistantPanel` mit:
- `sessionType="capability"`
- Custom `renderProposal`: rendert Proposal `{"node_id":"...","path":"..."}` als Breadcrumb-Karte mit "Übernehmen"-Button
- On "Übernehmen": `PATCH /api/v1/user-stories/{storyId}/capability-assignment` → mutate SWR → `onAssigned()` callback → Chat schließen

### 4.3 Integration in Prozesse-Tab

`frontend/app/[org]/stories/[id]/page.tsx`:

```tsx
{activeTab === "processes" && (
  <div className="space-y-6">
    <CapabilityAssignmentSection storyId={...} orgId={...} story={story} />
    <StoryProcessSection storyId={...} orgId={...} />
  </div>
)}
```

Tab-Reihenfolge in `ALL_TABS`:
```typescript
{ id: "story",     label: ... },
{ id: "processes", label: ... },  // ← verschoben
{ id: "features",  label: ... },
{ id: "tests",     label: ... },
{ id: "dod",       label: ... },
{ id: "docs",      label: ... },
{ id: "prompt",    label: ... },
```

`ROLE_TABS`:
```typescript
user:      ["story", "processes", "dod", "tests", "features", "docs"],
ba:        ["story", "processes", "dod", "tests", "features", "docs"],
architect: ["story", "processes", "dod", "features", "docs", "prompt"],
developer: ["story", "processes", "dod", "tests", "features", "prompt"],
tester:    ["story", "tests"],
release:   ["story", "processes", "tests", "features", "docs"],
```

---

## Section 5: Datenfluss

```
User öffnet Story → Prozesse-Tab
  → SWR lädt GET /capabilities/orgs/{orgId}/assignments?artifact_type=user_story&artifact_id={storyId}
  → Zuweisung oder Leerstand anzeigen

User klickt "Via Chat zuweisen"
  → StoryCapabilityChatPanel öffnet
  → POST /stories/{storyId}/assistant/capability (Session erstellen falls nicht existiert)
  → Chat-Nachrichten via POST /stories/{storyId}/assistant/capability/chat (SSE)
  → AI antwortet mit <!--proposal:{"node_id":"...","path":"..."}-->
  → Frontend zeigt Proposal-Karte

User klickt "Übernehmen"
  → PATCH /api/v1/user-stories/{storyId}/capability-assignment {node_id}
  → SWR mutate → Breadcrumb erscheint
  → Chat schließt sich
```

---

## Section 6: Fehlerbehandlung

- Capability-Baum leer (Org nicht initialisiert): Chat-Endpoint gibt 400 mit sprechender Fehlermeldung zurück; Frontend zeigt Hinweis "Bitte zuerst die Capability Map einrichten"
- node_id aus Proposal nicht in Org-Baum: PATCH gibt 404; Frontend zeigt "Knoten nicht gefunden, bitte erneut versuchen"
- Session-Typ nicht erlaubt: bestehende 422-Validierung greift

---

## Out of Scope

- Mehrfach-Zuweisungen (primary + secondary) pro Story
- Capability-Zuweisung für Epics/Projects (eigener Scope)
- BCM-Filter in der Story-Liste
