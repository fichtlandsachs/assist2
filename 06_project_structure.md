# 06 — Project Structure

## Repository-Struktur

```
platform/
├── frontend/                    # Next.js Workspace Shell
│   ├── app/                     # App Router
│   │   ├── (auth)/              # Auth-Routen (login, register, oauth)
│   │   ├── [org]/               # Org-gebundene Routen
│   │   │   ├── layout.tsx       # Org-Shell mit Sidebar
│   │   │   ├── dashboard/       # Dashboard
│   │   │   ├── members/         # Mitgliederverwaltung
│   │   │   ├── settings/        # Org-Einstellungen
│   │   │   └── plugins/         # Plugin-Routing
│   │   │       └── [slug]/      # Dynamisches Plugin-Routing
│   │   │           └── [...path]/
│   │   ├── layout.tsx           # Root Layout
│   │   └── page.tsx             # Landing / Redirect
│   ├── components/
│   │   ├── shell/               # WorkspaceShell, Sidebar, Topbar
│   │   ├── ui/                  # Shared UI-Komponenten (Button, Input, etc.)
│   │   ├── auth/                # AuthForms, OAuthButtons
│   │   └── plugins/             # Plugin-Slot-Renderer
│   ├── lib/
│   │   ├── api/                 # API-Client (fetch-Wrapper)
│   │   ├── auth/                # Auth-State, Token-Management
│   │   ├── plugins/             # Plugin-Registry, Slot-System
│   │   └── hooks/               # React Hooks
│   ├── types/                   # TypeScript Typdefinitionen
│   ├── public/                  # Statische Assets
│   ├── Dockerfile
│   ├── next.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                     # FastAPI Core API
│   ├── app/
│   │   ├── main.py              # FastAPI App, Router-Registrierung
│   │   ├── config.py            # Settings via pydantic-settings
│   │   ├── database.py          # SQLAlchemy Async Engine
│   │   ├── deps.py              # FastAPI Dependencies (auth, org, etc.)
│   │   ├── worker.py            # Celery App
│   │   │
│   │   ├── models/              # SQLAlchemy ORM Models
│   │   │   ├── user.py
│   │   │   ├── organization.py
│   │   │   ├── membership.py
│   │   │   ├── role.py
│   │   │   ├── group.py
│   │   │   ├── agent.py
│   │   │   ├── plugin.py
│   │   │   ├── workflow.py
│   │   │   └── __init__.py
│   │   │
│   │   ├── schemas/             # Pydantic Request/Response Schemas
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── organization.py
│   │   │   ├── membership.py
│   │   │   ├── role.py
│   │   │   ├── group.py
│   │   │   ├── plugin.py
│   │   │   ├── workflow.py
│   │   │   └── common.py        # Pagination, Error Response
│   │   │
│   │   ├── routers/             # FastAPI Router-Module
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── organizations.py
│   │   │   ├── memberships.py
│   │   │   ├── roles.py
│   │   │   ├── groups.py
│   │   │   ├── plugins.py
│   │   │   ├── workflows.py
│   │   │   └── agents.py
│   │   │
│   │   ├── services/            # Business Logic Layer
│   │   │   ├── auth_service.py
│   │   │   ├── user_service.py
│   │   │   ├── org_service.py
│   │   │   ├── membership_service.py
│   │   │   ├── permission_service.py
│   │   │   ├── plugin_service.py
│   │   │   ├── workflow_service.py
│   │   │   └── n8n_client.py    # n8n API Client
│   │   │
│   │   ├── core/                # Core Utilities
│   │   │   ├── security.py      # JWT, Password-Hashing, Encryption
│   │   │   ├── events.py        # Redis Pub/Sub Event Bus
│   │   │   ├── exceptions.py    # Custom Exception Classes
│   │   │   └── permissions.py   # Permission-Aggregation
│   │   │
│   │   └── tasks/               # Celery Tasks
│   │       ├── mail_sync.py
│   │       ├── calendar_sync.py
│   │       └── notifications.py
│   │
│   ├── migrations/              # Alembic Migrations
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial.py
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   │
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── alembic.ini
│
├── plugins/                     # Plugin-Pakete
│   ├── user-story/
│   │   ├── backend/
│   │   │   ├── routes.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── migrations/
│   │   ├── frontend/
│   │   │   ├── components/
│   │   │   ├── pages/
│   │   │   └── index.tsx
│   │   └── manifest.json
│   │
│   ├── unified-inbox/
│   │   ├── backend/
│   │   ├── frontend/
│   │   └── manifest.json
│   │
│   └── calendar/
│       ├── backend/
│       ├── frontend/
│       └── manifest.json
│
├── workflows/                   # n8n Workflow-Definitionen (JSON Export)
│   ├── user-provisioning.json
│   ├── story-lifecycle.json
│   ├── ai-delivery.json
│   └── deployment.json
│
├── schemas/                     # JSON Schemas
│   ├── plugin-manifest.v1.json
│   ├── agent-artifact.v1.json
│   ├── workflow-stage.v1.json
│   ├── gate-decision.v1.json
│   ├── rework-instruction.v1.json
│   ├── release-decision.v1.json
│   └── orchestrator-output.v1.json
│
├── prompts/                     # AI Agent System Prompts
│   ├── scrum_master/
│   │   ├── system.md
│   │   └── dor_check.md
│   ├── architect/
│   │   ├── system.md
│   │   └── architecture_design.md
│   ├── security/
│   │   ├── system.md
│   │   └── architecture_review.md
│   ├── coding/
│   │   ├── system.md
│   │   └── implementation.md
│   ├── testing/
│   │   ├── system.md
│   │   └── coverage_check.md
│   ├── deploy/
│   │   ├── system.md
│   │   └── deployment_plan.md
│   └── documentation_training/
│       ├── system.md
│       └── story_summary.md
│
├── infra/                       # Infrastruktur-Konfiguration
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── docker-compose.override.yml.example
│   ├── .env.example
│   ├── postgres/
│   │   └── init.sql
│   └── traefik/
│       └── traefik.yml
│
├── docs/                        # Technische Dokumentation
│   ├── architecture/
│   ├── api/
│   ├── plugins/
│   └── deployment/
│
├── .github/
│   └── workflows/               # CI/CD (optional)
│
├── .gitignore
├── Makefile                     # Build- und Dev-Shortcuts
└── README.md
```

---

## Makefile Shortcuts

```makefile
# Makefile

.PHONY: up down build migrate seed test lint

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

build:
	docker compose -f infra/docker-compose.yml build

migrate:
	docker compose -f infra/docker-compose.yml exec backend alembic upgrade head

seed:
	docker compose -f infra/docker-compose.yml exec backend python -m app.scripts.seed

test-backend:
	docker compose -f infra/docker-compose.yml exec backend pytest tests/

test-frontend:
	cd frontend && npm run test

lint-backend:
	cd backend && ruff check . && mypy app/

lint-frontend:
	cd frontend && npm run lint

logs:
	docker compose -f infra/docker-compose.yml logs -f

shell-backend:
	docker compose -f infra/docker-compose.yml exec backend bash

shell-db:
	docker compose -f infra/docker-compose.yml exec postgres psql -U $$POSTGRES_USER $$POSTGRES_DB
```

---

## Namenskonventionen

| Typ | Konvention | Beispiel |
|---|---|---|
| Python Module | snake_case | `user_service.py` |
| Python Klassen | PascalCase | `UserService` |
| TypeScript Komponenten | PascalCase | `StoryDetailPanel.tsx` |
| TypeScript Hooks | camelCase + `use` | `useCurrentOrg.ts` |
| API Endpoints | kebab-case | `/api/v1/user-stories` |
| DB Tabellen | snake_case plural | `user_stories` |
| DB Spalten | snake_case | `created_at` |
| Docker Services | kebab-case | `backend`, `n8n` |
| Env Variablen | UPPER_SNAKE_CASE | `JWT_SECRET` |
| Plugin Slugs | kebab-case | `user-story` |
| Workflow Slugs | kebab-case | `ai-delivery` |
