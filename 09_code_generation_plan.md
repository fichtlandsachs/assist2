# 09 — Code Generation Plan

Geordnete Liste aller zu generierenden Dateien.
Reihenfolge entspricht Abhängigkeitsgraph — jede Datei setzt vorherige voraus.

---

## Phase 0: Infrastruktur (Wave 1)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 001 | `infra/.env.example` | Config | Alle Env-Variablen mit Kommentaren |
| 002 | `infra/postgres/init.sql` | SQL | DB-Initialisierung, Extensions |
| 003 | `infra/docker-compose.yml` | Docker | Vollständiger Stack |
| 004 | `infra/docker-compose.dev.yml` | Docker | Dev-Overrides (Port-Bindings) |
| 005 | `Makefile` | Build | Shortcuts für alle häufigen Operationen |

---

## Phase 1: Backend Fundament (Wave 1)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 010 | `backend/requirements.txt` | Deps | fastapi, sqlalchemy, alembic, pydantic, redis, celery, cryptography, passlib, python-jose |
| 011 | `backend/requirements-dev.txt` | Deps | pytest, ruff, mypy, httpx |
| 012 | `backend/Dockerfile` | Docker | Multi-stage Build |
| 013 | `backend/alembic.ini` | Config | Alembic-Konfiguration |
| 014 | `backend/app/__init__.py` | Python | |
| 015 | `backend/app/config.py` | Python | Settings via pydantic-settings, alle Env-Variablen |
| 016 | `backend/app/database.py` | Python | Async SQLAlchemy Engine + Session Factory |
| 017 | `backend/app/main.py` | Python | FastAPI App, CORS, Router-Mount, Lifespan |

---

## Phase 2: Backend Core Models (Wave 1)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 020 | `backend/app/models/__init__.py` | Python | |
| 021 | `backend/app/models/base.py` | Python | SQLAlchemy Base, Mixins (UUIDMixin, TimestampMixin) |
| 022 | `backend/app/models/user.py` | Python | User, IdentityLink, UserSession |
| 023 | `backend/app/models/organization.py` | Python | Organization |
| 024 | `backend/app/models/membership.py` | Python | Membership, MembershipRole |
| 025 | `backend/app/models/role.py` | Python | Role, Permission, RolePermission |
| 026 | `backend/app/models/group.py` | Python | Group, GroupMember |
| 027 | `backend/app/models/agent.py` | Python | Agent |
| 028 | `backend/app/models/plugin.py` | Python | Plugin, OrganizationPluginActivation |
| 029 | `backend/app/models/workflow.py` | Python | WorkflowDefinition, WorkflowExecution |

---

## Phase 3: Backend Migrations (Wave 1)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 030 | `backend/migrations/env.py` | Python | Alembic Env mit Async-Support |
| 031 | `backend/migrations/versions/0001_initial.py` | Migration | Alle Core-Tabellen |

---

## Phase 4: Backend Schemas / Pydantic (Wave 1)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 040 | `backend/app/schemas/common.py` | Python | PaginatedResponse, ErrorResponse, UUIDParam |
| 041 | `backend/app/schemas/auth.py` | Python | RegisterRequest, LoginRequest, TokenResponse |
| 042 | `backend/app/schemas/user.py` | Python | UserRead, UserUpdate, IdentityLinkRead |
| 043 | `backend/app/schemas/organization.py` | Python | OrgCreate, OrgRead, OrgUpdate |
| 044 | `backend/app/schemas/membership.py` | Python | MembershipRead, InviteRequest |
| 045 | `backend/app/schemas/role.py` | Python | RoleRead, RoleCreate, PermissionRead |
| 046 | `backend/app/schemas/group.py` | Python | GroupRead, GroupCreate, GroupMemberRead |
| 047 | `backend/app/schemas/plugin.py` | Python | PluginRead, ActivationRequest, PluginConfigUpdate |
| 048 | `backend/app/schemas/workflow.py` | Python | WorkflowDefinitionRead, ExecutionRead, TriggerRequest |
| 049 | `backend/app/schemas/agent.py` | Python | AgentRead, AgentCreate, InvokeRequest |

---

## Phase 5: Backend Core Utilities (Wave 1)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 050 | `backend/app/core/security.py` | Python | JWT encode/decode, password_hash, verify_password, encrypt/decrypt |
| 051 | `backend/app/core/permissions.py` | Python | Permission-Aggregation, PermissionChecker |
| 052 | `backend/app/core/exceptions.py` | Python | HTTPException-Subklassen (Forbidden, NotFound, Conflict) |
| 053 | `backend/app/core/events.py` | Python | Redis Pub/Sub Event Bus |
| 054 | `backend/app/deps.py` | Python | get_current_user, get_current_org, require_permission |

---

## Phase 6: Backend Services (Wave 1)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 060 | `backend/app/services/auth_service.py` | Python | Register, Login, Refresh, OAuth2 |
| 061 | `backend/app/services/user_service.py` | Python | CRUD User, Profil |
| 062 | `backend/app/services/org_service.py` | Python | CRUD Org, Tenant-Scope |
| 063 | `backend/app/services/membership_service.py` | Python | Invite, Accept, Suspend |
| 064 | `backend/app/services/permission_service.py` | Python | Aggregation, Cache in Redis |
| 065 | `backend/app/services/plugin_service.py` | Python | Activate, Deactivate, Config-Validierung |
| 066 | `backend/app/services/workflow_service.py` | Python | Trigger, Execute, Snapshot |
| 067 | `backend/app/services/n8n_client.py` | Python | HTTP-Client für n8n API |

---

## Phase 7: Backend Routers (Wave 1)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 070 | `backend/app/routers/auth.py` | Python | /auth/* |
| 071 | `backend/app/routers/users.py` | Python | /users/* |
| 072 | `backend/app/routers/organizations.py` | Python | /organizations/* |
| 073 | `backend/app/routers/memberships.py` | Python | /organizations/{org_id}/members/* |
| 074 | `backend/app/routers/roles.py` | Python | /organizations/{org_id}/roles/* |
| 075 | `backend/app/routers/groups.py` | Python | /organizations/{org_id}/groups/* |
| 076 | `backend/app/routers/plugins.py` | Python | /plugins/*, /organizations/{org_id}/plugins/* |
| 077 | `backend/app/routers/workflows.py` | Python | /organizations/{org_id}/workflows/* |
| 078 | `backend/app/routers/agents.py` | Python | /organizations/{org_id}/agents/* |

---

## Phase 8: Backend Tests (Wave 1)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 080 | `backend/tests/conftest.py` | Python | Test-DB, Fixtures, Auth-Helpers |
| 081 | `backend/tests/unit/test_permissions.py` | Python | Permission-Aggregation Tests |
| 082 | `backend/tests/unit/test_security.py` | Python | JWT, Encryption Tests |
| 083 | `backend/tests/integration/test_auth.py` | Python | Login, Register, OAuth Flow |
| 084 | `backend/tests/integration/test_organizations.py` | Python | CRUD + Tenant-Isolation |
| 085 | `backend/tests/integration/test_memberships.py` | Python | Invite, Accept, Rollen |

---

## Phase 9: Frontend Fundament (Wave 2)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 090 | `frontend/package.json` | Deps | next, react, typescript, tailwindcss, zustand, swr |
| 091 | `frontend/tsconfig.json` | Config | TypeScript strict mode |
| 092 | `frontend/next.config.ts` | Config | App Router, Image Domains |
| 093 | `frontend/Dockerfile` | Docker | Multi-stage Build |
| 094 | `frontend/app/layout.tsx` | TSX | Root Layout |
| 095 | `frontend/lib/api/client.ts` | TS | Fetch-Wrapper mit Token-Handling |
| 096 | `frontend/lib/auth/context.tsx` | TSX | Auth-Context, useAuth Hook |
| 097 | `frontend/types/index.ts` | TS | User, Org, Membership etc. |

---

## Phase 10: Frontend Shell + Routing (Wave 2)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 100 | `frontend/app/(auth)/login/page.tsx` | TSX | Login-Seite |
| 101 | `frontend/app/(auth)/register/page.tsx` | TSX | Register-Seite |
| 102 | `frontend/app/[org]/layout.tsx` | TSX | Org-Shell mit Sidebar |
| 103 | `frontend/app/[org]/dashboard/page.tsx` | TSX | Dashboard |
| 104 | `frontend/components/shell/Sidebar.tsx` | TSX | Navigation mit Plugin-Slots |
| 105 | `frontend/components/shell/Topbar.tsx` | TSX | Header |
| 106 | `frontend/lib/plugins/registry.ts` | TS | Plugin-Registry, Loader |
| 107 | `frontend/lib/plugins/slots.tsx` | TSX | Slot-Renderer |

---

## Phase 11: JSON Schemas (Wave 1–3)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 110 | `schemas/plugin-manifest.v1.json` | Schema | Plugin Manifest |
| 111 | `schemas/agent-artifact.v1.json` | Schema | Agent Output |
| 112 | `schemas/workflow-stage.v1.json` | Schema | Stage State |
| 113 | `schemas/gate-decision.v1.json` | Schema | Gate Decision |
| 114 | `schemas/rework-instruction.v1.json` | Schema | Rework |
| 115 | `schemas/release-decision.v1.json` | Schema | Release |
| 116 | `schemas/orchestrator-output.v1.json` | Schema | Orchestrator Output |

---

## Phase 12: n8n Workflows (Wave 3)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 120 | `workflows/user-provisioning.json` | n8n | User Provisioning |
| 121 | `workflows/story-lifecycle.json` | n8n | Story Status Transitions |
| 122 | `workflows/ai-delivery.json` | n8n | Master Orchestrator |
| 123 | `workflows/deployment.json` | n8n | Deployment Workflow |

---

## Phase 13: AI Agent Prompts (Wave 3+)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 130 | `prompts/scrum_master/system.md` | Prompt | ScrumMasterAI System-Prompt |
| 131 | `prompts/scrum_master/dor_check.md` | Prompt | DoR-Check Prompt |
| 132 | `prompts/architect/system.md` | Prompt | ArchitectAI System-Prompt |
| 133 | `prompts/security/system.md` | Prompt | SecurityAI System-Prompt |
| 134 | `prompts/coding/system.md` | Prompt | CodingAI System-Prompt |
| 135 | `prompts/testing/system.md` | Prompt | TestingAI System-Prompt |
| 136 | `prompts/deploy/system.md` | Prompt | DeployAI System-Prompt |
| 137 | `prompts/documentation_training/system.md` | Prompt | DocumentationTrainingAI System-Prompt |

---

## Phase 14: User Story Plugin (Wave 4)

| # | Datei | Typ | Beschreibung |
|---|---|---|---|
| 140 | `plugins/user-story/manifest.json` | JSON | Plugin-Manifest |
| 141 | `plugins/user-story/backend/models.py` | Python | UserStory, TestCase Models |
| 142 | `plugins/user-story/backend/migrations/0001_story_tables.py` | Migration | |
| 143 | `plugins/user-story/backend/schemas.py` | Python | Pydantic Schemas |
| 144 | `plugins/user-story/backend/service.py` | Python | Business Logic |
| 145 | `plugins/user-story/backend/routes.py` | Python | FastAPI Router |
| 146 | `plugins/user-story/frontend/index.tsx` | TSX | Plugin Entry Point |
| 147 | `plugins/user-story/frontend/components/StoryList.tsx` | TSX | Story-Liste |
| 148 | `plugins/user-story/frontend/components/StoryDetail.tsx` | TSX | Story-Detail |

---

## Generierungsreihenfolge (Kurzform)

```
1. Infra (.env, docker-compose, init.sql)
2. Backend Fundament (config, db, main)
3. Backend Models (alle)
4. Backend Migrations (0001_initial)
5. Backend Schemas (alle)
6. Backend Core (security, permissions, deps)
7. Backend Services (alle)
8. Backend Routers (alle)
9. JSON Schemas (alle)
10. Frontend Fundament (config, client, auth)
11. Frontend Shell (layout, sidebar, slot-system)
12. n8n Workflows (alle 4)
13. AI Prompts (alle 8)
14. User Story Plugin (vollständig)
15. Tests (Backend, dann Frontend)
```
