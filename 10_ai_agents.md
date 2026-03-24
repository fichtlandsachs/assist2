# 10 — AI Agents

## Übersicht

Das AI-Delivery-Team besteht aus 11 spezialisierten Agentenrollen.
Jeder Agent:
- hat eine klar abgegrenzte Zuständigkeit
- liefert strukturierte JSON-Artefakte
- kann BLOCKING, WARNING oder OK signalisieren
- hat einen System-Prompt und domänenspezifische Task-Prompts

---

## Prioritätsregel (unveränderlich)

Bei Konflikten zwischen Agenten-Empfehlungen gilt zwingend:

```
1. Security  (höchste Priorität)
2. Performance
3. Feature

SecurityAI BLOCKING > PerformanceAI BLOCKING > alle anderen
```

---

## Agentenrollen

### ScrumMasterAI

**Verantwortung:**
- Definition of Ready (DoR) prüfen
- Aufgaben und Abhängigkeiten identifizieren
- Benötigte Agenten bestimmen
- Story in umsetzbare Subtasks zerlegen

**Aktivierung:** Story Analysis Stage

**Input:**
```json
{
  "story": { "id": "...", "title": "...", "description": "...", "acceptance_criteria": [] },
  "organization_context": {}
}
```

**Output (Artefakt-Typ: `story_analysis`):**
```json
{
  "agent": "ScrumMasterAI",
  "status": "OK | WARNING | BLOCKING",
  "artifact_type": "story_analysis",
  "artifact": {
    "dor_passed": true,
    "missing_fields": [],
    "tasks": [{ "title": "...", "estimated_points": 3 }],
    "dependencies": [],
    "required_agents": ["ArchitectAI", "CodingAI", "SecurityAI"],
    "risk_assessment": "low | medium | high",
    "suggestions": []
  },
  "blocking": false
}
```

**BLOCKING wenn:** DoR nicht erfüllt, Pflichtfelder fehlen, Story nicht umsetzbar

---

### ArchitectAI

**Verantwortung:**
- Technische Architektur für die Story entwerfen
- Service-Auswirkungen identifizieren
- API-Design vorschlagen
- DB-Schema-Änderungen planen
- Entscheidungen dokumentieren

**Aktivierung:** Architecture Design Stage

**Output (Artefakt-Typ: `architecture_design`):**
```json
{
  "agent": "ArchitectAI",
  "status": "OK",
  "artifact_type": "architecture_design",
  "artifact": {
    "components_affected": ["backend", "frontend"],
    "services_changed": [],
    "api_changes": [{ "method": "POST", "path": "/api/v1/...", "breaking": false }],
    "db_changes": [{ "table": "...", "operation": "add_column", "column": "..." }],
    "new_dependencies": [],
    "architecture_decisions": [{ "decision": "...", "reason": "...", "alternatives": [] }],
    "risks": [],
    "diagram_description": "..."
  },
  "blocking": false
}
```

---

### CodingAI

**Verantwortung:**
- Implementierung auf Basis der freigegebenen Architektur
- Code schreiben (Backend, Frontend, Migrations)
- Tests hinzufügen
- Code-Dokumentation

**Aktivierung:** Implementation Stage (nur nach Architecture approved)

**Output (Artefakt-Typ: `implementation`):**
```json
{
  "agent": "CodingAI",
  "status": "OK",
  "artifact_type": "implementation",
  "artifact": {
    "files_changed": [
      { "path": "backend/app/models/user.py", "operation": "modified", "summary": "..." }
    ],
    "tests_added": [
      { "path": "backend/tests/...", "type": "integration", "coverage_area": "..." }
    ],
    "migrations_added": [],
    "breaking_changes": false,
    "notes": "...",
    "estimated_test_coverage": 85
  },
  "blocking": false
}
```

---

### SecurityAI

**Verantwortung:**
- Sicherheitsrisiken in Architektur und Implementierung identifizieren
- OWASP Top 10 prüfen
- Secrets-Handling prüfen
- Permission-Logik verifizieren
- Deployment-Sicherheit prüfen

**Aktivierung:** Architecture Review, Post-Implementation Review, Deployment Preparation

**Output (Artefakt-Typ: `security_review`):**
```json
{
  "agent": "SecurityAI",
  "status": "OK | WARNING | BLOCKING",
  "artifact_type": "security_review",
  "artifact": {
    "owasp_checks": [
      { "category": "A01:2021-Broken Access Control", "status": "passed", "notes": "" }
    ],
    "secrets_scan": { "status": "clean", "findings": [] },
    "permission_check": { "status": "passed" },
    "vulnerability_summary": { "critical": 0, "high": 0, "medium": 1, "low": 2 }
  },
  "findings": [
    { "id": "SEC-001", "severity": "warning", "description": "...", "recommendation": "..." }
  ],
  "blocking": false
}
```

**BLOCKING wenn:** kritische oder hohe Sicherheitslücke, fehlende Permission-Prüfung, exposed Secrets

---

### PerformanceAI

**Verantwortung:**
- Performance-Auswirkungen der Architektur bewerten
- N+1-Query-Probleme identifizieren
- Caching-Strategien empfehlen
- Response-Zeit-Erwartungen setzen

**Aktivierung:** Architecture Review, Post-Implementation Review

**Output (Artefakt-Typ: `performance_review`):**
```json
{
  "agent": "PerformanceAI",
  "status": "OK",
  "artifact_type": "performance_review",
  "artifact": {
    "estimated_response_time_ms": 120,
    "db_queries_per_request": 3,
    "n1_query_risk": "low",
    "caching_recommended": true,
    "caching_strategy": "Redis TTL 300s für Permission-Aggregation",
    "load_concerns": []
  },
  "blocking": false
}
```

---

### UXAI

**Verantwortung:**
- UX-Konsistenz mit bestehender Shell prüfen
- Accessibility-Anforderungen prüfen
- UI-Flows validieren
- Naming und Labels prüfen

**Aktivierung:** Architecture Review (bei UI-Änderungen), Post-Implementation Review

**Output (Artefakt-Typ: `ux_review`):**
```json
{
  "agent": "UXAI",
  "status": "OK",
  "artifact_type": "ux_review",
  "artifact": {
    "consistency_check": "passed",
    "accessibility_issues": [],
    "flow_validation": "passed",
    "naming_issues": [],
    "recommendations": []
  },
  "blocking": false
}
```

---

### DatabaseAI

**Verantwortung:**
- Datenbankschema-Qualität prüfen
- Migration-Sicherheit prüfen (keine Datenverluste)
- Index-Strategie empfehlen
- Multi-Tenant-Isolation validieren

**Aktivierung:** Architecture Review, Post-Implementation Review

**Output (Artefakt-Typ: `database_review`):**
```json
{
  "agent": "DatabaseAI",
  "status": "OK",
  "artifact_type": "database_review",
  "artifact": {
    "schema_quality": "good",
    "migration_safety": "safe",
    "missing_indexes": [
      { "table": "user_stories", "column": "organization_id", "reason": "Tenant-Queries" }
    ],
    "tenant_isolation_check": "passed",
    "normalization_issues": []
  },
  "blocking": false
}
```

**BLOCKING wenn:** Migration würde Datenverlust verursachen, Tenant-Isolation verletzt

---

### NetworkAI

**Verantwortung:**
- Traefik-Routing-Konfiguration prüfen
- Port-Konflikte identifizieren
- Service-Discovery-Konsistenz prüfen
- Deployment-Netzwerk-Auswirkungen bewerten

**Aktivierung:** Architecture Review (bei neuen Services), Deployment Preparation

**Output (Artefakt-Typ: `network_review`):**
```json
{
  "agent": "NetworkAI",
  "status": "OK",
  "artifact_type": "network_review",
  "artifact": {
    "routing_check": "passed",
    "port_conflicts": [],
    "traefik_labels_valid": true,
    "new_routes": [],
    "internal_exposure_risk": "none"
  },
  "blocking": false
}
```

---

### DeployAI

**Verantwortung:**
- Deployment-Plan erstellen
- Docker Compose Diff berechnen
- Rollback-Strategie definieren
- Healthcheck-Plan erstellen
- Git-State validieren

**Aktivierung:** Deployment Preparation Stage

**Output (Artefakt-Typ: `deployment_plan`):**
```json
{
  "agent": "DeployAI",
  "status": "OK",
  "artifact_type": "deployment_plan",
  "artifact": {
    "git": {
      "branch": "feature/story-xxx",
      "commit": "abc123",
      "tag": "v1.2.0"
    },
    "services_changed": ["backend"],
    "docker_changes": {
      "rebuild_required": ["backend"],
      "compose_diff": "..."
    },
    "deployment_steps": ["pull", "build backend", "up -d backend", "healthcheck"],
    "rollback_plan": "docker compose up -d --scale backend=0 && tag v1.1.9",
    "checks": {
      "reproducible": true,
      "secrets_clean": true,
      "healthchecks_defined": true
    }
  },
  "blocking": false
}
```

---

### TestingAI

**Verantwortung:**
- Testabdeckung bewerten
- Fehlende Tests identifizieren
- Testqualität prüfen
- Integrationstests auf Vollständigkeit prüfen

**Aktivierung:** Architecture Review, Post-Implementation Review

**Output (Artefakt-Typ: `testing_review`):**
```json
{
  "agent": "TestingAI",
  "status": "OK",
  "artifact_type": "testing_review",
  "artifact": {
    "coverage_estimate": 82,
    "coverage_threshold": 80,
    "missing_tests": [
      { "type": "integration", "target": "permission check on story delete" }
    ],
    "test_quality": "good",
    "edge_cases_covered": true
  },
  "blocking": false
}
```

**BLOCKING wenn:** Coverage unter Threshold, kritische Pfade ungetestet

---

### DocumentationTrainingAI

**Verantwortung:**
- Technische Dokumentation generieren
- Confluence-Seitenstruktur erstellen
- Trainingsmaterialien erzeugen
- Changelogs schreiben
- Video-Scripts und PDF-Outlines erstellen

**Aktivierung:** Documentation & Training Stage

**Output (Artefakt-Typ: `documentation`):**
```json
{
  "agent": "DocumentationTrainingAI",
  "status": "OK",
  "artifact_type": "documentation",
  "artifact": {
    "confluence_structure": [
      { "title": "Feature: User Story Management", "parent": "Platform Docs", "content": "..." }
    ],
    "changelog_entry": "### v1.2.0\n- Added User Story Management Plugin\n- ...",
    "pdf_outline": ["Introduction", "Feature Overview", "How to Use", "API Reference"],
    "video_script": "Script: ...",
    "questionnaire": [
      { "question": "Was ist eine User Story?", "answer": "..." }
    ],
    "training_materials": []
  },
  "blocking": false
}
```

---

## Konfliktregel-Implementierung (Orchestrator-Logik)

```python
def apply_priority_rule(artifacts: list[AgentArtifact]) -> GateDecision:
    """
    Priorisierungsregel:
    1. Security BLOCKING → immer rework_required / blocked
    2. Performance BLOCKING → rework_required
    3. alle anderen BLOCKING → rework_required
    4. nur WARNINGs → approved_with_actions
    5. alle OK → approved
    """
    blocking_agents = [a.agent for a in artifacts if a.blocking]
    warning_agents = [a.agent for a in artifacts if a.status == "WARNING" and not a.blocking]

    if "SecurityAI" in blocking_agents:
        return GateDecision(decision="blocked", triggered_by="SecurityAI", ...)

    if "PerformanceAI" in blocking_agents:
        return GateDecision(decision="rework_required", triggered_by="PerformanceAI", ...)

    if blocking_agents:  # andere blockierende Agenten
        return GateDecision(decision="rework_required", triggered_by=blocking_agents[0], ...)

    if warning_agents:
        return GateDecision(decision="approved_with_actions", ...)

    return GateDecision(decision="approved", ...)
```
