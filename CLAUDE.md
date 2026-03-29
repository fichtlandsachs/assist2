# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**assist2** is a multi-tenant, AI-native workspace platform that orchestrates AI agents to manage user stories, deliver code, and coordinate complex workflows. It is a monorepo with a FastAPI backend, Next.js 14 frontend, n8n workflow engine, and a plugin architecture.

Detailed design documentation lives in the root `.md` files (German language, `00_overview.md` through `11_n8n_orchestrator.md`). Start with `INDEX.md` for navigation.

## Commands

All development tasks run through Docker Compose via the Makefile:

```bash
make up-dev          # Start all services with hot reload
make down-dev        # Stop dev services
make logs-backend    # Tail backend logs
make shell           # Interactive bash in backend container

make migrate                      # Run pending Alembic migrations
make makemigrations msg="desc"    # Generate a new migration
make seed                         # Seed initial data

make test            # Full test suite with coverage
make test-unit       # Unit tests only
make test-integration # Integration tests only

make format          # Format Python code with ruff
make lint            # Lint Python code with ruff

make build           # Build all Docker images
make ps              # Show running containers
```

Frontend development (inside container or with local Node):
```bash
cd frontend && npm run dev    # Next.js dev server
cd frontend && npm run build  # Production build
cd frontend && npm run lint   # ESLint
```

## Architecture

### Service Layout

```
Internet → Traefik v3 (TLS, routing, auth middleware)
              ├── Frontend  (Next.js 14, :3000)
              ├── Backend   (FastAPI, :8000)
              ├── n8n       (workflow engine, :5678)
              └── Authentik (identity, Wave 3+)

Backend → PostgreSQL 16 (primary DB)
        → Redis 7        (sessions, JWT blacklist, Celery queue, pub/sub)
        → n8n            (workflow triggers via REST)
        → Celery Worker  (background tasks: mail/calendar sync, notifications)
```

Infrastructure is defined in `infra/docker-compose.yml` (production) and `infra/docker-compose.dev.yml` (dev overrides). Runtime secrets live in `infra/.env`.

## Docker — Pflichtregeln

**Niemals `docker run` verwenden.** Alle Container werden ausschließlich über Docker Compose verwaltet:

```bash
# Einzelnen Service starten/neu starten
cd infra && docker compose -f docker-compose.yml up -d <service>

# Mehrere Services
cd infra && docker compose -f docker-compose.yml up -d backend frontend

# Image neu bauen und starten
cd infra && docker compose -f docker-compose.yml up -d --build <service>

# Logs
docker logs assist2-<service> --tail 20
```

Container die nicht über Compose gestartet werden, haben keine `com.docker.compose.project`-Labels und erscheinen nicht im Monitoring (Hostinger). Neue Services müssen zuerst in `infra/docker-compose.yml` definiert werden, bevor sie gestartet werden.

### Backend (`backend/`)

FastAPI app with async SQLAlchemy (PostgreSQL + asyncpg). Standard layered structure:

- `app/models/` — SQLAlchemy ORM models (20 files)
- `app/schemas/` — Pydantic v2 request/response schemas (17 files)
- `app/routers/` — FastAPI route handlers (18 files, mounted in `main.py`)
- `app/services/` — Business logic layer (14 files)
- `app/core/` — `security.py` (JWT/passwords), `permissions.py` (RBAC aggregation), `events.py` (Redis pub/sub), `exceptions.py`
- `app/ai/` — AI pipeline, context analysis, complexity scoring
- `migrations/` — Alembic migrations (core schema)

API base path: `/api/v1`. Auth: Bearer JWT. All responses paginated as `{total, page, page_size, items}`. Errors: `{error, code, details}`.

### Frontend (`frontend/`)

Next.js 14 App Router. Route groups:
- `app/(auth)/` — Login, register, OAuth callbacks (no org context)
- `app/[org]/` — All org-scoped pages; layout provides the sidebar shell

State management: Zustand. Data fetching: SWR. Icons: lucide-react. Styling: Tailwind CSS.

Plugin slot rendering is handled in `lib/plugins/` and mounted via `components/plugins/`.

### Plugin Architecture

Plugins are hybrid packages with backend (`models.py`, `routes.py`, `schemas.py`, `service.py`, `migrations/`) and frontend (`index.tsx`, `components/`) components. Each plugin has a `manifest.json` validated against `schemas/plugin-manifest.v1.json`.

The `plugins/user-story/` directory is the reference implementation.

Plugin-specific migrations run separately from core migrations (own Alembic branches).

### Workflow & AI Delivery

n8n executes 4 core workflows (source in `workflows/`):
1. `user-provisioning` — Onboard users
2. `story-lifecycle` — Story status transitions
3. `ai-delivery` — Master AI orchestration pipeline
4. `deployment` — Release management

The **ai-delivery** workflow stages: `intake → story_analysis → architecture_design → architecture_review → implementation → post_implementation_review → deployment_preparation → documentation_training → final_release_decision`.

Blocking gates (`SecurityAI` finding blocks all) enforce `Security > Performance > Feature` priority. Rework loops are capped at 3 iterations per spec.

AI agent system prompts live in `prompts/`. JSON schemas for agent artifacts, gate decisions, and orchestrator output are in `schemas/`.

The primary AI model is `claude-sonnet-4-6`. OpenAI is a fallback.

## Key Constraints

- **Multi-tenancy:** Every org-bound DB query MUST filter by `organization_id`. This is non-negotiable.
- **Permissions are server-side only.** Never gate features on frontend permission checks alone.
- **Plugin slugs:** kebab-case. DB tables: snake_case plural. UUIDs: v4. Timestamps: ISO 8601 UTC.
- **Secrets:** `.env` only. Never hardcoded, never returned from API.
- **n8n workflow changes** must be committed to `workflows/` as JSON (prevents drift).
