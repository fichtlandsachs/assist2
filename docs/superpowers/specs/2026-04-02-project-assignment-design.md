---
title: Project Assignment for Epics, User Stories & Features
date: 2026-04-02
status: draft
---

# Project Assignment — Design Spec

## Overview

Introduce a `Project` as a first-class top-level entity that sits above Epics in the hierarchy. Epics and standalone Stories can be assigned to a Project. Features always belong through a Story. This enables cross-cutting project views alongside the existing per-type boards.

### Hierarchy

```
Project
  ├── Epics
  │     └── Stories → Features
  └── Stories (standalone — small enough to need no Epic)
            └── Features
```

---

## 1. Data Model

### New table: `projects`

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default gen_random_uuid() |
| `organization_id` | UUID | FK → organizations, NOT NULL, indexed |
| `created_by_id` | UUID | FK → users, NOT NULL |
| `owner_id` | UUID | FK → users, nullable |
| `name` | VARCHAR(500) | NOT NULL |
| `description` | TEXT | nullable |
| `status` | enum `projectstatus` | NOT NULL, default 'planning' |
| `deadline` | DATE | nullable |
| `color` | VARCHAR(7) | nullable — hex e.g. `#E11D48` |
| `effort` | enum `effortlevel` | nullable |
| `complexity` | enum `complexitylevel` | nullable |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default now() |

**New enums:**
- `projectstatus`: planning, active, done, archived
- `effortlevel`: low, medium, high, xl
- `complexitylevel`: low, medium, high, xl

### Schema changes to existing tables

- `epics.project_id` — nullable UUID FK → projects, indexed
- `user_stories.project_id` — nullable UUID FK → projects, indexed

Features are NOT directly assigned to a project — they always belong through a Story.

---

## 2. Backend

### New model: `app/models/project.py`

Fields as above. Relationships:
- `organization` → Organization
- `created_by` → User
- `owner` → User (optional)
- `epics` → List[Epic] (back-populated)
- `stories` → List[UserStory] (back-populated, direct assignments)

### Updated models

- `Epic`: add `project_id` nullable FK + `project` relationship
- `UserStory`: add `project_id` nullable FK + `project` relationship

### New schemas: `app/schemas/project.py`

- `ProjectCreate`: name (required), description, status, deadline, color, effort, complexity, owner_id
- `ProjectUpdate`: all fields optional
- `ProjectRead`: all fields + `created_by_id`, `owner_id`, `created_at`, `updated_at`
- `ProjectSummary`: id, name, color, status (for use in Epic/Story read schemas)

### Updated schemas

- `EpicCreate` / `EpicUpdate`: add optional `project_id`
- `EpicRead`: add `project_id`, `project: ProjectSummary | None`
- `UserStoryCreate` / `UserStoryUpdate`: add optional `project_id`
- `UserStoryRead`: add `project_id`, `project: ProjectSummary | None`

### New router: `app/routers/projects.py`

All routes require authenticated user + org membership check.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/projects` | List org projects (`?status=`, `?owner_id=`) |
| `POST` | `/api/v1/projects` | Create project |
| `GET` | `/api/v1/projects/{id}` | Get project detail |
| `PATCH` | `/api/v1/projects/{id}` | Update project |
| `DELETE` | `/api/v1/projects/{id}` | Delete project (unlinks epics/stories, does not delete them) |
| `GET` | `/api/v1/projects/{id}/epics` | Epics assigned to this project |
| `GET` | `/api/v1/projects/{id}/stories` | Stories directly assigned to project (no epic) |

### Updated routers

- `GET /api/v1/epics` — add optional `?project_id=` filter
- `GET /api/v1/user-stories` — add optional `?project_id=` filter
- Epic create/update — persist `project_id` if provided
- Story create/update — persist `project_id` if provided

### New migration: `0023_projects.py`

1. Create enums: `projectstatus`, `effortlevel`, `complexitylevel`
2. Create `projects` table
3. Add `project_id` nullable FK + index to `epics`
4. Add `project_id` nullable FK + index to `user_stories`

---

## 3. Frontend

### New type: `Project` in `types/index.ts`

```ts
type ProjectStatus = "planning" | "active" | "done" | "archived"
type EffortLevel = "low" | "medium" | "high" | "xl"
type ComplexityLevel = "low" | "medium" | "high" | "xl"

interface Project {
  id: string
  organization_id: string
  created_by_id: string
  owner_id: string | null
  name: string
  description: string | null
  status: ProjectStatus
  deadline: string | null  // ISO date
  color: string | null     // hex
  effort: EffortLevel | null
  complexity: ComplexityLevel | null
  created_at: string
  updated_at: string
}
```

Update `Epic` and `UserStory` interfaces to include `project_id: string | null`.

### Sidebar

Add **"Projekte"** nav entry (above "User Stories") in `Sidebar.tsx`:
- Route: `/[org]/project/`
- Icon: `Folder` (lucide)
- Agile color: `text-teal-500` / `bg-teal-50`

### New pages under `app/[org]/project/`

**`/[org]/project/page.tsx` — Project list**
- src_agile card grid
- Each card shows: color label strip, name, status badge, deadline, owner avatar, effort + complexity chips
- "Neues Projekt" button → inline create form or modal
- Filter by status

**`/[org]/project/[id]/page.tsx` — Project detail**
- Header: color banner, name, description, status, deadline, owner, effort/complexity
- Two tabs:
  - **Epics** — assigned epics (src_agile cards linking to epic detail)
  - **Stories** — standalone stories assigned directly (without an epic)
- "Assign" button on each tab to attach existing items or create new ones

### Updated Stories section: sub-nav

Add a sub-nav strip at the top of all `/[org]/stories/*` pages:

```
Epics  |  User Stories  |  Features
```

- **Epics** → `/[org]/stories/epics/board/`
- **User Stories** → `/[org]/stories/board/`
- **Features** → `/[org]/stories/features/board/`

The active tab highlights based on current path segment. Implemented as a shared layout component at `app/[org]/stories/layout.tsx`.

### Project selector component

New reusable `components/stories/ProjectSelector.tsx`:
- Dropdown that fetches `/api/v1/projects`
- Shows color dot + project name
- "Kein Projekt" (no project) as first option
- Used in: story detail, story create form, epic create/edit form

### Project filter on boards

All three boards (Epics, Stories, Features) get a **project filter** in the toolbar:
- Renders `ProjectSelector` in filter mode
- When a project is selected, boards pass `?project_id=` to the API query

### AI Workspace

When saving a generated story from `/[org]/ai-workspace/`, show a `ProjectSelector` in the save confirmation dialog (optional — story can be saved without a project).

---

## 4. Error Handling

- Deleting a project does NOT cascade-delete epics or stories — it sets their `project_id` to NULL
- Multi-tenancy: all project queries filter by `organization_id` (non-negotiable per project convention)
- `project_id` on Story and Epic is always optional — existing items continue to work without a project

---

## 5. Migration Safety

- All new columns are nullable — zero downtime, no backfill needed
- Enum creation happens before table creation in the migration

---

## 6. Files to Create / Modify

| Action | Path |
|---|---|
| Create | `backend/app/models/project.py` |
| Modify | `backend/app/models/epic.py` |
| Modify | `backend/app/models/user_story.py` |
| Create | `backend/app/schemas/project.py` |
| Modify | `backend/app/schemas/user_story.py` |
| Modify | `backend/app/schemas/feature.py` (ProjectSummary import) |
| Create | `backend/app/routers/projects.py` |
| Modify | `backend/app/routers/epics.py` |
| Modify | `backend/app/routers/user_stories.py` |
| Modify | `backend/app/main.py` (mount projects router) |
| Create | `backend/migrations/versions/0023_projects.py` |
| Modify | `frontend/types/index.ts` |
| Modify | `frontend/components/shell/Sidebar.tsx` |
| Create | `frontend/app/[org]/project/page.tsx` |
| Create | `frontend/app/[org]/project/[id]/page.tsx` |
| Create | `frontend/app/[org]/stories/layout.tsx` (sub-nav) |
| Create | `frontend/components/stories/ProjectSelector.tsx` |
| Modify | `frontend/app/[org]/stories/board/page.tsx` |
| Modify | `frontend/app/[org]/stories/epics/board/page.tsx` |
| Modify | `frontend/app/[org]/stories/features/board/page.tsx` |
| Modify | `frontend/app/[org]/stories/new/page.tsx` |
| Modify | `frontend/app/[org]/stories/[id]/page.tsx` |
| Modify | `frontend/app/[org]/ai-workspace/page.tsx` |
