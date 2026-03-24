# AI-Native Workspace Platform — Dokumentations-Index

Diese Sammlung bildet die vollständige technische Bauanleitung für die AI-Native Workspace Platform.
Alle Dateien sind eigenständig nutzbar und direkt als Grundlage für Codegenerierung einsetzbar.

---

## Dateien

| Datei | Typ | Inhalt |
|---|---|---|
| [00_overview.md](00_overview.md) | Architektur | Executive Summary, Service Landscape, Komponenten |
| [01_domain_model.md](01_domain_model.md) | Domain | 17 Entitäten: User, Org, Membership, Role, Permission, Group, Agent, Plugin, Workflow, Story, TestCase, Mail, Calendar |
| [02_api_design.md](02_api_design.md) | API | REST-Endpoints für alle 11 Domänen mit Request/Response-Strukturen |
| [03_plugin_architecture.md](03_plugin_architecture.md) | Plugin | Manifest, Lifecycle, Slot-System, Provider-Integration |
| [04_workflow_architecture.md](04_workflow_architecture.md) | Workflows | 4 n8n-Workflows: Provisioning, Story, AI Delivery, Deployment |
| [05_docker_infrastructure.md](05_docker_infrastructure.md) | Infra | Docker Compose, Traefik, Netzwerke, Dockerfiles, .env |
| [06_project_structure.md](06_project_structure.md) | Struktur | Vollständige Repository-Struktur mit Erläuterungen |
| [07_implementation_waves.md](07_implementation_waves.md) | Plan | 6 Implementierungswellen mit Tasks und Abhängigkeiten |
| [08_json_schemas.md](08_json_schemas.md) | Schemas | 6 JSON Schemas: AgentArtifact, WorkflowStage, GateDecision, Rework, Release, OrchestratorOutput |
| [09_code_generation_plan.md](09_code_generation_plan.md) | Codegen | Geordnete Dateiliste (150+ Dateien) für die Implementierung |
| [10_ai_agents.md](10_ai_agents.md) | AI | 11 Agentenrollen mit Zuständigkeiten, Input/Output-Formaten, Konfliktregeln |
| [11_n8n_orchestrator.md](11_n8n_orchestrator.md) | Orchestrator | Master Orchestrator: Stage-Logik, Gate-Regeln, Rework-Schleifen, Invarianten |

---

## Einstiegspunkte nach Aufgabe

### Ich möchte die Infrastruktur aufsetzen
→ `05_docker_infrastructure.md` → `06_project_structure.md` → `09_code_generation_plan.md` Phase 0

### Ich möchte das Backend implementieren
→ `01_domain_model.md` → `02_api_design.md` → `09_code_generation_plan.md` Phase 1–8

### Ich möchte ein Plugin entwickeln
→ `03_plugin_architecture.md` → `09_code_generation_plan.md` Phase 14

### Ich möchte n8n-Workflows einrichten
→ `04_workflow_architecture.md` → `11_n8n_orchestrator.md` → `08_json_schemas.md`

### Ich möchte AI-Agenten integrieren
→ `10_ai_agents.md` → `11_n8n_orchestrator.md` → `08_json_schemas.md`

### Ich möchte den Delivery-Prozess verstehen
→ `11_n8n_orchestrator.md` → `10_ai_agents.md` → `04_workflow_architecture.md`

### Ich möchte die Implementierungsreihenfolge planen
→ `07_implementation_waves.md` → `09_code_generation_plan.md`

---

## Technologiestack

| Komponente | Technologie |
|---|---|
| Frontend | Next.js 14 + TypeScript + Tailwind CSS |
| Backend | FastAPI + Python 3.12 + SQLAlchemy + Alembic |
| Datenbank | PostgreSQL 16 |
| Cache/Queue | Redis 7 + Celery |
| Workflow Engine | n8n (selbstgehostet) |
| Reverse Proxy | Traefik v3 |
| Container | Docker Compose |
| AI-Modell (Default) | claude-sonnet-4-6 |

---

## Konsistenzregeln (für Codegenerierung)

- Alle UUIDs: UUID v4
- Alle Timestamps: ISO 8601 in UTC
- Alle API-Pfade: `/api/v1/{resource}`
- Alle Plugin-Slugs: kebab-case
- Alle DB-Tabellen: snake_case plural
- Alle Env-Variablen: UPPER_SNAKE_CASE
- Tenant-Isolation: `organization_id` in ALLEN Org-gebundenen Queries
- Permissions: serverseitig geprüft, niemals im Frontend
- Secrets: niemals in API-Responses, nur via `.env`

---

## Offene Risiken & Annahmen

| # | Typ | Beschreibung |
|---|---|---|
| A1 | [ANNAHME] | n8n verwendet eigene PostgreSQL-Datenbank (`n8n_db`) |
| A2 | [ANNAHME] | Wave 1 implementiert OAuth nur für Google (GitHub/Apple Wave 3+) |
| A3 | [ANNAHME] | Authentik ist optional — Backend implementiert direkt OAuth2 in Wave 1 |
| A4 | [ANNAHME] | KI-Modell: `claude-sonnet-4-6` als Standard für alle Agenten |
| R1 | [RISIKO] | n8n-Versionsupdates können Workflow-Definitionen brechen → Workflows in Git versioniert |
| R2 | [RISIKO] | Plugin-Migrationen müssen getrennt von Core-Migrationen laufen → eigene Alembic-Branches |
| R3 | [RISIKO] | Rework-Schleifen ohne Iterations-Limit können endlos laufen → max. 3 Iterationen implementieren |
| T1 | [TRADE-OFF] | Docker Compose statt Kubernetes (Wave 1–3) — einfacher, weniger overhead, ausreichend |
| T2 | [TRADE-OFF] | Monorepo-Struktur — einfacher für Teams, aber später Splitting möglich |
