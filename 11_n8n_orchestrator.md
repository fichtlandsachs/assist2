# 11 — N8N Master Orchestrator

## Rolle

Der Master Orchestrator ist **kein Implementierungsagent**.
Er orchestriert, validiert, entscheidet und eskaliert.

Verantwortung:
- Entgegennahme von User Stories und Delivery-Requests
- Routing zu den richtigen AI-Agenten
- Anwendung der Priorisierungsregel (Security > Performance > Feature)
- Validierung aller Agenten-Artefakte gegen JSON Schemas
- Gate-Steuerung mit dokumentierten Entscheidungen
- Rework-Schleifen mit klaren Rework-Instructions
- Vollständige Nachvollziehbarkeit (Audit Trail)

---

## Workflow-Stages

```
intake
  │
  ▼
story_analysis          ← ScrumMasterAI
  │
  ▼ (ready)
architecture_design     ← ArchitectAI
  │
  ▼
architecture_review     ← [SecurityAI, PerformanceAI, UXAI, DatabaseAI, NetworkAI, TestingAI] parallel
  │
  ▼
architecture_consolidation  ← Orchestrator: Gate Decision
  │
  ├─ BLOCKING (Security/Performance) → rework_architecture → architecture_design
  │
  ▼ (approved / approved_with_actions)
implementation          ← CodingAI
  │
  ▼
post_implementation_review ← [SecurityAI, PerformanceAI, TestingAI, DatabaseAI, NetworkAI, UXAI] parallel
  │
  ├─ BLOCKING → rework_implementation → implementation
  │
  ▼ (all passed)
deployment_preparation  ← [DeployAI, SecurityAI, NetworkAI] parallel
  │
  ├─ BLOCKING → rework_deployment → deployment_preparation
  │
  ▼
documentation_training  ← DocumentationTrainingAI
  │
  ▼
final_release_decision  ← Orchestrator: alle Gates prüfen
  │
  ▼ (all gates passed)
done
```

---

## Stage: intake

**Zweck:** Input normalisieren, validieren, process_id erzeugen

**Eingangs-Validierung:**
- `story.id` vorhanden?
- `story.title` vorhanden?
- `story.description` nicht leer?
- `context.organization_id` vorhanden?
- `governance.priority_rule` = `["security", "performance", "feature"]`?

**Fehlerfall:** Pflichtfelder fehlen → `status: blocked`, keine Weiterleitung

**Output:**
```json
{
  "process_id": "uuid-v4",
  "current_stage": "intake",
  "next_stage": "story_analysis",
  "status": "in_progress",
  "blocking_issues": [],
  "warnings": [],
  "required_agent_calls": [
    { "agent": "ScrumMasterAI", "stage": "story_analysis", "input": { "story": {...} }, "parallel": false }
  ],
  "artifacts_to_validate": [],
  "gate_decision": null,
  "rework_instruction": null,
  "decision_log": [
    { "timestamp": "...", "decision": "intake_validated", "reason": "All required fields present" }
  ]
}
```

---

## Stage: story_analysis

**Zweck:** ScrumMasterAI bewertet Story

**Eingehend:** ScrumMasterAI Artefakt (Typ: `story_analysis`)

**Validierung:**
1. Schema-Validierung gegen `agent-artifact.v1.json`
2. `artifact_type` == `story_analysis`?
3. `artifact.dor_passed` auswerten

**Gate-Logik:**
```
IF artifact.blocking == true OR artifact.status == "BLOCKING":
    → status: rework_required
    → Rework-Artefakt erzeugen
    → next_stage: story_analysis (mit missing_fields)

ELSE IF artifact.status == "WARNING":
    → Warnings speichern, weiter zu architecture_design

ELSE:
    → next_stage: architecture_design
```

---

## Stage: architecture_design

**Zweck:** ArchitectAI entwirft Architektur

**Eingehend:** ArchitectAI Artefakt (Typ: `architecture_design`)

**Validierung:**
1. Schema-Validierung
2. `artifact.components_affected` nicht leer?
3. `artifact.architecture_decisions` dokumentiert?

**Gate-Logik:**
```
IF blocking:
    → rework_architecture
ELSE:
    → next_stage: architecture_review
    → required_agent_calls: alle 6 Review-Agenten (parallel: true)
```

---

## Stage: architecture_review

**Zweck:** 6 Agenten prüfen Architektur parallel

**Eingehend:** 6 Artefakte von SecurityAI, PerformanceAI, UXAI, DatabaseAI, NetworkAI, TestingAI

**Warten auf:** alle 6 Artefakte bevor Konsolidierung

**Validierung je Artefakt:**
1. Schema-Validierung
2. Korrekte `artifact_type` für jeweiligen Agenten?

---

## Stage: architecture_consolidation

**Zweck:** Orchestrator wendet Prioritätsregel an

**Priorisierungsregel (zwingend):**
```
PRIORITY 1: SecurityAI
  IF SecurityAI.blocking == true:
    decision = "blocked"
    rework_type = "rework_architecture"
    next_agent = "ArchitectAI"
    STOP

PRIORITY 2: PerformanceAI
  IF PerformanceAI.blocking == true:
    decision = "rework_required"
    rework_type = "rework_architecture"
    next_agent = "ArchitectAI"
    STOP

PRIORITY 3: alle anderen
  FOR each agent IN [UXAI, DatabaseAI, NetworkAI, TestingAI]:
    IF agent.blocking == true:
      decision = "rework_required"
      rework_type = "rework_architecture"
      next_agent = "ArchitectAI"
      STOP

IF warnings_only:
  decision = "approved_with_actions"
  actions = collect(all required_actions from warning agents)
  next_stage = "implementation"

IF all_ok:
  decision = "approved"
  next_stage = "implementation"
```

**Gate Decision Artefakt:**
```json
{
  "gate_id": "architecture_approved",
  "decision": "approved | approved_with_actions | rework_required | blocked",
  "evaluated_at": "ISO8601",
  "rules_applied": [
    { "rule": "SecurityAI priority check", "result": "passed" },
    { "rule": "PerformanceAI priority check", "result": "passed" }
  ],
  "blocking_agents": [],
  "warning_agents": ["DatabaseAI"],
  "actions_required": ["Add index on user_stories.organization_id"],
  "next_stage": "implementation"
}
```

---

## Stage: implementation

**Zweck:** CodingAI implementiert (nur mit freigegebener Architektur)

**Vorbedingung:** `architecture_approved` Gate = approved oder approved_with_actions

**Validierung CodingAI-Artefakt:**
- `files_changed` nicht leer?
- `tests_added` nicht leer? (mind. 1 Test)
- `breaking_changes` dokumentiert?

---

## Stage: post_implementation_review

**Zweck:** 6 Agenten prüfen Implementierung parallel

**Rework-Logik:**
```
SecurityAI.blocking    → rework_implementation → CodingAI
TestingAI.blocking     → rework_implementation → CodingAI
DatabaseAI.blocking    → rework_implementation → CodingAI
NetworkAI.blocking     → rework_implementation → CodingAI
PerformanceAI.blocking → rework_implementation → CodingAI
```

---

## Stage: deployment_preparation

**Zweck:** Deployment vorbereiten und validieren

**Parallel:** DeployAI + SecurityAI + NetworkAI

**Gate-Logik:**
```
IF DeployAI.artifact.checks.reproducible == false:
  → rework_deployment

IF SecurityAI.blocking:
  → rework_deployment

IF NetworkAI.blocking:
  → rework_deployment

IF DeployAI.artifact.checks.secrets_clean == false:
  → BLOCKING (Security-Priorität)
```

---

## Stage: final_release_decision

**Zweck:** Alle Gates zusammenführen, finale Freigabe

**Bedingungen für Freigabe (alle müssen true sein):**

```json
{
  "architecture_approved": true,
  "security_passed": true,
  "performance_passed": true,
  "testing_passed": true,
  "deployment_ready": true,
  "documentation_ready": true
}
```

**Falls alle true:**
```json
{
  "release_id": "uuid",
  "decision": "approved",
  "version": "...",
  "gates_status": { "all": true },
  "approved_by": "orchestrator",
  "artifact_ids": [...]
}
```

**Falls eine Bedingung false:**
```json
{
  "decision": "blocked",
  "blocking_gate": "security_passed",
  "reason": "SecurityAI blocking finding not resolved"
}
```

---

## Rework-Artefakt (Standard)

```json
{
  "rework_id": "uuid",
  "rework_type": "rework_architecture | rework_implementation | rework_deployment",
  "triggered_by": "SecurityAI",
  "reason": "SQL Injection risk in user story query (SEC-001)",
  "next_agent": "ArchitectAI",
  "required_actions": [
    {
      "action": "Parameterisierte Queries verwenden für UserStory.title Filter",
      "priority": "critical",
      "context": "backend/app/services/story_service.py:query_stories()",
      "finding_ref": "SEC-001"
    }
  ],
  "previous_artifact_ids": ["arch-artifact-uuid"],
  "created_at": "ISO8601"
}
```

---

## Persistenz-Anforderungen

Für jeden Workflow-Lauf **muss** existieren:

| Feld | Typ | Beschreibung |
|---|---|---|
| `process_id` | UUID | Eindeutiger Prozess-Identifier |
| `story_id` | UUID | Referenz auf UserStory |
| `story_version` | integer | Snapshot-Version der Story |
| `workflow_execution_id` | UUID | Referenz auf WorkflowExecution |
| `artifact_ids` | UUID[] | Alle erzeugten Artefakte |
| `stage_history` | object[] | Alle durchlaufenen Stages mit Timestamps |
| `decision_log` | object[] | Alle Entscheidungen mit Begründung |

**Unveränderlichkeit:** `input_snapshot` und `context_snapshot` sind nach dem Start nicht änderbar.

---

## Eingabe-Schema (Mindestform)

```json
{
  "process_id": "uuid",
  "story": {
    "id": "uuid",
    "title": "Als User möchte ich Storys filtern können",
    "description": "Die Story-Liste soll nach Status und Priorität filterbar sein",
    "version": 1
  },
  "context": {
    "organization_id": "uuid",
    "requested_by": "user-uuid",
    "environment": "dev"
  },
  "governance": {
    "priority_rule": ["security", "performance", "feature"],
    "required_gates": [
      "architecture_approved",
      "security_passed",
      "performance_passed",
      "testing_passed",
      "deployment_ready",
      "documentation_ready"
    ]
  },
  "existing_artifacts": []
}
```

---

## Invarianten (niemals verletzbar)

1. Kein Stage-Übergang ohne valides Artefakt
2. SecurityAI BLOCKING = immer blocked/rework — keine Ausnahmen
3. Unstrukturierte Agenten-Outputs werden abgewiesen (Schema-Validierung)
4. Jede Entscheidung wird im `decision_log` dokumentiert
5. `input_snapshot` und `context_snapshot` sind unveränderlich
6. Rework-Schleifen sind auf 3 Iterationen pro Stage begrenzt (dann: manueller Eingriff)
7. Fehlendes = Risiko, nicht Detail (Fehlende Informationen blockieren den Prozess)
