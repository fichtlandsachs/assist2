# Project Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `Project` entity as the top-level container above Epics, so Epics and standalone Stories can be assigned to a Project, with full CRUD API and a dedicated `/[org]/project/` section in the frontend.

**Architecture:** New `projects` table with nullable `project_id` FK added to both `epics` and `user_stories`. A FastAPI router provides CRUD + filtered list endpoints. The frontend gains a sidebar nav entry, a project list/detail section, a reusable `ProjectSelector` component, a sub-nav strip on the stories section, and project filters on all three boards.

**Tech Stack:** FastAPI, SQLAlchemy (async mapped_column style), Alembic, Pydantic v2, Next.js 14 App Router, SWR, TypeScript, Tailwind CSS (src_agile design tokens)

---

## File Map

| Action | Path |
|---|---|
| Create | `backend/app/models/project.py` |
| Modify | `backend/app/models/__init__.py` |
| Modify | `backend/app/models/epic.py` |
| Modify | `backend/app/models/user_story.py` |
| Create | `backend/app/schemas/project.py` |
| Modify | `backend/app/schemas/user_story.py` |
| Create | `backend/app/routers/projects.py` |
| Modify | `backend/app/routers/epics.py` |
| Modify | `backend/app/routers/user_stories.py` |
| Modify | `backend/app/main.py` |
| Create | `backend/migrations/versions/0023_projects.py` |
| Create | `backend/tests/integration/test_projects.py` |
| Modify | `frontend/types/index.ts` |
| Modify | `frontend/components/shell/Sidebar.tsx` |
| Create | `frontend/app/[org]/stories/layout.tsx` |
| Create | `frontend/components/stories/ProjectSelector.tsx` |
| Create | `frontend/app/[org]/project/page.tsx` |
| Create | `frontend/app/[org]/project/[id]/page.tsx` |
| Modify | `frontend/app/[org]/stories/board/page.tsx` |
| Modify | `frontend/app/[org]/stories/epics/board/page.tsx` |
| Modify | `frontend/app/[org]/stories/features/board/page.tsx` |
| Modify | `frontend/app/[org]/stories/new/page.tsx` |
| Modify | `frontend/app/[org]/stories/[id]/page.tsx` |
| Modify | `frontend/app/[org]/ai-workspace/page.tsx` |

---

## Task 1: Project model + migration

**Files:**
- Create: `backend/app/models/project.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/migrations/versions/0023_projects.py`

- [ ] **Step 1: Write the failing integration test**

Create `backend/tests/integration/test_projects.py`:

```python
"""Integration tests for /api/v1/projects endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient, auth_headers: dict, test_org: Organization):
    response = await client.post(
        f"/api/v1/projects?org_id={test_org.id}",
        json={"name": "Alpha Release", "status": "planning"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alpha Release"
    assert data["status"] == "planning"
    assert data["color"] is None
    assert "id" in data


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient, auth_headers: dict, test_org: Organization):
    await client.post(
        f"/api/v1/projects?org_id={test_org.id}",
        json={"name": "Project One", "status": "active"},
        headers=auth_headers,
    )
    response = await client.get(
        f"/api/v1/projects?org_id={test_org.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(p["name"] == "Project One" for p in data)


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient, auth_headers: dict, test_org: Organization):
    create = await client.post(
        f"/api/v1/projects?org_id={test_org.id}",
        json={"name": "Beta", "status": "planning"},
        headers=auth_headers,
    )
    project_id = create.json()["id"]
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"status": "active", "color": "#E11D48"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert response.json()["color"] == "#E11D48"


@pytest.mark.asyncio
async def test_delete_project_unlinks_items(client: AsyncClient, auth_headers: dict, test_org: Organization):
    """Deleting a project must not delete epics — it must unlink them."""
    proj = await client.post(
        f"/api/v1/projects?org_id={test_org.id}",
        json={"name": "To Delete"},
        headers=auth_headers,
    )
    project_id = proj.json()["id"]
    epic = await client.post(
        f"/api/v1/epics?org_id={test_org.id}",
        json={"title": "Orphan Epic", "project_id": project_id},
        headers=auth_headers,
    )
    assert epic.status_code == 201

    del_resp = await client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    # Epic still exists
    list_resp = await client.get(f"/api/v1/epics?org_id={test_org.id}", headers=auth_headers)
    assert any(e["title"] == "Orphan Epic" for e in list_resp.json())
    # Epic is now unlinked
    orphan = next(e for e in list_resp.json() if e["title"] == "Orphan Epic")
    assert orphan["project_id"] is None
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /opt/assist2 && make shell
# inside container:
pytest tests/integration/test_projects.py -v 2>&1 | head -30
```

Expected: ImportError or 404/422 — model and router don't exist yet.

- [ ] **Step 3: Create the Project model**

Create `backend/app/models/project.py`:

```python
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Enum, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.epic import Epic
    from app.models.user_story import UserStory
    from app.models.user import User


class ProjectStatus(str, enum.Enum):
    planning = "planning"
    active = "active"
    done = "done"
    archived = "archived"


class EffortLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    xl = "xl"


class ComplexityLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    xl = "xl"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.planning, nullable=False
    )
    deadline: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    effort: Mapped[Optional[EffortLevel]] = mapped_column(Enum(EffortLevel), nullable=True)
    complexity: Mapped[Optional[ComplexityLevel]] = mapped_column(Enum(ComplexityLevel), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    epics: Mapped[List["Epic"]] = relationship("Epic", back_populates="project")
    stories: Mapped[List["UserStory"]] = relationship("UserStory", back_populates="project")
```

- [ ] **Step 4: Register model in `__init__.py`**

Add to `backend/app/models/__init__.py` after the existing imports (after the `from app.models.feature import ...` line):

```python
from app.models.project import Project, ProjectStatus, EffortLevel, ComplexityLevel
```

- [ ] **Step 5: Add `project_id` to Epic model**

In `backend/app/models/epic.py`:

Add `Project` to TYPE_CHECKING imports:
```python
if TYPE_CHECKING:
    from app.models.user_story import UserStory
    from app.models.feature import Feature
    from app.models.project import Project
```

Add column and relationship after the `updated_at` field (before the relationships):
```python
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="epics")
    stories: Mapped[List["UserStory"]] = relationship("UserStory", back_populates="epic", foreign_keys="UserStory.epic_id")
    features: Mapped[List["Feature"]] = relationship("Feature", back_populates="epic")
```

The full file after modification:

```python
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user_story import UserStory
    from app.models.feature import Feature
    from app.models.project import Project


class EpicStatus(str, enum.Enum):
    planning = "planning"
    in_progress = "in_progress"
    done = "done"
    archived = "archived"


class Epic(Base):
    __tablename__ = "epics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[EpicStatus] = mapped_column(Enum(EpicStatus), default=EpicStatus.planning, nullable=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="epics")
    stories: Mapped[List["UserStory"]] = relationship("UserStory", back_populates="epic", foreign_keys="UserStory.epic_id")
    features: Mapped[List["Feature"]] = relationship("Feature", back_populates="epic")
```

- [ ] **Step 6: Add `project_id` to UserStory model**

In `backend/app/models/user_story.py`, add to TYPE_CHECKING block:
```python
if TYPE_CHECKING:
    from app.models.epic import Epic
    from app.models.feature import Feature
    from app.models.project import Project
```

Add column after `epic_id` line (line 57):
```python
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
```

Add relationship after `epic` relationship (line 64):
```python
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="stories")
```

- [ ] **Step 7: Create the Alembic migration**

Create `backend/migrations/versions/0023_projects.py`:

```python
"""add projects table and project_id FK to epics and user_stories

Revision ID: 0023
Revises: 0022
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    op.execute("CREATE TYPE projectstatus AS ENUM ('planning', 'active', 'done', 'archived')")
    op.execute("CREATE TYPE effortlevel AS ENUM ('low', 'medium', 'high', 'xl')")
    op.execute("CREATE TYPE complexitylevel AS ENUM ('low', 'medium', 'high', 'xl')")

    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.Enum('planning', 'active', 'done', 'archived', name='projectstatus', create_type=False), nullable=False, server_default='planning'),
        sa.Column('deadline', sa.Date, nullable=True),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('effort', sa.Enum('low', 'medium', 'high', 'xl', name='effortlevel', create_type=False), nullable=True),
        sa.Column('complexity', sa.Enum('low', 'medium', 'high', 'xl', name='complexitylevel', create_type=False), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_projects_organization_id', 'projects', ['organization_id'])

    op.add_column('epics', sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id'), nullable=True))
    op.create_index('ix_epics_project_id', 'epics', ['project_id'])

    op.add_column('user_stories', sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id'), nullable=True))
    op.create_index('ix_user_stories_project_id', 'user_stories', ['project_id'])


def downgrade() -> None:
    op.drop_index('ix_user_stories_project_id', table_name='user_stories')
    op.drop_column('user_stories', 'project_id')
    op.drop_index('ix_epics_project_id', table_name='epics')
    op.drop_column('epics', 'project_id')
    op.drop_index('ix_projects_organization_id', table_name='projects')
    op.drop_table('projects')
    op.execute('DROP TYPE projectstatus')
    op.execute('DROP TYPE effortlevel')
    op.execute('DROP TYPE complexitylevel')
```

- [ ] **Step 8: Run migration**

```bash
cd /opt/assist2 && make migrate
```

Expected: `Running upgrade 0022 -> 0023` with no errors.

- [ ] **Step 9: Commit**

```bash
cd /opt/assist2
git add backend/app/models/project.py backend/app/models/__init__.py \
        backend/app/models/epic.py backend/app/models/user_story.py \
        backend/migrations/versions/0023_projects.py \
        backend/tests/integration/test_projects.py
git commit -m "feat(projects): add Project model, migration, and FK columns on epics/stories"
```

---

## Task 2: Project schemas

**Files:**
- Create: `backend/app/schemas/project.py`
- Modify: `backend/app/schemas/user_story.py`

- [ ] **Step 1: Create project schemas**

Create `backend/app/schemas/project.py`:

```python
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime, date
import uuid
from app.models.project import ProjectStatus, EffortLevel, ComplexityLevel


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.planning
    deadline: Optional[date] = None
    color: Optional[str] = None
    effort: Optional[EffortLevel] = None
    complexity: Optional[ComplexityLevel] = None
    owner_id: Optional[uuid.UUID] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    deadline: Optional[date] = None
    color: Optional[str] = None
    effort: Optional[EffortLevel] = None
    complexity: Optional[ComplexityLevel] = None
    owner_id: Optional[uuid.UUID] = None


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: Optional[str]
    status: ProjectStatus


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_id: uuid.UUID
    owner_id: Optional[uuid.UUID]
    name: str
    description: Optional[str]
    status: ProjectStatus
    deadline: Optional[date]
    color: Optional[str]
    effort: Optional[EffortLevel]
    complexity: Optional[ComplexityLevel]
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Add `project_id` to Epic schemas**

In `backend/app/schemas/user_story.py`, add `project_id` field to `EpicCreate`, `EpicUpdate`, and `EpicRead`.

After the existing `EpicCreate` class (which currently has just `title` and `description`), the updated classes look like:

```python
class EpicCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: Optional[uuid.UUID] = None


class EpicUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[EpicStatus] = None
    project_id: Optional[uuid.UUID] = None


class EpicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_id: uuid.UUID
    title: str
    description: Optional[str]
    status: EpicStatus
    project_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
```

Find the existing `EpicCreate`, `EpicUpdate`, and `EpicRead` classes in `backend/app/schemas/user_story.py` and add `project_id: Optional[uuid.UUID] = None` to each one. Also add `project_id: Optional[uuid.UUID]` (no default) to `EpicRead`.

- [ ] **Step 3: Add `project_id` to UserStory schemas**

In `backend/app/schemas/user_story.py`:

Add `project_id: Optional[uuid.UUID] = None` to `UserStoryCreate` and `UserStoryUpdate`.

Add `project_id: Optional[uuid.UUID]` to `UserStoryRead`.

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2
git add backend/app/schemas/project.py backend/app/schemas/user_story.py
git commit -m "feat(projects): add ProjectRead/Create/Update schemas, extend Epic+Story schemas with project_id"
```

---

## Task 3: Projects router + wire into main.py

**Files:**
- Create: `backend/app/routers/projects.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create the projects router**

Create `backend/app/routers/projects.py`:

```python
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.project import Project
from app.models.epic import Epic
from app.models.user_story import UserStory
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.user_story import EpicRead, UserStoryRead
from app.core.exceptions import NotFoundException

router = APIRouter()


@router.get("/projects", response_model=List[ProjectRead])
async def list_projects(
    org_id: uuid.UUID,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ProjectRead]:
    stmt = select(Project).where(Project.organization_id == org_id).order_by(Project.created_at.desc())
    if status:
        stmt = stmt.where(Project.status == status)
    result = await db.execute(stmt)
    return [ProjectRead.model_validate(p) for p in result.scalars().all()]


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    org_id: uuid.UUID,
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    project = Project(
        organization_id=org_id,
        created_by_id=current_user.id,
        owner_id=data.owner_id,
        name=data.name,
        description=data.description,
        status=data.status,
        deadline=data.deadline,
        color=data.color,
        effort=data.effort,
        complexity=data.complexity,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.get("/projects/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException("Project not found")
    return ProjectRead.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException("Project not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException("Project not found")
    # Unlink epics before deletion
    epic_stmt = select(Epic).where(Epic.project_id == project_id)
    epics = (await db.execute(epic_stmt)).scalars().all()
    for epic in epics:
        epic.project_id = None
    # Unlink stories before deletion
    story_stmt = select(UserStory).where(UserStory.project_id == project_id)
    stories = (await db.execute(story_stmt)).scalars().all()
    for story in stories:
        story.project_id = None
    await db.delete(project)
    await db.commit()


@router.get("/projects/{project_id}/epics", response_model=List[EpicRead])
async def list_project_epics(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EpicRead]:
    stmt = select(Epic).where(Epic.project_id == project_id).order_by(Epic.created_at.desc())
    result = await db.execute(stmt)
    return [EpicRead.model_validate(e) for e in result.scalars().all()]


@router.get("/projects/{project_id}/stories", response_model=List[UserStoryRead])
async def list_project_stories(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[UserStoryRead]:
    """Stories directly assigned to this project (without an epic)."""
    stmt = (
        select(UserStory)
        .where(UserStory.project_id == project_id, UserStory.epic_id.is_(None))
        .order_by(UserStory.created_at.desc())
    )
    result = await db.execute(stmt)
    return [UserStoryRead.model_validate(s) for s in result.scalars().all()]
```

- [ ] **Step 2: Mount router in main.py**

In `backend/app/main.py`, add the import at the top with the other router imports:

```python
from app.routers.projects import router as projects_router
```

Then add the include_router call after the `auth_github_router` line:

```python
app.include_router(projects_router, prefix="/api/v1", tags=["Projects"])
```

- [ ] **Step 3: Update Epic router to support project_id**

In `backend/app/routers/epics.py`:

The `create_epic` function currently sets only `organization_id`, `created_by_id`, `title`, `description`. Update it to also pass `project_id`:

```python
@router.post("/epics", response_model=EpicRead, status_code=status.HTTP_201_CREATED)
async def create_epic(
    org_id: uuid.UUID,
    data: EpicCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EpicRead:
    epic = Epic(
        organization_id=org_id,
        created_by_id=current_user.id,
        title=data.title,
        description=data.description,
        project_id=data.project_id,
    )
    db.add(epic)
    await db.commit()
    await db.refresh(epic)
    return EpicRead.model_validate(epic)
```

Also add an optional `project_id` query filter to `list_epics`:

```python
@router.get("/epics", response_model=List[EpicRead])
async def list_epics(
    org_id: uuid.UUID,
    project_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EpicRead]:
    stmt = select(Epic).where(Epic.organization_id == org_id).order_by(Epic.created_at.desc())
    if project_id is not None:
        stmt = stmt.where(Epic.project_id == project_id)
    result = await db.execute(stmt)
    return [EpicRead.model_validate(e) for e in result.scalars().all()]
```

Add `from typing import Optional` to the imports at the top of `epics.py` if not already present.

- [ ] **Step 4: Update UserStory router to support project_id**

In `backend/app/routers/user_stories.py`:

Update `list_user_stories` to accept an optional `project_id` query param:

```python
@router.get(
    "/user-stories",
    response_model=List[UserStoryRead],
    summary="List user stories for an organization",
)
async def list_user_stories(
    org_id: uuid.UUID,
    project_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[UserStoryRead]:
    stmt = (
        select(UserStory)
        .where(UserStory.organization_id == org_id)
        .order_by(UserStory.created_at.desc())
    )
    if project_id is not None:
        stmt = stmt.where(UserStory.project_id == project_id)
    result = await db.execute(stmt)
    stories = result.scalars().all()
    return [UserStoryRead.model_validate(s) for s in stories]
```

Update `create_user_story` to pass `project_id` from `data`:

```python
    story = UserStory(
        organization_id=org_id,
        created_by_id=current_user.id,
        title=data.title,
        description=data.description,
        acceptance_criteria=data.acceptance_criteria,
        priority=data.priority,
        story_points=data.story_points,
        epic_id=data.epic_id,
        project_id=data.project_id,
    )
```

In `update_user_story` (the PATCH endpoint), `project_id` is already handled via the generic `model_dump(exclude_unset=True)` loop — no change needed there.

- [ ] **Step 5: Run the integration tests**

```bash
cd /opt/assist2 && make shell
# inside container:
pytest tests/integration/test_projects.py -v
```

Expected: All 4 tests pass.

- [ ] **Step 6: Restart backend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d backend
docker logs assist2-backend --tail 20
```

Expected: No import errors, service starts cleanly.

- [ ] **Step 7: Commit**

```bash
cd /opt/assist2
git add backend/app/routers/projects.py backend/app/main.py \
        backend/app/routers/epics.py backend/app/routers/user_stories.py
git commit -m "feat(projects): add projects router, mount in main.py, extend epic+story routers with project_id filter"
```

---

## Task 4: Frontend types + Sidebar

**Files:**
- Modify: `frontend/types/index.ts`
- Modify: `frontend/components/shell/Sidebar.tsx`

- [ ] **Step 1: Add Project types to `types/index.ts`**

Find the section in `frontend/types/index.ts` where `EpicStatus`, `Epic`, `UserStory`, `Feature` are defined. Add the following **before** the `EpicStatus` definition:

```typescript
export type ProjectStatus = "planning" | "active" | "done" | "archived"
export type EffortLevel = "low" | "medium" | "high" | "xl"
export type ComplexityLevel = "low" | "medium" | "high" | "xl"

export interface Project {
  id: string
  organization_id: string
  created_by_id: string
  owner_id: string | null
  name: string
  description: string | null
  status: ProjectStatus
  deadline: string | null
  color: string | null
  effort: EffortLevel | null
  complexity: ComplexityLevel | null
  created_at: string
  updated_at: string
}
```

Add `project_id: string | null` to the `Epic` interface (after `status`).

Add `project_id: string | null` to the `UserStory` interface (after `epic_id`).

- [ ] **Step 2: Add "Projekte" to Sidebar nav**

In `frontend/components/shell/Sidebar.tsx`, the `NAV_COLORS` record needs a new entry for `"project"`:

```typescript
const NAV_COLORS: Record<string, { icon: string; bg: string }> = {
  dashboard:      { icon: "text-rose-500",    bg: "bg-rose-50" },
  "ai-workspace": { icon: "text-indigo-500",  bg: "bg-indigo-50" },
  project:        { icon: "text-teal-500",    bg: "bg-teal-50" },
  stories:        { icon: "text-amber-500",   bg: "bg-amber-50" },
  inbox:          { icon: "text-sky-500",     bg: "bg-sky-50" },
  calendar:       { icon: "text-emerald-500", bg: "bg-emerald-50" },
  workflows:      { icon: "text-violet-500",  bg: "bg-violet-50" },
  docs:           { icon: "text-orange-500",  bg: "bg-orange-50" },
  settings:       { icon: "text-slate-500",   bg: "bg-slate-50" },
  admin:          { icon: "text-red-500",     bg: "bg-red-50" },
};
```

Add `Folder` to the lucide-react import at the top of the file (it's already imported — verify it's there, it is).

In the `navItems` array, add the "Projekte" entry **between** "ai-workspace" and "stories":

```typescript
  { id: "project",     label: "Projekte",       icon: Folder,          route: `/${orgSlug}/project` },
```

Also add `"project"` to the `PAGE_TITLES` in `Topbar.tsx`:

```typescript
  project:        "Projekte",
```

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add frontend/types/index.ts frontend/components/shell/Sidebar.tsx frontend/components/shell/Topbar.tsx
git commit -m "feat(projects): add Project types, Projekte sidebar nav entry"
```

---

## Task 5: Stories sub-nav layout

**Files:**
- Create: `frontend/app/[org]/stories/layout.tsx`

The current `frontend/app/[org]/stories/page.tsx` redirects to `/board`. With a layout, the redirect stays but all child pages get the sub-nav automatically.

- [ ] **Step 1: Create stories layout with sub-nav**

Create `frontend/app/[org]/stories/layout.tsx`:

```tsx
"use client";

import { use } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface Props {
  children: React.ReactNode;
  params: Promise<{ org: string }>;
}

export default function StoriesLayout({ children, params }: Props) {
  const { org } = use(params);
  const pathname = usePathname();

  const tabs = [
    { label: "Epics",         href: `/${org}/stories/epics/board` },
    { label: "User Stories",  href: `/${org}/stories/board` },
    { label: "Features",      href: `/${org}/stories/features/board` },
  ];

  const activeHref = tabs.find(t => pathname.startsWith(t.href.replace("/board", "")))?.href ?? tabs[1].href;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1 mb-4 border-b-2 border-slate-900/5 pb-0">
        {tabs.map(tab => {
          const isActive = pathname.startsWith(tab.href.replace("/board", ""));
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`px-4 py-2 text-[12px] font-bold font-['Architects_Daughter'] tracking-wide transition-colors border-b-2 -mb-[2px] ${
                isActive
                  ? "text-slate-900 border-slate-900"
                  : "text-slate-400 border-transparent hover:text-slate-600 hover:border-slate-300"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the stories redirect page still works**

`frontend/app/[org]/stories/page.tsx` does a server-side redirect to `/board` — this is fine. The layout wraps all child routes including `/board`, `/epics/board`, `/features/board`.

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add frontend/app/[org]/stories/layout.tsx
git commit -m "feat(projects): add stories section sub-nav (Epics | User Stories | Features)"
```

---

## Task 6: ProjectSelector component

**Files:**
- Create: `frontend/components/stories/ProjectSelector.tsx`

This component follows the same pattern as the existing `EpicSelector.tsx`.

- [ ] **Step 1: Create ProjectSelector**

Create `frontend/components/stories/ProjectSelector.tsx`:

```tsx
"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api/client";
import type { Project } from "@/types";

interface Props {
  orgId: string;
  value: string | null;
  onChange: (projectId: string | null) => void;
  disabled?: boolean;
  label?: string;
}

export function ProjectSelector({ orgId, value, onChange, disabled, label = "Projekt" }: Props) {
  const { data: projects } = useSWR<Project[]>(
    orgId ? `/api/v1/projects?org_id=${orgId}` : null,
    fetcher
  );

  const selected = projects?.find(p => p.id === value);

  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1.5">{label}</label>
      <div className="flex items-center gap-2">
        {selected?.color && (
          <span
            className="w-3 h-3 rounded-full flex-shrink-0 border border-slate-200"
            style={{ background: selected.color }}
          />
        )}
        <select
          value={value ?? ""}
          onChange={e => onChange(e.target.value || null)}
          disabled={disabled}
          className="flex-1 px-3 py-2 text-sm border border-slate-300 rounded-lg outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100 bg-white disabled:bg-slate-50 disabled:text-slate-500"
        >
          <option value="">— Kein Projekt —</option>
          {(projects ?? []).map(project => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /opt/assist2
git add frontend/components/stories/ProjectSelector.tsx
git commit -m "feat(projects): add ProjectSelector reusable component"
```

---

## Task 7: Project list page

**Files:**
- Create: `frontend/app/[org]/project/page.tsx`

- [ ] **Step 1: Create the project list page**

Create `frontend/app/[org]/project/page.tsx`:

```tsx
"use client";

import { use, useState } from "react";
import useSWR from "swr";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import type { Project, ProjectStatus } from "@/types";
import Link from "next/link";
import { Plus, X, Folder } from "lucide-react";

const STATUS_LABELS: Record<ProjectStatus, string> = {
  planning: "Planung",
  active:   "Aktiv",
  done:     "Fertig",
  archived: "Archiviert",
};

const STATUS_COLORS: Record<ProjectStatus, string> = {
  planning: "bg-slate-100 text-slate-600",
  active:   "bg-teal-100 text-teal-700",
  done:     "bg-emerald-100 text-emerald-700",
  archived: "bg-slate-50 text-slate-400",
};

const EFFORT_LABELS: Record<string, string> = {
  low: "Niedrig", medium: "Mittel", high: "Hoch", xl: "XL",
};

const COMPLEXITY_LABELS: Record<string, string> = {
  low: "Einfach", medium: "Mittel", high: "Komplex", xl: "XL",
};

const COLOR_OPTIONS = [
  "#E11D48", "#F59E0B", "#10B981", "#3B82F6", "#8B5CF6", "#EC4899", "#6B7280",
];

function ProjectCard({ project, orgSlug }: { project: Project; orgSlug: string }) {
  return (
    <Link href={`/${orgSlug}/project/${project.id}`}
      className="bg-[var(--card)] border-2 border-slate-900/10 rounded-2xl p-5 hover:border-slate-900/30 hover:shadow-[4px_4px_0_rgba(0,0,0,.08)] transition-all flex flex-col gap-3 group">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {project.color ? (
            <span className="w-4 h-4 rounded-full flex-shrink-0 border-2 border-white shadow" style={{ background: project.color }} />
          ) : (
            <Folder size={16} className="text-slate-400 flex-shrink-0" />
          )}
          <span className="font-bold text-slate-900 font-['Architects_Daughter'] text-[15px] group-hover:text-teal-600 transition-colors leading-snug">
            {project.name}
          </span>
        </div>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 font-['Architects_Daughter'] ${STATUS_COLORS[project.status]}`}>
          {STATUS_LABELS[project.status]}
        </span>
      </div>
      {project.description && (
        <p className="text-[12px] text-slate-500 line-clamp-2 leading-relaxed">{project.description}</p>
      )}
      <div className="flex items-center gap-3 flex-wrap">
        {project.deadline && (
          <span className="text-[10px] text-slate-400 font-['Architects_Daughter']">
            ⏰ {new Date(project.deadline).toLocaleDateString("de-DE")}
          </span>
        )}
        {project.effort && (
          <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-['Architects_Daughter']">
            Aufwand: {EFFORT_LABELS[project.effort]}
          </span>
        )}
        {project.complexity && (
          <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-['Architects_Daughter']">
            Kompl.: {COMPLEXITY_LABELS[project.complexity]}
          </span>
        )}
      </div>
    </Link>
  );
}

export default function ProjectListPage({ params }: { params: Promise<{ org: string }> }) {
  const { org: orgSlug } = use(params);
  const { org } = useOrg(orgSlug);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const { data: projects, isLoading, mutate } = useSWR<Project[]>(
    org ? `/api/v1/projects?org_id=${org.id}` : null,
    fetcher
  );

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !org) return;
    setSaving(true);
    try {
      const project = await apiRequest<Project>(`/api/v1/projects?org_id=${org.id}`, {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), description: description.trim() || null, color, status: "planning" }),
      });
      mutate(prev => [project, ...(prev ?? [])], false);
      setShowForm(false);
      setName("");
      setDescription("");
      setColor(null);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-['Gochi_Hand']">Projekte</h1>
          <p className="text-[12px] text-slate-400 font-['Architects_Daughter'] mt-0.5">
            {projects?.length ?? 0} Projekt{(projects?.length ?? 0) !== 1 ? "e" : ""}
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-xl text-[12px] font-bold font-['Architects_Daughter'] hover:bg-teal-600 transition-colors border-2 border-slate-900 shadow-[2px_2px_0_rgba(0,0,0,1)]"
        >
          <Plus size={14} />
          Neues Projekt
        </button>
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={e => void handleCreate(e)}
            className="bg-white border-2 border-slate-900 rounded-2xl p-6 shadow-[6px_6px_0_rgba(0,0,0,1)] w-full max-w-md flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-900 font-['Gochi_Hand'] text-xl">Neues Projekt</h2>
              <button type="button" onClick={() => setShowForm(false)} className="p-1 text-slate-400 hover:text-slate-700">
                <X size={18} />
              </button>
            </div>
            <input
              autoFocus
              required
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Projektname"
              className="px-3 py-2 border-2 border-slate-200 rounded-xl text-sm outline-none focus:border-teal-400 font-['Architects_Daughter']"
            />
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Beschreibung (optional)"
              rows={2}
              className="px-3 py-2 border-2 border-slate-200 rounded-xl text-sm outline-none focus:border-teal-400 resize-none font-['Architects_Daughter']"
            />
            <div>
              <p className="text-[11px] font-bold text-slate-500 font-['Architects_Daughter'] mb-2">Farbe</p>
              <div className="flex gap-2">
                <button type="button" onClick={() => setColor(null)}
                  className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${!color ? "border-slate-900" : "border-slate-200"}`}>
                  <span className="text-[9px] text-slate-400">—</span>
                </button>
                {COLOR_OPTIONS.map(c => (
                  <button key={c} type="button" onClick={() => setColor(c)}
                    className={`w-6 h-6 rounded-full border-2 ${color === c ? "border-slate-900 shadow" : "border-transparent"}`}
                    style={{ background: c }} />
                ))}
              </div>
            </div>
            <div className="flex gap-2 justify-end pt-2">
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 py-2 border-2 border-slate-200 rounded-xl text-sm text-slate-600 font-['Architects_Daughter'] hover:bg-slate-50">
                Abbrechen
              </button>
              <button type="submit" disabled={saving || !name.trim()}
                className="px-4 py-2 bg-slate-900 text-white rounded-xl text-sm font-bold font-['Architects_Daughter'] hover:bg-teal-600 transition-colors disabled:opacity-50">
                {saving ? "Speichern..." : "Erstellen"}
              </button>
            </div>
          </form>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900" />
        </div>
      )}

      {!isLoading && projects?.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Folder size={40} className="text-slate-300 mb-3" />
          <p className="text-slate-400 font-['Architects_Daughter'] text-sm">Noch keine Projekte</p>
          <button onClick={() => setShowForm(true)} className="mt-3 text-teal-600 text-sm font-bold font-['Architects_Daughter'] hover:underline">
            Erstes Projekt anlegen →
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {(projects ?? []).map(project => (
          <ProjectCard key={project.id} project={project} orgSlug={orgSlug} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /opt/assist2
git add frontend/app/[org]/project/page.tsx
git commit -m "feat(projects): add project list page at /[org]/project/"
```

---

## Task 8: Project detail page

**Files:**
- Create: `frontend/app/[org]/project/[id]/page.tsx`

- [ ] **Step 1: Create the project detail page**

Create `frontend/app/[org]/project/[id]/page.tsx`:

```tsx
"use client";

import { use, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import type { Project, Epic, UserStory } from "@/types";
import { ArrowLeft, Layers, BookOpen } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  planning: "Planung", active: "Aktiv", done: "Fertig", archived: "Archiviert",
  in_progress: "In Arbeit",
};
const STATUS_COLORS: Record<string, string> = {
  planning: "bg-slate-100 text-slate-600",
  active:   "bg-teal-100 text-teal-700",
  done:     "bg-emerald-100 text-emerald-700",
  archived: "bg-slate-50 text-slate-400",
  in_progress: "bg-amber-100 text-amber-700",
};

type TabId = "epics" | "stories";

export default function ProjectDetailPage({ params }: { params: Promise<{ org: string; id: string }> }) {
  const { org: orgSlug, id: projectId } = use(params);
  const { org } = useOrg(orgSlug);
  const [tab, setTab] = useState<TabId>("epics");

  const { data: project, isLoading: loadingProject } = useSWR<Project>(
    `/api/v1/projects/${projectId}`,
    fetcher
  );

  const { data: epics } = useSWR<Epic[]>(
    `/api/v1/projects/${projectId}/epics`,
    fetcher
  );

  const { data: stories } = useSWR<UserStory[]>(
    `/api/v1/projects/${projectId}/stories`,
    fetcher
  );

  if (loadingProject) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-20">
        <p className="text-slate-400 font-['Architects_Daughter']">Projekt nicht gefunden</p>
        <Link href={`/${orgSlug}/project`} className="mt-3 text-teal-600 text-sm font-bold font-['Architects_Daughter'] hover:underline">
          ← Zurück
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <Link href={`/${orgSlug}/project`}
          className="flex items-center gap-1.5 text-[11px] text-slate-400 font-['Architects_Daughter'] hover:text-teal-600 mb-3 transition-colors">
          <ArrowLeft size={12} />
          Alle Projekte
        </Link>

        <div className="bg-[var(--card)] border-2 border-slate-900/10 rounded-2xl p-5 flex flex-col gap-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              {project.color && (
                <span className="w-5 h-5 rounded-full flex-shrink-0 border-2 border-white shadow-[2px_2px_0_rgba(0,0,0,.15)]"
                  style={{ background: project.color }} />
              )}
              <h1 className="text-2xl font-bold text-slate-900 font-['Gochi_Hand']">{project.name}</h1>
            </div>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 font-['Architects_Daughter'] ${STATUS_COLORS[project.status]}`}>
              {STATUS_LABELS[project.status]}
            </span>
          </div>
          {project.description && (
            <p className="text-sm text-slate-500 leading-relaxed">{project.description}</p>
          )}
          <div className="flex items-center gap-4 flex-wrap text-[11px] text-slate-400 font-['Architects_Daughter']">
            {project.deadline && <span>⏰ {new Date(project.deadline).toLocaleDateString("de-DE")}</span>}
            {project.effort && <span>Aufwand: {project.effort.toUpperCase()}</span>}
            {project.complexity && <span>Komplexität: {project.complexity.toUpperCase()}</span>}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b-2 border-slate-900/5 pb-0">
        {([
          { id: "epics" as TabId, label: "Epics", icon: Layers, count: epics?.length ?? 0 },
          { id: "stories" as TabId, label: "Standalone Stories", icon: BookOpen, count: stories?.length ?? 0 },
        ] as const).map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2 text-[12px] font-bold font-['Architects_Daughter'] tracking-wide transition-colors border-b-2 -mb-[2px] ${
              tab === t.id
                ? "text-slate-900 border-slate-900"
                : "text-slate-400 border-transparent hover:text-slate-600"
            }`}>
            <t.icon size={13} />
            {t.label}
            <span className="ml-1 px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded-full text-[9px]">{t.count}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "epics" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {(epics ?? []).length === 0 && (
            <p className="text-slate-400 text-sm font-['Architects_Daughter'] col-span-3">Keine Epics zugewiesen.</p>
          )}
          {(epics ?? []).map(epic => (
            <div key={epic.id} className="bg-[var(--card)] border-2 border-slate-900/10 rounded-xl p-4 flex flex-col gap-2 hover:border-slate-900/20 transition-all">
              <div className="flex items-start justify-between gap-2">
                <p className="font-bold text-slate-900 font-['Architects_Daughter'] text-[13px] leading-snug line-clamp-2">{epic.title}</p>
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 font-['Architects_Daughter'] ${STATUS_COLORS[epic.status] ?? "bg-slate-100 text-slate-500"}`}>
                  {STATUS_LABELS[epic.status] ?? epic.status}
                </span>
              </div>
              {epic.description && (
                <p className="text-[11px] text-slate-400 line-clamp-2">{epic.description}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "stories" && (
        <div className="flex flex-col gap-2">
          {(stories ?? []).length === 0 && (
            <p className="text-slate-400 text-sm font-['Architects_Daughter']">Keine direkten Stories (ohne Epic) zugewiesen.</p>
          )}
          {(stories ?? []).map(story => (
            <Link key={story.id} href={`/${orgSlug}/stories/${story.id}`}
              className="bg-[var(--card)] border-2 border-slate-900/10 rounded-xl p-4 flex items-center justify-between gap-3 hover:border-slate-900/20 transition-all">
              <p className="font-bold text-slate-900 font-['Architects_Daughter'] text-[13px] truncate">{story.title}</p>
              <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 font-['Architects_Daughter'] ${STATUS_COLORS[story.status] ?? "bg-slate-100 text-slate-500"}`}>
                {STATUS_LABELS[story.status] ?? story.status}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /opt/assist2
git add frontend/app/[org]/project/[id]/page.tsx
git commit -m "feat(projects): add project detail page with Epics + Stories tabs"
```

---

## Task 9: Project filter on boards + story/epic forms

**Files:**
- Modify: `frontend/app/[org]/stories/board/page.tsx`
- Modify: `frontend/app/[org]/stories/epics/board/page.tsx`
- Modify: `frontend/app/[org]/stories/features/board/page.tsx`
- Modify: `frontend/app/[org]/stories/new/page.tsx`
- Modify: `frontend/app/[org]/stories/[id]/page.tsx`

- [ ] **Step 1: Add project filter to Stories board**

In `frontend/app/[org]/stories/board/page.tsx`:

Add `ProjectSelector` import at the top:
```tsx
import { ProjectSelector } from "@/components/stories/ProjectSelector";
```

Add state inside the component:
```tsx
const [projectFilter, setProjectFilter] = useState<string | null>(null);
```

Change the SWR key to include the filter:
```tsx
const { data: stories, isLoading, error, mutate } = useSWR<UserStory[]>(
  org ? `/api/v1/user-stories?org_id=${org.id}${projectFilter ? `&project_id=${projectFilter}` : ""}` : null,
  fetcher
);
```

Add the selector just before the columns render area (after the existing toolbar div that contains the `LayoutList`/`Columns` links). Find the `<div` containing the Link for board/list views and add ProjectSelector next to it:

```tsx
{org && (
  <div className="w-48">
    <ProjectSelector
      orgId={org.id}
      value={projectFilter}
      onChange={setProjectFilter}
      label=""
    />
  </div>
)}
```

- [ ] **Step 2: Add project filter to Epics board**

In `frontend/app/[org]/stories/epics/board/page.tsx`:

Add `ProjectSelector` import:
```tsx
import { ProjectSelector } from "@/components/stories/ProjectSelector";
```

Add state:
```tsx
const [projectFilter, setProjectFilter] = useState<string | null>(null);
```

Change SWR key:
```tsx
const { data: epics, isLoading, error, mutate } = useSWR<Epic[]>(
  org ? `/api/v1/epics?org_id=${org.id}${projectFilter ? `&project_id=${projectFilter}` : ""}` : null,
  fetcher
);
```

Add `ProjectSelector` to the toolbar (next to the "Neues Epic" button area):
```tsx
{org && (
  <div className="w-48">
    <ProjectSelector orgId={org.id} value={projectFilter} onChange={setProjectFilter} label="" />
  </div>
)}
```

- [ ] **Step 3: Add project filter to Features board**

In `frontend/app/[org]/stories/features/board/page.tsx`:

Read the file first to understand the current SWR key and toolbar structure. The features board fetches `/api/v1/features?org_id=...`. Features don't have `project_id` directly, but filtering by project is useful through the story relationship. Since the API doesn't support `?project_id=` on features, skip the API filter for features and instead filter client-side if needed, or simply skip the project filter on this board.

**Decision:** Skip the project filter on the Features board — features are always subordinate to stories, and filtering there adds complexity without proportional value. No changes needed to this file.

- [ ] **Step 4: Add ProjectSelector to New Story form**

In `frontend/app/[org]/stories/new/page.tsx`:

Add import:
```tsx
import { ProjectSelector } from "@/components/stories/ProjectSelector";
```

Add state:
```tsx
const [projectId, setProjectId] = useState<string | null>(null);
```

Add `ProjectSelector` to the form, after the `EpicSelector`:
```tsx
{org && (
  <ProjectSelector orgId={org.id} value={projectId} onChange={setProjectId} />
)}
```

Include `project_id` in the POST body when creating a story. Find the `apiRequest` call for story creation and add it:
```tsx
body: JSON.stringify({
  title,
  description,
  acceptance_criteria: acceptanceCriteria,
  priority,
  story_points: storyPoints ? parseInt(storyPoints, 10) : null,
  epic_id: epicId,
  project_id: projectId,
}),
```

- [ ] **Step 5: Add ProjectSelector to Story detail page**

In `frontend/app/[org]/stories/[id]/page.tsx`:

Read the file to find how `epic_id` is displayed and updated. Then add `ProjectSelector` in the same section.

Add import:
```tsx
import { ProjectSelector } from "@/components/stories/ProjectSelector";
```

Find where `epicId` state is defined and updated. Add alongside it:
```tsx
const [projectId, setProjectId] = useState<string | null>(story.project_id);
```

Add `ProjectSelector` in the form, near the `EpicSelector`:
```tsx
{org && (
  <ProjectSelector orgId={org.id} value={projectId} onChange={async (val) => {
    setProjectId(val);
    await apiRequest(`/api/v1/user-stories/${story.id}`, {
      method: "PATCH",
      body: JSON.stringify({ project_id: val }),
    });
    await mutate();
  }} />
)}
```

- [ ] **Step 6: Commit**

```bash
cd /opt/assist2
git add frontend/app/[org]/stories/board/page.tsx \
        frontend/app/[org]/stories/epics/board/page.tsx \
        frontend/app/[org]/stories/new/page.tsx \
        frontend/app/[org]/stories/[id]/page.tsx
git commit -m "feat(projects): add project filter to boards and project selector to story forms"
```

---

## Task 10: AI Workspace project picker

**Files:**
- Modify: `frontend/app/[org]/ai-workspace/page.tsx`

- [ ] **Step 1: Read the current save dialog in ai-workspace**

Read `frontend/app/[org]/ai-workspace/page.tsx` and find where the story save confirmation is triggered (look for `saveStory`, `handleSave`, or a modal/dialog that confirms the save action).

- [ ] **Step 2: Add project picker to save dialog**

Add import:
```tsx
import { ProjectSelector } from "@/components/stories/ProjectSelector";
```

Add state:
```tsx
const [saveProjectId, setSaveProjectId] = useState<string | null>(null);
```

In the save dialog/form (wherever the user confirms saving a generated story), add:
```tsx
{org && (
  <ProjectSelector
    orgId={org.id}
    value={saveProjectId}
    onChange={setSaveProjectId}
    label="Projekt (optional)"
  />
)}
```

Include `project_id: saveProjectId` in the POST body when saving the story to the API.

Reset on dialog close:
```tsx
setSaveProjectId(null);
```

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add frontend/app/[org]/ai-workspace/page.tsx
git commit -m "feat(projects): add project picker to AI workspace save dialog"
```

---

## Task 11: Final verification

- [ ] **Step 1: Run full backend test suite**

```bash
cd /opt/assist2 && make shell
# inside container:
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All existing tests pass, new project tests pass.

- [ ] **Step 2: Restart all services and smoke-test**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d backend frontend
docker logs assist2-backend --tail 20
docker logs assist2-frontend --tail 20
```

Manually verify:
- Sidebar shows "Projekte" nav entry
- `/[org]/project/` loads the project list
- Can create a project with a name and color
- Click a project → detail page with Epics / Stories tabs
- Stories board shows project filter dropdown
- Epics board shows project filter dropdown
- New story form shows project selector
- Story detail shows project selector

- [ ] **Step 3: Final commit**

```bash
cd /opt/assist2
git add -p  # stage any remaining unstaged changes
git commit -m "feat(projects): complete project assignment feature — Projects → Epics → Stories"
```
