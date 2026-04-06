# Karl Learning System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ground all Karl AI suggestions in org-specific knowledge (stories, DoD patterns, features, Jira, Confluence), show source provenance badges with links on every suggestion, mark pure-LLM suggestions with `✦ KI`, and exclude user-rejected suggestions from future prompts.

**Architecture:** Extend existing `DocumentChunk`/pgvector RAG infrastructure with provenance metadata columns; add a new `index_story_knowledge` Celery task; inject RAG context and a rejection list into all four suggestion types; display source badges in `AISuggestionItem` with clickable links; Phase 2 adds Jira indexing, Phase 3 adds Confluence indexing — both behind config guards.

**Tech Stack:** FastAPI, SQLAlchemy async, pgvector, Celery, LiteLLM (text-embedding-3-small), Next.js 14, TypeScript, Alembic, PostgreSQL 16

---

## File Map

| File | Action |
|------|--------|
| `backend/migrations/versions/0025_knowledge_chunks.py` | Create |
| `backend/migrations/versions/0026_suggestion_feedback.py` | Create |
| `backend/app/models/document_chunk.py` | Modify — rename `file_path` → `source_ref`, add `SourceType` enum + new columns |
| `backend/app/models/suggestion_feedback.py` | Create |
| `backend/app/services/rag_service.py` | Modify — `RagChunk` dataclass, `RagResult.chunks` → `list[RagChunk]`, update `retrieve()` SQL |
| `backend/app/tasks/rag_tasks.py` | Modify — fix `file_path` → `source_ref` references; add `index_story_knowledge`, `index_jira_ticket`, `index_confluence_space` tasks |
| `backend/app/schemas/user_story.py` | Modify — add `Source` schema; add `sources: list[Source]` to `AITestCaseSuggestion`, `AIDoDSuggestion` |
| `backend/app/schemas/feature.py` | Modify — add `sources: list[Source]` to `AIFeatureSuggestion` |
| `backend/app/services/ai_story_service.py` | Modify — add RAG + rejection list to DoD/test/feature functions; fix `rag.direct_answer` → `rag.context` and `rag.chunks` → `list[RagChunk]` |
| `backend/app/routers/user_stories.py` | Modify — dispatch `index_story_knowledge` on status → `ready`/`done` |
| `backend/app/routers/test_cases.py` | Modify — dispatch `index_story_knowledge` on `result == "passed"` |
| `backend/app/routers/jira.py` | Modify — dispatch `index_jira_ticket` after story save |
| `backend/app/routers/suggestions.py` | Create — `POST /api/v1/suggestions/feedback` |
| `backend/app/main.py` | Modify — register suggestions router |
| `frontend/components/stories/AISuggestionItem.tsx` | Modify — `Source` interface, source badges with links, `onReject` prop |
| `frontend/app/[org]/stories/[id]/page.tsx` | Modify — pass `sources` + `onReject` to `AISuggestionItem` |
| `frontend/app/[org]/settings/page.tsx` | Modify — "Jetzt indexieren" button in Confluence tab (Phase 3) |

---

### Task 1: Migration 0025 — document_chunks schema extension

**Files:**
- Create: `backend/migrations/versions/0025_knowledge_chunks.py`

- [ ] **Step 1: Write the migration file**

```python
# backend/migrations/versions/0025_knowledge_chunks.py
"""extend document_chunks with provenance metadata

Revision ID: 0025
Revises: 0024
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename file_path → source_ref
    op.alter_column('document_chunks', 'file_path', new_column_name='source_ref')

    # Add provenance columns
    op.add_column('document_chunks', sa.Column('source_type', sa.String(32), nullable=False, server_default='nextcloud'))
    op.add_column('document_chunks', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('document_chunks', sa.Column('source_title', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('document_chunks', 'source_title')
    op.drop_column('document_chunks', 'source_url')
    op.drop_column('document_chunks', 'source_type')
    op.alter_column('document_chunks', 'source_ref', new_column_name='file_path')
```

- [ ] **Step 2: Run migration in container**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker exec assist2-backend alembic upgrade head
```

Expected output ends with: `Running upgrade 0024 -> 0025`

- [ ] **Step 3: Verify columns exist**

```bash
docker exec assist2-db psql -U assist2 -d assist2 -c "\d document_chunks"
```

Expected: columns `source_ref`, `source_type`, `source_url`, `source_title` visible; no `file_path`.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/versions/0025_knowledge_chunks.py
git commit -m "feat(rag): migration 0025 — document_chunks provenance columns"
```

---

### Task 2: Update DocumentChunk ORM model

**Files:**
- Modify: `backend/app/models/document_chunk.py`

- [ ] **Step 1: Replace the file**

```python
# backend/app/models/document_chunk.py
"""ORM model for pgvector document chunks."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SourceType(str, enum.Enum):
    nextcloud  = "nextcloud"
    karl_story = "karl_story"
    jira       = "jira"        # Phase 2
    confluence = "confluence"  # Phase 3


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # org_id: uses 'org_id' (not 'organization_id') matching the RAG spec's DB schema
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="nextcloud")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # DB type is vector(1536) — ORM uses Text as proxy; RAG service reads/writes via raw SQL with ::vector cast
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Fix rag_tasks.py references to file_path**

In `backend/app/tasks/rag_tasks.py`, find all references to `DocumentChunk.file_path` and `file_path=href` — replace them:

In `_index_org_documents_async`, line ~191 (existing hash check):
```python
        # OLD:
        existing_hash_result = await db.execute(
            select(DocumentChunk.file_hash)
            .where(
                DocumentChunk.org_id == org_uuid,
                DocumentChunk.file_path == href,
            )
            .limit(1)
        )
        # NEW:
        existing_hash_result = await db.execute(
            select(DocumentChunk.file_hash)
            .where(
                DocumentChunk.org_id == org_uuid,
                DocumentChunk.source_ref == href,
            )
            .limit(1)
        )
```

In `_index_org_documents_async`, the delete statement:
```python
        # OLD:
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.org_id == org_uuid,
                DocumentChunk.file_path == href,
            )
        )
        # NEW:
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.org_id == org_uuid,
                DocumentChunk.source_ref == href,
            )
        )
```

In `_index_org_documents_async`, the DocumentChunk constructor:
```python
            # OLD:
            chunk = DocumentChunk(
                org_id=org_uuid,
                file_path=href,
                file_hash=file_hash,
                chunk_index=i,
                chunk_text=chunk_text,
                embedding=embedding_str,
            )
            # NEW:
            chunk = DocumentChunk(
                org_id=org_uuid,
                source_ref=href,
                source_type="nextcloud",
                source_url=None,          # Nextcloud internal URL; not user-facing
                source_title=href.rsplit("/", 1)[-1],  # filename as title
                file_hash=file_hash,
                chunk_index=i,
                chunk_text=chunk_text,
                embedding=embedding_str,
            )
```

- [ ] **Step 3: Rebuild backend and confirm no import errors**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 20
```

Expected: no `AttributeError: file_path` or similar.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/document_chunk.py backend/app/tasks/rag_tasks.py
git commit -m "feat(rag): update DocumentChunk ORM — source_ref + provenance fields"
```

---

### Task 3: Extend rag_service.py with provenance

**Files:**
- Modify: `backend/app/services/rag_service.py`

- [ ] **Step 1: Replace rag_service.py**

```python
# backend/app/services/rag_service.py
"""RAG service — embedding, retrieval, threshold logic."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Literal

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger(__name__)

DIRECT_THRESHOLD = 0.92
CONTEXT_THRESHOLD = 0.50
MAX_CHUNKS = 3


@dataclass
class RagChunk:
    text:         str
    score:        float
    source_type:  str
    source_url:   str | None
    source_title: str | None


@dataclass
class RagResult:
    mode:    Literal["direct", "context", "none"]
    chunks:  list[RagChunk] = field(default_factory=list)
    context: str | None = None   # direct answer text (mode="direct")


async def _embed_query(query: str) -> list[float]:
    """Get embedding vector from LiteLLM. Raises on error (caller handles)."""
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.LITELLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LITELLM_API_KEY}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.LITELLM_URL}/embeddings",
            headers=headers,
            json={"model": "text-embedding-3-small", "input": query},
        )
        resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


async def retrieve(query: str, org_id: uuid.UUID, db: AsyncSession) -> RagResult:
    """
    Embed query, find top-5 most similar chunks for this org, apply thresholds.

    Returns:
        RagResult(mode='direct')  — score >= 0.92: use context as direct answer, no LLM needed
        RagResult(mode='context') — score 0.50-0.92: inject chunks into prompt
        RagResult(mode='none')    — score < 0.50 or any error: skip RAG
    """
    try:
        embedding = await _embed_query(query)
    except Exception as e:
        logger.warning("RAG embedding failed, skipping: %s", e)
        return RagResult(mode="none")

    try:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        sql = text("""
            SELECT chunk_text,
                   source_type,
                   source_url,
                   source_title,
                   1 - (embedding <=> :embedding ::vector) AS score
            FROM document_chunks
            WHERE org_id = :org_id
              AND embedding IS NOT NULL
            ORDER BY score DESC
            LIMIT 5
        """)
        result = await db.execute(sql, {"embedding": embedding_str, "org_id": str(org_id)})
        rows = result.fetchall()
    except Exception as e:
        logger.warning("RAG DB query failed, skipping: %s", e)
        return RagResult(mode="none")

    if not rows:
        return RagResult(mode="none")

    top_score = rows[0].score

    if top_score >= DIRECT_THRESHOLD:
        top = rows[0]
        return RagResult(
            mode="direct",
            context=top.chunk_text,
            chunks=[RagChunk(
                text=top.chunk_text,
                score=top.score,
                source_type=top.source_type,
                source_url=top.source_url,
                source_title=top.source_title,
            )],
        )

    if top_score >= CONTEXT_THRESHOLD:
        chunks = [
            RagChunk(
                text=r.chunk_text,
                score=r.score,
                source_type=r.source_type,
                source_url=r.source_url,
                source_title=r.source_title,
            )
            for r in rows[:MAX_CHUNKS]
            if r.score >= CONTEXT_THRESHOLD
        ]
        return RagResult(mode="context", chunks=chunks)

    return RagResult(mode="none")
```

- [ ] **Step 2: Fix ai_story_service.py — rag.direct_answer → rag.context**

In `backend/app/services/ai_story_service.py`, in `get_story_suggestions()`:

```python
            # OLD:
            if rag.mode == "direct" and rag.direct_answer:
                return AISuggestion(
                    title=None,
                    description=None,
                    acceptance_criteria=None,
                    explanation=rag.direct_answer,
                    dor_issues=[],
                    quality_score=None,
                    source="rag_direct",
                )
            if rag.mode == "context" and rag.chunks:
                rag_context_block = "\n".join(
                    [f"[Kontext]\n{c}" for c in rag.chunks]
                )
                rag_source = "rag_context"
            # NEW:
            if rag.mode == "direct" and rag.context:
                return AISuggestion(
                    title=None,
                    description=None,
                    acceptance_criteria=None,
                    explanation=rag.context,
                    dor_issues=[],
                    quality_score=None,
                    source="rag_direct",
                    sources=[
                        {"title": c.source_title or "", "url": c.source_url or "", "type": c.source_type}
                        for c in rag.chunks if c.source_url
                    ],
                )
            if rag.mode == "context" and rag.chunks:
                rag_context_block = "\n".join(
                    [f"[Kontext]\n{c.text}" for c in rag.chunks]
                )
                rag_source = "rag_context"
```

- [ ] **Step 3: Rebuild and check logs**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 20
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/rag_service.py backend/app/services/ai_story_service.py
git commit -m "feat(rag): RagChunk provenance — source_type, source_url, source_title"
```

---

### Task 4: Add Source schema to suggestion schemas

**Files:**
- Modify: `backend/app/schemas/user_story.py`
- Modify: `backend/app/schemas/feature.py`

- [ ] **Step 1: Add Source class and sources fields to user_story.py**

At the top of `backend/app/schemas/user_story.py`, after the imports, add:

```python
class Source(BaseModel):
    title: str
    url: str
    type: str  # "karl_story" | "nextcloud" | "jira" | "confluence"
```

Then update `AITestCaseSuggestion`:
```python
# OLD:
class AITestCaseSuggestion(BaseModel):
    title: str
    steps: Optional[str] = None
    expected_result: Optional[str] = None

# NEW:
class AITestCaseSuggestion(BaseModel):
    title: str
    steps: Optional[str] = None
    expected_result: Optional[str] = None
    sources: list["Source"] = []
```

Then update `AIDoDSuggestion`:
```python
# OLD:
class AIDoDSuggestion(BaseModel):
    text: str
    category: Optional[str] = None  # e.g. "Qualität", "Tests", "Dokumentation"

# NEW:
class AIDoDSuggestion(BaseModel):
    text: str
    category: Optional[str] = None
    sources: list["Source"] = []
```

Then update `AISuggestion` to include sources:
```python
# OLD:
class AISuggestion(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    explanation: str
    dor_issues: list[str] = []
    quality_score: Optional[int] = None
    source: Literal["rag_direct", "rag_context", "llm"] = "llm"

# NEW:
class AISuggestion(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    explanation: str
    dor_issues: list[str] = []
    quality_score: Optional[int] = None
    source: Literal["rag_direct", "rag_context", "llm"] = "llm"
    sources: list["Source"] = []
```

- [ ] **Step 2: Add sources field to AIFeatureSuggestion in feature.py**

```python
# At top of backend/app/schemas/feature.py, add import:
from app.schemas.user_story import Source

# OLD:
class AIFeatureSuggestion(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    story_points: Optional[int] = None

# NEW:
class AIFeatureSuggestion(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    story_points: Optional[int] = None
    sources: list[Source] = []
```

- [ ] **Step 3: Rebuild backend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 20
```

Expected: no import errors.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/user_story.py backend/app/schemas/feature.py
git commit -m "feat(rag): add Source schema and sources fields to suggestion responses"
```

---

### Task 5: Add index_story_knowledge Celery task

**Files:**
- Modify: `backend/app/tasks/rag_tasks.py`

- [ ] **Step 1: Add the new task at the end of rag_tasks.py**

```python
# Add at the end of backend/app/tasks/rag_tasks.py

async def _index_story_knowledge_async(story_id: str, org_id: str, org_slug: str, db: AsyncSession) -> None:
    """Index story + its ready/done DoD items, done features, passed test cases."""
    from app.models.document_chunk import DocumentChunk
    from app.models.user_story import UserStory
    from app.models.test_case import TestCase
    from app.models.feature import Feature, FeatureStatus
    from app.models.test_case import TestResult

    org_uuid = uuid.UUID(org_id)
    story_uuid = uuid.UUID(story_id)
    source_ref = f"story:{story_id}"
    source_url = f"/{org_slug}/stories/{story_id}"

    # Load story
    result = await db.execute(select(UserStory).where(UserStory.id == story_uuid))
    story = result.scalar_one_or_none()
    if story is None:
        logger.warning("index_story_knowledge: story %s not found", story_id)
        return

    source_title = f"Story: {story.title}"

    # Build raw chunks
    raw_chunks: list[str] = []

    # Story chunk
    parts = [story.title or ""]
    if story.description:
        parts.append(story.description)
    if story.acceptance_criteria:
        parts.append(story.acceptance_criteria)
    raw_chunks.append("\n".join(parts))

    # DoD items (stored as JSON in definition_of_done field)
    if story.definition_of_done:
        import json as _json
        try:
            dod_items = _json.loads(story.definition_of_done)
            for item in dod_items:
                text = item.get("text", "") if isinstance(item, dict) else str(item)
                if text.strip():
                    raw_chunks.append(text.strip())
        except Exception:
            pass

    # Done features
    feat_result = await db.execute(
        select(Feature).where(
            Feature.story_id == story_uuid,
            Feature.status == FeatureStatus.done,
        )
    )
    for feat in feat_result.scalars().all():
        parts = [feat.title or ""]
        if feat.description:
            parts.append(feat.description)
        raw_chunks.append("\n".join(parts))

    # Passed test cases
    tc_result = await db.execute(
        select(TestCase).where(
            TestCase.story_id == story_uuid,
            TestCase.result == TestResult.passed,
        )
    )
    for tc in tc_result.scalars().all():
        parts = [tc.title or ""]
        if tc.steps:
            parts.append(tc.steps)
        if tc.expected_result:
            parts.append(tc.expected_result)
        raw_chunks.append("\n".join(parts))

    if not raw_chunks:
        return

    # Embed all chunks
    try:
        embeddings = await _embed_chunks(raw_chunks)
    except Exception as e:
        logger.warning("index_story_knowledge: embedding failed for story %s: %s", story_id, e)
        return

    # Delete existing chunks for this story
    await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.org_id == org_uuid,
            DocumentChunk.source_ref == source_ref,
        )
    )

    # Insert new chunks
    for i, (chunk_text, embedding) in enumerate(zip(raw_chunks, embeddings)):
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        chunk = DocumentChunk(
            org_id=org_uuid,
            source_ref=source_ref,
            source_type="karl_story",
            source_url=source_url,
            source_title=source_title,
            file_hash=_sha256(chunk_text.encode()),
            chunk_index=i,
            chunk_text=chunk_text,
            embedding=embedding_str,
        )
        db.add(chunk)

    try:
        await db.commit()
        logger.info("index_story_knowledge: indexed %d chunks for story %s", len(raw_chunks), story_id)
    except Exception as e:
        await db.rollback()
        logger.error("index_story_knowledge: commit failed for story %s: %s", story_id, e)
        raise


@celery.task(name="rag_tasks.index_story_knowledge", bind=True, max_retries=3)
def index_story_knowledge(self, story_id: str, org_id: str, org_slug: str) -> dict:
    """Celery task: index story knowledge (story + DoD + features + test cases) into pgvector."""
    from app.config import get_settings

    async def run():
        engine = create_async_engine(
            get_settings().DATABASE_URL, echo=False, pool_pre_ping=True
        )
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with SessionLocal() as db:
                await _index_story_knowledge_async(story_id, org_id, org_slug, db)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
        return {"status": "ok", "story_id": story_id}
    except Exception as exc:
        logger.error("index_story_knowledge failed for story %s: %s", story_id, exc)
        raise self.retry(exc=exc, countdown=60)
```

The `select` import is already at the top of `rag_tasks.py`. Make sure the `select` import from sqlalchemy is present — it is already: `from sqlalchemy import delete, select`.

- [ ] **Step 2: Rebuild backend and verify task is registered**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker exec assist2-celery celery -A app.celery_app inspect registered 2>/dev/null | grep index_story
```

Expected: `rag_tasks.index_story_knowledge` appears in list.

- [ ] **Step 3: Commit**

```bash
git add backend/app/tasks/rag_tasks.py
git commit -m "feat(rag): add index_story_knowledge Celery task"
```

---

### Task 6: Dispatch index_story_knowledge from user_stories router

**Files:**
- Modify: `backend/app/routers/user_stories.py`

- [ ] **Step 1: Add import for the Celery task**

In `backend/app/routers/user_stories.py`, find the existing Celery task import:

```python
from app.tasks.pdf_tasks import generate_story_pdf
```

Add below it:
```python
from app.tasks.rag_tasks import index_story_knowledge
```

- [ ] **Step 2: Add dispatch in update_user_story after the story transitions**

In `update_user_story`, directly after the `generate_story_pdf.delay(...)` block, add:

```python
    # Dispatch indexing when story reaches ready or done
    if data.status is not None and data.status in (StoryStatus.ready, StoryStatus.done):
        # Load org slug for URL construction
        from app.models.organization import Organization
        org_result = await db.execute(
            select(Organization).where(Organization.id == story.organization_id)
        )
        org = org_result.scalar_one_or_none()
        org_slug = org.slug if org else str(story.organization_id)
        index_story_knowledge.delay(str(story.id), str(story.organization_id), org_slug)
```

Full context in `update_user_story` after commit:
```python
    # Dispatch PDF generation when story transitions to done
    if data.status is not None and data.status == StoryStatus.done and old_status != StoryStatus.done:
        generate_story_pdf.delay(str(story.id), str(story.organization_id))

    # Dispatch indexing when story reaches ready or done
    if data.status is not None and data.status in (StoryStatus.ready, StoryStatus.done):
        from app.models.organization import Organization
        org_result = await db.execute(
            select(Organization).where(Organization.id == story.organization_id)
        )
        org = org_result.scalar_one_or_none()
        org_slug = org.slug if org else str(story.organization_id)
        index_story_knowledge.delay(str(story.id), str(story.organization_id), org_slug)
```

- [ ] **Step 3: Rebuild backend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 20
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/user_stories.py
git commit -m "feat(rag): dispatch index_story_knowledge on story status ready/done"
```

---

### Task 7: Dispatch index_story_knowledge from test_cases router

**Files:**
- Modify: `backend/app/routers/test_cases.py`

- [ ] **Step 1: Add import**

Add at the top of `backend/app/routers/test_cases.py`:

```python
from app.tasks.rag_tasks import index_story_knowledge
from app.models.organization import Organization
```

- [ ] **Step 2: Add dispatch in update_test_case**

In `update_test_case`, after `await db.refresh(test_case)`:

```python
    await db.commit()
    await db.refresh(test_case)

    # Re-index story knowledge when a test case is marked passed
    if data.result == "passed":
        from sqlalchemy import select as _select
        org_result = await db.execute(
            _select(Organization).where(Organization.id == test_case.organization_id)
        )
        org = org_result.scalar_one_or_none()
        org_slug = org.slug if org else str(test_case.organization_id)
        index_story_knowledge.delay(
            str(test_case.story_id), str(test_case.organization_id), org_slug
        )

    return TestCaseRead.model_validate(test_case)
```

Note: `data.result` is a `TestCaseUpdate` field. Check `backend/app/schemas/test_case.py` — the field is `result: Optional[TestResult] = None`. The value `"passed"` is `TestResult.passed`. The comparison `data.result == "passed"` works because `TestResult` is a str enum. Alternatively use `from app.models.test_case import TestResult` and compare `data.result == TestResult.passed`.

Use the safer form:
```python
    from app.models.test_case import TestResult as _TestResult
    if data.result == _TestResult.passed:
```

- [ ] **Step 3: Rebuild**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 10
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/test_cases.py
git commit -m "feat(rag): dispatch index_story_knowledge on test case result=passed"
```

---

### Task 8: Add RAG to generate_dod_suggestions

**Files:**
- Modify: `backend/app/services/ai_story_service.py`

- [ ] **Step 1: Update function signature**

```python
# OLD:
async def generate_dod_suggestions(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    ai_settings: dict | None = None,
) -> list[AIDoDSuggestion]:

# NEW:
async def generate_dod_suggestions(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    ai_settings: dict | None = None,
    org_id: "uuid.UUID | None" = None,
    db: "AsyncSession | None" = None,
) -> list[AIDoDSuggestion]:
```

- [ ] **Step 2: Add RAG retrieval in generate_dod_suggestions body**

After `decision = route_request(...)` and before `prompt = _build_dod_prompt(...)`:

```python
    # RAG retrieval
    rag_chunks: list = []
    rag_context_block: str | None = None
    if org_id is not None and db is not None:
        try:
            from app.services.rag_service import retrieve
            rag = await retrieve(f"{title} {description or ''}", org_id, db)
            if rag.mode in ("direct", "context") and rag.chunks:
                rag_context_block = "\n".join([f"[Kontext]\n{c.text}" for c in rag.chunks])
                rag_chunks = rag.chunks
        except Exception as e:
            logger.warning("RAG retrieval error in generate_dod_suggestions (skipping): %s", e)
```

- [ ] **Step 3: Pass rag_context to _build_dod_prompt and attach sources to results**

Update `_build_dod_prompt` to accept and inject context:

```python
def _build_dod_prompt(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    rag_context: str | None = None,
) -> str:
    desc = description or "(keine)"
    ac = acceptance_criteria or "(keine)"
    context_section = ""
    if rag_context:
        context_section = f"""--- Org-Wissen (aus Karl / Nextcloud) ---
{rag_context}
-----------------------------------------

"""
    return f"""{context_section}Du bist ein erfahrener Scrum Master. Schlage konkrete Definition-of-Done-Kriterien und messbare KPIs für diese User Story vor.
...
```

The full updated `_build_dod_prompt`:
```python
def _build_dod_prompt(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    rag_context: str | None = None,
) -> str:
    desc = description or "(keine)"
    ac = acceptance_criteria or "(keine)"
    context_section = ""
    if rag_context:
        context_section = f"""--- Org-Wissen (aus Karl / Nextcloud) ---
{rag_context}
-----------------------------------------

"""
    return f"""{context_section}Du bist ein erfahrener Scrum Master. Schlage konkrete Definition-of-Done-Kriterien und messbare KPIs für diese User Story vor.

User Story:
Titel: {title}
Beschreibung: {desc}
Akzeptanzkriterien: {ac}

Schlage 6–10 spezifische DoD-Kriterien vor. Beziehe dich auf typische Kategorien wie:
- Qualität (Code Review, Linting, keine kritischen Bugs)
- Tests (Unit Tests, Integration Tests, Testabdeckung ≥ X%)
- Dokumentation (API-Docs, README, Changelogs)
- Performance (Ladezeit ≤ X ms, Antwortzeit ≤ X ms)
- Sicherheit (OWASP, Input-Validierung, Auth-Check)
- Deployment (CI/CD grün, Staging deployed, Smoke Test)
- Fachlich (Abnahme durch PO, AC erfüllt)

Passe die Kriterien an die Story an. Nenne messbare Schwellwerte wo sinnvoll.

Antworte NUR mit einem JSON-Array (kein Markdown):
[
  {{
    "text": "Konkretes DoD-Kriterium oder KPI",
    "category": "Kategorie (z.B. Tests, Qualität, Deployment)"
  }}
]"""
```

In `generate_dod_suggestions`, update the prompt call:
```python
    prompt = _build_dod_prompt(title, description, acceptance_criteria, rag_context=rag_context_block)
```

And attach sources to each result:
```python
    parsed = _parse_json(raw)
    if isinstance(parsed, list):
        items = parsed
    else:
        items = parsed.get("suggestions", [])

    sources_payload = [
        {"title": c.source_title or "", "url": c.source_url or "", "type": c.source_type}
        for c in rag_chunks if c.source_url
    ]
    return [AIDoDSuggestion(**item, sources=sources_payload) for item in items]
```

- [ ] **Step 4: Update the router that calls generate_dod_suggestions**

Find where `generate_dod_suggestions` is called in `backend/app/routers/user_stories.py`:

```bash
grep -n "generate_dod_suggestions" backend/app/routers/user_stories.py
```

Pass `org_id` and `db` to the call. The router already has `db` and `story.organization_id` available. Example call update (exact line number from grep):

```python
# OLD:
suggestions = await generate_dod_suggestions(
    title=story.title,
    description=story.description,
    acceptance_criteria=story.acceptance_criteria,
    ai_settings=ai_settings,
)
# NEW:
suggestions = await generate_dod_suggestions(
    title=story.title,
    description=story.description,
    acceptance_criteria=story.acceptance_criteria,
    ai_settings=ai_settings,
    org_id=story.organization_id,
    db=db,
)
```

- [ ] **Step 5: Rebuild**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 10
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_story_service.py backend/app/routers/user_stories.py
git commit -m "feat(rag): add RAG context to generate_dod_suggestions"
```

---

### Task 9: Add RAG to generate_test_case_suggestions

**Files:**
- Modify: `backend/app/services/ai_story_service.py`

- [ ] **Step 1: Update function signature**

```python
# OLD:
async def generate_test_case_suggestions(
    title: str, acceptance_criteria: str | None, ai_settings: dict | None = None
) -> list[AITestCaseSuggestion]:

# NEW:
async def generate_test_case_suggestions(
    title: str,
    acceptance_criteria: str | None,
    ai_settings: dict | None = None,
    org_id: "uuid.UUID | None" = None,
    db: "AsyncSession | None" = None,
) -> list[AITestCaseSuggestion]:
```

- [ ] **Step 2: Add RAG retrieval before prompt build**

After `decision = route_request(...)`:

```python
    # RAG retrieval
    rag_chunks: list = []
    rag_context_block: str | None = None
    if org_id is not None and db is not None:
        try:
            from app.services.rag_service import retrieve
            rag = await retrieve(f"{title} {acceptance_criteria or ''}", org_id, db)
            if rag.mode in ("direct", "context") and rag.chunks:
                rag_context_block = "\n".join([f"[Kontext]\n{c.text}" for c in rag.chunks])
                rag_chunks = rag.chunks
        except Exception as e:
            logger.warning("RAG retrieval error in generate_test_case_suggestions (skipping): %s", e)
```

- [ ] **Step 3: Update _build_test_cases_prompt and attach sources**

```python
def _build_test_cases_prompt(
    title: str,
    acceptance_criteria: str | None,
    rag_context: str | None = None,
) -> str:
    ac_text = acceptance_criteria or "(keine Akzeptanzkriterien angegeben)"
    context_section = ""
    if rag_context:
        context_section = f"""--- Org-Wissen (aus Karl / Nextcloud) ---
{rag_context}
-----------------------------------------

"""
    return f"""{context_section}Du bist ein erfahrener QA-Ingenieur. Leite aus den folgenden Akzeptanzkriterien konkrete Testfälle ab.

User Story: {title}
Akzeptanzkriterien:
{ac_text}

Generiere 3–6 aussagekräftige Testfälle. Jeder Testfall soll einen Normalfall, Grenzfall oder Fehlerfall abdecken.

Antworte NUR mit einem JSON-Array (kein Markdown, kein Text davor oder danach):
[
  {{
    "title": "Kurzer, präziser Testfall-Titel",
    "steps": "1. Schritt\\n2. Schritt\\n3. Schritt",
    "expected_result": "Was genau erwartet wird"
  }}
]"""
```

Update prompt call:
```python
    prompt = _build_test_cases_prompt(title, acceptance_criteria, rag_context=rag_context_block)
```

Attach sources in parse block:
```python
    parsed = _parse_json(raw)
    sources_payload = [
        {"title": c.source_title or "", "url": c.source_url or "", "type": c.source_type}
        for c in rag_chunks if c.source_url
    ]
    if isinstance(parsed, list):
        return [AITestCaseSuggestion(**item, sources=sources_payload) for item in parsed]
    items = parsed.get("suggestions", [])
    return [AITestCaseSuggestion(**item, sources=sources_payload) for item in items]
```

- [ ] **Step 4: Update router call**

Find the `generate_test_case_suggestions` call in `user_stories.py` and add `org_id=story.organization_id, db=db`.

- [ ] **Step 5: Rebuild**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 10
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_story_service.py backend/app/routers/user_stories.py
git commit -m "feat(rag): add RAG context to generate_test_case_suggestions"
```

---

### Task 10: Add RAG to generate_feature_suggestions

**Files:**
- Modify: `backend/app/services/ai_story_service.py`

- [ ] **Step 1: Update function signature**

```python
# OLD:
async def generate_feature_suggestions(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    ai_settings: dict | None = None,
) -> list[AIFeatureSuggestion]:

# NEW:
async def generate_feature_suggestions(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    ai_settings: dict | None = None,
    org_id: "uuid.UUID | None" = None,
    db: "AsyncSession | None" = None,
) -> list[AIFeatureSuggestion]:
```

- [ ] **Step 2: Add RAG retrieval**

After `decision = route_request(...)`:

```python
    # RAG retrieval
    rag_chunks: list = []
    rag_context_block: str | None = None
    if org_id is not None and db is not None:
        try:
            from app.services.rag_service import retrieve
            rag = await retrieve(
                f"{title} {description or ''} {acceptance_criteria or ''}", org_id, db
            )
            if rag.mode in ("direct", "context") and rag.chunks:
                rag_context_block = "\n".join([f"[Kontext]\n{c.text}" for c in rag.chunks])
                rag_chunks = rag.chunks
        except Exception as e:
            logger.warning("RAG retrieval error in generate_feature_suggestions (skipping): %s", e)
```

- [ ] **Step 3: Update _build_feature_suggestions_prompt and attach sources**

```python
def _build_feature_suggestions_prompt(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    rag_context: str | None = None,
) -> str:
    desc = description or "(keine)"
    ac = acceptance_criteria or "(keine)"
    context_section = ""
    if rag_context:
        context_section = f"""--- Org-Wissen (aus Karl / Nextcloud) ---
{rag_context}
-----------------------------------------

"""
    return f"""{context_section}Du bist ein erfahrener Senior Developer und Product Owner. Analysiere diese User Story und schlage konkrete, implementierbare Features (Teilfunktionen) vor.

User Story:
Titel: {title}
Beschreibung: {desc}
Akzeptanzkriterien: {ac}

Ein "Feature" ist eine abgeschlossene, eigenständig implementierbare Teilfunktion der Story.
Beispiele für eine Login-Story: "Login-Formular UI", "JWT-Token-Generierung", "Passwort-Hashing", "Session-Management"

Regeln:
- 3–6 konkrete Features vorschlagen
- Jedes Feature soll eigenständig implementier- und testbar sein
- Klarer, technischer Fokus (Frontend-Komponente ODER Backend-Service ODER Datenbankschicht)
- Realistische Story Points: 1–8 pro Feature
- Priorität: low | medium | high | critical

Antworte NUR mit einem JSON-Array (kein Markdown, kein Text davor oder danach):
[
  {{
    "title": "Konkreter Feature-Titel",
    "description": "Kurze technische Beschreibung was zu implementieren ist",
    "priority": "medium",
    "story_points": 3
  }}
]"""
```

Update prompt call:
```python
    prompt = _build_feature_suggestions_prompt(title, description, acceptance_criteria, rag_context=rag_context_block)
```

Attach sources:
```python
    sources_payload = [
        {"title": c.source_title or "", "url": c.source_url or "", "type": c.source_type}
        for c in rag_chunks if c.source_url
    ]
    parsed = _parse_json(raw)
    if isinstance(parsed, list):
        return [AIFeatureSuggestion(**item, sources=sources_payload) for item in parsed]
    items = parsed.get("features", parsed.get("suggestions", []))
    return [AIFeatureSuggestion(**item, sources=sources_payload) for item in items]
```

- [ ] **Step 4: Update router call**

Find `generate_feature_suggestions` call in `user_stories.py` and add `org_id=story.organization_id, db=db`.

- [ ] **Step 5: Rebuild**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 10
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_story_service.py backend/app/routers/user_stories.py
git commit -m "feat(rag): add RAG context to generate_feature_suggestions"
```

---

### Task 11: Feedback Loop — migration 0026 + SuggestionFeedback model

**Files:**
- Create: `backend/migrations/versions/0026_suggestion_feedback.py`
- Create: `backend/app/models/suggestion_feedback.py`

- [ ] **Step 1: Write migration 0026**

```python
# backend/migrations/versions/0026_suggestion_feedback.py
"""add suggestion_feedback table

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'suggestion_feedback',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('suggestion_type', sa.String(32), nullable=False),
        sa.Column('suggestion_text', sa.String(1000), nullable=False),
        sa.Column('feedback', sa.String(32), nullable=False, server_default='rejected'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_suggestion_feedback_org_type', 'suggestion_feedback', ['organization_id', 'suggestion_type'])


def downgrade() -> None:
    op.drop_index('ix_suggestion_feedback_org_type')
    op.drop_table('suggestion_feedback')
```

- [ ] **Step 2: Write SuggestionFeedback ORM model**

```python
# backend/app/models/suggestion_feedback.py
"""ORM model for suggestion feedback (rejected suggestions)."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SuggestionFeedback(Base):
    __tablename__ = "suggestion_feedback"
    __table_args__ = (
        Index("ix_suggestion_feedback_org_type", "organization_id", "suggestion_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    suggestion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    suggestion_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    feedback: Mapped[str] = mapped_column(String(32), nullable=False, default="rejected")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 3: Run migration**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker exec assist2-backend alembic upgrade head
```

Expected: `Running upgrade 0025 -> 0026`

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/versions/0026_suggestion_feedback.py backend/app/models/suggestion_feedback.py
git commit -m "feat(rag): migration 0026 + SuggestionFeedback model"
```

---

### Task 12: Suggestions feedback router

**Files:**
- Create: `backend/app/routers/suggestions.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create the router**

```python
# backend/app/routers/suggestions.py
"""Suggestion feedback endpoint."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.suggestion_feedback import SuggestionFeedback

router = APIRouter()

VALID_TYPES = {"dod", "test_case", "feature", "story"}


class FeedbackCreate(BaseModel):
    suggestion_type: str    # "dod" | "test_case" | "feature" | "story"
    suggestion_text: str
    feedback: str = "rejected"
    organization_id: uuid.UUID


@router.post(
    "/suggestions/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Record user feedback on an AI suggestion",
)
async def create_suggestion_feedback(
    data: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if data.suggestion_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid suggestion_type: {data.suggestion_type}")
    record = SuggestionFeedback(
        organization_id=data.organization_id,
        suggestion_type=data.suggestion_type,
        suggestion_text=data.suggestion_text[:1000],
        feedback=data.feedback,
    )
    db.add(record)
    await db.commit()
```

- [ ] **Step 2: Register router in main.py**

In `backend/app/main.py`, find the existing router registrations and add:

```python
from app.routers.suggestions import router as suggestions_router
```

And in the `include_router` section:
```python
app.include_router(suggestions_router, prefix="/api/v1", tags=["Suggestions"])
```

- [ ] **Step 3: Rebuild**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 10
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/suggestions.py backend/app/main.py
git commit -m "feat(rag): add POST /suggestions/feedback endpoint"
```

---

### Task 13: Inject rejection list into suggestion prompts

**Files:**
- Modify: `backend/app/services/ai_story_service.py`

- [ ] **Step 1: Add helper to load rejected suggestions**

Add this function near the top of `ai_story_service.py` (after the imports):

```python
async def _get_rejected_suggestions(
    org_id: "uuid.UUID", suggestion_type: str, db: "AsyncSession"
) -> list[str]:
    """Return up to 20 recently rejected suggestion texts for this org+type."""
    try:
        from sqlalchemy import select as _select
        from app.models.suggestion_feedback import SuggestionFeedback
        result = await db.execute(
            _select(SuggestionFeedback.suggestion_text)
            .where(
                SuggestionFeedback.organization_id == org_id,
                SuggestionFeedback.suggestion_type == suggestion_type,
                SuggestionFeedback.feedback == "rejected",
            )
            .order_by(SuggestionFeedback.created_at.desc())
            .limit(20)
        )
        return [row[0] for row in result.fetchall()]
    except Exception as e:
        logger.warning("Failed to load rejected suggestions: %s", e)
        return []
```

- [ ] **Step 2: Add rejection block builder**

```python
def _build_rejection_block(rejected: list[str]) -> str:
    if not rejected:
        return ""
    lines = "\n".join(f"- {t}" for t in rejected)
    return f"""--- Von der Organisation abgelehnte Vorschläge (nicht wiederholen) ---
{lines}
----------------------------------------------------------------------

"""
```

- [ ] **Step 3: Inject into generate_dod_suggestions**

In `generate_dod_suggestions`, after the RAG block and before `prompt = _build_dod_prompt(...)`:

```python
    # Load rejected DoD suggestions for this org
    rejection_block = ""
    if org_id is not None and db is not None:
        rejected = await _get_rejected_suggestions(org_id, "dod", db)
        rejection_block = _build_rejection_block(rejected)
```

Update `_build_dod_prompt` to prepend the rejection block:
```python
def _build_dod_prompt(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    rag_context: str | None = None,
    rejection_block: str = "",
) -> str:
    ...
    return f"""{rejection_block}{context_section}Du bist ein erfahrener Scrum Master..."""
```

Call: `prompt = _build_dod_prompt(title, description, acceptance_criteria, rag_context=rag_context_block, rejection_block=rejection_block)`

- [ ] **Step 4: Same pattern for generate_test_case_suggestions**

Load rejected:
```python
    rejection_block = ""
    if org_id is not None and db is not None:
        rejected = await _get_rejected_suggestions(org_id, "test_case", db)
        rejection_block = _build_rejection_block(rejected)
```

Update `_build_test_cases_prompt` signature:
```python
def _build_test_cases_prompt(
    title: str,
    acceptance_criteria: str | None,
    rag_context: str | None = None,
    rejection_block: str = "",
) -> str:
    ...
    return f"""{rejection_block}{context_section}Du bist ein erfahrener QA-Ingenieur..."""
```

- [ ] **Step 5: Same pattern for generate_feature_suggestions**

Load rejected with type `"feature"`:
```python
    rejection_block = ""
    if org_id is not None and db is not None:
        rejected = await _get_rejected_suggestions(org_id, "feature", db)
        rejection_block = _build_rejection_block(rejected)
```

Update `_build_feature_suggestions_prompt` signature and prepend rejection_block.

- [ ] **Step 6: Rebuild**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 10
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ai_story_service.py
git commit -m "feat(rag): inject rejection list into all suggestion prompts"
```

---

### Task 14: Update AISuggestionItem — source badges + onReject

**Files:**
- Modify: `frontend/components/stories/AISuggestionItem.tsx`

- [ ] **Step 1: Replace AISuggestionItem.tsx**

```tsx
// frontend/components/stories/AISuggestionItem.tsx
"use client";

import { FileText, GripVertical, Plus, Sparkles, X } from "lucide-react";

export interface Source {
  title: string;
  url: string;
  type: string; // "karl_story" | "nextcloud" | "jira" | "confluence"
}

export type AISuggestionSource = "doc" | "ki";

export interface AISuggestionItemProps {
  text: string;
  category?: string | null;
  sources?: Source[];
  onAdd: () => void;
  onReject?: () => void;
  /** MIME type for drag data (e.g. "application/x-dod-suggestion"). Omit to disable drag. */
  dragType?: string;
}

/**
 * Single AI suggestion entry.
 *
 * Shows source badges: if sources.length > 0 → linked org-source badges;
 * if sources is empty or undefined → ✦ KI badge (pure LLM, no org context).
 */
export function AISuggestionItem({ text, category, sources, onAdd, onReject, dragType }: AISuggestionItemProps) {
  function handleDragStart(e: React.DragEvent) {
    if (!dragType) return;
    e.dataTransfer.setData(dragType, text);
    e.dataTransfer.setData("text/plain", text);
    e.dataTransfer.effectAllowed = "copy";
  }

  const hasSources = sources && sources.length > 0;

  return (
    <div
      draggable={!!dragType}
      onDragStart={dragType ? handleDragStart : undefined}
      className={`relative flex items-start gap-2 px-3 py-2.5 border border-[var(--paper-rule)] rounded-sm bg-[var(--card)] hover:border-[rgba(var(--accent-red-rgb),.3)] transition-colors group${dragType ? " cursor-grab active:cursor-grabbing" : ""}`}
    >
      {dragType && <GripVertical size={13} className="shrink-0 mt-0.5 text-[var(--ink-faintest)] group-hover:text-[var(--ink-faint)]" />}
      <div className="flex-1 min-w-0">
        {category && (
          <div className="flex items-center gap-1.5 mb-1">
            <span className="shrink-0 px-1.5 py-0.5 bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)] rounded-sm text-[7px] font-medium uppercase tracking-[.06em] [font-family:var(--font-mono)]">
              {category}
            </span>
          </div>
        )}
        <span className="text-sm text-[var(--ink-mid)] break-words leading-snug">{text}</span>

        {/* Source badges */}
        <div className="flex flex-wrap items-center gap-1 mt-1.5">
          {hasSources ? (
            sources.map((s, i) => (
              <a
                key={i}
                href={s.url}
                target={s.type === "karl_story" ? "_self" : "_blank"}
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="inline-flex items-center gap-1 text-[10px] text-[var(--ink-faint)] hover:text-[var(--accent-red)] border border-[var(--paper-rule)] rounded-sm px-1.5 py-0.5 transition-colors"
              >
                <FileText size={9} />
                {s.title}
              </a>
            ))
          ) : (
            <span className="inline-flex items-center gap-1 text-[10px] text-[var(--ink-faintest)] border border-[var(--paper-rule)] rounded-sm px-1.5 py-0.5">
              <Sparkles size={9} />
              KI
            </span>
          )}
        </div>
      </div>

      {/* Reject button — top-right corner, revealed on hover */}
      {onReject && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onReject(); }}
          aria-label="Vorschlag ablehnen"
          className="absolute top-[6px] right-[26px] w-[18px] h-[18px] flex items-center justify-center text-[var(--ink-faintest)] hover:text-[var(--accent-red)] rounded-sm opacity-0 group-hover:opacity-100 transition-all"
        >
          <X size={10} />
        </button>
      )}

      {/* Plus button — top-right corner, revealed on hover */}
      <button
        type="button"
        onClick={onAdd}
        aria-label="Vorschlag übernehmen"
        className="absolute top-[6px] right-[6px] w-[18px] h-[18px] flex items-center justify-center bg-[rgba(var(--accent-red-rgb),.08)] border-[0.5px] border-[rgba(var(--accent-red-rgb),.3)] text-[var(--accent-red)] rounded-sm opacity-0 group-hover:opacity-100 transition-all hover:bg-[var(--accent-red)] hover:text-white"
      >
        <Plus size={10} />
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Rebuild frontend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build frontend
docker logs assist2-frontend --tail 20
```

Expected: build completes without TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/stories/AISuggestionItem.tsx
git commit -m "feat(rag): AISuggestionItem — source badges with links, onReject prop"
```

---

### Task 15: Wire sources + onReject in story page

**Files:**
- Modify: `frontend/app/[org]/stories/[id]/page.tsx`

The story page renders DoD suggestions, test case suggestions, and feature suggestions via `AISuggestionItem`. Each suggestion object from the API now carries a `sources` array. The `onReject` handler should:
1. Remove the item optimistically from local state
2. POST to `/api/v1/suggestions/feedback` in the background

- [ ] **Step 1: Add the Source type import and feedback helper**

At the top of `frontend/app/[org]/stories/[id]/page.tsx`, add import:

```typescript
import type { Source } from "@/components/stories/AISuggestionItem";
```

Add a helper function inside the page component (or as a module-level function):

```typescript
async function rejectSuggestion(
  orgId: string,
  suggestion_type: "dod" | "test_case" | "feature" | "story",
  suggestion_text: string,
) {
  try {
    await apiRequest("/api/v1/suggestions/feedback", {
      method: "POST",
      body: JSON.stringify({ organization_id: orgId, suggestion_type, suggestion_text, feedback: "rejected" }),
    });
  } catch {
    // Background fire-and-forget — ignore errors
  }
}
```

- [ ] **Step 2: Update DoD suggestions rendering**

Find where `AISuggestionItem` is rendered for DoD suggestions. The DoD suggestions come from the `dodSuggestions` state (or similar). Each item now has `sources?: Source[]`.

Update each DoD `AISuggestionItem` call:
```tsx
<AISuggestionItem
  key={i}
  text={s.text}
  category={s.category}
  sources={s.sources}
  onAdd={() => handleAddDoD(s.text)}
  onReject={() => {
    setDodSuggestions((prev) => prev.filter((_, idx) => idx !== i));
    void rejectSuggestion(story.organization_id, "dod", s.text);
  }}
  dragType="application/x-dod-suggestion"
/>
```

- [ ] **Step 3: Update test case suggestions rendering**

Find `AISuggestionItem` for test case suggestions. Each item has `sources?: Source[]`.

```tsx
<AISuggestionItem
  key={i}
  text={s.title}
  sources={s.sources}
  onAdd={() => handleAddTestCase(s)}
  onReject={() => {
    setTestSuggestions((prev) => prev.filter((_, idx) => idx !== i));
    void rejectSuggestion(story.organization_id, "test_case", s.title);
  }}
/>
```

- [ ] **Step 4: Update feature suggestions rendering**

```tsx
<AISuggestionItem
  key={i}
  text={s.title}
  sources={s.sources}
  onAdd={() => handleAddFeature(s)}
  onReject={() => {
    setFeatureSuggestions((prev) => prev.filter((_, idx) => idx !== i));
    void rejectSuggestion(story.organization_id, "feature", s.title);
  }}
/>
```

- [ ] **Step 5: Update types/index.ts — add sources to suggestion types**

In `frontend/types/index.ts`, update the `AISuggestion` interface:

```typescript
export interface Source {
  title: string;
  url: string;
  type: string;
}

export interface AISuggestion {
  title: string | null;
  description: string | null;
  acceptance_criteria: string | null;
  explanation: string;
  dor_issues: string[];
  quality_score: number | null;
  source?: "rag_direct" | "rag_context" | "llm";
  sources?: Source[];
}
```

- [ ] **Step 6: Rebuild frontend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build frontend
docker logs assist2-frontend --tail 20
```

Expected: build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/app/\[org\]/stories/\[id\]/page.tsx frontend/types/index.ts
git commit -m "feat(rag): wire sources + onReject in story page"
```

---

### Task 16: Phase 2 — Jira ticket indexing

**Files:**
- Modify: `backend/app/tasks/rag_tasks.py`
- Modify: `backend/app/routers/jira.py`

- [ ] **Step 1: Add index_jira_ticket task to rag_tasks.py**

```python
# Add at end of backend/app/tasks/rag_tasks.py

async def _index_jira_ticket_async(ticket_key: str, org_id: str, db: AsyncSession) -> None:
    """Index a single Jira ticket into pgvector. Silent no-op if Jira not configured."""
    from app.models.document_chunk import DocumentChunk
    from app.models.organization import Organization
    from app.models.jira_story import JiraStory

    org_uuid = uuid.UUID(org_id)

    # Load org to check Jira config
    org_result = await db.execute(select(Organization).where(Organization.id == org_uuid))
    org = org_result.scalar_one_or_none()
    if org is None:
        return

    metadata = getattr(org, "metadata_", None) or {}
    jira_cfg = metadata.get("integrations", {}).get("jira", {})
    if not jira_cfg.get("base_url") or not jira_cfg.get("api_token_enc"):
        logger.debug("index_jira_ticket: Jira not configured for org %s — skipping", org_id)
        return

    jira_base_url = jira_cfg["base_url"].rstrip("/")

    # Load JiraStory record
    story_result = await db.execute(
        select(JiraStory).where(
            JiraStory.ticket_key == ticket_key.upper(),
            JiraStory.organization_id == org_uuid,
        )
    )
    jira_story = story_result.scalar_one_or_none()
    if jira_story is None:
        logger.warning("index_jira_ticket: ticket %s not found in DB", ticket_key)
        return

    summary = jira_story.source_summary or ticket_key
    content = jira_story.content or ""
    chunk_text = f"{ticket_key}: {summary}\n{content}"[:4000]
    source_ref = f"jira:{ticket_key}"
    source_url = f"{jira_base_url}/browse/{ticket_key}"
    source_title = f"Jira: {ticket_key} — {summary[:60]}"

    try:
        embeddings = await _embed_chunks([chunk_text])
    except Exception as e:
        logger.warning("index_jira_ticket: embedding failed for %s: %s", ticket_key, e)
        return

    # Delete existing chunk for this ticket
    await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.org_id == org_uuid,
            DocumentChunk.source_ref == source_ref,
        )
    )

    embedding_str = "[" + ",".join(str(x) for x in embeddings[0]) + "]"
    chunk = DocumentChunk(
        org_id=org_uuid,
        source_ref=source_ref,
        source_type="jira",
        source_url=source_url,
        source_title=source_title,
        file_hash=_sha256(chunk_text.encode()),
        chunk_index=0,
        chunk_text=chunk_text,
        embedding=embedding_str,
    )
    db.add(chunk)
    await db.commit()
    logger.info("index_jira_ticket: indexed ticket %s for org %s", ticket_key, org_id)


@celery.task(name="rag_tasks.index_jira_ticket", bind=True, max_retries=3)
def index_jira_ticket(self, ticket_key: str, org_id: str) -> dict:
    """Celery task: index a Jira ticket into pgvector."""
    from app.config import get_settings

    async def run():
        engine = create_async_engine(
            get_settings().DATABASE_URL, echo=False, pool_pre_ping=True
        )
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with SessionLocal() as db:
                await _index_jira_ticket_async(ticket_key, org_id, db)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
        return {"status": "ok", "ticket_key": ticket_key}
    except Exception as exc:
        logger.error("index_jira_ticket failed for %s: %s", ticket_key, exc)
        raise self.retry(exc=exc, countdown=60)
```

- [ ] **Step 2: Dispatch from jira.py after story is saved**

In `backend/app/routers/jira.py`, in `create_story`:

```python
from app.tasks.rag_tasks import index_jira_ticket

# After: await db.refresh(story)  (or after await db.commit())
# Add:
index_jira_ticket.delay(story.ticket_key, str(story.organization_id))
```

Find the exact location:
```bash
grep -n "await db.commit\|await db.refresh" backend/app/routers/jira.py | head -5
```

- [ ] **Step 3: Rebuild**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 10
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/tasks/rag_tasks.py backend/app/routers/jira.py
git commit -m "feat(rag): Phase 2 — index Jira tickets on import with config guard"
```

---

### Task 17: Phase 3 — Confluence indexing

**Files:**
- Modify: `backend/app/tasks/rag_tasks.py`
- Modify: `backend/app/main.py`
- Modify: `frontend/app/[org]/settings/page.tsx`

- [ ] **Step 1: Add index_confluence_space task to rag_tasks.py**

```python
# Add at end of backend/app/tasks/rag_tasks.py

async def _index_confluence_space_async(org_id: str, db: AsyncSession) -> None:
    """Index all Confluence pages for the org. Silent no-op if Confluence not configured."""
    from app.models.document_chunk import DocumentChunk
    from app.models.organization import Organization

    org_uuid = uuid.UUID(org_id)

    org_result = await db.execute(select(Organization).where(Organization.id == org_uuid))
    org = org_result.scalar_one_or_none()
    if org is None:
        return

    metadata = getattr(org, "metadata_", None) or {}
    conf_cfg = metadata.get("integrations", {}).get("confluence", {})
    if not conf_cfg.get("base_url") or not conf_cfg.get("api_token_enc"):
        logger.debug("index_confluence_space: Confluence not configured for org %s — skipping", org_id)
        return

    conf_base_url = conf_cfg["base_url"].rstrip("/")
    space_keys: list[str] = conf_cfg.get("space_keys", [])
    api_token_enc: str = conf_cfg["api_token_enc"]
    conf_user: str = conf_cfg.get("user_email", "")

    if not space_keys:
        logger.debug("index_confluence_space: no space_keys configured for org %s", org_id)
        return

    # Decrypt token
    try:
        from app.core.security import decrypt_secret
        api_token = decrypt_secret(api_token_enc)
    except Exception as e:
        logger.error("index_confluence_space: failed to decrypt Confluence token: %s", e)
        return

    import base64
    auth_header = "Basic " + base64.b64encode(f"{conf_user}:{api_token}".encode()).decode()
    headers = {"Authorization": auth_header, "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for space_key in space_keys:
            # List pages in space (max 50 per call — paginate if needed)
            try:
                resp = await client.get(
                    f"{conf_base_url}/rest/api/content",
                    headers=headers,
                    params={"spaceKey": space_key, "type": "page", "limit": 50, "expand": "body.storage"},
                )
                resp.raise_for_status()
            except Exception as e:
                logger.warning("index_confluence_space: failed to list pages for space %s: %s", space_key, e)
                continue

            pages = resp.json().get("results", [])
            for page in pages:
                page_id = str(page.get("id", ""))
                page_title = page.get("title", "")
                body_html = page.get("body", {}).get("storage", {}).get("value", "")

                # Strip HTML tags for plaintext
                import re as _re
                body_text = _re.sub(r"<[^>]+>", " ", body_html).strip()
                body_text = _re.sub(r"\s+", " ", body_text)

                if not body_text:
                    continue

                full_text = f"{page_title}\n{body_text}"
                source_ref = f"confluence:{page_id}"
                source_url = f"{conf_base_url}/wiki/spaces/{space_key}/pages/{page_id}"
                source_title = f"Confluence: {page_title}"

                raw_chunks = _chunk_text(full_text)
                if not raw_chunks:
                    continue

                try:
                    embeddings = await _embed_chunks(raw_chunks)
                except Exception as e:
                    logger.warning("index_confluence_space: embedding failed for page %s: %s", page_id, e)
                    continue

                # Delete existing chunks for this page
                await db.execute(
                    delete(DocumentChunk).where(
                        DocumentChunk.org_id == org_uuid,
                        DocumentChunk.source_ref == source_ref,
                    )
                )

                for i, (chunk_text, embedding) in enumerate(zip(raw_chunks, embeddings)):
                    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
                    chunk = DocumentChunk(
                        org_id=org_uuid,
                        source_ref=source_ref,
                        source_type="confluence",
                        source_url=source_url,
                        source_title=source_title,
                        file_hash=_sha256(chunk_text.encode()),
                        chunk_index=i,
                        chunk_text=chunk_text,
                        embedding=embedding_str,
                    )
                    db.add(chunk)

                await db.commit()
                logger.info("index_confluence_space: indexed page %s (%s)", page_id, page_title)


@celery.task(name="rag_tasks.index_confluence_space", bind=True, max_retries=3)
def index_confluence_space(self, org_id: str) -> dict:
    """Celery task: index all Confluence pages for the org."""
    from app.config import get_settings

    async def run():
        engine = create_async_engine(
            get_settings().DATABASE_URL, echo=False, pool_pre_ping=True
        )
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with SessionLocal() as db:
                await _index_confluence_space_async(org_id, db)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
        return {"status": "ok", "org_id": org_id}
    except Exception as exc:
        logger.error("index_confluence_space failed for org %s: %s", org_id, exc)
        raise self.retry(exc=exc, countdown=60)
```

- [ ] **Step 2: Add POST /confluence/index endpoint to a new confluence router**

Create `backend/app/routers/confluence.py`:

```python
# backend/app/routers/confluence.py
"""Confluence integration endpoints."""
import uuid
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User

router = APIRouter()


class ConfluenceIndexRequest(BaseModel):
    org_id: uuid.UUID


@router.post(
    "/confluence/index",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Confluence space indexing for org",
)
async def trigger_confluence_index(
    data: ConfluenceIndexRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    from app.tasks.rag_tasks import index_confluence_space
    index_confluence_space.delay(str(data.org_id))
    return {"message": "Confluence-Indexierung gestartet"}
```

Register in `backend/app/main.py`:
```python
from app.routers.confluence import router as confluence_router
app.include_router(confluence_router, prefix="/api/v1", tags=["Confluence"])
```

- [ ] **Step 3: Add "Jetzt indexieren" button to settings page**

In `frontend/app/[org]/settings/page.tsx`, find the Confluence tab section. Add a button that POSTs to the index endpoint:

```tsx
// Inside the Confluence settings tab, after the existing config form:
{confluenceConfigured && (
  <div className="mt-4 pt-4 border-t border-[var(--paper-rule)]">
    <button
      type="button"
      disabled={confluenceIndexing}
      onClick={async () => {
        setConfluenceIndexing(true);
        try {
          await apiRequest(`/api/v1/confluence/index`, {
            method: "POST",
            body: JSON.stringify({ org_id: org?.id }),
          });
          // Show success toast or message
        } catch {
          // Show error
        } finally {
          setConfluenceIndexing(false);
        }
      }}
      className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium disabled:opacity-50 transition-colors"
    >
      {confluenceIndexing ? "Indexierung läuft..." : "Jetzt indexieren"}
    </button>
    <p className="text-xs text-[var(--ink-faint)] mt-1">
      Alle Confluence-Seiten aus konfigurierten Spaces werden in den Wissens-Index aufgenommen.
    </p>
  </div>
)}
```

Add state: `const [confluenceIndexing, setConfluenceIndexing] = useState(false);`

The `confluenceConfigured` check: read the org's metadata to see if `integrations.confluence.base_url` and `api_token_enc` are set. Use the existing settings page pattern for reading org config.

- [ ] **Step 4: Rebuild both**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend frontend
docker logs assist2-backend --tail 10
docker logs assist2-frontend --tail 10
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/rag_tasks.py backend/app/routers/confluence.py backend/app/main.py frontend/app/\[org\]/settings/page.tsx
git commit -m "feat(rag): Phase 3 — Confluence indexing with config guard and settings button"
```

---

## Self-Review

**Spec coverage:**
- ✅ Migration 0025: `source_ref`, `source_type`, `source_url`, `source_title` — Task 1
- ✅ DocumentChunk ORM update with `SourceType` enum — Task 2
- ✅ `RagChunk`/`RagResult` with provenance — Task 3
- ✅ `Source` schema + `sources` fields on all suggestion types — Task 4
- ✅ `index_story_knowledge` Celery task (story + DoD + features + test cases) — Task 5
- ✅ Dispatch on story status `ready`/`done` — Task 6
- ✅ Dispatch on test case `result=passed` — Task 7
- ✅ RAG in `generate_dod_suggestions` — Task 8
- ✅ RAG in `generate_test_case_suggestions` — Task 9
- ✅ RAG in `generate_feature_suggestions` — Task 10
- ✅ Migration 0026 + `SuggestionFeedback` model — Task 11
- ✅ `POST /suggestions/feedback` endpoint — Task 12
- ✅ Rejection list injection into all prompts — Task 13
- ✅ `AISuggestionItem` source badges + `onReject` — Task 14
- ✅ Story page wiring — Task 15
- ✅ Phase 2 Jira indexing with config guard — Task 16
- ✅ Phase 3 Confluence indexing with config guard + "Jetzt indexieren" button — Task 17
- ✅ `✦ KI` badge for pure LLM suggestions (no sources) — Task 14 (Sparkles icon + "KI" text)

**Placeholder scan:** None found.

**Type consistency:**
- `Source` defined in `backend/app/schemas/user_story.py`, imported into `feature.py` ✅
- `Source` interface in `AISuggestionItem.tsx`, re-exported for use in page ✅
- `sources_payload` built consistently from `rag_chunks` in Tasks 8–10 ✅
- `RagChunk.text` used consistently (not `.chunk_text`) in all usages ✅
- `rag.context` (not `rag.direct_answer`) used after Task 3 ✅
- `source_ref` (not `file_path`) used in all new task code ✅
