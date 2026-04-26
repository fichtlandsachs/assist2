# HeyKarl Backend — Architektur

## Plattform-Komponenten

```
backend/app/
├── modules/                        ← Neue Domain-Struktur
│   ├── core/                       ← HeyKarl Core
│   │   ├── models/                 Organisations, User, Roles, Stories, Epics, Projects
│   │   ├── routers/                REST-APIs für Core-Artefakte
│   │   ├── services/               Business Logic
│   │   └── schemas/                Pydantic Schemas
│   │
│   ├── compliance/                 ← HeyKarl Compliance Engine
│   │   ├── models/                 Controls, Frameworks, Assessments, Evidence
│   │   ├── routers/                Compliance APIs
│   │   ├── services/               Compliance Business Logic
│   │   └── schemas/
│   │
│   ├── conversation/               ← HeyKarl Conversation Engine
│   │   ├── models/                 Dialog Profiles, Messages, Sessions
│   │   ├── routers/                AI/Chat APIs
│   │   ├── services/               Prompt Control, Response Signals
│   │   └── schemas/
│   │
│   ├── knowledge/                  ← HeyKarl KnowledgeBase / RAG
│   │   ├── models/                 Document Chunks, RAG Zones, Trust Profiles
│   │   ├── routers/                RAG/Source APIs
│   │   ├── services/               Retrieval, Trust Engine, Embedding
│   │   └── schemas/
│   │
│   ├── integration/                ← HeyKarl Integration Layer
│   │   ├── models/                 Resources, Connectors, Credentials
│   │   ├── routers/                Integration APIs (Jira, n8n, Webhooks, ...)
│   │   ├── services/               Authentik, LiteLLM, n8n, Nextcloud, Jira, ...
│   │   └── schemas/
│   │
│   ├── accounting/                 ← Accounting
│   │   ├── models/                 Plans, Entitlements, Usage
│   │   ├── routers/                Billing APIs
│   │   ├── services/               Stripe, PayPal
│   │   └── schemas/
│   │
│   └── system/                     ← System / Security
│       ├── models/                 GlobalConfig, SystemConfig
│       ├── routers/                SuperAdmin APIs
│       ├── services/               Settings Service
│       └── schemas/
│
├── models/                         ← Flat model files (bleiben bestehen, Backward-Compat)
├── routers/                        ← Flat router files (bleiben bestehen, Backward-Compat)
├── services/                       ← Flat service files (bleiben bestehen, Backward-Compat)
├── core/                           ← Querschnittslogik (Auth, Billing Guard, Story Filter)
├── schemas/                        ← Shared Pydantic Schemas
└── main.py                         ← Router-Registrierung
```

## Ressourcen-Typen (Integration Layer)

| Typ                  | Beispiele                              | Location |
|----------------------|----------------------------------------|----------|
| `docker_service`     | Authentik, LiteLLM, n8n, Nextcloud    | docker   |
| `external_service`   | Jira Cloud, GitHub, SAP Help          | external |
| `database`           | PostgreSQL, Redis, MariaDB             | docker   |
| `admin_ui`           | pgAdmin, phpMyAdmin, Redis Commander  | docker   |
| `ai_model_gateway`   | LiteLLM                                | docker   |
| `automation_service` | n8n                                    | docker   |
| `identity_provider`  | Authentik                              | docker   |
| `file_source`        | Nextcloud, Fileshare                  | docker   |
| `utility_service`    | Stirling PDF, Whisper                 | docker   |
| `documentation_source`| Confluence, SAP Help Portal          | external |
| `api_connector`      | GitHub, ServiceNow                    | external |
| `webhook`            | Webhooks                               | external |
| `rag_source`         | Knowledge sources for RAG             | varies   |

## Override Policies

| Policy             | Beschreibung                                   |
|--------------------|------------------------------------------------|
| `locked`           | Org kann nicht überschreiben                   |
| `overridable`      | Org kann frei überschreiben                    |
| `extend_only`      | Org kann nur Werte hinzufügen                  |
| `disable_only`     | Org kann nur deaktivieren                      |
| `approval_required`| Org kann anfragen, Superadmin muss genehmigen  |

## Superadmin-Navigation

```
/superadmin
├── /dashboard
├── /core           → Core Settings (Tabs: General, Orgs, Roles, Artifacts, Stories, Flags)
├── /conversation   → Conversation Engine (Tabs: Profiles, Questions, Signals, Prompts, Test)
├── /compliance     → Compliance Engine (Tabs: Frameworks, Controls, Scoring, Gates)
├── /knowledge      → KnowledgeBase/RAG (Tabs: Sources, Ingest, Trust, Retrieval, Index)
├── /integration    → Integration Layer (Tabs: Overview, Docker, External, AdminUIs, ...)
├── /accounting     → Accounting (Tabs: Plans, Entitlements, Usage, Billing)
├── /resources      → Resources Overview (read-only status board)
└── /system         → System/Security (Tabs: Security, Backup, Settings, Audit)
```
