# 08 — JSON Schemas

Alle Schemas folgen JSON Schema Draft-07.
Speicherort: `schemas/` im Repository-Root.

---

## 1. Agent Artifact Schema

**Datei:** `schemas/agent-artifact.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://platform.local/schemas/agent-artifact.v1.json",
  "title": "AgentArtifact",
  "description": "Standardisiertes Ausgabeformat für alle AI-Agenten",
  "type": "object",
  "required": ["agent", "status", "artifact_type", "artifact", "blocking"],
  "additionalProperties": false,
  "properties": {
    "agent": {
      "type": "string",
      "enum": [
        "ScrumMasterAI", "ArchitectAI", "CodingAI", "SecurityAI",
        "PerformanceAI", "UXAI", "DatabaseAI", "NetworkAI",
        "DeployAI", "TestingAI", "DocumentationTrainingAI"
      ],
      "description": "Erzeugende Agentenrolle"
    },
    "status": {
      "type": "string",
      "enum": ["OK", "WARNING", "BLOCKING"],
      "description": "Gesamtstatus des Artefakts"
    },
    "artifact_type": {
      "type": "string",
      "description": "Typ des Artefakts, z.B. architecture_design, security_review"
    },
    "artifact": {
      "type": "object",
      "description": "Eigentlicher Artefakt-Inhalt (typ-spezifisch)"
    },
    "blocking": {
      "type": "boolean",
      "description": "True = blockiert Fortschritt im Workflow"
    },
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "severity", "description"],
        "properties": {
          "id": { "type": "string" },
          "severity": { "type": "string", "enum": ["info", "warning", "critical"] },
          "description": { "type": "string" },
          "location": { "type": "string" },
          "recommendation": { "type": "string" }
        }
      }
    },
    "required_actions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["action", "priority"],
        "properties": {
          "action": { "type": "string" },
          "priority": { "type": "string", "enum": ["low", "medium", "high", "critical"] },
          "assignee_agent": { "type": "string" },
          "deadline": { "type": "string", "format": "date-time" }
        }
      }
    },
    "meta": {
      "type": "object",
      "properties": {
        "model_id": { "type": "string" },
        "prompt_ref": { "type": "string" },
        "prompt_version": { "type": "string" },
        "temperature": { "type": "number" },
        "input_tokens": { "type": "integer" },
        "output_tokens": { "type": "integer" },
        "generated_at": { "type": "string", "format": "date-time" }
      }
    }
  }
}
```

---

## 2. Workflow Stage Schema

**Datei:** `schemas/workflow-stage.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://platform.local/schemas/workflow-stage.v1.json",
  "title": "WorkflowStage",
  "description": "Repräsentiert den Zustand einer Workflow-Stage",
  "type": "object",
  "required": ["stage", "status", "started_at"],
  "additionalProperties": false,
  "properties": {
    "stage": {
      "type": "string",
      "enum": [
        "intake", "story_analysis", "architecture_design",
        "architecture_review", "architecture_consolidation",
        "implementation", "post_implementation_review",
        "deployment_preparation", "documentation_training",
        "final_release_decision", "done",
        "rework_architecture", "rework_implementation", "rework_deployment"
      ]
    },
    "status": {
      "type": "string",
      "enum": ["pending", "in_progress", "completed", "blocked", "rework_required"]
    },
    "started_at": {
      "type": "string",
      "format": "date-time"
    },
    "completed_at": {
      "type": ["string", "null"],
      "format": "date-time"
    },
    "agent_artifacts": {
      "type": "array",
      "items": { "$ref": "agent-artifact.v1.json" }
    },
    "gate_decision": {
      "$ref": "gate-decision.v1.json"
    },
    "rework_instruction": {
      "oneOf": [
        { "$ref": "rework-instruction.v1.json" },
        { "type": "null" }
      ]
    },
    "decision_log": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["timestamp", "decision", "reason"],
        "properties": {
          "timestamp": { "type": "string", "format": "date-time" },
          "decision": { "type": "string" },
          "reason": { "type": "string" },
          "triggered_by": { "type": "string" }
        }
      }
    }
  }
}
```

---

## 3. Gate Decision Schema

**Datei:** `schemas/gate-decision.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://platform.local/schemas/gate-decision.v1.json",
  "title": "GateDecision",
  "description": "Entscheidung an einem Workflow-Gate",
  "type": "object",
  "required": ["gate_id", "decision", "evaluated_at", "rules_applied"],
  "additionalProperties": false,
  "properties": {
    "gate_id": {
      "type": "string",
      "description": "Identifier des Gates, z.B. architecture_approved"
    },
    "decision": {
      "type": "string",
      "enum": ["approved", "approved_with_actions", "rework_required", "blocked"],
      "description": "Ergebnis der Gate-Prüfung"
    },
    "evaluated_at": {
      "type": "string",
      "format": "date-time"
    },
    "rules_applied": {
      "type": "array",
      "description": "Angewendete Entscheidungsregeln in Prioritätsreihenfolge",
      "items": {
        "type": "object",
        "required": ["rule", "result"],
        "properties": {
          "rule": { "type": "string" },
          "result": { "type": "string", "enum": ["passed", "warning", "blocked"] },
          "detail": { "type": "string" }
        }
      }
    },
    "blocking_agents": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Agenten die BLOCKING gemeldet haben"
    },
    "warning_agents": {
      "type": "array",
      "items": { "type": "string" }
    },
    "actions_required": {
      "type": "array",
      "items": { "type": "string" }
    },
    "next_stage": {
      "type": "string",
      "description": "Folge-Stage basierend auf der Entscheidung"
    }
  }
}
```

---

## 4. Rework Instruction Schema

**Datei:** `schemas/rework-instruction.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://platform.local/schemas/rework-instruction.v1.json",
  "title": "ReworkInstruction",
  "description": "Anweisung zur Überarbeitung an einen Agenten",
  "type": "object",
  "required": ["rework_id", "rework_type", "triggered_by", "reason", "next_agent", "required_actions"],
  "additionalProperties": false,
  "properties": {
    "rework_id": { "type": "string", "format": "uuid" },
    "rework_type": {
      "type": "string",
      "enum": ["rework_architecture", "rework_implementation", "rework_deployment"]
    },
    "triggered_by": {
      "type": "string",
      "description": "Agent oder System das den Rework ausgelöst hat"
    },
    "reason": {
      "type": "string",
      "description": "Klare Beschreibung warum Rework notwendig ist"
    },
    "next_agent": {
      "type": "string",
      "description": "Zielagent für den Rework, z.B. ArchitectAI"
    },
    "required_actions": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["action", "priority"],
        "properties": {
          "action": { "type": "string" },
          "priority": { "type": "string", "enum": ["low", "medium", "high", "critical"] },
          "context": { "type": "string" },
          "finding_ref": { "type": "string" }
        }
      }
    },
    "previous_artifact_ids": {
      "type": "array",
      "items": { "type": "string" }
    },
    "created_at": { "type": "string", "format": "date-time" },
    "deadline": { "type": ["string", "null"], "format": "date-time" }
  }
}
```

---

## 5. Release Decision Schema

**Datei:** `schemas/release-decision.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://platform.local/schemas/release-decision.v1.json",
  "title": "ReleaseDecision",
  "description": "Finale Freigabe-Entscheidung für ein Release",
  "type": "object",
  "required": [
    "release_id", "process_id", "decision",
    "gates_status", "evaluated_at"
  ],
  "additionalProperties": false,
  "properties": {
    "release_id": { "type": "string", "format": "uuid" },
    "process_id": { "type": "string", "format": "uuid" },
    "story_id": { "type": "string", "format": "uuid" },
    "decision": {
      "type": "string",
      "enum": ["approved", "blocked"],
      "description": "Freigabe nur wenn ALLE gates passed sind"
    },
    "gates_status": {
      "type": "object",
      "required": [
        "architecture_approved",
        "security_passed",
        "performance_passed",
        "testing_passed",
        "deployment_ready",
        "documentation_ready"
      ],
      "properties": {
        "architecture_approved": { "type": "boolean" },
        "security_passed": { "type": "boolean" },
        "performance_passed": { "type": "boolean" },
        "testing_passed": { "type": "boolean" },
        "deployment_ready": { "type": "boolean" },
        "documentation_ready": { "type": "boolean" }
      }
    },
    "evaluated_at": { "type": "string", "format": "date-time" },
    "approved_by": {
      "type": ["string", "null"],
      "description": "User-ID oder 'orchestrator' bei automatischer Freigabe"
    },
    "version": { "type": "string", "description": "Release-Version, z.B. 1.2.0" },
    "artifact_ids": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Alle Artefakt-IDs die zur Entscheidung geführt haben"
    },
    "notes": { "type": "string" }
  }
}
```

---

## 6. Orchestrator Output Schema

**Datei:** `schemas/orchestrator-output.v1.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://platform.local/schemas/orchestrator-output.v1.json",
  "title": "OrchestratorOutput",
  "description": "Standardisierter Output des Master Orchestrators pro Stage",
  "type": "object",
  "required": [
    "process_id", "current_stage", "next_stage",
    "status", "blocking_issues", "warnings",
    "required_agent_calls", "artifacts_to_validate",
    "gate_decision", "decision_log"
  ],
  "additionalProperties": false,
  "properties": {
    "process_id": { "type": "string", "format": "uuid" },
    "current_stage": { "type": "string" },
    "next_stage": { "type": "string" },
    "status": {
      "type": "string",
      "enum": ["in_progress", "blocked", "rework_required", "approved", "done"]
    },
    "blocking_issues": {
      "type": "array",
      "items": { "type": "string" }
    },
    "warnings": {
      "type": "array",
      "items": { "type": "string" }
    },
    "required_agent_calls": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["agent", "stage", "input"],
        "properties": {
          "agent": { "type": "string" },
          "stage": { "type": "string" },
          "input": { "type": "object" },
          "parallel": { "type": "boolean", "default": false }
        }
      }
    },
    "artifacts_to_validate": {
      "type": "array",
      "items": { "type": "string" }
    },
    "gate_decision": {
      "oneOf": [
        { "$ref": "gate-decision.v1.json" },
        { "type": "null" }
      ]
    },
    "rework_instruction": {
      "oneOf": [
        { "$ref": "rework-instruction.v1.json" },
        { "type": "null" }
      ]
    },
    "decision_log": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["timestamp", "decision", "reason"],
        "properties": {
          "timestamp": { "type": "string", "format": "date-time" },
          "decision": { "type": "string" },
          "reason": { "type": "string" },
          "priority_rule_applied": { "type": "string" }
        }
      }
    }
  }
}
```
