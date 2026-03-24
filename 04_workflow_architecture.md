# 04 — Workflow Architecture (n8n)

## Grundprinzipien

- n8n ist die **einzige** Orchestrierungsinstanz
- Workflows sind **versioniert** (Definition gespeichert in `WorkflowDefinition`)
- Jede Ausführung speichert **Input-, Kontext- und Ergebnis-Snapshot** in `WorkflowExecution`
- AI-Schritte speichern **Modell-ID, Prompt-Referenz, Temperatur und Token-Counts**
- **Reproduzierbarkeit** ist Pflicht — kein impliziter globaler Zustand

---

## Workflow 1: User Provisioning

**Name:** `user-provisioning`
**Trigger:** `event: user.invited` (via Backend-Webhook)
**Zweck:** Neuen Nutzer onboarden, E-Mail senden, Gruppen zuweisen

### Input Payload
```json
{
  "process_id": "uuid",
  "event": "user.invited",
  "membership_id": "uuid",
  "user": {
    "id": "uuid", "email": "...", "display_name": "..."
  },
  "organization": {
    "id": "uuid", "name": "...", "slug": "..."
  },
  "invited_by": { "id": "uuid", "display_name": "..." },
  "assigned_roles": ["org_member"],
  "context": { "environment": "prod" }
}
```

### Steps
1. **Validate Input** — Schema-Validierung gegen `user_provisioning_input.schema.json`
2. **Check Duplicate** — Prüfe ob Membership bereits aktiv ist
3. **Send Invitation Email** — Template-E-Mail via SMTP/Provider
4. **Create Default Groups** — Optional: Auto-Assign zu Default-Gruppen
5. **Trigger AI Welcome** — Optional: ScrumMasterAI-Begrüßungsnotiz
6. **Update Membership Status** — PATCH membership.status = 'active' (nach Annahme)
7. **Emit Event** — `user.provisioned` Event via Redis Pub/Sub
8. **Persist Execution** — WorkflowExecution.result_snapshot setzen

### Ausgaben
```json
{
  "status": "completed",
  "membership_id": "uuid",
  "email_sent": true,
  "groups_assigned": ["uuid"],
  "provisioned_at": "ISO8601"
}
```

### Fehlerfälle
| Fehler | Aktion |
|---|---|
| Invalid Input | Workflow abbrechen, Error-Event emittieren |
| Email-Versand fehlgeschlagen | Retry 3x, dann Fehler loggen + Alert |
| User already active | Idempotenz-Check, kein Fehler |

---

## Workflow 2: Story Lifecycle

**Name:** `story-lifecycle`
**Trigger:** `webhook: story.status_changed`
**Zweck:** Status-Übergänge einer Story orchestrieren, AI-Aktionen auslösen

### Input Payload
```json
{
  "process_id": "uuid",
  "event": "story.status_changed",
  "story": {
    "id": "uuid",
    "title": "...",
    "status_from": "draft",
    "status_to": "ready",
    "version": 3,
    "assignee_id": "uuid",
    "acceptance_criteria": [],
    "story_points": 5
  },
  "organization": { "id": "uuid" },
  "triggered_by": { "id": "uuid" }
}
```

### Steps (status_to = "ready")
1. **Validate Status Transition** — Erlaubte Übergänge prüfen
2. **ScrumMasterAI: Definition of Ready Check**
   - Modell: `claude-sonnet-4-6`
   - Prompt-Ref: `prompts/scrum_master/dor_check.md`
   - Output: `{ ready: bool, missing_fields: [], suggestions: [] }`
3. **Gate: DoR passed?**
   - Ja → weiter
   - Nein → Status zurück auf `draft`, Kommentar erstellen
4. **Notify Assignee** — Push-Notification / E-Mail
5. **Persist Execution**

### Steps (status_to = "in_progress")
1. **Validate**
2. **ArchitectAI: Implementation Hint** (optional, nur bei komplexen Stories)
3. **Create Sub-Tasks** (optional)
4. **Emit Event: `story.development_started`**

### Steps (status_to = "done")
1. **Validate**
2. **TestingAI: Test Coverage Check**
3. **Gate: Tests passed?**
4. **DocumentationTrainingAI: Generate Story Summary**
5. **Emit Event: `story.completed`**

### Ausgaben
```json
{
  "status": "completed",
  "story_id": "uuid",
  "transition": "draft→ready",
  "ai_assessments": [{ "agent": "ScrumMasterAI", "status": "OK" }],
  "gate_decision": "approved"
}
```

---

## Workflow 3: AI Delivery Workflow (Master Orchestrator)

**Name:** `ai-delivery`
**Trigger:** `manual` oder `webhook: story.ai_delivery_requested`
**Zweck:** Vollständige AI-gesteuerte Story-Umsetzung von Intake bis Release

Dieser Workflow implementiert den **N8N Master Orchestrator** (siehe `11_n8n_orchestrator.md`).

### Input Payload (Mindestform)
```json
{
  "process_id": "uuid",
  "story": {
    "id": "uuid",
    "title": "...",
    "description": "...",
    "version": 1
  },
  "context": {
    "organization_id": "uuid",
    "requested_by": "uuid",
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
  }
}
```

### Stage-Sequenz

```
intake
  ↓
story_analysis          [ScrumMasterAI]
  ↓ (ready)
architecture_design     [ArchitectAI]
  ↓
architecture_review     [SecurityAI || PerformanceAI || UXAI || DatabaseAI || NetworkAI || TestingAI] (parallel)
  ↓
architecture_consolidation [Orchestrator: Gate Decision]
  ↓ (approved)
implementation          [CodingAI]
  ↓
post_implementation_review [SecurityAI || PerformanceAI || TestingAI || DatabaseAI || NetworkAI || UXAI] (parallel)
  ↓ (all passed)
deployment_preparation  [DeployAI || SecurityAI || NetworkAI] (parallel)
  ↓
documentation_training  [DocumentationTrainingAI]
  ↓
final_release_decision  [Orchestrator]
  ↓ (all gates passed)
done
```

### Rework-Schleifen
```
architecture_review → BLOCKING Security/Performance → rework_architecture → architecture_design
post_review → BLOCKING Security/Testing → rework_implementation → implementation
deployment → BLOCKING Network/Security → rework_deployment → deployment_preparation
```

### Persistenz je Stage
Jede Stage schreibt:
```json
{
  "stage": "architecture_review",
  "started_at": "ISO8601",
  "completed_at": "ISO8601",
  "agent_artifacts": [],
  "gate_decision": {},
  "decision_log": []
}
```

---

## Workflow 4: Deployment Workflow

**Name:** `deployment`
**Trigger:** `webhook: release.approved` oder `manual`
**Zweck:** Container-Build und Deployment orchestrieren

### Input Payload
```json
{
  "process_id": "uuid",
  "release": {
    "id": "uuid",
    "version": "1.2.0",
    "story_ids": ["uuid"],
    "files_changed": [],
    "services_affected": ["backend", "frontend"]
  },
  "context": {
    "organization_id": "uuid",
    "environment": "staging",
    "triggered_by": "uuid"
  }
}
```

### Steps
1. **Validate Release Artifacts** — Schema-Validierung
2. **SecurityAI: Pre-Deployment Security Check**
   - Secrets Scan
   - Config Exposure Check
   - Dependency Vulnerabilities
3. **Gate: Security passed?**
4. **NetworkAI: Routing & DNS Check**
   - Traefik-Labels prüfen
   - Port-Konflikte prüfen
5. **DeployAI: Compose Diff** — Änderungen am Docker Compose
6. **DeployAI: Docker Build Plan** — Welche Images werden gebaut?
7. **Gate: Deployment Plan valid?**
8. **Execute: docker compose pull && docker compose up -d**
9. **Healthcheck: alle Dienste erreichbar?**
10. **Gate: Healthchecks passed?**
11. **Rollback** wenn Gate 10 fehlschlägt
12. **Emit Event: `deployment.completed`** oder `deployment.failed`
13. **DocumentationTrainingAI: Deployment-Log**

### Ausgaben
```json
{
  "status": "deployed",
  "environment": "staging",
  "services_deployed": ["backend", "frontend"],
  "version": "1.2.0",
  "deployed_at": "ISO8601",
  "healthchecks": { "backend": "ok", "frontend": "ok" }
}
```

### Fehlerfälle
| Fehler | Aktion |
|---|---|
| Security BLOCKING | Deployment abbrechen, Rework-Artefakt erzeugen |
| Healthcheck failed | Automatischer Rollback, Alert |
| Compose-Fehler | Deployment abbrechen, Error-Log |

---

## AI-Step Persistenz (alle Workflows)

Jeder AI-Schritt in einem Workflow muss folgendes persistieren:

```json
{
  "step_id": "uuid",
  "workflow_execution_id": "uuid",
  "agent_role": "SecurityAI",
  "model_id": "claude-sonnet-4-6",
  "prompt_ref": "prompts/security/architecture_review.md",
  "prompt_version": "2.1",
  "temperature": 0.1,
  "max_tokens": 4096,
  "input_tokens": 1200,
  "output_tokens": 800,
  "input_snapshot": {},
  "output_snapshot": {},
  "started_at": "ISO8601",
  "completed_at": "ISO8601"
}
```

**Zweck:** Vollständige Reproduzierbarkeit jeder KI-Entscheidung.
