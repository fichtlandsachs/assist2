# Capability Map — Sub-Plan 1: Data Foundation & Backend API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CapabilityNode and ArtifactAssignment models, extend Organization and Project with init/brief/Jira fields, create the capability backend API (CRUD, tree, import, story-count aggregation), and add a Jira project-listing endpoint — fully tested.

**Architecture:** New `capability_nodes` and `artifact_assignments` tables are added via Alembic migration 0018. A capability service builds the tree and computes aggregated story counts bottom-up. A separate import service validates and parses Excel/template/demo data. The router is registered at `/api/v1/capabilities`. No existing tables are removed; Organization and Project receive additive nullable columns.

**Tech Stack:** FastAPI · SQLAlchemy 2 (async, mapped columns) · Alembic · Pydantic v2 · openpyxl (Excel parsing) · pytest + pytest-asyncio (sqlite+aiosqlite in-memory)

---

## File Map

**Create:**
- `backend/app/models/capability_node.py`
- `backend/app/models/artifact_assignment.py`
- `backend/app/schemas/capability.py`
- `backend/app/services/capability_service.py`
- `backend/app/services/capability_import_service.py`
- `backend/app/routers/capabilities.py`
- `backend/migrations/versions/0018_capability_map.py`
- `backend/tests/unit/test_capability_import.py`
- `backend/tests/unit/test_capability_service.py`
- `backend/tests/integration/test_capabilities_api.py`

**Modify:**
- `backend/app/models/organization.py` — add 5 init-status columns
- `backend/app/models/project.py` — add project_brief, planned_start/end_date, Jira fields
- `backend/app/schemas/project.py` — expose new project fields in Create/Read/Update
- `backend/app/routers/projects.py` — write new fields on create/update
- `backend/app/models/__init__.py` — export new models
- `backend/app/main.py` — register capabilities router
- `backend/requirements.txt` — add openpyxl

---

## Task 1: CapabilityNode model

**Files:**
- Create: `backend/app/models/capability_node.py`

- [ ] **Step 1: Write the failing import test**

```python
# backend/tests/unit/test_capability_import.py
def test_capability_node_import():
    from app.models.capability_node import CapabilityNode, NodeType
    assert NodeType.capability == "capability"
    assert NodeType.level_1 == "level_1"
    assert NodeType.level_2 == "level_2"
    assert NodeType.level_3 == "level_3"
    assert CapabilityNode.__tablename__ == "capability_nodes"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_import.py::test_capability_node_import -v
```
Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Create the model**

```python
# backend/app/models/capability_node.py
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Integer, Boolean, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.artifact_assignment import ArtifactAssignment


class NodeType(str, enum.Enum):
    capability = "capability"
    level_1 = "level_1"
    level_2 = "level_2"
    level_3 = "level_3"


# Allowed parent node types per level
ALLOWED_PARENTS: dict[NodeType, list[NodeType]] = {
    NodeType.level_1: [NodeType.capability],
    NodeType.level_2: [NodeType.level_1],
    NodeType.level_3: [NodeType.level_2],
}

# Allowed assignment levels per artifact type (enforced in service)
ALLOWED_ASSIGNMENT_LEVELS = {
    "project":    [NodeType.capability, NodeType.level_1],
    "epic":       [NodeType.level_1, NodeType.level_2, NodeType.level_3],
    "user_story": [NodeType.level_2, NodeType.level_3],
}

EXCEPTION_ALLOWED_LEVELS = {
    "epic":       [NodeType.level_1],
    "user_story": [NodeType.level_1],
}


class CapabilityNode(Base):
    __tablename__ = "capability_nodes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("capability_nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    external_import_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    parent: Mapped[Optional["CapabilityNode"]] = relationship(
        "CapabilityNode",
        remote_side="CapabilityNode.id",
        back_populates="children",
    )
    children: Mapped[List["CapabilityNode"]] = relationship(
        "CapabilityNode",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="CapabilityNode.sort_order",
    )
    assignments: Mapped[List["ArtifactAssignment"]] = relationship(
        "ArtifactAssignment",
        back_populates="node",
        cascade="all, delete-orphan",
    )
```

- [ ] **Step 4: Run the test again**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_import.py::test_capability_node_import -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2/backend && git add app/models/capability_node.py tests/unit/test_capability_import.py
git commit -m "feat(capability): add CapabilityNode model"
```

---

## Task 2: ArtifactAssignment model

**Files:**
- Create: `backend/app/models/artifact_assignment.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/test_capability_import.py`:

```python
def test_artifact_assignment_import():
    from app.models.artifact_assignment import ArtifactAssignment, ArtifactType, RelationType
    assert ArtifactType.project == "project"
    assert ArtifactType.epic == "epic"
    assert ArtifactType.user_story == "user_story"
    assert RelationType.primary == "primary"
    assert RelationType.secondary == "secondary"
    assert ArtifactAssignment.__tablename__ == "artifact_assignments"
```

- [ ] **Step 2: Verify it fails**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_import.py::test_artifact_assignment_import -v
```

- [ ] **Step 3: Create the model**

```python
# backend/app/models/artifact_assignment.py
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.capability_node import CapabilityNode


class ArtifactType(str, enum.Enum):
    project = "project"
    epic = "epic"
    user_story = "user_story"


class RelationType(str, enum.Enum):
    primary = "primary"
    secondary = "secondary"


class ArtifactAssignment(Base):
    __tablename__ = "artifact_assignments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(20), nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(20), nullable=False, default="primary")
    assignment_is_exception: Mapped[bool] = mapped_column(Boolean, default=False)
    assignment_exception_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    node: Mapped["CapabilityNode"] = relationship(
        "CapabilityNode", back_populates="assignments"
    )
```

- [ ] **Step 4: Verify test passes**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_import.py -v
```
Expected: both tests PASS

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2/backend && git add app/models/artifact_assignment.py tests/unit/test_capability_import.py
git commit -m "feat(capability): add ArtifactAssignment model"
```

---

## Task 3: Extend Organization model with init fields

**Files:**
- Modify: `backend/app/models/organization.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/unit/test_capability_import.py`:

```python
def test_org_has_init_fields():
    from app.models.organization import Organization, OrgInitializationStatus
    assert OrgInitializationStatus.not_initialized == "not_initialized"
    assert OrgInitializationStatus.initialized == "initialized"
    cols = {c.name for c in Organization.__table__.c}
    assert "initialization_status" in cols
    assert "initialization_completed_at" in cols
    assert "capability_map_version" in cols
    assert "initial_setup_source" in cols
```

- [ ] **Step 2: Verify it fails**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_import.py::test_org_has_init_fields -v
```

- [ ] **Step 3: Extend the model**

Open `backend/app/models/organization.py`. Add at the top (after existing imports):

```python
import enum
from sqlalchemy import Integer
```

Add the enum before the `Organization` class:

```python
class OrgInitializationStatus(str, enum.Enum):
    not_initialized = "not_initialized"
    capability_setup_in_progress = "capability_setup_in_progress"
    capability_setup_validated = "capability_setup_validated"
    entry_chat_in_progress = "entry_chat_in_progress"
    initialized = "initialized"
```

Add these columns inside the `Organization` class (after existing columns, before relationships):

```python
    initialization_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="not_initialized", server_default="not_initialized"
    )
    initialization_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    capability_map_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    initial_setup_completed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    initial_setup_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
```

Note: `Organization` already imports `Optional`, `datetime`, `uuid`, `String`, `ForeignKey`, `DateTime`, `Mapped`, `mapped_column` — check existing imports and only add what's missing.

- [ ] **Step 4: Verify test passes**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_import.py::test_org_has_init_fields -v
```

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2/backend && git add app/models/organization.py tests/unit/test_capability_import.py
git commit -m "feat(capability): add org initialization status fields"
```

---

## Task 4: Extend Project model with brief, dates, Jira fields

**Files:**
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/schemas/project.py`
- Modify: `backend/app/routers/projects.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/unit/test_capability_import.py`:

```python
def test_project_has_extended_fields():
    from app.models.project import Project
    cols = {c.name for c in Project.__table__.c}
    assert "project_brief" in cols
    assert "planned_start_date" in cols
    assert "planned_end_date" in cols
    assert "jira_project_key" in cols
    assert "jira_source_metadata" in cols
```

- [ ] **Step 2: Verify it fails**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_import.py::test_project_has_extended_fields -v
```

- [ ] **Step 3: Extend the Project model**

Open `backend/app/models/project.py`. Add missing imports at the top:

```python
from sqlalchemy import JSON
```

(The model already imports `String, Text, ForeignKey, Date, DateTime` — verify and add only `JSON` if missing.)

Add these columns inside the `Project` class after the existing `complexity` column:

```python
    # Project brief & timeline
    project_brief: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    planned_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    planned_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Jira reference fields
    jira_project_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jira_project_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    jira_project_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    jira_project_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    jira_project_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    jira_project_lead: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jira_board_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jira_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    jira_source_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 4: Update ProjectCreate, ProjectUpdate, ProjectRead schemas**

Open `backend/app/schemas/project.py`. Add these fields:

```python
from typing import Optional, Any
import uuid
from datetime import datetime, date

# In ProjectCreate — add after existing fields:
    project_brief: Optional[str] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    jira_project_id: Optional[str] = None
    jira_project_key: Optional[str] = None
    jira_project_name: Optional[str] = None
    jira_project_url: Optional[str] = None
    jira_project_type: Optional[str] = None
    jira_project_lead: Optional[str] = None
    jira_board_id: Optional[str] = None
    jira_source_metadata: Optional[dict[str, Any]] = None

# In ProjectUpdate — add the same Optional fields

# In ProjectRead — add after existing fields:
    project_brief: Optional[str]
    planned_start_date: Optional[date]
    planned_end_date: Optional[date]
    actual_start_date: Optional[date]
    actual_end_date: Optional[date]
    jira_project_id: Optional[str]
    jira_project_key: Optional[str]
    jira_project_name: Optional[str]
    jira_project_url: Optional[str]
    jira_project_type: Optional[str]
    jira_project_lead: Optional[str]
    jira_board_id: Optional[str]
    jira_synced_at: Optional[datetime]
    jira_source_metadata: Optional[dict[str, Any]]
```

- [ ] **Step 5: Update the projects router to write new fields**

Open `backend/app/routers/projects.py`. In `create_project`, add to the `Project(...)` constructor:

```python
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
        # New fields
        project_brief=data.project_brief,
        planned_start_date=data.planned_start_date,
        planned_end_date=data.planned_end_date,
        jira_project_id=data.jira_project_id,
        jira_project_key=data.jira_project_key,
        jira_project_name=data.jira_project_name,
        jira_project_url=data.jira_project_url,
        jira_project_type=data.jira_project_type,
        jira_project_lead=data.jira_project_lead,
        jira_board_id=data.jira_board_id,
        jira_source_metadata=data.jira_source_metadata,
    )
```

In `update_project` (the PATCH endpoint), add:

```python
    for field in [
        "project_brief", "planned_start_date", "planned_end_date",
        "actual_start_date", "actual_end_date",
        "jira_project_id", "jira_project_key", "jira_project_name",
        "jira_project_url", "jira_project_type", "jira_project_lead",
        "jira_board_id", "jira_source_metadata",
    ]:
        if (val := getattr(data, field, None)) is not None:
            setattr(project, field, val)
```

- [ ] **Step 6: Verify test passes**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_import.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 7: Commit**

```bash
cd /opt/assist2/backend && git add app/models/project.py app/schemas/project.py app/routers/projects.py tests/unit/test_capability_import.py
git commit -m "feat(capability): extend Project with brief, timeline, and Jira reference fields"
```

---

## Task 5: Register new models in __init__.py

**Files:**
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Add imports and __all__ entries**

Open `backend/app/models/__init__.py`. Add after the last import:

```python
from app.models.capability_node import CapabilityNode, NodeType
from app.models.artifact_assignment import ArtifactAssignment, ArtifactType, RelationType
from app.models.organization import OrgInitializationStatus
```

Add to `__all__`:

```python
    "CapabilityNode",
    "NodeType",
    "ArtifactAssignment",
    "ArtifactType",
    "RelationType",
    "OrgInitializationStatus",
```

- [ ] **Step 2: Verify imports work**

```bash
cd /opt/assist2/backend && python -c "from app.models import CapabilityNode, ArtifactAssignment, OrgInitializationStatus; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2/backend && git add app/models/__init__.py
git commit -m "feat(capability): register new models in __init__"
```

---

## Task 6: Alembic migration 0018

**Files:**
- Create: `backend/migrations/versions/0018_capability_map.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/migrations/versions/0018_capability_map.py
"""capability map: nodes, assignments, org init fields, project extended fields

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── capability_nodes ────────────────────────────────────────────────────
    op.create_table(
        "capability_nodes",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.UUID(as_uuid=True), sa.ForeignKey("capability_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("node_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("external_import_key", sa.String(255), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_capability_nodes_org_id", "capability_nodes", ["org_id"])
    op.create_index("ix_capability_nodes_parent_id", "capability_nodes", ["parent_id"])

    # ── artifact_assignments ─────────────────────────────────────────────────
    op.create_table(
        "artifact_assignments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_type", sa.String(20), nullable=False),
        sa.Column("artifact_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.UUID(as_uuid=True), sa.ForeignKey("capability_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(20), nullable=False, server_default="primary"),
        sa.Column("assignment_is_exception", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("assignment_exception_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_artifact_assignments_org_id", "artifact_assignments", ["org_id"])
    op.create_index("ix_artifact_assignments_artifact_id", "artifact_assignments", ["artifact_id"])
    op.create_index("ix_artifact_assignments_node_id", "artifact_assignments", ["node_id"])

    # ── organizations: init fields ───────────────────────────────────────────
    op.add_column("organizations", sa.Column("initialization_status", sa.String(50), nullable=False, server_default="not_initialized"))
    op.add_column("organizations", sa.Column("initialization_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organizations", sa.Column("capability_map_version", sa.Integer, nullable=False, server_default="0"))
    op.add_column("organizations", sa.Column("initial_setup_completed_by_id", sa.UUID(as_uuid=True), nullable=True))
    op.add_column("organizations", sa.Column("initial_setup_source", sa.String(50), nullable=True))
    op.create_foreign_key(
        "fk_organizations_setup_by",
        "organizations", "users",
        ["initial_setup_completed_by_id"], ["id"],
        ondelete="SET NULL",
    )

    # ── projects: extended fields ────────────────────────────────────────────
    op.add_column("projects", sa.Column("project_brief", sa.Text, nullable=True))
    op.add_column("projects", sa.Column("planned_start_date", sa.Date, nullable=True))
    op.add_column("projects", sa.Column("planned_end_date", sa.Date, nullable=True))
    op.add_column("projects", sa.Column("actual_start_date", sa.Date, nullable=True))
    op.add_column("projects", sa.Column("actual_end_date", sa.Date, nullable=True))
    op.add_column("projects", sa.Column("jira_project_id", sa.String(255), nullable=True))
    op.add_column("projects", sa.Column("jira_project_key", sa.String(50), nullable=True))
    op.add_column("projects", sa.Column("jira_project_name", sa.String(500), nullable=True))
    op.add_column("projects", sa.Column("jira_project_url", sa.String(2048), nullable=True))
    op.add_column("projects", sa.Column("jira_project_type", sa.String(100), nullable=True))
    op.add_column("projects", sa.Column("jira_project_lead", sa.String(255), nullable=True))
    op.add_column("projects", sa.Column("jira_board_id", sa.String(255), nullable=True))
    op.add_column("projects", sa.Column("jira_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("jira_source_metadata", sa.JSON, nullable=True))


def downgrade() -> None:
    # projects
    for col in ["jira_source_metadata", "jira_synced_at", "jira_board_id", "jira_project_lead",
                "jira_project_type", "jira_project_url", "jira_project_name", "jira_project_key",
                "jira_project_id", "actual_end_date", "actual_start_date", "planned_end_date",
                "planned_start_date", "project_brief"]:
        op.drop_column("projects", col)
    # organizations
    op.drop_constraint("fk_organizations_setup_by", "organizations", type_="foreignkey")
    for col in ["initial_setup_source", "initial_setup_completed_by_id",
                "capability_map_version", "initialization_completed_at", "initialization_status"]:
        op.drop_column("organizations", col)
    # artifact_assignments
    op.drop_index("ix_artifact_assignments_node_id", "artifact_assignments")
    op.drop_index("ix_artifact_assignments_artifact_id", "artifact_assignments")
    op.drop_index("ix_artifact_assignments_org_id", "artifact_assignments")
    op.drop_table("artifact_assignments")
    # capability_nodes
    op.drop_index("ix_capability_nodes_parent_id", "capability_nodes")
    op.drop_index("ix_capability_nodes_org_id", "capability_nodes")
    op.drop_table("capability_nodes")
```

- [ ] **Step 2: Run the migration against the running DB**

```bash
cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec backend alembic upgrade head
```
Expected: `Running upgrade 0017 -> 0018, capability map: nodes, assignments, org init fields, project extended fields`

- [ ] **Step 3: Verify tables exist**

```bash
cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec backend python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings
s = get_settings()
async def check():
    engine = create_async_engine(s.DATABASE_URL)
    async with engine.connect() as conn:
        for t in ['capability_nodes','artifact_assignments']:
            r = await conn.execute(__import__('sqlalchemy').text(f'SELECT COUNT(*) FROM {t}'))
            print(t, r.scalar())
    await engine.dispose()
asyncio.run(check())
"
```
Expected: both tables print `0`

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2/backend && git add migrations/versions/0018_capability_map.py
git commit -m "feat(capability): migration 0018 — capability_nodes, artifact_assignments, org/project extensions"
```

---

## Task 7: Capability Pydantic schemas

**Files:**
- Create: `backend/app/schemas/capability.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_capability_service.py`:

```python
"""Unit tests for capability service logic (no DB needed)."""
import uuid
import pytest
from app.schemas.capability import CapabilityNodeRead, CapabilityTreeNode, ImportValidationResult
```

- [ ] **Step 2: Verify import fails**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_service.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create the schemas**

```python
# backend/app/schemas/capability.py
from __future__ import annotations
from typing import Optional, Any
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator


class CapabilityNodeCreate(BaseModel):
    node_type: str  # capability | level_1 | level_2 | level_3
    title: str
    description: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    sort_order: int = 0
    external_import_key: Optional[str] = None
    source_type: Optional[str] = None  # excel | template | demo | manual

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        allowed = {"capability", "level_1", "level_2", "level_3"}
        if v not in allowed:
            raise ValueError(f"node_type must be one of {allowed}")
        return v


class CapabilityNodeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CapabilityNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    parent_id: Optional[uuid.UUID]
    node_type: str
    title: str
    description: Optional[str]
    sort_order: int
    is_active: bool
    external_import_key: Optional[str]
    source_type: Optional[str]
    created_at: datetime
    updated_at: datetime


class CapabilityTreeNode(BaseModel):
    """A node in the serialised capability tree (includes children + story count)."""
    id: str
    org_id: str
    parent_id: Optional[str]
    node_type: str
    title: str
    description: Optional[str]
    sort_order: int
    is_active: bool
    external_import_key: Optional[str]
    source_type: Optional[str]
    story_count: int = 0
    children: list[CapabilityTreeNode] = []


class ArtifactAssignmentCreate(BaseModel):
    artifact_type: str  # project | epic | user_story
    artifact_id: uuid.UUID
    node_id: uuid.UUID
    relation_type: str = "primary"  # primary | secondary
    assignment_is_exception: bool = False
    assignment_exception_reason: Optional[str] = None

    @field_validator("artifact_type")
    @classmethod
    def validate_artifact_type(cls, v: str) -> str:
        if v not in {"project", "epic", "user_story"}:
            raise ValueError("artifact_type must be project, epic, or user_story")
        return v

    @field_validator("relation_type")
    @classmethod
    def validate_relation_type(cls, v: str) -> str:
        if v not in {"primary", "secondary"}:
            raise ValueError("relation_type must be primary or secondary")
        return v


class ArtifactAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    artifact_type: str
    artifact_id: uuid.UUID
    node_id: uuid.UUID
    relation_type: str
    assignment_is_exception: bool
    assignment_exception_reason: Optional[str]
    created_at: datetime
    created_by_id: Optional[uuid.UUID]


# ── Import validation schemas ─────────────────────────────────────────────────

class ImportNodeRow(BaseModel):
    """A single row from the import source before tree assembly."""
    capability: str
    level_1: Optional[str] = None
    level_2: Optional[str] = None
    level_3: Optional[str] = None
    description: Optional[str] = None
    responsible: Optional[str] = None
    is_active: bool = True
    external_key: Optional[str] = None


class ImportIssue(BaseModel):
    level: str  # "error" | "warning"
    message: str
    row: Optional[int] = None
    field: Optional[str] = None


class ImportValidationResult(BaseModel):
    is_valid: bool
    error_count: int
    warning_count: int
    capability_count: int
    level_1_count: int
    level_2_count: int
    level_3_count: int
    issues: list[ImportIssue]
    # Resolved flat node list ready for DB insertion (only present when is_valid=True)
    nodes: list[dict[str, Any]] = []


# ── Org initialization ────────────────────────────────────────────────────────

class OrgInitStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    initialization_status: str
    initialization_completed_at: Optional[datetime]
    capability_map_version: int
    initial_setup_source: Optional[str]


class OrgInitAdvance(BaseModel):
    """Move org to the next init step."""
    status: str
    source: Optional[str] = None  # excel | template | demo

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {
            "capability_setup_in_progress",
            "capability_setup_validated",
            "entry_chat_in_progress",
            "initialized",
        }
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v
```

- [ ] **Step 4: Verify the import test passes**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_service.py -v
```
Expected: PASS (collection succeeds)

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2/backend && git add app/schemas/capability.py tests/unit/test_capability_service.py
git commit -m "feat(capability): Pydantic schemas for capability nodes, assignments, import, init"
```

---

## Task 8: Capability service (tree, counts, CRUD)

**Files:**
- Create: `backend/app/services/capability_service.py`

- [ ] **Step 1: Write unit tests for tree building and count aggregation**

Add to `backend/tests/unit/test_capability_service.py`:

```python
from app.services.capability_service import _build_tree, _apply_counts


def _make_node(id: str, node_type: str, parent_id: str | None = None, title: str = "N") -> dict:
    return {
        "id": id,
        "org_id": "org1",
        "parent_id": parent_id,
        "node_type": node_type,
        "title": title,
        "description": None,
        "sort_order": 0,
        "is_active": True,
        "external_import_key": None,
        "source_type": None,
        "children": [],
        "story_count": 0,
    }


def test_build_tree_single_root():
    nodes = [_make_node("cap1", "capability")]
    tree = _build_tree(nodes)
    assert len(tree) == 1
    assert tree[0]["id"] == "cap1"
    assert tree[0]["children"] == []


def test_build_tree_hierarchy():
    nodes = [
        _make_node("cap1", "capability"),
        _make_node("l1a", "level_1", parent_id="cap1"),
        _make_node("l2a", "level_2", parent_id="l1a"),
        _make_node("l3a", "level_3", parent_id="l2a"),
    ]
    tree = _build_tree(nodes)
    assert len(tree) == 1  # one root
    l1_children = tree[0]["children"]
    assert len(l1_children) == 1
    assert l1_children[0]["id"] == "l1a"
    l2_children = l1_children[0]["children"]
    assert l2_children[0]["id"] == "l2a"


def test_apply_counts_aggregates_bottom_up():
    nodes = [
        _make_node("cap1", "capability"),
        _make_node("l1a", "level_1", parent_id="cap1"),
        _make_node("l2a", "level_2", parent_id="l1a"),
        _make_node("l3a", "level_3", parent_id="l2a"),
    ]
    tree = _build_tree(nodes)
    # 3 stories directly assigned to l3a
    counts = {"l3a": 3}
    _apply_counts(tree, counts)
    l3 = tree[0]["children"][0]["children"][0]["children"][0]
    assert l3["story_count"] == 3  # direct
    l2 = tree[0]["children"][0]["children"][0]
    assert l2["story_count"] == 3  # aggregated from l3
    l1 = tree[0]["children"][0]
    assert l1["story_count"] == 3  # aggregated from l2
    cap = tree[0]
    assert cap["story_count"] == 3  # aggregated from l1


def test_apply_counts_multi_branch():
    nodes = [
        _make_node("cap1", "capability"),
        _make_node("l1a", "level_1", parent_id="cap1"),
        _make_node("l1b", "level_1", parent_id="cap1"),
        _make_node("l2a", "level_2", parent_id="l1a"),
        _make_node("l2b", "level_2", parent_id="l1b"),
    ]
    tree = _build_tree(nodes)
    counts = {"l2a": 2, "l2b": 5}
    _apply_counts(tree, counts)
    assert tree[0]["story_count"] == 7  # 2 + 5 aggregated to root
```

- [ ] **Step 2: Verify tests fail**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_service.py -v
```
Expected: `ImportError` for `capability_service`

- [ ] **Step 3: Create the service**

```python
# backend/app/services/capability_service.py
"""Capability node CRUD, tree assembly, and story-count aggregation."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capability_node import CapabilityNode
from app.models.artifact_assignment import ArtifactAssignment
from app.models.organization import Organization, OrgInitializationStatus
from app.schemas.capability import (
    CapabilityNodeCreate,
    CapabilityNodeUpdate,
    OrgInitAdvance,
)


# ── Tree helpers ──────────────────────────────────────────────────────────────

def _node_to_dict(node: CapabilityNode) -> dict[str, Any]:
    return {
        "id": str(node.id),
        "org_id": str(node.org_id),
        "parent_id": str(node.parent_id) if node.parent_id else None,
        "node_type": node.node_type,
        "title": node.title,
        "description": node.description,
        "sort_order": node.sort_order,
        "is_active": node.is_active,
        "external_import_key": node.external_import_key,
        "source_type": node.source_type,
        "children": [],
        "story_count": 0,
    }


def _build_tree(flat: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assemble a parent-child tree from a flat node list."""
    by_id = {n["id"]: n for n in flat}
    roots: list[dict[str, Any]] = []
    for node in flat:
        pid = node["parent_id"]
        if pid and pid in by_id:
            by_id[pid]["children"].append(node)
        else:
            roots.append(node)
    return roots


def _apply_counts(nodes: list[dict[str, Any]], counts: dict[str, int]) -> int:
    """Set story_count on each node = direct + all descendant counts. Returns subtree total."""
    total = 0
    for node in nodes:
        child_total = _apply_counts(node["children"], counts)
        direct = counts.get(node["id"], 0)
        node["story_count"] = direct + child_total
        total += direct + child_total
    return total


# ── DB queries ─────────────────────────────────────────────────────────────────

async def get_capability_tree(db: AsyncSession, org_id: uuid.UUID) -> list[dict[str, Any]]:
    """Return the full active tree for an org (no story counts)."""
    stmt = (
        select(CapabilityNode)
        .where(CapabilityNode.org_id == org_id, CapabilityNode.is_active == True)  # noqa: E712
        .order_by(CapabilityNode.node_type, CapabilityNode.sort_order, CapabilityNode.title)
    )
    result = await db.execute(stmt)
    flat = [_node_to_dict(n) for n in result.scalars().all()]
    return _build_tree(flat)


async def get_capability_tree_with_counts(
    db: AsyncSession, org_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Return tree with aggregated story counts per node."""
    tree = await get_capability_tree(db, org_id)
    # Direct counts per node
    stmt = (
        select(ArtifactAssignment.node_id, func.count(ArtifactAssignment.id))
        .where(
            ArtifactAssignment.org_id == org_id,
            ArtifactAssignment.artifact_type == "user_story",
        )
        .group_by(ArtifactAssignment.node_id)
    )
    result = await db.execute(stmt)
    counts = {str(row[0]): row[1] for row in result.all()}
    _apply_counts(tree, counts)
    return tree


async def get_node(
    db: AsyncSession, org_id: uuid.UUID, node_id: uuid.UUID
) -> Optional[CapabilityNode]:
    stmt = select(CapabilityNode).where(
        CapabilityNode.org_id == org_id, CapabilityNode.id == node_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_node(
    db: AsyncSession, org_id: uuid.UUID, data: CapabilityNodeCreate
) -> CapabilityNode:
    node = CapabilityNode(
        org_id=org_id,
        parent_id=data.parent_id,
        node_type=data.node_type,
        title=data.title,
        description=data.description,
        sort_order=data.sort_order,
        external_import_key=data.external_import_key,
        source_type=data.source_type,
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node


async def update_node(
    db: AsyncSession, node: CapabilityNode, data: CapabilityNodeUpdate
) -> CapabilityNode:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(node, field, value)
    await db.commit()
    await db.refresh(node)
    return node


async def delete_org_nodes(db: AsyncSession, org_id: uuid.UUID) -> None:
    """Delete all capability nodes for an org (used before re-import)."""
    await db.execute(
        delete(CapabilityNode).where(CapabilityNode.org_id == org_id)
    )
    await db.commit()


async def bulk_create_nodes(
    db: AsyncSession, org_id: uuid.UUID, nodes: list[dict[str, Any]]
) -> int:
    """Insert pre-validated node dicts. Returns count inserted."""
    objs = [
        CapabilityNode(
            org_id=org_id,
            parent_id=n.get("parent_id"),
            node_type=n["node_type"],
            title=n["title"],
            description=n.get("description"),
            sort_order=n.get("sort_order", 0),
            external_import_key=n.get("external_import_key"),
            source_type=n.get("source_type"),
            is_active=n.get("is_active", True),
        )
        for n in nodes
    ]
    db.add_all(objs)
    await db.commit()
    return len(objs)


# ── Org initialization ─────────────────────────────────────────────────────────

async def get_org_init_status(db: AsyncSession, org: Organization) -> dict[str, Any]:
    return {
        "initialization_status": org.initialization_status,
        "initialization_completed_at": org.initialization_completed_at,
        "capability_map_version": org.capability_map_version,
        "initial_setup_source": org.initial_setup_source,
    }


async def advance_org_init_status(
    db: AsyncSession, org: Organization, data: OrgInitAdvance, user_id: uuid.UUID
) -> Organization:
    from datetime import datetime, timezone

    org.initialization_status = data.status
    if data.source:
        org.initial_setup_source = data.source
    if data.status == "initialized":
        org.initialization_completed_at = datetime.now(timezone.utc)
        org.initial_setup_completed_by_id = user_id
        org.capability_map_version = (org.capability_map_version or 0) + 1
    await db.commit()
    await db.refresh(org)
    return org
```

- [ ] **Step 4: Run the unit tests**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_service.py -v
```
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2/backend && git add app/services/capability_service.py tests/unit/test_capability_service.py
git commit -m "feat(capability): capability service — tree building, count aggregation, CRUD, init status"
```

---

## Task 9: Excel import service + validation

**Files:**
- Create: `backend/app/services/capability_import_service.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add openpyxl to requirements**

Open `backend/requirements.txt`. Add:
```
openpyxl==3.1.5
```

- [ ] **Step 2: Write unit tests for import validation**

Create `backend/tests/unit/test_capability_import_service.py`:

```python
"""Unit tests for capability import validation logic."""
import pytest
from app.services.capability_import_service import validate_rows, build_nodes_from_rows


def _row(cap="Cap A", l1="Proc 1", l2="Sub 1", l3=None, key=None) -> dict:
    return {
        "capability": cap,
        "level_1": l1,
        "level_2": l2,
        "level_3": l3,
        "description": None,
        "external_key": key,
        "is_active": True,
    }


def test_valid_rows_produce_no_errors():
    rows = [_row("Cap A", "Proc 1", "Sub 1"), _row("Cap A", "Proc 1", "Sub 2")]
    result = validate_rows(rows)
    assert result.is_valid
    assert result.error_count == 0


def test_missing_capability_is_error():
    rows = [_row("", "Proc 1", "Sub 1")]
    result = validate_rows(rows)
    assert not result.is_valid
    assert result.error_count >= 1
    assert any("capability" in i.message.lower() for i in result.issues if i.level == "error")


def test_level_2_without_level_1_is_error():
    rows = [{"capability": "Cap A", "level_1": "", "level_2": "Orphaned", "level_3": None,
             "description": None, "external_key": None, "is_active": True}]
    result = validate_rows(rows)
    assert not result.is_valid
    assert any("level_1" in i.message.lower() or "parent" in i.message.lower()
               for i in result.issues if i.level == "error")


def test_duplicate_title_at_same_level_is_warning():
    rows = [_row("Cap A", "Proc 1", "Sub 1"), _row("Cap A", "Proc 1", "Sub 1")]
    result = validate_rows(rows)
    # duplicate should trigger at least a warning
    assert result.warning_count >= 1 or not result.is_valid


def test_build_nodes_creates_correct_hierarchy():
    rows = [_row("Cap A", "Proc 1", "Sub 1", "Task 1")]
    result = validate_rows(rows)
    assert result.is_valid
    nodes = build_nodes_from_rows(rows, source_type="excel")
    types = {n["node_type"] for n in nodes}
    assert "capability" in types
    assert "level_1" in types
    assert "level_2" in types
    assert "level_3" in types
    assert len(nodes) == 4


def test_build_nodes_deduplicates_repeated_capabilities():
    rows = [_row("Cap A", "Proc 1", "Sub 1"), _row("Cap A", "Proc 2", "Sub 2")]
    nodes = build_nodes_from_rows(rows, source_type="excel")
    caps = [n for n in nodes if n["node_type"] == "capability"]
    assert len(caps) == 1  # "Cap A" appears once


def test_counts_are_correct():
    rows = [
        _row("Cap A", "Proc 1", "Sub 1"),
        _row("Cap A", "Proc 1", "Sub 2"),
        _row("Cap B", "Proc 3", "Sub 3"),
    ]
    result = validate_rows(rows)
    assert result.capability_count == 2
    assert result.level_1_count == 2
    assert result.level_2_count == 3
```

- [ ] **Step 3: Verify tests fail**

```bash
cd /opt/assist2/backend && python -m pytest tests/unit/test_capability_import_service.py -v
```
Expected: `ImportError`

- [ ] **Step 4: Create the import service**

```python
# backend/app/services/capability_import_service.py
"""Capability map import: Excel parsing, validation, and node assembly."""
from __future__ import annotations

import io
import uuid
from typing import Any, Optional

from app.schemas.capability import ImportValidationResult, ImportIssue


# ── Validation ────────────────────────────────────────────────────────────────

def validate_rows(rows: list[dict[str, Any]]) -> ImportValidationResult:
    """Validate a list of flat import rows. Returns errors, warnings, and counts."""
    errors: list[ImportIssue] = []
    warnings: list[ImportIssue] = []

    seen: dict[str, set[str]] = {
        "capability": set(),
        "level_1": set(),  # keyed as "cap||l1"
        "level_2": set(),  # keyed as "cap||l1||l2"
    }
    caps: set[str] = set()
    l1s: set[str] = set()
    l2s: set[str] = set()
    l3s: set[str] = set()

    for i, row in enumerate(rows):
        row_num = i + 2  # 1-indexed + header
        cap = (row.get("capability") or "").strip()
        l1 = (row.get("level_1") or "").strip()
        l2 = (row.get("level_2") or "").strip()
        l3 = (row.get("level_3") or "").strip() or None

        if not cap:
            errors.append(ImportIssue(level="error", message="Missing Capability title", row=row_num, field="capability"))
            continue

        if l2 and not l1:
            errors.append(ImportIssue(level="error", message=f"Level 2 '{l2}' has no Level 1 parent", row=row_num, field="level_1"))

        if l3 and not l2:
            errors.append(ImportIssue(level="error", message=f"Level 3 '{l3}' has no Level 2 parent", row=row_num, field="level_2"))

        # Duplicate detection
        if cap:
            if cap in seen["capability"]:
                pass  # cap repetition is normal (multiple rows per cap)
            seen["capability"].add(cap)
            caps.add(cap)

        if l1:
            key = f"{cap}||{l1}"
            if key in seen["level_1"]:
                pass  # repetition is normal
            seen["level_1"].add(key)
            l1s.add(key)

        if l2:
            key = f"{cap}||{l1}||{l2}"
            if key in seen["level_2"]:
                warnings.append(ImportIssue(level="warning", message=f"Duplicate Level 2 '{l2}' under '{l1}'", row=row_num, field="level_2"))
            seen["level_2"].add(key)
            l2s.add(key)

        if l3:
            key = f"{cap}||{l1}||{l2}||{l3}"
            l3s.add(key)

    is_valid = len(errors) == 0
    return ImportValidationResult(
        is_valid=is_valid,
        error_count=len(errors),
        warning_count=len(warnings),
        capability_count=len(caps),
        level_1_count=len(l1s),
        level_2_count=len(l2s),
        level_3_count=len(l3s),
        issues=errors + warnings,
        nodes=build_nodes_from_rows(rows, source_type="import") if is_valid else [],
    )


def build_nodes_from_rows(
    rows: list[dict[str, Any]], source_type: str = "excel"
) -> list[dict[str, Any]]:
    """Build a flat list of node dicts from import rows (deduplicates, assigns temp IDs)."""
    caps: dict[str, str] = {}       # title → temp_id
    l1s: dict[str, str] = {}        # "cap||l1" → temp_id
    l2s: dict[str, str] = {}        # "cap||l1||l2" → temp_id
    nodes: list[dict[str, Any]] = []

    def _new_id() -> str:
        return str(uuid.uuid4())

    for i, row in enumerate(rows):
        cap = (row.get("capability") or "").strip()
        l1 = (row.get("level_1") or "").strip()
        l2 = (row.get("level_2") or "").strip()
        l3 = (row.get("level_3") or "").strip() or None
        desc = (row.get("description") or "").strip() or None
        ext_key = row.get("external_key")
        is_active = bool(row.get("is_active", True))

        if not cap:
            continue

        if cap not in caps:
            tid = _new_id()
            caps[cap] = tid
            nodes.append({
                "node_type": "capability",
                "title": cap,
                "description": None,
                "parent_id": None,
                "sort_order": len(caps) - 1,
                "external_import_key": ext_key if not l1 else None,
                "source_type": source_type,
                "is_active": is_active,
                "_temp_id": tid,
            })

        if l1:
            l1_key = f"{cap}||{l1}"
            if l1_key not in l1s:
                tid = _new_id()
                l1s[l1_key] = tid
                nodes.append({
                    "node_type": "level_1",
                    "title": l1,
                    "description": None,
                    "parent_id": caps[cap],
                    "sort_order": len(l1s) - 1,
                    "external_import_key": ext_key if not l2 else None,
                    "source_type": source_type,
                    "is_active": is_active,
                    "_temp_id": tid,
                })

            if l2:
                l2_key = f"{cap}||{l1}||{l2}"
                if l2_key not in l2s:
                    tid = _new_id()
                    l2s[l2_key] = tid
                    nodes.append({
                        "node_type": "level_2",
                        "title": l2,
                        "description": desc,
                        "parent_id": l1s[l1_key],
                        "sort_order": len(l2s) - 1,
                        "external_import_key": ext_key if not l3 else None,
                        "source_type": source_type,
                        "is_active": is_active,
                        "_temp_id": tid,
                    })

                if l3:
                    nodes.append({
                        "node_type": "level_3",
                        "title": l3,
                        "description": desc,
                        "parent_id": l2s[l2_key],
                        "sort_order": i,
                        "external_import_key": ext_key,
                        "source_type": source_type,
                        "is_active": is_active,
                        "_temp_id": _new_id(),
                    })

    # Replace _temp_id references in parent_id
    id_map = {n["_temp_id"]: n["_temp_id"] for n in nodes}
    for n in nodes:
        del n["_temp_id"]

    return nodes


# ── Excel parsing ─────────────────────────────────────────────────────────────

def parse_excel(file_bytes: bytes) -> ImportValidationResult:
    """Parse XLSX bytes and return validation result."""
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl is required for Excel import: pip install openpyxl")

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = [str(c).strip().lower() if c else "" for c in next(rows_iter)]
    except StopIteration:
        return ImportValidationResult(
            is_valid=False,
            error_count=1,
            warning_count=0,
            capability_count=0, level_1_count=0, level_2_count=0, level_3_count=0,
            issues=[ImportIssue(level="error", message="Excel file is empty or has no header row")],
        )

    # Normalise column names
    col_aliases = {
        "capability": ["capability", "cap", "fähigkeit", "kompetenz"],
        "level_1": ["level1", "level 1", "l1", "prozess 1", "level_1", "lvl1"],
        "level_2": ["level2", "level 2", "l2", "prozess 2", "level_2", "lvl2"],
        "level_3": ["level3", "level 3", "l3", "prozess 3", "level_3", "lvl3"],
        "description": ["description", "beschreibung", "desc"],
        "external_key": ["external_key", "key", "import_key", "external key"],
        "is_active": ["is_active", "aktiv", "active"],
    }

    col_idx: dict[str, int | None] = {}
    for field, aliases in col_aliases.items():
        idx = None
        for alias in aliases:
            try:
                idx = header.index(alias)
                break
            except ValueError:
                pass
        col_idx[field] = idx

    def _cell(row: tuple, field: str) -> Optional[str]:
        idx = col_idx.get(field)
        if idx is None or idx >= len(row):
            return None
        val = row[idx]
        return str(val).strip() if val is not None else None

    parsed_rows: list[dict[str, Any]] = []
    for row in rows_iter:
        if all(c is None for c in row):
            continue
        parsed_rows.append({
            "capability": _cell(row, "capability") or "",
            "level_1": _cell(row, "level_1"),
            "level_2": _cell(row, "level_2"),
            "level_3": _cell(row, "level_3"),
            "description": _cell(row, "description"),
            "external_key": _cell(row, "external_key"),
            "is_active": True,
        })

    wb.close()
    return validate_rows(parsed_rows)


# ── Demo / Template seeds ─────────────────────────────────────────────────────

DEMO_ROWS: list[dict[str, Any]] = [
    {"capability": "Digitale Transformation", "level_1": "IT-Strategie", "level_2": "Cloud-Migration", "level_3": "Assessment", "description": "Bewertung der Cloud-Readiness", "external_key": None, "is_active": True},
    {"capability": "Digitale Transformation", "level_1": "IT-Strategie", "level_2": "Cloud-Migration", "level_3": "Planung", "description": None, "external_key": None, "is_active": True},
    {"capability": "Digitale Transformation", "level_1": "IT-Strategie", "level_2": "Architektur", "level_3": None, "description": "Enterprise-Architektur", "external_key": None, "is_active": True},
    {"capability": "Digitale Transformation", "level_1": "Datenstrategie", "level_2": "Data Governance", "level_3": "Richtlinien", "description": None, "external_key": None, "is_active": True},
    {"capability": "Digitale Transformation", "level_1": "Datenstrategie", "level_2": "Analytics", "level_3": None, "description": "Business Intelligence & Reporting", "external_key": None, "is_active": True},
    {"capability": "Produkt & Entwicklung", "level_1": "Produktmanagement", "level_2": "Roadmap-Planung", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Produkt & Entwicklung", "level_1": "Produktmanagement", "level_2": "Anforderungsmanagement", "level_3": "User Stories", "description": None, "external_key": None, "is_active": True},
    {"capability": "Produkt & Entwicklung", "level_1": "Software-Entwicklung", "level_2": "Frontend", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Produkt & Entwicklung", "level_1": "Software-Entwicklung", "level_2": "Backend", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Produkt & Entwicklung", "level_1": "Software-Entwicklung", "level_2": "QA & Testing", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Betrieb & Infrastruktur", "level_1": "IT-Betrieb", "level_2": "Monitoring", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Betrieb & Infrastruktur", "level_1": "IT-Betrieb", "level_2": "Deployment", "level_3": "CI/CD", "description": None, "external_key": None, "is_active": True},
    {"capability": "Betrieb & Infrastruktur", "level_1": "Sicherheit", "level_2": "Identity & Access", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Betrieb & Infrastruktur", "level_1": "Sicherheit", "level_2": "Compliance", "level_3": "Audit", "description": None, "external_key": None, "is_active": True},
]

TEMPLATE_ROWS: dict[str, list[dict[str, Any]]] = {
    "software_product": [
        {"capability": "Strategie", "level_1": "Produktvision", "level_2": "Roadmap", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Strategie", "level_1": "Markt & Wettbewerb", "level_2": "Marktanalyse", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Entwicklung", "level_1": "Frontend", "level_2": "UI/UX", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Entwicklung", "level_1": "Backend", "level_2": "API", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Entwicklung", "level_1": "Backend", "level_2": "Datenbank", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Betrieb", "level_1": "DevOps", "level_2": "CI/CD", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Betrieb", "level_1": "Support", "level_2": "Kundensupport", "level_3": None, "description": None, "external_key": None, "is_active": True},
    ],
    "it_operations": [
        {"capability": "Infrastruktur", "level_1": "Server & Netzwerk", "level_2": "Netzwerk", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Infrastruktur", "level_1": "Cloud", "level_2": "AWS", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Sicherheit", "level_1": "Identity & Access", "level_2": "SSO", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Sicherheit", "level_1": "Compliance", "level_2": "Audit", "level_3": None, "description": None, "external_key": None, "is_active": True},
    ],
}


def get_demo_nodes(source_type: str = "demo") -> list[dict[str, Any]]:
    return build_nodes_from_rows(DEMO_ROWS, source_type=source_type)


def get_template_nodes(template_key: str) -> list[dict[str, Any]]:
    rows = TEMPLATE_ROWS.get(template_key, [])
    if not rows:
        raise ValueError(f"Unknown template: {template_key}. Available: {list(TEMPLATE_ROWS.keys())}")
    return build_nodes_from_rows(rows, source_type="template")


def list_templates() -> list[dict[str, str]]:
    return [
        {"key": "software_product", "label": "Software-Produkt"},
        {"key": "it_operations", "label": "IT-Betrieb"},
    ]
```

- [ ] **Step 5: Run the import service tests**

```bash
cd /opt/assist2/backend && pip install openpyxl==3.1.5 -q && python -m pytest tests/unit/test_capability_import_service.py -v
```
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
cd /opt/assist2/backend && git add app/services/capability_import_service.py tests/unit/test_capability_import_service.py requirements.txt
git commit -m "feat(capability): import service — Excel parsing, validation, demo/template seeds"
```

---

## Task 10: Capabilities router

**Files:**
- Create: `backend/app/routers/capabilities.py`

- [ ] **Step 1: Create the router**

```python
# backend/app/routers/capabilities.py
"""Capability map endpoints: CRUD, tree, import, org init status."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.organization import Organization
from app.models.capability_node import CapabilityNode
from app.schemas.capability import (
    CapabilityNodeCreate,
    CapabilityNodeRead,
    CapabilityNodeUpdate,
    ArtifactAssignmentCreate,
    ArtifactAssignmentRead,
    ImportValidationResult,
    OrgInitStatusRead,
    OrgInitAdvance,
)
from app.services import capability_service as svc
from app.services.capability_import_service import (
    parse_excel,
    get_demo_nodes,
    get_template_nodes,
    list_templates,
    validate_rows,
)
from app.models.artifact_assignment import ArtifactAssignment
from app.models.capability_node import ALLOWED_ASSIGNMENT_LEVELS, EXCEPTION_ALLOWED_LEVELS

router = APIRouter(prefix="/capabilities", tags=["Capabilities"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_org(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


# ── Org initialization status ─────────────────────────────────────────────────

@router.get("/orgs/{org_id}/init-status", response_model=OrgInitStatusRead)
async def get_init_status(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> OrgInitStatusRead:
    org = await _get_org(db, org_id)
    return OrgInitStatusRead.model_validate(org)


@router.patch("/orgs/{org_id}/init-status", response_model=OrgInitStatusRead)
async def advance_init_status(
    org_id: uuid.UUID,
    data: OrgInitAdvance,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrgInitStatusRead:
    org = await _get_org(db, org_id)
    updated = await svc.advance_org_init_status(db, org, data, current_user.id)
    return OrgInitStatusRead.model_validate(updated)


# ── Tree ──────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/tree")
async def get_tree(
    org_id: uuid.UUID,
    with_counts: bool = Query(False, description="Include aggregated story counts"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    if with_counts:
        return await svc.get_capability_tree_with_counts(db, org_id)
    return await svc.get_capability_tree(db, org_id)


# ── Nodes CRUD ────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/nodes", response_model=list[CapabilityNodeRead])
async def list_nodes(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[CapabilityNodeRead]:
    result = await db.execute(
        select(CapabilityNode).where(CapabilityNode.org_id == org_id)
        .order_by(CapabilityNode.node_type, CapabilityNode.sort_order)
    )
    return [CapabilityNodeRead.model_validate(n) for n in result.scalars().all()]


@router.post("/orgs/{org_id}/nodes", response_model=CapabilityNodeRead, status_code=201)
async def create_node(
    org_id: uuid.UUID,
    data: CapabilityNodeCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CapabilityNodeRead:
    node = await svc.create_node(db, org_id, data)
    return CapabilityNodeRead.model_validate(node)


@router.patch("/orgs/{org_id}/nodes/{node_id}", response_model=CapabilityNodeRead)
async def update_node(
    org_id: uuid.UUID,
    node_id: uuid.UUID,
    data: CapabilityNodeUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CapabilityNodeRead:
    node = await svc.get_node(db, org_id, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    updated = await svc.update_node(db, node, data)
    return CapabilityNodeRead.model_validate(updated)


@router.delete("/orgs/{org_id}/nodes/{node_id}", status_code=204)
async def delete_node(
    org_id: uuid.UUID,
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    node = await svc.get_node(db, org_id, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    await db.delete(node)
    await db.commit()


# ── Import ────────────────────────────────────────────────────────────────────

@router.post("/orgs/{org_id}/import/excel", response_model=ImportValidationResult)
async def import_excel(
    org_id: uuid.UUID,
    file: UploadFile = File(...),
    dry_run: bool = Query(True, description="Validate only; set false to persist"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportValidationResult:
    content = await file.read()
    result = parse_excel(content)
    if not dry_run and result.is_valid:
        await svc.delete_org_nodes(db, org_id)
        await svc.bulk_create_nodes(db, org_id, result.nodes)
        # Advance org status
        org = await _get_org(db, org_id)
        from app.schemas.capability import OrgInitAdvance
        await svc.advance_org_init_status(
            db, org, OrgInitAdvance(status="capability_setup_validated", source="excel"), current_user.id
        )
    return result


@router.get("/orgs/{org_id}/import/templates")
async def list_import_templates(_user: User = Depends(get_current_user)) -> list[dict]:
    return list_templates()


@router.post("/orgs/{org_id}/import/template/{template_key}", response_model=ImportValidationResult)
async def apply_template(
    org_id: uuid.UUID,
    template_key: str,
    dry_run: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportValidationResult:
    try:
        nodes = get_template_nodes(template_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    result = ImportValidationResult(
        is_valid=True, error_count=0, warning_count=0,
        capability_count=sum(1 for n in nodes if n["node_type"] == "capability"),
        level_1_count=sum(1 for n in nodes if n["node_type"] == "level_1"),
        level_2_count=sum(1 for n in nodes if n["node_type"] == "level_2"),
        level_3_count=sum(1 for n in nodes if n["node_type"] == "level_3"),
        issues=[],
        nodes=nodes,
    )
    if not dry_run:
        await svc.delete_org_nodes(db, org_id)
        await svc.bulk_create_nodes(db, org_id, result.nodes)
        org = await _get_org(db, org_id)
        from app.schemas.capability import OrgInitAdvance
        await svc.advance_org_init_status(
            db, org, OrgInitAdvance(status="capability_setup_validated", source="template"), current_user.id
        )
    return result


@router.post("/orgs/{org_id}/import/demo", response_model=ImportValidationResult)
async def apply_demo(
    org_id: uuid.UUID,
    dry_run: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportValidationResult:
    nodes = get_demo_nodes()
    result = ImportValidationResult(
        is_valid=True, error_count=0, warning_count=0,
        capability_count=sum(1 for n in nodes if n["node_type"] == "capability"),
        level_1_count=sum(1 for n in nodes if n["node_type"] == "level_1"),
        level_2_count=sum(1 for n in nodes if n["node_type"] == "level_2"),
        level_3_count=sum(1 for n in nodes if n["node_type"] == "level_3"),
        issues=[],
        nodes=nodes,
    )
    if not dry_run:
        await svc.delete_org_nodes(db, org_id)
        await svc.bulk_create_nodes(db, org_id, result.nodes)
        org = await _get_org(db, org_id)
        from app.schemas.capability import OrgInitAdvance
        await svc.advance_org_init_status(
            db, org, OrgInitAdvance(status="capability_setup_validated", source="demo"), current_user.id
        )
    return result


# ── Assignments ───────────────────────────────────────────────────────────────

def _validate_assignment_level(
    artifact_type: str,
    node_type: str,
    is_exception: bool,
    exception_reason: str | None,
) -> None:
    """Raise HTTPException if assignment level is invalid."""
    from app.models.capability_node import NodeType
    nt = NodeType(node_type)
    allowed = ALLOWED_ASSIGNMENT_LEVELS.get(artifact_type, [])
    exception_levels = EXCEPTION_ALLOWED_LEVELS.get(artifact_type, [])

    if nt in allowed:
        return  # Standard assignment
    if is_exception and nt in exception_levels:
        if not exception_reason:
            raise HTTPException(
                status_code=422,
                detail=f"assignment_exception_reason is required when assigning {artifact_type} to {node_type}",
            )
        return  # Exception assignment with reason
    raise HTTPException(
        status_code=422,
        detail=(
            f"Cannot assign {artifact_type} to {node_type}. "
            f"Allowed: {[n.value for n in allowed]}. "
            f"Exception levels (require reason): {[n.value for n in exception_levels]}."
        ),
    )


@router.post("/orgs/{org_id}/assignments", response_model=ArtifactAssignmentRead, status_code=201)
async def create_assignment(
    org_id: uuid.UUID,
    data: ArtifactAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArtifactAssignmentRead:
    # Validate the target node exists and belongs to the org
    node = await svc.get_node(db, org_id, data.node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Capability node not found in this org")

    # Enforce assignment level rules
    _validate_assignment_level(
        data.artifact_type,
        node.node_type,
        data.assignment_is_exception,
        data.assignment_exception_reason,
    )

    assignment = ArtifactAssignment(
        org_id=org_id,
        artifact_type=data.artifact_type,
        artifact_id=data.artifact_id,
        node_id=data.node_id,
        relation_type=data.relation_type,
        assignment_is_exception=data.assignment_is_exception,
        assignment_exception_reason=data.assignment_exception_reason,
        created_by_id=current_user.id,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return ArtifactAssignmentRead.model_validate(assignment)


@router.get("/orgs/{org_id}/assignments", response_model=list[ArtifactAssignmentRead])
async def list_assignments(
    org_id: uuid.UUID,
    artifact_type: str | None = Query(None),
    artifact_id: uuid.UUID | None = Query(None),
    node_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ArtifactAssignmentRead]:
    stmt = select(ArtifactAssignment).where(ArtifactAssignment.org_id == org_id)
    if artifact_type:
        stmt = stmt.where(ArtifactAssignment.artifact_type == artifact_type)
    if artifact_id:
        stmt = stmt.where(ArtifactAssignment.artifact_id == artifact_id)
    if node_id:
        stmt = stmt.where(ArtifactAssignment.node_id == node_id)
    result = await db.execute(stmt)
    return [ArtifactAssignmentRead.model_validate(a) for a in result.scalars().all()]


@router.delete("/orgs/{org_id}/assignments/{assignment_id}", status_code=204)
async def delete_assignment(
    org_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(ArtifactAssignment).where(
            ArtifactAssignment.org_id == org_id,
            ArtifactAssignment.id == assignment_id,
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await db.delete(obj)
    await db.commit()
```

- [ ] **Step 2: Commit**

```bash
cd /opt/assist2/backend && git add app/routers/capabilities.py
git commit -m "feat(capability): capabilities router — tree, CRUD, import, assignments, init status"
```

---

## Task 11: Register router and models in main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add import and include_router**

Open `backend/app/main.py`.

Add to the imports block (after the `rag_zones_router` import):

```python
from app.routers.capabilities import router as capabilities_router
```

Add after the last `app.include_router(...)` line:

```python
app.include_router(capabilities_router, prefix="/api/v1", tags=["Capabilities"])
```

- [ ] **Step 2: Verify the app starts**

```bash
cd /opt/assist2/backend && python -c "from app.main import app; print('routes:', len(app.routes))"
```
Expected: prints a number > 100 without errors.

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2/backend && git add app/main.py
git commit -m "feat(capability): register capabilities router in main.py"
```

---

## Task 12: Integration tests for capabilities API

**Files:**
- Create: `backend/tests/integration/test_capabilities_api.py`

- [ ] **Step 1: Write the tests**

```python
# backend/tests/integration/test_capabilities_api.py
"""Integration tests for capability map API endpoints."""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def base_url():
    return "http://test"


@pytest_asyncio.fixture
async def client(db):
    """Async HTTP client wired to in-memory DB."""
    from app.database import get_db
    from app.deps import get_current_user

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_client(client, db):
    """Client with a seeded org + member user injected via dependency override."""
    import uuid
    from app.deps import get_current_user
    from app.models.user import User
    from app.models.organization import Organization
    from app.models.membership import Membership, MembershipRole

    # Create org
    org = Organization(id=uuid.uuid4(), slug="test-org", name="Test Org", plan="free")
    user = User(
        id=uuid.uuid4(),
        email="admin@test.org",
        display_name="Admin",
        hashed_password="x",
        is_active=True,
    )
    db.add_all([org, user])
    await db.commit()

    membership = Membership(
        organization_id=org.id, user_id=user.id, role=MembershipRole.owner
    )
    db.add(membership)
    await db.commit()

    # Override auth
    async def override_user():
        return user

    from app.database import get_db
    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    return client, org, user


@pytest.mark.asyncio
async def test_get_init_status_default_is_not_initialized(auth_client):
    client, org, _ = auth_client
    resp = await client.get(f"/api/v1/capabilities/orgs/{org.id}/init-status")
    assert resp.status_code == 200
    assert resp.json()["initialization_status"] == "not_initialized"


@pytest.mark.asyncio
async def test_advance_init_status(auth_client):
    client, org, _ = auth_client
    resp = await client.patch(
        f"/api/v1/capabilities/orgs/{org.id}/init-status",
        json={"status": "capability_setup_in_progress"},
    )
    assert resp.status_code == 200
    assert resp.json()["initialization_status"] == "capability_setup_in_progress"


@pytest.mark.asyncio
async def test_get_empty_tree(auth_client):
    client, org, _ = auth_client
    resp = await client.get(f"/api/v1/capabilities/orgs/{org.id}/tree")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_apply_demo_dry_run(auth_client):
    client, org, _ = auth_client
    resp = await client.post(
        f"/api/v1/capabilities/orgs/{org.id}/import/demo?dry_run=true"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["capability_count"] >= 3
    # Dry run: no nodes persisted
    tree_resp = await client.get(f"/api/v1/capabilities/orgs/{org.id}/tree")
    assert tree_resp.json() == []


@pytest.mark.asyncio
async def test_apply_demo_persist(auth_client):
    client, org, _ = auth_client
    resp = await client.post(
        f"/api/v1/capabilities/orgs/{org.id}/import/demo?dry_run=false"
    )
    assert resp.status_code == 200
    assert resp.json()["is_valid"] is True
    tree_resp = await client.get(f"/api/v1/capabilities/orgs/{org.id}/tree")
    tree = tree_resp.json()
    assert len(tree) >= 3  # demo has 3 root capabilities


@pytest.mark.asyncio
async def test_assignment_level_validation_user_story_on_capability_rejected(auth_client, db):
    client, org, user = auth_client
    import uuid
    from app.models.capability_node import CapabilityNode
    # Create a root capability node
    node = CapabilityNode(
        org_id=org.id, node_type="capability", title="Cap A"
    )
    db.add(node)
    await db.commit()

    resp = await client.post(
        f"/api/v1/capabilities/orgs/{org.id}/assignments",
        json={
            "artifact_type": "user_story",
            "artifact_id": str(uuid.uuid4()),
            "node_id": str(node.id),
            "relation_type": "primary",
        },
    )
    assert resp.status_code == 422  # capability direct not allowed for user_story


@pytest.mark.asyncio
async def test_assignment_level_3_user_story_accepted(auth_client, db):
    client, org, _ = auth_client
    import uuid
    from app.models.capability_node import CapabilityNode

    cap = CapabilityNode(org_id=org.id, node_type="capability", title="Cap")
    l1 = CapabilityNode(org_id=org.id, node_type="level_1", title="L1")
    db.add_all([cap, l1])
    await db.flush()
    l1.parent_id = cap.id
    l2 = CapabilityNode(org_id=org.id, node_type="level_2", title="L2", parent_id=l1.id)
    l3 = CapabilityNode(org_id=org.id, node_type="level_3", title="L3", parent_id=l2.id)
    db.add_all([l2, l3])
    await db.commit()

    story_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/v1/capabilities/orgs/{org.id}/assignments",
        json={
            "artifact_type": "user_story",
            "artifact_id": story_id,
            "node_id": str(l3.id),
            "relation_type": "primary",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["artifact_type"] == "user_story"


@pytest.mark.asyncio
async def test_tree_with_story_counts(auth_client, db):
    client, org, _ = auth_client
    import uuid
    from app.models.capability_node import CapabilityNode
    from app.models.artifact_assignment import ArtifactAssignment

    cap = CapabilityNode(org_id=org.id, node_type="capability", title="Cap")
    l1 = CapabilityNode(org_id=org.id, node_type="level_1", title="L1")
    db.add_all([cap, l1])
    await db.flush()
    l1.parent_id = cap.id
    l2 = CapabilityNode(org_id=org.id, node_type="level_2", title="L2", parent_id=l1.id)
    l3 = CapabilityNode(org_id=org.id, node_type="level_3", title="L3")
    db.add_all([l2, l3])
    await db.flush()
    l3.parent_id = l2.id
    await db.commit()

    # Assign 2 stories to l3
    for _ in range(2):
        db.add(ArtifactAssignment(
            org_id=org.id, artifact_type="user_story",
            artifact_id=uuid.uuid4(), node_id=l3.id,
            relation_type="primary",
        ))
    await db.commit()

    resp = await client.get(f"/api/v1/capabilities/orgs/{org.id}/tree?with_counts=true")
    assert resp.status_code == 200
    tree = resp.json()
    cap_node = tree[0]
    assert cap_node["story_count"] == 2  # aggregated from l3 through l2 -> l1 -> cap
```

- [ ] **Step 2: Run the integration tests**

```bash
cd /opt/assist2/backend && python -m pytest tests/integration/test_capabilities_api.py -v
```
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2/backend && git add tests/integration/test_capabilities_api.py
git commit -m "test(capability): integration tests for capability API — tree, import, assignments, counts"
```

---

## Task 13: Build and run the backend in Docker

- [ ] **Step 1: Install openpyxl in Dockerfile context**

Verify `requirements.txt` has `openpyxl==3.1.5` (added in Task 9 Step 1).

- [ ] **Step 2: Rebuild and restart backend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
```

- [ ] **Step 3: Run the migration**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend alembic upgrade head
```
Expected: `Running upgrade 0017 -> 0018`

- [ ] **Step 4: Smoke-test the API**

```bash
# Check capabilities endpoints are registered
curl -s https://heykarl.app/api/v1/docs | grep -o 'capabilities' | head -3
# Or check from inside the container
docker compose -f docker-compose.yml exec backend python -c "from app.main import app; print([r.path for r in app.routes if 'capabilit' in str(r.path)])"
```
Expected: several `/api/v1/capabilities/...` routes printed

- [ ] **Step 5: Final commit**

```bash
cd /opt/assist2/backend && git add -A
git commit -m "feat(capability): sub-plan 1 complete — backend data foundation, API, tests"
```

---

## Self-Review Checklist

- [x] CapabilityNode model — `capability_nodes` table with self-referential parent
- [x] ArtifactAssignment model — polymorphic, no FK on artifact_id
- [x] Organization extended — 5 init-status fields
- [x] Project extended — project_brief, planned_start/end_date, 9 Jira fields
- [x] Migration 0018 — additive only, downgrade implemented
- [x] Pydantic schemas — create/read/update for nodes, assignments, import result, init status
- [x] Capability service — tree building, bottom-up count aggregation, CRUD, bulk insert, init status
- [x] Import service — Excel parsing (openpyxl), validate_rows, build_nodes_from_rows, demo data, 2 templates
- [x] Capabilities router — tree (plain + with counts), CRUD, import (excel/template/demo), assignments (with level validation), init status
- [x] models/__init__.py — new exports
- [x] main.py — router registered
- [x] Unit tests — tree building, count aggregation (no DB)
- [x] Unit tests — import validation (no DB)
- [x] Integration tests — full API coverage for tree, import, assignments, count aggregation

**Spec gaps addressed:**
- Jira reference fields on Project: ✅ (Sub-Plan 3 will add the actual Jira project listing endpoint inside the existing `/jira` router)
- Assignment level rules enforced server-side: ✅
- Demo/template seed data: ✅ (German labels, realistic structure)
- Org init state machine persisted: ✅
