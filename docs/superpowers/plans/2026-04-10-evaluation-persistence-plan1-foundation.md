# Evaluation Persistence v2 — Plan 1: Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add story versioning, configurable rule sets, scoring profiles, and new evaluation/review tables to the database with full CRUD APIs — the prerequisite layer for the async evaluation engine (Plan 2) and review loop (Plan 3).

**Architecture:** Additive Alembic migrations only. Existing tables get nullable FK columns where needed. New SQLAlchemy models follow the `Base + UUIDMixin + TimestampMixin` pattern from `app/models/base.py`. New services and routers follow patterns in `app/services/evaluation_service.py` and `app/routers/evaluations.py`. Tests use the existing SQLite in-memory conftest.

**Tech Stack:** PostgreSQL 16, SQLAlchemy 2.0 async, Alembic, FastAPI, Pydantic v2, pytest-asyncio, SQLite (test)

---

## File Map

```
backend/
  migrations/versions/
    0037_story_versions.py          ← new table + FK on user_stories
    0038_rule_sets.py               ← rule_sets + rule_definitions
    0039_scoring_profiles.py        ← scoring_profiles
    0040_evaluation_tables_v2.py    ← extend evaluation_runs + step_results + results
    0041_review_tables.py           ← review_tasks + review_decisions
    0042_audit_logs.py              ← audit_logs (partitioned)
  app/
    models/
      story_version.py              ← new: StoryVersion
      rule_set.py                   ← new: RuleSet
      rule_definition.py            ← new: RuleDefinition
      scoring_profile.py            ← new: ScoringProfile
      evaluation_step_result.py     ← new: EvaluationStepResult
      evaluation_result_v2.py       ← new: EvaluationResultV2
      review_task.py                ← new: ReviewTask
      review_decision.py            ← new: ReviewDecision
      audit_log.py                  ← new: AuditLog
      evaluation_run.py             ← modify: add thread_id, snapshots, new status values
      user_story.py                 ← modify: add current_version_id FK
      __init__.py                   ← modify: import all new models
    schemas/
      story_version.py              ← new Pydantic schemas
      rule_set.py                   ← new Pydantic schemas
      scoring_profile.py            ← new Pydantic schemas
    services/
      rule_set_service.py           ← new: CRUD + freeze + activate
      story_version_service.py      ← new: create_version, list, get
    routers/
      rule_sets.py                  ← new: /rule-sets endpoints
      scoring_profiles.py           ← new: /scoring-profiles endpoints
      story_versions.py             ← new: /stories/{id}/versions endpoints
    main.py                         ← modify: include 3 new routers
  tests/integration/
    test_rule_sets.py               ← new integration tests
    test_scoring_profiles.py        ← new integration tests
    test_story_versions.py          ← new integration tests
```

---

### Task 1: Migration 0037 — story_versions

**Files:**
- Create: `backend/migrations/versions/0037_story_versions.py`

- [ ] **Step 1: Write the migration file**

```python
# backend/migrations/versions/0037_story_versions.py
"""Add story_versions table and current_version_id to user_stories

Revision ID: 0037
Revises: 0036
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'story_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('story_id', UUID(as_uuid=True),
                  sa.ForeignKey('user_stories.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('org_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('as_a', sa.Text(), nullable=True),
        sa.Column('i_want', sa.Text(), nullable=True),
        sa.Column('so_that', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('acceptance_criteria', JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column('priority', sa.String(20), nullable=True),
        sa.Column('story_points', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='draft'),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('external_ref', sa.Text(), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('story_id', 'version_number', name='uq_story_versions_story_ver'),
    )
    op.create_index('idx_story_versions_story', 'story_versions', ['story_id'])
    op.create_index('idx_story_versions_hash', 'story_versions', ['story_id', 'content_hash'])
    op.create_index(
        'idx_story_versions_pending',
        'story_versions', ['status'],
        postgresql_where=sa.text("status IN ('pending_evaluation','evaluating')")
    )

    # Add current_version_id to user_stories (deferred FK to avoid circular dependency)
    op.add_column(
        'user_stories',
        sa.Column('current_version_id', UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_stories_current_version',
        'user_stories', 'story_versions',
        ['current_version_id'], ['id'],
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint('fk_stories_current_version', 'user_stories', type_='foreignkey')
    op.drop_column('user_stories', 'current_version_id')
    op.drop_index('idx_story_versions_pending', 'story_versions')
    op.drop_index('idx_story_versions_hash', 'story_versions')
    op.drop_index('idx_story_versions_story', 'story_versions')
    op.drop_table('story_versions')
```

- [ ] **Step 2: Run migration**

```bash
make migrate
```

Expected output: `Running upgrade 0036 -> 0037`

- [ ] **Step 3: Verify table exists**

```bash
make shell
# inside container:
python -c "
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal
async def check():
    async with AsyncSessionLocal() as db:
        r = await db.execute(text('SELECT column_name FROM information_schema.columns WHERE table_name=\'story_versions\' ORDER BY ordinal_position'))
        print([row[0] for row in r.fetchall()])
asyncio.run(check())
"
```

Expected: list of column names including `id`, `story_id`, `content_hash`, `version_number`

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/versions/0037_story_versions.py
git commit -m "feat(db): add story_versions table + current_version_id on user_stories"
```

---

### Task 2: Model — StoryVersion + update UserStory

**Files:**
- Create: `backend/app/models/story_version.py`
- Modify: `backend/app/models/user_story.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create story_version.py**

```python
# backend/app/models/story_version.py
from __future__ import annotations
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user_story import UserStory
    from app.models.user import User
    from app.models.organization import Organization


class StoryVersionStatus(str, enum.Enum):
    draft = "draft"
    pending_evaluation = "pending_evaluation"
    evaluating = "evaluating"
    evaluated = "evaluated"
    approved = "approved"
    rejected = "rejected"


class StoryVersion(Base):
    __tablename__ = "story_versions"
    __table_args__ = (
        UniqueConstraint("story_id", "version_number", name="uq_story_versions_story_ver"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_stories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    as_a: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    i_want: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    so_that: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON so it works in both SQLite (tests) and PostgreSQL (JSONB)
    acceptance_criteria: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    story_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    external_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    story: Mapped["UserStory"] = relationship(
        "UserStory", back_populates="versions", foreign_keys=[story_id]
    )
```

- [ ] **Step 2: Update user_story.py — add current_version_id and versions relationship**

Add these lines to `UserStory` in `backend/app/models/user_story.py`:

```python
# Add to imports at top:
# from app.models.story_version import StoryVersion  ← add to TYPE_CHECKING block

# Add to TYPE_CHECKING block:
if TYPE_CHECKING:
    from app.models.epic import Epic
    from app.models.feature import Feature
    from app.models.project import Project
    from app.models.story_process_change import StoryProcessChange
    from app.models.story_version import StoryVersion  # ← add this line

# Add to UserStory class body (after existing columns):
    current_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("story_versions.id", use_alter=True,
                   name="fk_stories_current_version"),
        nullable=True,
    )

    versions: Mapped[list["StoryVersion"]] = relationship(
        "StoryVersion",
        back_populates="story",
        foreign_keys="StoryVersion.story_id",
        order_by="StoryVersion.version_number",
        passive_deletes=True,
    )
```

- [ ] **Step 3: Update \_\_init\_\_.py**

Add to `backend/app/models/__init__.py` (after existing imports):

```python
from app.models.story_version import StoryVersion, StoryVersionStatus
```

Add to `__all__` list:
```python
"StoryVersion",
"StoryVersionStatus",
```

- [ ] **Step 4: Run tests to verify models load**

```bash
make test-unit
```

Expected: all existing tests pass (no new failures)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/story_version.py backend/app/models/user_story.py backend/app/models/__init__.py
git commit -m "feat(models): add StoryVersion model, update UserStory with current_version_id"
```

---

### Task 3: Migration 0038 — rule_sets + rule_definitions

**Files:**
- Create: `backend/migrations/versions/0038_rule_sets.py`

- [ ] **Step 1: Create migration file**

```python
# backend/migrations/versions/0038_rule_sets.py
"""Add rule_sets and rule_definitions tables

Revision ID: 0038
Revises: 0037
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0038'
down_revision = '0037'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'rule_sets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('frozen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('org_id', 'name', 'version', name='uq_rule_sets_org_name_ver'),
    )
    op.create_index('idx_rule_sets_org_status', 'rule_sets', ['org_id', 'status'])

    op.create_table(
        'rule_definitions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('rule_set_id', UUID(as_uuid=True),
                  sa.ForeignKey('rule_sets.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_type', sa.String(30), nullable=False),
        sa.Column('dimension', sa.String(50), nullable=False),
        sa.Column('weight', sa.Numeric(5, 4), nullable=False, server_default='1.0'),
        sa.Column('parameters', JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('prompt_template', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('rule_set_id', 'name', name='uq_rule_defs_ruleset_name'),
    )
    op.create_index('idx_rule_defs_active', 'rule_definitions', ['rule_set_id'],
                    postgresql_where=sa.text('is_active = true'))


def downgrade() -> None:
    op.drop_index('idx_rule_defs_active', 'rule_definitions')
    op.drop_table('rule_definitions')
    op.drop_index('idx_rule_sets_org_status', 'rule_sets')
    op.drop_table('rule_sets')
```

- [ ] **Step 2: Run migration**

```bash
make migrate
```

Expected: `Running upgrade 0037 -> 0038`

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/versions/0038_rule_sets.py
git commit -m "feat(db): add rule_sets and rule_definitions tables"
```

---

### Task 4: Models — RuleSet + RuleDefinition

**Files:**
- Create: `backend/app/models/rule_set.py`
- Create: `backend/app/models/rule_definition.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create rule_set.py**

```python
# backend/app/models/rule_set.py
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.rule_definition import RuleDefinition
    from app.models.scoring_profile import ScoringProfile


class RuleSet(UUIDMixin, Base):
    __tablename__ = "rule_sets"
    __table_args__ = (
        UniqueConstraint("org_id", "name", "version", name="uq_rule_sets_org_name_ver"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # status: draft | active | archived
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    frozen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    rules: Mapped[list["RuleDefinition"]] = relationship(
        "RuleDefinition", back_populates="rule_set",
        cascade="all, delete-orphan", order_by="RuleDefinition.order_index"
    )
    scoring_profiles: Mapped[list["ScoringProfile"]] = relationship(
        "ScoringProfile", back_populates="rule_set"
    )

    @property
    def is_frozen(self) -> bool:
        return self.frozen_at is not None

    def to_snapshot_dict(self) -> dict:
        """Frozen snapshot for evaluation_runs. Call before starting a run."""
        return {
            "rule_set_id": str(self.id),
            "name": self.name,
            "version": self.version,
            "frozen_at": self.frozen_at.isoformat() if self.frozen_at else None,
            "rules": [
                {
                    "rule_id": str(r.id),
                    "name": r.name,
                    "dimension": r.dimension,
                    "weight": float(r.weight),
                    "parameters": r.parameters or {},
                    "prompt_template": r.prompt_template,
                }
                for r in self.rules if r.is_active
            ],
        }
```

- [ ] **Step 2: Create rule_definition.py**

```python
# backend/app/models/rule_definition.py
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.rule_set import RuleSet


class RuleDefinition(Base):
    __tablename__ = "rule_definitions"
    __table_args__ = (
        UniqueConstraint("rule_set_id", "name", name="uq_rule_defs_ruleset_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # rule_type: quality | completeness | compliance | testability | custom
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)
    dimension: Mapped[str] = mapped_column(String(50), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=1.0)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    prompt_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    rule_set: Mapped["RuleSet"] = relationship("RuleSet", back_populates="rules")
```

- [ ] **Step 3: Update \_\_init\_\_.py**

```python
# Add to backend/app/models/__init__.py:
from app.models.rule_set import RuleSet
from app.models.rule_definition import RuleDefinition
```

Add `"RuleSet"`, `"RuleDefinition"` to `__all__`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/rule_set.py backend/app/models/rule_definition.py backend/app/models/__init__.py
git commit -m "feat(models): add RuleSet and RuleDefinition models"
```

---

### Task 5: Migration + Model — scoring_profiles

**Files:**
- Create: `backend/migrations/versions/0039_scoring_profiles.py`
- Create: `backend/app/models/scoring_profile.py`

- [ ] **Step 1: Create migration**

```python
# backend/migrations/versions/0039_scoring_profiles.py
"""Add scoring_profiles table

Revision ID: 0039
Revises: 0038
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0039'
down_revision = '0038'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'scoring_profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('rule_set_id', UUID(as_uuid=True),
                  sa.ForeignKey('rule_sets.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('dimension_weights', JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('pass_threshold', sa.Numeric(5, 4), nullable=False,
                  server_default='0.70'),
        sa.Column('warn_threshold', sa.Numeric(5, 4), nullable=False,
                  server_default='0.50'),
        sa.Column('auto_approve_threshold', sa.Numeric(5, 4), nullable=False,
                  server_default='0.90'),
        sa.Column('require_review_below', sa.Numeric(5, 4), nullable=False,
                  server_default='0.60'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('org_id', 'rule_set_id', 'name', 'version',
                            name='uq_scoring_profiles_unique'),
    )
    op.create_index('idx_scoring_profiles_ruleset', 'scoring_profiles', ['rule_set_id'])


def downgrade() -> None:
    op.drop_index('idx_scoring_profiles_ruleset', 'scoring_profiles')
    op.drop_table('scoring_profiles')
```

- [ ] **Step 2: Create scoring_profile.py model**

```python
# backend/app/models/scoring_profile.py
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.rule_set import RuleSet


class ScoringProfile(Base):
    __tablename__ = "scoring_profiles"
    __table_args__ = (
        UniqueConstraint("org_id", "rule_set_id", "name", "version",
                         name="uq_scoring_profiles_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    dimension_weights: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    pass_threshold: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.70)
    warn_threshold: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.50)
    auto_approve_threshold: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.90)
    require_review_below: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.60)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    rule_set: Mapped["RuleSet"] = relationship("RuleSet", back_populates="scoring_profiles")

    def to_snapshot_dict(self) -> dict:
        return {
            "profile_id": str(self.id),
            "dimension_weights": self.dimension_weights or {},
            "pass_threshold": float(self.pass_threshold),
            "warn_threshold": float(self.warn_threshold),
            "auto_approve_threshold": float(self.auto_approve_threshold),
            "require_review_below": float(self.require_review_below),
        }
```

- [ ] **Step 3: Update \_\_init\_\_.py**

```python
from app.models.scoring_profile import ScoringProfile
```

Add `"ScoringProfile"` to `__all__`.

- [ ] **Step 4: Run migrations**

```bash
make migrate
```

Expected: `Running upgrade 0038 -> 0039`

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0039_scoring_profiles.py backend/app/models/scoring_profile.py backend/app/models/__init__.py
git commit -m "feat(db+models): add scoring_profiles table and model"
```

---

### Task 6: Migration 0040 — extend evaluation_runs + new evaluation tables

**Files:**
- Create: `backend/migrations/versions/0040_evaluation_tables_v2.py`

- [ ] **Step 1: Create migration**

```python
# backend/migrations/versions/0040_evaluation_tables_v2.py
"""Extend evaluation_runs, add evaluation_step_results and evaluation_results_v2

Revision ID: 0040
Revises: 0039
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0040'
down_revision = '0039'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend existing evaluation_runs with new columns (all nullable for backward compat)
    op.add_column('evaluation_runs',
        sa.Column('story_version_id', UUID(as_uuid=True),
                  sa.ForeignKey('story_versions.id', ondelete='RESTRICT'), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('rule_set_id', UUID(as_uuid=True),
                  sa.ForeignKey('rule_sets.id', ondelete='RESTRICT'), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('rule_set_snapshot', JSONB(), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('scoring_profile_id', UUID(as_uuid=True),
                  sa.ForeignKey('scoring_profiles.id', ondelete='SET NULL'), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('scoring_profile_snapshot', JSONB(), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('langgraph_thread_id', sa.Text(), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('trigger_type', sa.String(20), nullable=False, server_default='manual'))
    op.add_column('evaluation_runs',
        sa.Column('parent_run_id', UUID(as_uuid=True),
                  sa.ForeignKey('evaluation_runs.id', ondelete='SET NULL'), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('evaluation_runs',
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('idx_eval_runs_thread', 'evaluation_runs', ['langgraph_thread_id'],
                    unique=True,
                    postgresql_where=sa.text('langgraph_thread_id IS NOT NULL'))
    op.create_index('idx_eval_runs_story_ver', 'evaluation_runs', ['story_version_id'])

    # Extend status enum to include paused and cancelled
    op.execute("ALTER TYPE evaluation_status ADD VALUE IF NOT EXISTS 'PAUSED'")
    op.execute("ALTER TYPE evaluation_status ADD VALUE IF NOT EXISTS 'CANCELLED'")

    # evaluation_step_results
    op.create_table(
        'evaluation_step_results',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('evaluation_run_id', UUID(as_uuid=True),
                  sa.ForeignKey('evaluation_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_name', sa.String(100), nullable=False),
        sa.Column('dimension', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('score', sa.Numeric(5, 4), nullable=True),
        sa.Column('findings', JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('input_snapshot', JSONB(), nullable=True),
        sa.Column('output_snapshot', JSONB(), nullable=True),
        sa.Column('llm_model', sa.String(100), nullable=True),
        sa.Column('token_usage', JSONB(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('evaluation_run_id', 'step_name',
                            name='uq_eval_step_run_step'),
    )
    op.create_index('idx_eval_step_results_run', 'evaluation_step_results', ['evaluation_run_id'])

    # evaluation_results_v2 (replaces result_json on run)
    op.create_table(
        'evaluation_results_v2',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('evaluation_run_id', UUID(as_uuid=True),
                  sa.ForeignKey('evaluation_runs.id', ondelete='CASCADE'),
                  nullable=False, unique=True),
        sa.Column('story_version_id', UUID(as_uuid=True),
                  sa.ForeignKey('story_versions.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('overall_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('overall_status', sa.String(10), nullable=True),
        sa.Column('dimension_scores', JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('findings', JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('rewrite_suggestions', JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column('is_final', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('human_overridden', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('override_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('override_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_eval_results_v2_story_ver', 'evaluation_results_v2',
                    ['story_version_id'],
                    postgresql_where=sa.text('is_final = true'))


def downgrade() -> None:
    op.drop_index('idx_eval_results_v2_story_ver', 'evaluation_results_v2')
    op.drop_table('evaluation_results_v2')
    op.drop_index('idx_eval_step_results_run', 'evaluation_step_results')
    op.drop_table('evaluation_step_results')
    op.drop_index('idx_eval_runs_story_ver', 'evaluation_runs')
    op.drop_index('idx_eval_runs_thread', 'evaluation_runs')
    for col in ['paused_at', 'started_at', 'retry_count', 'parent_run_id',
                'trigger_type', 'langgraph_thread_id', 'scoring_profile_snapshot',
                'scoring_profile_id', 'rule_set_snapshot', 'rule_set_id',
                'story_version_id']:
        op.drop_column('evaluation_runs', col)
    # Note: cannot remove enum values in PostgreSQL — leave paused/cancelled in enum
```

- [ ] **Step 2: Run migration**

```bash
make migrate
```

Expected: `Running upgrade 0039 -> 0040`

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/versions/0040_evaluation_tables_v2.py
git commit -m "feat(db): extend evaluation_runs + add step_results + results_v2 tables"
```

---

### Task 7: Models — EvaluationStepResult + EvaluationResultV2 + update EvaluationRun

**Files:**
- Create: `backend/app/models/evaluation_step_result.py`
- Create: `backend/app/models/evaluation_result_v2.py`
- Modify: `backend/app/models/evaluation_run.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create evaluation_step_result.py**

```python
# backend/app/models/evaluation_step_result.py
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.evaluation_run import EvaluationRun


class EvaluationStepResult(Base):
    __tablename__ = "evaluation_step_results"
    __table_args__ = (
        UniqueConstraint("evaluation_run_id", "step_name", name="uq_eval_step_run_step"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # status: pending | running | completed | failed | skipped
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    findings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    input_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    token_usage: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    run: Mapped["EvaluationRun"] = relationship("EvaluationRun", back_populates="step_results")
```

- [ ] **Step 2: Create evaluation_result_v2.py**

```python
# backend/app/models/evaluation_result_v2.py
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.evaluation_run import EvaluationRun


class EvaluationResultV2(Base):
    __tablename__ = "evaluation_results_v2"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    story_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), nullable=True
    )
    overall_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    # overall_status: pass | warn | fail | pending
    overall_status: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    dimension_scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    findings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rewrite_suggestions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped["EvaluationRun"] = relationship("EvaluationRun", back_populates="result_v2")
```

- [ ] **Step 3: Update evaluation_run.py — add new columns and relationships**

Add to `EvaluationRun` class in `backend/app/models/evaluation_run.py`:

```python
# Add to imports:
from typing import Optional, TYPE_CHECKING
# Add to TYPE_CHECKING block:
if TYPE_CHECKING:
    from app.models.evaluation_step_result import EvaluationStepResult
    from app.models.evaluation_result_v2 import EvaluationResultV2

# Add to EvaluationStatus enum:
class EvaluationStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"      # ← new
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"  # ← new

# Add to EvaluationRun class body (new columns):
    story_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    rule_set_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="RESTRICT"), nullable=True
    )
    rule_set_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    scoring_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("scoring_profiles.id", ondelete="SET NULL"), nullable=True
    )
    scoring_profile_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    langgraph_thread_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    parent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    step_results: Mapped[list["EvaluationStepResult"]] = relationship(
        "EvaluationStepResult", back_populates="run",
        cascade="all, delete-orphan", order_by="EvaluationStepResult.created_at"
    )
    result_v2: Mapped[Optional["EvaluationResultV2"]] = relationship(
        "EvaluationResultV2", back_populates="run", uselist=False,
        cascade="all, delete-orphan"
    )
```

- [ ] **Step 4: Update \_\_init\_\_.py**

```python
from app.models.evaluation_step_result import EvaluationStepResult
from app.models.evaluation_result_v2 import EvaluationResultV2
```

- [ ] **Step 5: Run tests**

```bash
make test-unit
```

Expected: all existing tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/evaluation_step_result.py backend/app/models/evaluation_result_v2.py backend/app/models/evaluation_run.py backend/app/models/__init__.py
git commit -m "feat(models): add EvaluationStepResult, EvaluationResultV2, extend EvaluationRun"
```

---

### Task 8: Migrations 0041 + 0042 — review tables + audit_logs

**Files:**
- Create: `backend/migrations/versions/0041_review_tables.py`
- Create: `backend/migrations/versions/0042_audit_logs.py`

- [ ] **Step 1: Create 0041 migration**

```python
# backend/migrations/versions/0041_review_tables.py
"""Add review_tasks and review_decisions tables

Revision ID: 0041
Revises: 0040
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0041'
down_revision = '0040'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'review_tasks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('evaluation_run_id', UUID(as_uuid=True),
                  sa.ForeignKey('evaluation_runs.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('story_version_id', UUID(as_uuid=True),
                  sa.ForeignKey('story_versions.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('review_type', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('assigned_to', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('requested_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('priority', sa.String(10), nullable=False, server_default='normal'),
        sa.Column('context_snapshot', JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('timeout_action', sa.String(20), nullable=False, server_default='escalate'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_review_tasks_run', 'review_tasks', ['evaluation_run_id'])
    op.create_index('idx_review_tasks_assigned', 'review_tasks', ['assigned_to', 'status'],
                    postgresql_where=sa.text(
                        "assigned_to IS NOT NULL AND status IN ('pending','in_review')"))
    op.create_index('idx_review_tasks_due', 'review_tasks', ['due_at'],
                    postgresql_where=sa.text("status IN ('pending','in_review')"))

    op.create_table(
        'review_decisions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('review_task_id', UUID(as_uuid=True),
                  sa.ForeignKey('review_tasks.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reviewer_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('decision', sa.String(30), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('score_override', sa.Numeric(5, 4), nullable=True),
        sa.Column('decision_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('resume_trigger_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('metadata_', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index('idx_review_decisions_task', 'review_decisions', ['review_task_id'])


def downgrade() -> None:
    op.drop_index('idx_review_decisions_task', 'review_decisions')
    op.drop_table('review_decisions')
    op.drop_index('idx_review_tasks_due', 'review_tasks')
    op.drop_index('idx_review_tasks_assigned', 'review_tasks')
    op.drop_index('idx_review_tasks_run', 'review_tasks')
    op.drop_table('review_tasks')
```

- [ ] **Step 2: Create 0042 migration**

```python
# backend/migrations/versions/0042_audit_logs.py
"""Add audit_logs table (partitioned by occurred_at)

Revision ID: 0042
Revises: 0041
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET

revision = '0042'
down_revision = '0041'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create partitioned parent table
    op.execute("""
        CREATE TABLE audit_logs (
            id          BIGSERIAL,
            org_id      UUID NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id   UUID NOT NULL,
            action      TEXT NOT NULL,
            actor_id    UUID,
            actor_type  TEXT NOT NULL DEFAULT 'user',
            old_value   JSONB,
            new_value   JSONB,
            diff        JSONB,
            ip_address  INET,
            session_id  TEXT,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata_   JSONB NOT NULL DEFAULT '{}',
            PRIMARY KEY (id, occurred_at)
        ) PARTITION BY RANGE (occurred_at)
    """)
    # Default partition catches everything until monthly partitions are added
    op.execute("""
        CREATE TABLE audit_logs_default
        PARTITION OF audit_logs DEFAULT
    """)
    op.execute("""
        CREATE INDEX idx_audit_entity
        ON audit_logs (entity_type, entity_id, occurred_at DESC)
    """)
    op.execute("""
        CREATE INDEX idx_audit_org_time
        ON audit_logs (org_id, occurred_at DESC)
    """)
    # Append-only policy: app_role can INSERT but not UPDATE/DELETE
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_role') THEN
                EXECUTE 'CREATE POLICY audit_append_only ON audit_logs
                    FOR INSERT TO app_role WITH CHECK (true)';
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
```

- [ ] **Step 3: Run both migrations**

```bash
make migrate
```

Expected: `Running upgrade 0040 -> 0041` then `Running upgrade 0041 -> 0042`

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/versions/0041_review_tables.py backend/migrations/versions/0042_audit_logs.py
git commit -m "feat(db): add review_tasks, review_decisions, audit_logs tables"
```

---

### Task 9: Models — ReviewTask + ReviewDecision + AuditLog

**Files:**
- Create: `backend/app/models/review_task.py`
- Create: `backend/app/models/review_decision.py`
- Create: `backend/app/models/audit_log.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create review_task.py**

```python
# backend/app/models/review_task.py
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.review_decision import ReviewDecision


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    story_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), nullable=True
    )
    # review_type: threshold_review | compliance_review | escalation | final_approval
    review_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # status: pending | in_review | approved | rejected | escalated | expired | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # priority: low | normal | high | critical
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    context_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # timeout_action: auto_approve | auto_reject | escalate
    timeout_action: Mapped[str] = mapped_column(String(20), nullable=False, default="escalate")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    decisions: Mapped[list["ReviewDecision"]] = relationship(
        "ReviewDecision", back_populates="task", cascade="all, delete-orphan"
    )
```

- [ ] **Step 2: Create review_decision.py**

```python
# backend/app/models/review_decision.py
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.review_task import ReviewTask


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    review_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("review_tasks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # decision: approved | rejected | requested_changes | escalated
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score_override: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    decision_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    resume_trigger_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    task: Mapped["ReviewTask"] = relationship("ReviewTask", back_populates="decisions")
```

- [ ] **Step 3: Create audit_log.py**

```python
# backend/app/models/audit_log.py
"""
AuditLog is append-only. Never UPDATE or DELETE rows — write via AuditService only.
The table is partitioned by occurred_at in PostgreSQL.
SQLite tests use it as a regular table (no partitioning).
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    # No UUIDMixin — partition key requires (id, occurred_at) composite PK in Postgres
    # For SQLite tests, id is sufficient
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    # actor_type: user | system | agent
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    old_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    diff: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        nullable=False, index=True
    )
    metadata_: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
```

- [ ] **Step 4: Update \_\_init\_\_.py**

```python
from app.models.review_task import ReviewTask
from app.models.review_decision import ReviewDecision
from app.models.audit_log import AuditLog
```

Add to `__all__`: `"ReviewTask"`, `"ReviewDecision"`, `"AuditLog"`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/review_task.py backend/app/models/review_decision.py backend/app/models/audit_log.py backend/app/models/__init__.py
git commit -m "feat(models): add ReviewTask, ReviewDecision, AuditLog models"
```

---

### Task 10: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/story_version.py`
- Create: `backend/app/schemas/rule_set.py`
- Create: `backend/app/schemas/scoring_profile.py`

- [ ] **Step 1: Create story_version.py schemas**

```python
# backend/app/schemas/story_version.py
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class StoryVersionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    as_a: Optional[str] = None
    i_want: Optional[str] = None
    so_that: Optional[str] = None
    acceptance_criteria: list[dict] = []
    priority: Optional[str] = None
    story_points: Optional[int] = None


class StoryVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    story_id: uuid.UUID
    version_number: int
    title: str
    description: Optional[str]
    as_a: Optional[str]
    i_want: Optional[str]
    so_that: Optional[str]
    acceptance_criteria: list
    priority: Optional[str]
    story_points: Optional[int]
    status: str
    content_hash: str
    created_by: Optional[uuid.UUID]
    created_at: datetime
```

- [ ] **Step 2: Create rule_set.py schemas**

```python
# backend/app/schemas/rule_set.py
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class RuleDefinitionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str
    dimension: str
    weight: float = 1.0
    parameters: dict = {}
    prompt_template: Optional[str] = None
    order_index: int = 0

    @field_validator("rule_type")
    @classmethod
    def validate_rule_type(cls, v: str) -> str:
        allowed = {"quality", "completeness", "compliance", "testability", "custom"}
        if v not in allowed:
            raise ValueError(f"rule_type must be one of {allowed}")
        return v

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("weight must be between 0.0 and 1.0")
        return v


class RuleDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_set_id: uuid.UUID
    name: str
    description: Optional[str]
    rule_type: str
    dimension: str
    weight: float
    parameters: dict
    prompt_template: Optional[str]
    is_active: bool
    order_index: int
    created_at: datetime
    updated_at: datetime


class RuleDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[float] = None
    parameters: Optional[dict] = None
    prompt_template: Optional[str] = None
    is_active: Optional[bool] = None
    order_index: Optional[int] = None


class RuleSetCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RuleSetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str]
    version: int
    status: str
    frozen_at: Optional[datetime]
    activated_at: Optional[datetime]
    archived_at: Optional[datetime]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    rules: list[RuleDefinitionRead] = []


class RuleSetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
```

- [ ] **Step 3: Create scoring_profile.py schemas**

```python
# backend/app/schemas/scoring_profile.py
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, model_validator


class ScoringProfileCreate(BaseModel):
    rule_set_id: uuid.UUID
    name: str
    dimension_weights: dict[str, float] = {}
    pass_threshold: float = 0.70
    warn_threshold: float = 0.50
    auto_approve_threshold: float = 0.90
    require_review_below: float = 0.60
    is_default: bool = False

    @model_validator(mode="after")
    def validate_thresholds(self) -> "ScoringProfileCreate":
        if not (self.warn_threshold < self.pass_threshold < self.auto_approve_threshold):
            raise ValueError(
                "Thresholds must satisfy: warn < pass < auto_approve"
            )
        return self


class ScoringProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    rule_set_id: uuid.UUID
    name: str
    version: int
    dimension_weights: dict
    pass_threshold: float
    warn_threshold: float
    auto_approve_threshold: float
    require_review_below: float
    is_default: bool
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class ScoringProfileUpdate(BaseModel):
    name: Optional[str] = None
    dimension_weights: Optional[dict[str, float]] = None
    pass_threshold: Optional[float] = None
    warn_threshold: Optional[float] = None
    auto_approve_threshold: Optional[float] = None
    require_review_below: Optional[float] = None
    is_default: Optional[bool] = None
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/story_version.py backend/app/schemas/rule_set.py backend/app/schemas/scoring_profile.py
git commit -m "feat(schemas): add Pydantic schemas for story_version, rule_set, scoring_profile"
```

---

### Task 11: RuleSetService

**Files:**
- Create: `backend/app/services/rule_set_service.py`
- Create: `backend/tests/integration/test_rule_sets.py`

- [ ] **Step 1: Write the failing tests first**

```python
# backend/tests/integration/test_rule_sets.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User
from app.deps import get_current_user


@pytest.fixture
def admin_headers(test_user: User):
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_create_rule_set(client: AsyncClient, admin_headers: dict, test_org):
    r = await client.post(
        f"/api/v1/rule-sets",
        json={"name": "Default Rules", "description": "Base rule set"},
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Default Rules"
    assert data["status"] == "draft"
    assert data["version"] == 1
    assert data["frozen_at"] is None


@pytest.mark.asyncio
async def test_create_rule_set_duplicate_name_rejected(
    client: AsyncClient, admin_headers: dict, test_org
):
    payload = {"name": "Unique Rules"}
    params = {"org_id": str(test_org.id)}
    await client.post("/api/v1/rule-sets", json=payload, params=params, headers=admin_headers)
    r = await client.post("/api/v1/rule-sets", json=payload, params=params, headers=admin_headers)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_add_rule_to_rule_set(client: AsyncClient, admin_headers: dict, test_org):
    create_r = await client.post(
        "/api/v1/rule-sets",
        json={"name": "Rules With Defs"},
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )
    rs_id = create_r.json()["id"]

    r = await client.post(
        f"/api/v1/rule-sets/{rs_id}/rules",
        json={
            "name": "min_criteria",
            "rule_type": "completeness",
            "dimension": "completeness",
            "weight": 0.8,
            "parameters": {"min_criteria": 3},
            "prompt_template": "Check that the story has at least {{min_criteria}} criteria.",
        },
        headers=admin_headers,
    )
    assert r.status_code == 201
    assert r.json()["dimension"] == "completeness"


@pytest.mark.asyncio
async def test_activate_rule_set_freezes_it(client: AsyncClient, admin_headers: dict, test_org):
    create_r = await client.post(
        "/api/v1/rule-sets",
        json={"name": "Rules To Activate"},
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )
    rs_id = create_r.json()["id"]

    r = await client.post(f"/api/v1/rule-sets/{rs_id}/activate", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "active"
    assert data["frozen_at"] is not None


@pytest.mark.asyncio
async def test_cannot_add_rule_to_frozen_rule_set(
    client: AsyncClient, admin_headers: dict, test_org
):
    create_r = await client.post(
        "/api/v1/rule-sets",
        json={"name": "Frozen Rules"},
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )
    rs_id = create_r.json()["id"]
    await client.post(f"/api/v1/rule-sets/{rs_id}/activate", headers=admin_headers)

    r = await client.post(
        f"/api/v1/rule-sets/{rs_id}/rules",
        json={"name": "new rule", "rule_type": "quality", "dimension": "clarity", "weight": 0.5},
        headers=admin_headers,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_list_rule_sets_for_org(client: AsyncClient, admin_headers: dict, test_org):
    for name in ["RS A", "RS B"]:
        await client.post(
            "/api/v1/rule-sets",
            json={"name": name},
            params={"org_id": str(test_org.id)},
            headers=admin_headers,
        )
    r = await client.get(
        "/api/v1/rule-sets", params={"org_id": str(test_org.id)}, headers=admin_headers
    )
    assert r.status_code == 200
    assert len(r.json()) >= 2
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /opt/assist2/infra && docker compose exec assist2-backend pytest tests/integration/test_rule_sets.py -v 2>&1 | tail -10
```

Expected: `ERROR` — router not found (404s)

- [ ] **Step 3: Create rule_set_service.py**

```python
# backend/app/services/rule_set_service.py
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rule_set import RuleSet
from app.models.rule_definition import RuleDefinition
from app.schemas.rule_set import RuleSetCreate, RuleSetUpdate, RuleDefinitionCreate, RuleDefinitionUpdate


async def create_rule_set(
    db: AsyncSession,
    org_id: uuid.UUID,
    data: RuleSetCreate,
    created_by: uuid.UUID,
) -> RuleSet:
    existing = await db.execute(
        select(RuleSet).where(
            RuleSet.org_id == org_id,
            RuleSet.name == data.name,
            RuleSet.status != "archived",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Rule set with this name already exists")

    rs = RuleSet(
        org_id=org_id,
        name=data.name,
        description=data.description,
        version=1,
        status="draft",
        created_by=created_by,
    )
    db.add(rs)
    await db.commit()
    await db.refresh(rs)
    return rs


async def get_rule_set(
    db: AsyncSession, rule_set_id: uuid.UUID, org_id: uuid.UUID
) -> RuleSet:
    result = await db.execute(
        select(RuleSet)
        .options(selectinload(RuleSet.rules))
        .where(RuleSet.id == rule_set_id, RuleSet.org_id == org_id)
    )
    rs = result.scalar_one_or_none()
    if rs is None:
        raise HTTPException(status_code=404, detail="Rule set not found")
    return rs


async def list_rule_sets(
    db: AsyncSession, org_id: uuid.UUID, status: Optional[str] = None
) -> list[RuleSet]:
    stmt = (
        select(RuleSet)
        .options(selectinload(RuleSet.rules))
        .where(RuleSet.org_id == org_id)
        .order_by(RuleSet.created_at.desc())
    )
    if status:
        stmt = stmt.where(RuleSet.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_rule_set(
    db: AsyncSession, rule_set_id: uuid.UUID, org_id: uuid.UUID, data: RuleSetUpdate
) -> RuleSet:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.is_frozen:
        raise HTTPException(status_code=409, detail="Rule set is frozen and cannot be modified")
    if data.name is not None:
        rs.name = data.name
    if data.description is not None:
        rs.description = data.description
    await db.commit()
    await db.refresh(rs)
    return rs


async def activate_rule_set(
    db: AsyncSession, rule_set_id: uuid.UUID, org_id: uuid.UUID
) -> RuleSet:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.status == "active":
        raise HTTPException(status_code=409, detail="Rule set is already active")
    if rs.status == "archived":
        raise HTTPException(status_code=409, detail="Cannot activate an archived rule set")
    now = datetime.now(timezone.utc)
    rs.status = "active"
    rs.frozen_at = now
    rs.activated_at = now
    await db.commit()
    await db.refresh(rs)
    return rs


async def archive_rule_set(
    db: AsyncSession, rule_set_id: uuid.UUID, org_id: uuid.UUID
) -> RuleSet:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.status == "archived":
        raise HTTPException(status_code=409, detail="Already archived")
    rs.status = "archived"
    rs.archived_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(rs)
    return rs


async def add_rule(
    db: AsyncSession, rule_set_id: uuid.UUID, org_id: uuid.UUID, data: RuleDefinitionCreate
) -> RuleDefinition:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.is_frozen:
        raise HTTPException(status_code=409, detail="Rule set is frozen — cannot add rules")
    rule = RuleDefinition(
        rule_set_id=rule_set_id,
        name=data.name,
        description=data.description,
        rule_type=data.rule_type,
        dimension=data.dimension,
        weight=data.weight,
        parameters=data.parameters,
        prompt_template=data.prompt_template,
        order_index=data.order_index,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def update_rule(
    db: AsyncSession,
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    org_id: uuid.UUID,
    data: RuleDefinitionUpdate,
) -> RuleDefinition:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.is_frozen:
        raise HTTPException(status_code=409, detail="Rule set is frozen — cannot modify rules")
    result = await db.execute(
        select(RuleDefinition).where(
            RuleDefinition.id == rule_id,
            RuleDefinition.rule_set_id == rule_set_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(
    db: AsyncSession, rule_set_id: uuid.UUID, rule_id: uuid.UUID, org_id: uuid.UUID
) -> None:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.is_frozen:
        raise HTTPException(status_code=409, detail="Rule set is frozen — cannot delete rules")
    result = await db.execute(
        select(RuleDefinition).where(
            RuleDefinition.id == rule_id,
            RuleDefinition.rule_set_id == rule_set_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
```

- [ ] **Step 4: Create rule_sets.py router**

```python
# backend/app/routers/rule_sets.py
from __future__ import annotations
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.rule_set import (
    RuleSetCreate, RuleSetRead, RuleSetUpdate,
    RuleDefinitionCreate, RuleDefinitionRead, RuleDefinitionUpdate,
)
from app.services import rule_set_service

router = APIRouter(prefix="/api/v1/rule-sets", tags=["rule-sets"])


@router.get("", response_model=list[RuleSetRead])
async def list_rule_sets(
    org_id: uuid.UUID = Query(...),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.list_rule_sets(db, org_id, status)


@router.post("", response_model=RuleSetRead, status_code=201)
async def create_rule_set(
    data: RuleSetCreate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.create_rule_set(db, org_id, data, current_user.id)


@router.get("/{rule_set_id}", response_model=RuleSetRead)
async def get_rule_set(
    rule_set_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.get_rule_set(db, rule_set_id, org_id)


@router.patch("/{rule_set_id}", response_model=RuleSetRead)
async def update_rule_set(
    rule_set_id: uuid.UUID,
    data: RuleSetUpdate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.update_rule_set(db, rule_set_id, org_id, data)


@router.post("/{rule_set_id}/activate", response_model=RuleSetRead)
async def activate_rule_set(
    rule_set_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.activate_rule_set(db, rule_set_id, org_id)


@router.post("/{rule_set_id}/archive", response_model=RuleSetRead)
async def archive_rule_set(
    rule_set_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.archive_rule_set(db, rule_set_id, org_id)


@router.post("/{rule_set_id}/rules", response_model=RuleDefinitionRead, status_code=201)
async def add_rule(
    rule_set_id: uuid.UUID,
    data: RuleDefinitionCreate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.add_rule(db, rule_set_id, org_id, data)


@router.patch("/{rule_set_id}/rules/{rule_id}", response_model=RuleDefinitionRead)
async def update_rule(
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: RuleDefinitionUpdate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.update_rule(db, rule_set_id, rule_id, org_id, data)


@router.delete("/{rule_set_id}/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await rule_set_service.delete_rule(db, rule_set_id, rule_id, org_id)
```

- [ ] **Step 5: Register router in main.py**

In `backend/app/main.py`, add:
```python
from app.routers.rule_sets import router as rule_sets_router
```

In the router registration block, add:
```python
app.include_router(rule_sets_router)
```

- [ ] **Step 6: Run tests**

```bash
cd /opt/assist2 && make shell
# inside container:
pytest tests/integration/test_rule_sets.py -v
```

Expected: all 6 tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/rule_set_service.py backend/app/routers/rule_sets.py backend/app/main.py backend/tests/integration/test_rule_sets.py
git commit -m "feat: add rule set management API with freeze/activate lifecycle"
```

---

### Task 12: ScoringProfile API + Story Versioning API

**Files:**
- Create: `backend/app/services/scoring_profile_service.py`
- Create: `backend/app/routers/scoring_profiles.py`
- Create: `backend/app/services/story_version_service.py`
- Create: `backend/app/routers/story_versions.py`
- Create: `backend/tests/integration/test_scoring_profiles.py`
- Create: `backend/tests/integration/test_story_versions.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests for scoring profiles**

```python
# backend/tests/integration/test_scoring_profiles.py
import pytest
import uuid
from httpx import AsyncClient
from app.main import app
from app.models.user import User
from app.deps import get_current_user


@pytest.fixture
def auth_headers_fixture(test_user: User):
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def test_rule_set(client: AsyncClient, auth_headers_fixture, test_org):
    r = await client.post(
        "/api/v1/rule-sets",
        json={"name": "Profile Test RS"},
        params={"org_id": str(test_org.id)},
        headers=auth_headers_fixture,
    )
    return r.json()


@pytest.mark.asyncio
async def test_create_scoring_profile(
    client: AsyncClient, auth_headers_fixture, test_org, test_rule_set
):
    r = await client.post(
        "/api/v1/scoring-profiles",
        json={
            "rule_set_id": test_rule_set["id"],
            "name": "Strict",
            "pass_threshold": 0.80,
            "warn_threshold": 0.60,
            "auto_approve_threshold": 0.95,
            "require_review_below": 0.70,
        },
        params={"org_id": str(test_org.id)},
        headers=auth_headers_fixture,
    )
    assert r.status_code == 201
    assert r.json()["name"] == "Strict"
    assert r.json()["pass_threshold"] == 0.80


@pytest.mark.asyncio
async def test_invalid_thresholds_rejected(
    client: AsyncClient, auth_headers_fixture, test_org, test_rule_set
):
    r = await client.post(
        "/api/v1/scoring-profiles",
        json={
            "rule_set_id": test_rule_set["id"],
            "name": "Invalid",
            "pass_threshold": 0.40,   # lower than warn_threshold
            "warn_threshold": 0.60,
            "auto_approve_threshold": 0.95,
            "require_review_below": 0.50,
        },
        params={"org_id": str(test_org.id)},
        headers=auth_headers_fixture,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_profiles_for_rule_set(
    client: AsyncClient, auth_headers_fixture, test_org, test_rule_set
):
    await client.post(
        "/api/v1/scoring-profiles",
        json={"rule_set_id": test_rule_set["id"], "name": "P1",
              "pass_threshold": 0.7, "warn_threshold": 0.5,
              "auto_approve_threshold": 0.9, "require_review_below": 0.6},
        params={"org_id": str(test_org.id)},
        headers=auth_headers_fixture,
    )
    r = await client.get(
        f"/api/v1/scoring-profiles",
        params={"org_id": str(test_org.id), "rule_set_id": test_rule_set["id"]},
        headers=auth_headers_fixture,
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1
```

- [ ] **Step 2: Create scoring_profile_service.py**

```python
# backend/app/services/scoring_profile_service.py
from __future__ import annotations
import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scoring_profile import ScoringProfile
from app.schemas.scoring_profile import ScoringProfileCreate, ScoringProfileUpdate


async def create_scoring_profile(
    db: AsyncSession,
    org_id: uuid.UUID,
    data: ScoringProfileCreate,
    created_by: uuid.UUID,
) -> ScoringProfile:
    profile = ScoringProfile(
        org_id=org_id,
        rule_set_id=data.rule_set_id,
        name=data.name,
        version=1,
        dimension_weights=data.dimension_weights,
        pass_threshold=data.pass_threshold,
        warn_threshold=data.warn_threshold,
        auto_approve_threshold=data.auto_approve_threshold,
        require_review_below=data.require_review_below,
        is_default=data.is_default,
        created_by=created_by,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def get_scoring_profile(
    db: AsyncSession, profile_id: uuid.UUID, org_id: uuid.UUID
) -> ScoringProfile:
    result = await db.execute(
        select(ScoringProfile).where(
            ScoringProfile.id == profile_id, ScoringProfile.org_id == org_id
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Scoring profile not found")
    return profile


async def list_scoring_profiles(
    db: AsyncSession, org_id: uuid.UUID, rule_set_id: Optional[uuid.UUID] = None
) -> list[ScoringProfile]:
    stmt = select(ScoringProfile).where(ScoringProfile.org_id == org_id)
    if rule_set_id:
        stmt = stmt.where(ScoringProfile.rule_set_id == rule_set_id)
    result = await db.execute(stmt.order_by(ScoringProfile.created_at.desc()))
    return list(result.scalars().all())


async def update_scoring_profile(
    db: AsyncSession, profile_id: uuid.UUID, org_id: uuid.UUID, data: ScoringProfileUpdate
) -> ScoringProfile:
    profile = await get_scoring_profile(db, profile_id, org_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile
```

- [ ] **Step 3: Create scoring_profiles.py router**

```python
# backend/app/routers/scoring_profiles.py
from __future__ import annotations
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.scoring_profile import ScoringProfileCreate, ScoringProfileRead, ScoringProfileUpdate
from app.services import scoring_profile_service

router = APIRouter(prefix="/api/v1/scoring-profiles", tags=["scoring-profiles"])


@router.get("", response_model=list[ScoringProfileRead])
async def list_profiles(
    org_id: uuid.UUID = Query(...),
    rule_set_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await scoring_profile_service.list_scoring_profiles(db, org_id, rule_set_id)


@router.post("", response_model=ScoringProfileRead, status_code=201)
async def create_profile(
    data: ScoringProfileCreate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await scoring_profile_service.create_scoring_profile(db, org_id, data, current_user.id)


@router.get("/{profile_id}", response_model=ScoringProfileRead)
async def get_profile(
    profile_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await scoring_profile_service.get_scoring_profile(db, profile_id, org_id)


@router.patch("/{profile_id}", response_model=ScoringProfileRead)
async def update_profile(
    profile_id: uuid.UUID,
    data: ScoringProfileUpdate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await scoring_profile_service.update_scoring_profile(db, profile_id, org_id, data)
```

- [ ] **Step 4: Write failing story version tests**

```python
# backend/tests/integration/test_story_versions.py
import pytest
from httpx import AsyncClient
from app.main import app
from app.models.user import User
from app.deps import get_current_user


@pytest.fixture
def auth_headers_v(test_user: User):
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def test_story(client: AsyncClient, auth_headers_v, test_org):
    r = await client.post(
        f"/api/v1/{test_org.slug}/stories",
        json={"title": "Versioned Story", "description": "as a user"},
        headers=auth_headers_v,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@pytest.mark.asyncio
async def test_create_version_returns_version_number(
    client: AsyncClient, auth_headers_v, test_org, test_story
):
    story_id = test_story["id"]
    r = await client.post(
        f"/api/v1/stories/{story_id}/versions",
        json={
            "title": "Versioned Story",
            "description": "As a user I want to login",
            "acceptance_criteria": [{"text": "Can log in with email"}],
        },
        headers=auth_headers_v,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["version_number"] == 1
    assert data["story_id"] == story_id


@pytest.mark.asyncio
async def test_duplicate_content_returns_409(
    client: AsyncClient, auth_headers_v, test_org, test_story
):
    story_id = test_story["id"]
    payload = {"title": "Same Content", "description": "same description"}
    r1 = await client.post(
        f"/api/v1/stories/{story_id}/versions", json=payload, headers=auth_headers_v
    )
    assert r1.status_code == 201

    r2 = await client.post(
        f"/api/v1/stories/{story_id}/versions", json=payload, headers=auth_headers_v
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_version_number_increments(
    client: AsyncClient, auth_headers_v, test_org, test_story
):
    story_id = test_story["id"]
    v1 = await client.post(
        f"/api/v1/stories/{story_id}/versions",
        json={"title": "V1", "description": "first"},
        headers=auth_headers_v,
    )
    v2 = await client.post(
        f"/api/v1/stories/{story_id}/versions",
        json={"title": "V2", "description": "second, different content"},
        headers=auth_headers_v,
    )
    assert v1.json()["version_number"] == 1
    assert v2.json()["version_number"] == 2


@pytest.mark.asyncio
async def test_list_versions_for_story(
    client: AsyncClient, auth_headers_v, test_org, test_story
):
    story_id = test_story["id"]
    for i in range(3):
        await client.post(
            f"/api/v1/stories/{story_id}/versions",
            json={"title": f"Version {i}", "description": f"desc {i}"},
            headers=auth_headers_v,
        )
    r = await client.get(f"/api/v1/stories/{story_id}/versions", headers=auth_headers_v)
    assert r.status_code == 200
    assert len(r.json()) >= 3
```

- [ ] **Step 5: Create story_version_service.py**

```python
# backend/app/services/story_version_service.py
from __future__ import annotations
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.story_version import StoryVersion
from app.models.user_story import UserStory
from app.schemas.story_version import StoryVersionCreate


def _compute_content_hash(data: StoryVersionCreate) -> str:
    """SHA-256 over deterministic JSON of story content."""
    content = {
        "title": data.title,
        "description": data.description or "",
        "as_a": data.as_a or "",
        "i_want": data.i_want or "",
        "so_that": data.so_that or "",
        "acceptance_criteria": sorted(
            json.dumps(c, sort_keys=True) for c in (data.acceptance_criteria or [])
        ),
    }
    serialized = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()


async def create_version(
    db: AsyncSession,
    story_id: uuid.UUID,
    org_id: uuid.UUID,
    data: StoryVersionCreate,
    created_by: uuid.UUID,
) -> StoryVersion:
    # Verify story exists and belongs to org
    story = await db.get(UserStory, story_id)
    if story is None or story.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Story not found")

    content_hash = _compute_content_hash(data)

    # Dedup: reject if identical content already has a version
    existing_hash = await db.execute(
        select(StoryVersion).where(
            StoryVersion.story_id == story_id,
            StoryVersion.content_hash == content_hash,
        )
    )
    if existing_hash.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Identical content already exists as a version")

    # Next version number
    max_ver_result = await db.execute(
        select(func.max(StoryVersion.version_number)).where(
            StoryVersion.story_id == story_id
        )
    )
    max_ver: int = max_ver_result.scalar() or 0

    version = StoryVersion(
        story_id=story_id,
        org_id=org_id,
        version_number=max_ver + 1,
        title=data.title,
        description=data.description,
        as_a=data.as_a,
        i_want=data.i_want,
        so_that=data.so_that,
        acceptance_criteria=data.acceptance_criteria or [],
        priority=data.priority,
        story_points=data.story_points,
        status="draft",
        content_hash=content_hash,
        created_by=created_by,
    )
    db.add(version)

    # Update story.current_version_id
    story.current_version_id = version.id
    story.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(version)
    return version


async def list_versions(
    db: AsyncSession, story_id: uuid.UUID, org_id: uuid.UUID
) -> list[StoryVersion]:
    story = await db.get(UserStory, story_id)
    if story is None or story.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Story not found")
    result = await db.execute(
        select(StoryVersion)
        .where(StoryVersion.story_id == story_id)
        .order_by(StoryVersion.version_number.asc())
    )
    return list(result.scalars().all())


async def get_version(
    db: AsyncSession, story_id: uuid.UUID, version_id: uuid.UUID, org_id: uuid.UUID
) -> StoryVersion:
    result = await db.execute(
        select(StoryVersion).where(
            StoryVersion.id == version_id,
            StoryVersion.story_id == story_id,
            StoryVersion.org_id == org_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Story version not found")
    return version
```

- [ ] **Step 6: Create story_versions.py router**

```python
# backend/app/routers/story_versions.py
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.story_version import StoryVersionCreate, StoryVersionRead
from app.services import story_version_service

router = APIRouter(prefix="/api/v1/stories", tags=["story-versions"])


@router.post("/{story_id}/versions", response_model=StoryVersionRead, status_code=201)
async def create_version(
    story_id: uuid.UUID,
    data: StoryVersionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # org_id resolved from story itself — no separate param needed
    from app.models.user_story import UserStory
    story = await db.get(UserStory, story_id)
    if story is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Story not found")
    return await story_version_service.create_version(
        db, story_id, story.organization_id, data, current_user.id
    )


@router.get("/{story_id}/versions", response_model=list[StoryVersionRead])
async def list_versions(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user_story import UserStory
    story = await db.get(UserStory, story_id)
    if story is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Story not found")
    return await story_version_service.list_versions(db, story_id, story.organization_id)


@router.get("/{story_id}/versions/{version_id}", response_model=StoryVersionRead)
async def get_version(
    story_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user_story import UserStory
    story = await db.get(UserStory, story_id)
    if story is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Story not found")
    return await story_version_service.get_version(
        db, story_id, version_id, story.organization_id
    )
```

- [ ] **Step 7: Register both new routers in main.py**

```python
# Add to imports in backend/app/main.py:
from app.routers.scoring_profiles import router as scoring_profiles_router
from app.routers.story_versions import router as story_versions_router

# Add to router registration block:
app.include_router(scoring_profiles_router)
app.include_router(story_versions_router)
```

- [ ] **Step 8: Run all new tests via Docker**

```bash
timeout 120 docker run --rm \
  --network assist2-internal \
  -e DATABASE_URL="postgresql+asyncpg://assist2:assist2dev@assist2-postgres:5432/assist2" \
  -e REDIS_URL="redis://:9yKbS1WMx8FzLKnzuy3AFFfvYoeHoiRgniGD0jvKVH0@assist2-redis:6379/0" \
  -e JWT_SECRET="521acf4ab73dd40a10bcd551c74613e6fc158c71084887d5b72976f4099461c03bd8916dc33a839457b0629dc33d0d042c54b97bb0c9777642e20a1195003483" \
  -e ENCRYPTION_KEY="_anFE99b1q2w1RpvM8Ulwe3qlwXKY5zTcJ0IvrOyon8=" \
  -e APP_BASE_URL="https://heykarl.app" \
  -e ENVIRONMENT="test" \
  -v /opt/assist2/backend:/app \
  $(docker build -q -f /opt/assist2/backend/Dockerfile.test /opt/assist2/backend) \
  pytest tests/integration/test_rule_sets.py tests/integration/test_scoring_profiles.py tests/integration/test_story_versions.py -v 2>&1 | tail -30
```

Expected: all tests pass

- [ ] **Step 9: Rebuild and restart backend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
```

- [ ] **Step 10: Final commit**

```bash
git add \
  backend/app/services/scoring_profile_service.py \
  backend/app/routers/scoring_profiles.py \
  backend/app/services/story_version_service.py \
  backend/app/routers/story_versions.py \
  backend/tests/integration/test_scoring_profiles.py \
  backend/tests/integration/test_story_versions.py \
  backend/app/main.py
git commit -m "feat: add scoring profile + story versioning APIs with full test coverage"
```

---

## Plan Complete

After all 12 tasks, the system has:

| What | Where |
|---|---|
| 6 new DB migrations (0037–0042) | `backend/migrations/versions/` |
| 9 new SQLAlchemy models | `backend/app/models/` |
| 3 new Pydantic schema files | `backend/app/schemas/` |
| 3 new service files | `backend/app/services/` |
| 3 new router files | `backend/app/routers/` |
| 3 integration test files | `backend/tests/integration/` |

**What is NOT in this plan (Plan 2):**
- LangGraph service upgrade to `AsyncPostgresSaver`
- `interrupt_after` / pause-resume logic
- Async evaluation dispatch via ARQ
- Evaluation endpoint that uses `rule_set_id` + `story_version_id`

**What is NOT in this plan (Plan 3):**
- Review task lifecycle management
- Graph resume after reviewer decision
- `AuditService` write helpers
- Timeout job for expired review tasks
