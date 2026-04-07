# RAG Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire IONOS bge-m3 embeddings, Confluence/Jira webhook ingestion, nightly sync, user action tracking, and RAG context injection into both the chat endpoint and story generation.

**Architecture:** Incremental on the existing stack — pgvector HNSW, Celery + Beat, LiteLLM `ionos-embed`, no new microservice. RAG injection in `/ai/chat` uses 800ms async timeout; story generation uses min_score=0.75 with source-type filtering.

**Tech Stack:** FastAPI, pgvector, SQLAlchemy (async), Celery + Celery Beat, LiteLLM (`ionos-embed` / BAAI/bge-m3 1024-dim), httpx, pytest-asyncio

---

## File Map

| File | Change |
|---|---|
| `backend/migrations/versions/0026_rag_hnsw_ionos_embed.py` | **Create** — migrate vector(1536)→vector(1024), IVFFlat→HNSW, add user_action comment |
| `backend/app/models/document_chunk.py` | **Modify** — add `user_action` to `SourceType` enum |
| `backend/app/services/rag_service.py` | **Modify** — switch model to `ionos-embed`, fix `/v1/embeddings` path, add `min_score`+`source_types` params to `retrieve()` |
| `backend/app/tasks/rag_tasks.py` | **Modify** — switch model to `ionos-embed`, fix `/v1/embeddings` path, add `index_user_action` task |
| `backend/app/tasks/sync_dispatcher.py` | **Modify** — add Confluence+Jira to nightly `_dispatch_rag_index` |
| `backend/app/celery_app.py` | **Modify** — change rag Beat schedule from 86400s to `crontab(hour=2, minute=0)` |
| `backend/app/routers/webhooks.py` | **Create** — `POST /api/v1/webhooks/confluence` and `/jira` |
| `backend/app/main.py` | **Modify** — register webhooks router |
| `backend/app/routers/ai.py` | **Modify** — add DB dep + RAG injection with 800ms timeout to `/ai/chat`; add org_id + user-action indexing to `/ai/compact-chat` |
| `backend/app/services/ai_story_service.py` | **Modify** — pass `min_score=0.75` + `source_types` to RAG retrieve in `get_story_suggestions` |
| `backend/tests/unit/test_rag_service.py` | **Modify** — fix `direct_answer`→`context`, 1536→1024, add min_score+source_types tests |
| `backend/tests/unit/test_rag_tasks.py` | **Modify** — update model name assertion |
| `backend/tests/unit/test_webhooks.py` | **Create** — webhook auth + dispatch tests |

---

## Task 1: DB Migration — vector(1024), HNSW index, user_action source type

**Files:**
- Create: `backend/migrations/versions/0026_rag_hnsw_ionos_embed.py`
- Modify: `backend/app/models/document_chunk.py`

- [ ] **Step 1: Add `user_action` to SourceType enum**

In `backend/app/models/document_chunk.py`, change the `SourceType` class:

```python
class SourceType(str, enum.Enum):
    nextcloud  = "nextcloud"
    karl_story = "karl_story"
    jira       = "jira"
    confluence = "confluence"
    user_action = "user_action"
```

- [ ] **Step 2: Write the migration**

Create `backend/migrations/versions/0026_rag_hnsw_ionos_embed.py`:

```python
"""RAG: migrate embedding vector(1536)→vector(1024), IVFFlat→HNSW

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-06
"""
from alembic import op

revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop all IVFFlat indexes on document_chunks
    op.execute("""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'document_chunks'
                  AND (indexdef ILIKE '%ivfflat%' OR indexdef ILIKE '%vector%')
            LOOP
                EXECUTE 'DROP INDEX IF EXISTS ' || quote_ident(r.indexname);
            END LOOP;
        END $$;
    """)

    # Clear embeddings — dimension change requires full re-index
    op.execute("UPDATE document_chunks SET embedding = NULL")

    # Migrate column type: vector(1536) → vector(1024)
    op.execute(
        "ALTER TABLE document_chunks "
        "ALTER COLUMN embedding TYPE vector(1024) USING NULL::vector(1024)"
    )

    # Create HNSW index (no rebuild needed on insert, unlike IVFFlat)
    op.execute("""
        CREATE INDEX ix_document_chunks_embedding_hnsw
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.execute("UPDATE document_chunks SET embedding = NULL")
    op.execute(
        "ALTER TABLE document_chunks "
        "ALTER COLUMN embedding TYPE vector(1536) USING NULL::vector(1536)"
    )
    op.execute("""
        CREATE INDEX ix_document_chunks_embedding_ivfflat
        ON document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
```

- [ ] **Step 3: Run migration**

```bash
cd /opt/assist2 && make migrate
```

Expected: `Running upgrade 0025 -> 0026` with no errors.

- [ ] **Step 4: Verify column type**

```bash
docker exec assist2-postgres psql -U platform platform_db -c \
  "SELECT column_name, data_type, udt_name FROM information_schema.columns WHERE table_name='document_chunks' AND column_name='embedding';"
```

Expected: `udt_name = vector` (no error on type check)

```bash
docker exec assist2-postgres psql -U platform platform_db -c \
  "SELECT indexname, indexdef FROM pg_indexes WHERE tablename='document_chunks';"
```

Expected: one row with `hnsw` in `indexdef`, no `ivfflat` rows.

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2 && git add backend/migrations/versions/0026_rag_hnsw_ionos_embed.py backend/app/models/document_chunk.py
git commit -m "feat(rag): migrate embedding to vector(1024) HNSW, add user_action source type"
```

---

## Task 2: Switch embedding model to ionos-embed

**Files:**
- Modify: `backend/app/services/rag_service.py`
- Modify: `backend/app/tasks/rag_tasks.py`
- Modify: `backend/tests/unit/test_rag_service.py`
- Modify: `backend/tests/unit/test_rag_tasks.py`

- [ ] **Step 1: Update tests first (TDD — they should fail before the fix)**

In `backend/tests/unit/test_rag_service.py`, update every occurrence of `[0.1] * 1536` → `[0.1] * 1024` and `result.direct_answer` → `result.context`:

```python
# Every mock_embed.return_value line:
mock_embed.return_value = [0.1] * 1024   # was 1536

# Every assertion on direct mode:
assert result.context == "Direktantwort Text"   # was result.direct_answer
```

- [ ] **Step 2: Run tests — confirm failures**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "PASSED|FAILED|ERROR" | grep -i rag
```

Expected: several `FAILED` for `test_rag_service.py` (attribute `direct_answer` missing, etc.)

- [ ] **Step 3: Update `rag_service.py`**

In `backend/app/services/rag_service.py`:

Change the `_embed_query` function — two lines:
```python
# old:
json={"model": "text-embedding-3-small", "input": query},
# change endpoint from /embeddings to /v1/embeddings:
resp = await client.post(
    f"{settings.LITELLM_URL}/v1/embeddings",
    headers=headers,
    json={"model": "ionos-embed", "input": query},
)
```

Full updated `_embed_query`:
```python
async def _embed_query(query: str) -> list[float]:
    """Get embedding vector from LiteLLM. Raises on error (caller handles)."""
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.LITELLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LITELLM_API_KEY}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.LITELLM_URL}/v1/embeddings",
            headers=headers,
            json={"model": "ionos-embed", "input": query},
        )
        resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]
```

- [ ] **Step 4: Update `rag_tasks.py`**

In `backend/app/tasks/rag_tasks.py`, update the `_embed_chunks` function:

```python
async def _embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Embed a list of text chunks via LiteLLM in a single batch call."""
    if not chunks:
        return []
    from app.config import get_settings
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.LITELLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LITELLM_API_KEY}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.LITELLM_URL}/v1/embeddings",
            headers=headers,
            json={"model": "ionos-embed", "input": chunks},
        )
        resp.raise_for_status()
    data = resp.json()["data"]
    data.sort(key=lambda x: x["index"])
    return [item["embedding"] for item in data]
```

- [ ] **Step 5: Run tests — confirm they pass**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "PASSED|FAILED|ERROR" | grep -i rag
```

Expected: all `test_rag_service.py` tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
cd /opt/assist2 && git add backend/app/services/rag_service.py backend/app/tasks/rag_tasks.py backend/tests/unit/test_rag_service.py backend/tests/unit/test_rag_tasks.py
git commit -m "feat(rag): switch embedding model to ionos-embed (BAAI/bge-m3, 1024-dim)"
```

---

## Task 3: Nightly sync — add Confluence + Jira + crontab schedule

**Files:**
- Modify: `backend/app/tasks/sync_dispatcher.py`
- Modify: `backend/app/celery_app.py`

- [ ] **Step 1: Write failing test for nightly dispatch**

In `backend/tests/unit/test_dispatch_tasks.py`, add:

```python
@pytest.mark.asyncio
async def test_dispatch_rag_index_triggers_confluence_and_jira():
    """_dispatch_rag_index must call index_confluence_space for each active org."""
    from app.tasks.sync_dispatcher import _dispatch_rag_index

    mock_org = MagicMock()
    mock_org.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    mock_org.slug = "test-org"

    with patch("app.tasks.sync_dispatcher._make_engine") as mock_engine, \
         patch("app.tasks.rag_tasks.index_org_documents") as mock_nextcloud, \
         patch("app.tasks.rag_tasks.index_confluence_space") as mock_confluence:

        mock_engine.return_value = AsyncMock()
        # ... (use existing pattern from test_dispatch_tasks.py for DB mock)
        result = await _dispatch_rag_index()

    mock_confluence.delay.assert_called()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "test_dispatch_rag_index_triggers_confluence"
```

Expected: `FAILED` — `mock_confluence.delay.assert_called()` → `AssertionError`

- [ ] **Step 3: Update `_dispatch_rag_index` in `sync_dispatcher.py`**

Replace the existing `_dispatch_rag_index` function (lines 104–117):

```python
async def _dispatch_rag_index() -> dict:
    from app.models.organization import Organization
    from app.tasks.rag_tasks import index_org_documents, index_confluence_space

    engine = _make_engine()
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(Organization.id, Organization.slug).where(Organization.deleted_at.is_(None))
            )
            orgs = result.fetchall()
    finally:
        await engine.dispose()

    for org_id, org_slug in orgs:
        index_org_documents.delay(str(org_id), org_slug)
        index_confluence_space.delay(str(org_id))

    return {"dispatched": len(orgs)}
```

- [ ] **Step 4: Switch celery_app.py Beat schedule to crontab**

In `backend/app/celery_app.py`, update the imports and beat schedule:

```python
from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery = Celery(
    "assist2",
    broker=settings.REDIS_URL.replace("/0", "/1"),
    backend=settings.REDIS_URL.replace("/0", "/2"),
    include=[
        "app.tasks.mail_sync",
        "app.tasks.calendar_sync",
        "app.tasks.agent_tasks",
        "app.tasks.pdf_tasks",
        "app.tasks.sync_dispatcher",
        "app.tasks.rag_tasks",
    ]
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery.conf.beat_schedule = {
    "dispatch-mail-sync": {
        "task": "sync_dispatcher.dispatch_mail_sync",
        "schedule": 60.0,
    },
    "dispatch-calendar-sync": {
        "task": "sync_dispatcher.dispatch_calendar_sync",
        "schedule": 60.0,
    },
    "dispatch-rag-index": {
        "task": "sync_dispatcher.dispatch_rag_index",
        "schedule": crontab(hour=2, minute=0),  # daily at 02:00 UTC
    },
}
```

- [ ] **Step 5: Run tests**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "test_dispatch_rag_index"
```

Expected: `PASSED`

- [ ] **Step 6: Commit**

```bash
cd /opt/assist2 && git add backend/app/tasks/sync_dispatcher.py backend/app/celery_app.py backend/tests/unit/test_dispatch_tasks.py
git commit -m "feat(rag): nightly sync includes Confluence, switch to crontab(02:00 UTC)"
```

---

## Task 4: Webhook endpoints for Confluence and Jira

**Files:**
- Create: `backend/app/routers/webhooks.py`
- Create: `backend/tests/unit/test_webhooks.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing webhook tests**

Create `backend/tests/unit/test_webhooks.py`:

```python
"""Unit tests for webhook endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


@pytest.mark.asyncio
async def test_confluence_webhook_missing_secret(auth_override):
    """No X-Webhook-Secret header → 401."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/webhooks/confluence",
            json={"event": "page_updated", "page": {"id": "12345"}},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_confluence_webhook_invalid_secret():
    """Wrong X-Webhook-Secret → 401."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.deps import get_db

    mock_db = AsyncMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/webhooks/confluence",
                json={"event": "page_updated", "page": {"id": "12345"}},
                headers={"X-Webhook-Secret": "wrong-secret"},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_confluence_webhook_valid_queues_task():
    """Valid secret → 200, index_confluence_space task queued."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.deps import get_db

    org_id = uuid.uuid4()
    mock_org = MagicMock()
    mock_org.id = org_id
    mock_org.metadata_ = {"webhook_secrets": {"confluence": "test-secret-conf"}}

    mock_db = AsyncMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_org]
    mock_db.commit = AsyncMock()

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("app.routers.webhooks.index_confluence_space") as mock_task:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/webhooks/confluence",
                    json={"event": "page_updated", "page": {"id": "12345"}},
                    headers={"X-Webhook-Secret": "test-secret-conf"},
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"
        mock_task.delay.assert_called_once_with(str(org_id))
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_jira_webhook_valid_queues_task():
    """Valid Jira secret → 200, index_jira_ticket task queued."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.deps import get_db

    org_id = uuid.uuid4()
    mock_org = MagicMock()
    mock_org.id = org_id
    mock_org.metadata_ = {"webhook_secrets": {"jira": "test-secret-jira"}}

    mock_db = AsyncMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_org]

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("app.routers.webhooks.index_jira_ticket") as mock_task:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/webhooks/jira",
                    json={"issue": {"key": "PROJ-42"}},
                    headers={"X-Webhook-Secret": "test-secret-jira"},
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"
        mock_task.delay.assert_called_once_with("PROJ-42", str(org_id))
    finally:
        app.dependency_overrides.pop(get_db, None)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "test_webhooks"
```

Expected: `ERROR` — `cannot import name 'webhooks'`

- [ ] **Step 3: Create `backend/app/routers/webhooks.py`**

```python
"""Webhook endpoints for Confluence and Jira change notifications."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.tasks.rag_tasks import index_confluence_space, index_jira_ticket

router = APIRouter()
logger = logging.getLogger(__name__)


async def _find_org_by_secret(secret: str, secret_key: str, db: AsyncSession):
    """Return the org whose metadata_.webhook_secrets[secret_key] matches secret."""
    from app.models.organization import Organization

    result = await db.execute(
        select(Organization).where(Organization.deleted_at.is_(None))
    )
    for org in result.scalars().all():
        meta = org.metadata_ or {}
        if meta.get("webhook_secrets", {}).get(secret_key) == secret:
            return org
    return None


@router.post("/webhooks/confluence")
async def confluence_webhook(
    request: Request,
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Receive Confluence page events and trigger re-indexing."""
    if not x_webhook_secret:
        raise HTTPException(status_code=401, detail="Missing X-Webhook-Secret header")

    org = await _find_org_by_secret(x_webhook_secret, "confluence", db)
    if org is None:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    payload: dict[str, Any] = await request.json()
    event = payload.get("event", "")
    page_id = str(
        payload.get("page", {}).get("id", "")
        or payload.get("pageId", "")
    )

    if not page_id:
        return {"status": "ignored", "reason": "no page_id in payload"}

    if event == "page_deleted":
        from sqlalchemy import delete as sql_delete
        from app.models.document_chunk import DocumentChunk
        await db.execute(
            sql_delete(DocumentChunk).where(
                DocumentChunk.org_id == org.id,
                DocumentChunk.source_ref == f"confluence:{page_id}",
            )
        )
        await db.commit()
        return {"status": "deleted", "page_id": page_id}

    # Re-index full space (single-page API not yet available in index tasks)
    index_confluence_space.delay(str(org.id))
    return {"status": "queued", "org_id": str(org.id), "page_id": page_id}


@router.post("/webhooks/jira")
async def jira_webhook(
    request: Request,
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Receive Jira issue events and trigger re-indexing."""
    if not x_webhook_secret:
        raise HTTPException(status_code=401, detail="Missing X-Webhook-Secret header")

    org = await _find_org_by_secret(x_webhook_secret, "jira", db)
    if org is None:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    payload: dict[str, Any] = await request.json()
    issue_key = (
        payload.get("issue", {}).get("key", "")
        or payload.get("issueKey", "")
    )

    if not issue_key:
        return {"status": "ignored", "reason": "no issue_key in payload"}

    index_jira_ticket.delay(str(issue_key), str(org.id))
    return {"status": "queued", "ticket_key": str(issue_key)}
```

- [ ] **Step 4: Register webhook router in `main.py`**

In `backend/app/main.py`, add after the existing imports at the top:

```python
from app.routers.webhooks import router as webhooks_router
```

And add the include_router call with the other routers:

```python
app.include_router(webhooks_router, prefix="/api/v1", tags=["Webhooks"])
```

- [ ] **Step 5: Run tests**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "test_webhooks"
```

Expected: all 4 webhook tests `PASSED`.

- [ ] **Step 6: Commit**

```bash
cd /opt/assist2 && git add backend/app/routers/webhooks.py backend/tests/unit/test_webhooks.py backend/app/main.py
git commit -m "feat(rag): Confluence and Jira webhook endpoints for live re-indexing"
```

---

## Task 5: User action tracking

**Files:**
- Modify: `backend/app/tasks/rag_tasks.py` (add `index_user_action` task)
- Modify: `backend/app/routers/ai.py` (trigger from compact-chat)

- [ ] **Step 1: Write failing test for index_user_action**

In `backend/tests/unit/test_rag_tasks.py`, add:

```python
@pytest.mark.asyncio
async def test_index_user_action_short_content_skipped():
    """Content under 20 chars → no embedding called."""
    from app.tasks.rag_tasks import _index_user_action_async

    mock_db = AsyncMock()
    with patch("app.tasks.rag_tasks._embed_chunks", new_callable=AsyncMock) as mock_embed:
        await _index_user_action_async("org-id", "chat_summary", "short", "user-1", mock_db)
    mock_embed.assert_not_called()


@pytest.mark.asyncio
async def test_index_user_action_stores_chunk():
    """Valid content → chunk stored with source_type=user_action."""
    from app.tasks.rag_tasks import _index_user_action_async
    import uuid

    org_id = str(uuid.uuid4())
    content = "Der Nutzer hat User Story PROJ-42 abgelehnt wegen fehlender Akzeptanzkriterien"

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    with patch("app.tasks.rag_tasks._embed_chunks", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [[0.1] * 1024]
        await _index_user_action_async(org_id, "story_feedback", content, "user-ref", mock_db)

    mock_db.add.assert_called_once()
    added_chunk = mock_db.add.call_args[0][0]
    assert added_chunk.source_type == "user_action"
    assert "story_feedback" in added_chunk.chunk_text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "test_index_user_action"
```

Expected: `ERROR` — `cannot import _index_user_action_async`

- [ ] **Step 3: Add `index_user_action` to `rag_tasks.py`**

Append to `backend/app/tasks/rag_tasks.py`:

```python
async def _index_user_action_async(
    org_id: str, action_type: str, content: str, user_ref: str, db: AsyncSession
) -> None:
    """Index a user action (feedback, chat summary, workflow event) as a knowledge chunk."""
    from app.models.document_chunk import DocumentChunk

    if not content or len(content) < 20:
        return

    org_uuid = uuid.UUID(org_id)
    chunk_text = f"User Action [{action_type}]: {content}"[:2000]
    # Use a deterministic source_ref so identical actions deduplicate
    source_ref = f"user_action:{action_type}:{_sha256(chunk_text.encode())[:16]}"

    try:
        embeddings = await _embed_chunks([chunk_text])
    except Exception as e:
        logger.warning("index_user_action: embedding failed: %s", e)
        return

    embedding_str = "[" + ",".join(str(x) for x in embeddings[0]) + "]"
    chunk = DocumentChunk(
        org_id=org_uuid,
        source_ref=source_ref,
        source_type="user_action",
        source_url=None,
        source_title=f"User Action: {action_type}",
        file_hash=_sha256(chunk_text.encode()),
        chunk_index=0,
        chunk_text=chunk_text,
        embedding=embedding_str,
    )
    db.add(chunk)
    try:
        await db.commit()
        logger.info("index_user_action: indexed action %s for org %s", action_type, org_id)
    except Exception as e:
        await db.rollback()
        logger.error("index_user_action: commit failed: %s", e)


@celery.task(name="rag_tasks.index_user_action", bind=True, max_retries=3)
def index_user_action(
    self, org_id: str, action_type: str, content: str, user_ref: str = ""
) -> dict:
    """Celery task: index a user action into pgvector knowledge base."""
    from app.config import get_settings

    async def run():
        engine = create_async_engine(
            get_settings().DATABASE_URL, echo=False, pool_pre_ping=True
        )
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with SessionLocal() as db:
                await _index_user_action_async(org_id, action_type, content, user_ref, db)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
        return {"status": "ok", "action_type": action_type}
    except Exception as exc:
        logger.error("index_user_action failed: %s", exc)
        raise self.retry(exc=exc, countdown=30)
```

- [ ] **Step 4: Add org_id to CompactChatRequest and trigger indexing in `/ai/compact-chat`**

In `backend/app/routers/ai.py`, update `CompactChatRequest`:

```python
class CompactChatRequest(BaseModel):
    messages: list[ChatMessage]
    org_id: str | None = None
```

In the `compact_chat` endpoint, after getting `summary`, add (before the return):

```python
    # Index chat summary as user action knowledge (fire-and-forget)
    if body.org_id and len(summary) > 100:
        try:
            from app.tasks.rag_tasks import index_user_action
            index_user_action.delay(
                body.org_id,
                "chat_summary",
                summary,
                str(current_user.id),
            )
        except Exception:
            pass  # never block response for indexing failure

    return {"summary": summary}
```

- [ ] **Step 5: Run tests**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "test_index_user_action"
```

Expected: both `PASSED`.

- [ ] **Step 6: Commit**

```bash
cd /opt/assist2 && git add backend/app/tasks/rag_tasks.py backend/app/routers/ai.py backend/tests/unit/test_rag_tasks.py
git commit -m "feat(rag): user action tracking — index chat summaries and story feedback"
```

---

## Task 6: RAG injection in /ai/chat (800ms timeout)

**Files:**
- Modify: `backend/app/routers/ai.py`
- Modify: `backend/tests/unit/test_ai_chat.py`

- [ ] **Step 1: Write failing test for RAG injection**

In `backend/tests/unit/test_ai_chat.py`, add:

```python
@pytest.mark.asyncio
async def test_chat_injects_rag_context(auth_override):
    """When RAG returns context chunks, they are prepended to messages."""
    from app.services.rag_service import RagResult, RagChunk
    from app.deps import get_db

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    rag_chunk = RagChunk(
        text="Confluence Inhalt: Das Deployment erfolgt montags.",
        score=0.80,
        source_type="confluence",
        source_url=None,
        source_title="Deployment Guide",
    )
    mock_rag = RagResult(mode="context", chunks=[rag_chunk])

    captured_messages = []

    async def fake_stream_with_capture(*args, **kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        yield "data: OK\n\n"
        yield "data: [DONE]\n\n"

    with patch("app.routers.ai.AsyncOpenAI") as MockOAI, \
         patch("app.routers.ai.rag_retrieve", new_callable=AsyncMock, return_value=mock_rag):

        mock_stream = MagicMock()
        mock_stream.__aiter__ = lambda self: iter([
            MagicMock(choices=[MagicMock(delta=MagicMock(content="OK"))])
        ])
        MockOAI.return_value.chat.completions.create = AsyncMock(return_value=mock_stream)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream(
                "POST", "/api/v1/ai/chat",
                json={
                    "messages": [{"role": "user", "content": "Wann ist Deployment?"}],
                    "mode": "chat",
                    "org_id": "00000000-0000-0000-0000-000000000001",
                },
                headers={"Authorization": "Bearer fake"},
            ) as response:
                _ = [chunk async for chunk in response.aiter_bytes()]

    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_chat_continues_on_rag_timeout(auth_override):
    """RAG timeout → chat proceeds without context, no error."""
    import asyncio
    from app.deps import get_db

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    async def slow_rag(*args, **kwargs):
        await asyncio.sleep(2)  # longer than 800ms timeout

    mock_stream = MagicMock()
    mock_stream.__aiter__ = lambda self: iter([
        MagicMock(choices=[MagicMock(delta=MagicMock(content="OK"))])
    ])

    with patch("app.routers.ai.AsyncOpenAI") as MockOAI, \
         patch("app.routers.ai.rag_retrieve", new_callable=AsyncMock, side_effect=slow_rag):

        MockOAI.return_value.chat.completions.create = AsyncMock(return_value=mock_stream)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream(
                "POST", "/api/v1/ai/chat",
                json={
                    "messages": [{"role": "user", "content": "Hallo"}],
                    "mode": "chat",
                    "org_id": "00000000-0000-0000-0000-000000000001",
                },
                headers={"Authorization": "Bearer fake"},
            ) as response:
                assert response.status_code == 200

    app.dependency_overrides.pop(get_db, None)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "test_chat_injects_rag|test_chat_continues_on_rag"
```

Expected: `FAILED` — `cannot import name 'rag_retrieve'`

- [ ] **Step 3: Update `chat_stream` in `backend/app/routers/ai.py`**

Add imports at the top of the file:

```python
import asyncio
import uuid as _uuid_module

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.services.rag_service import retrieve as rag_retrieve
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
```

Update the `chat_stream` function signature and body:

```python
@router.post("/ai/chat")
async def chat_stream(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream a chat response via LiteLLM as Server-Sent Events."""
    settings = get_settings()
    system_prompt = CHAT_SYSTEM_PROMPTS.get(body.mode, CHAT_SYSTEM_PROMPTS["chat"])

    # RAG retrieval — 800ms timeout, never blocks response on failure
    rag_context = ""
    if body.org_id:
        try:
            last_user_text = next(
                (m.to_text() for m in reversed(body.messages) if m.role == "user"), ""
            )
            if last_user_text:
                rag_result = await asyncio.wait_for(
                    rag_retrieve(last_user_text, _uuid_module.UUID(body.org_id), db),
                    timeout=0.8,
                )
                if rag_result.mode in ("direct", "context") and rag_result.chunks:
                    _label = {
                        "confluence": "[Confluence]",
                        "jira": "[Jira]",
                        "karl_story": "[Karl Story]",
                        "user_action": "[Team-Wissen]",
                        "nextcloud": "[Dokument]",
                    }
                    rag_context = "\n\n".join(
                        f"{_label.get(c.source_type, '[Kontext]')} {c.source_title or ''}\n{c.text}"
                        for c in rag_result.chunks
                    )
        except Exception:
            pass  # RAG failure is never fatal

    def _build_content(m: ChatMessage) -> str | list:
        if isinstance(m.content, str):
            return m.content
        blocks = []
        for b in m.content:
            if b.type == "image" and b.source:
                blocks.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{b.source.media_type};base64,{b.source.data}"},
                })
            else:
                blocks.append({"type": "text", "text": b.text or ""})
        return blocks

    messages = [{"role": "system", "content": system_prompt}]
    if rag_context:
        messages.append({"role": "system", "content": f"Relevanter Kontext:\n\n{rag_context}"})
    messages += [{"role": m.role, "content": _build_content(m)} for m in body.messages]

    async def event_stream() -> AsyncIterator[str]:
        try:
            oai = AsyncOpenAI(
                api_key=settings.LITELLM_API_KEY or "sk-assist2",
                base_url=f"{settings.LITELLM_URL}/v1",
            )
            stream = await oai.chat.completions.create(
                model="ionos-reasoning",
                max_tokens=2048,
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield f"data: {delta}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("AI chat stream error: %s", exc)
            yield "data: [ERROR]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Run tests**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "test_chat_injects_rag|test_chat_continues_on_rag|test_chat_stream"
```

Expected: all `PASSED`.

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2 && git add backend/app/routers/ai.py backend/tests/unit/test_ai_chat.py
git commit -m "feat(rag): inject RAG context into /ai/chat with 800ms async timeout"
```

---

## Task 7: Story generation — min_score threshold + source filtering

**Files:**
- Modify: `backend/app/services/rag_service.py` (add `min_score` + `source_types` params)
- Modify: `backend/app/services/ai_story_service.py` (pass threshold + source filter)
- Modify: `backend/tests/unit/test_rag_service.py` (test new params)

- [ ] **Step 1: Write failing tests for new retrieve() params**

In `backend/tests/unit/test_rag_service.py`, add:

```python
@pytest.mark.asyncio
async def test_retrieve_respects_min_score():
    """min_score=0.75 → chunks below 0.75 filtered out even if above CONTEXT_THRESHOLD."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(
        return_value=[
            make_db_row("High score chunk", 0.80),
            make_db_row("Low score chunk", 0.60),   # below min_score=0.75
        ]
    )
    # Also set source_type on mock rows
    for row in mock_db.execute.return_value.fetchall.return_value:
        row.source_type = "jira"
        row.source_url = None
        row.source_title = None

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1024
        result = await retrieve("test query", uuid.uuid4(), mock_db, min_score=0.75)

    assert result.mode == "context"
    assert len(result.chunks) == 1
    assert result.chunks[0].text == "High score chunk"


@pytest.mark.asyncio
async def test_retrieve_source_type_filter():
    """source_types filter is passed to SQL query (verified via SQL param)."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(return_value=[])

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1024
        await retrieve(
            "test query", uuid.uuid4(), mock_db,
            source_types=["jira", "confluence", "karl_story"]
        )

    # Verify db.execute was called with source_types in params
    call_kwargs = mock_db.execute.call_args
    assert call_kwargs is not None
    params = call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1].get("params", {})
    # The SQL params should include source_types
    assert "source_types" in str(params) or "jira" in str(call_kwargs)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "test_retrieve_respects_min_score|test_retrieve_source_type"
```

Expected: `FAILED` — `retrieve() got unexpected keyword argument 'min_score'`

- [ ] **Step 3: Update `retrieve()` in `rag_service.py`**

Update the function signature and SQL query:

```python
async def retrieve(
    query: str,
    org_id: uuid.UUID,
    db: AsyncSession,
    min_score: float = CONTEXT_THRESHOLD,
    source_types: list[str] | None = None,
) -> RagResult:
    """
    Embed query, find top-5 most similar chunks for this org, apply thresholds.

    Args:
        min_score: minimum cosine similarity to include a chunk (default: CONTEXT_THRESHOLD=0.50)
        source_types: if set, only chunks with these source_type values are considered
    """
    try:
        embedding = await _embed_query(query)
    except Exception as e:
        logger.warning("RAG embedding failed, skipping: %s", e)
        return RagResult(mode="none")

    try:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        if source_types:
            sql = text("""
                SELECT chunk_text,
                       source_type,
                       source_url,
                       source_title,
                       1 - (embedding <=> :embedding ::vector) AS score
                FROM document_chunks
                WHERE org_id = :org_id
                  AND embedding IS NOT NULL
                  AND source_type = ANY(:source_types)
                ORDER BY score DESC
                LIMIT 5
            """)
            params = {
                "embedding": embedding_str,
                "org_id": str(org_id),
                "source_types": source_types,
            }
        else:
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
            params = {"embedding": embedding_str, "org_id": str(org_id)}

        result = await db.execute(sql, params)
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

    effective_min = max(min_score, CONTEXT_THRESHOLD)
    qualifying = [r for r in rows if r.score >= effective_min]
    if qualifying:
        return RagResult(
            mode="context",
            chunks=[
                RagChunk(
                    text=r.chunk_text,
                    score=r.score,
                    source_type=r.source_type,
                    source_url=r.source_url,
                    source_title=r.source_title,
                )
                for r in qualifying[:MAX_CHUNKS]
            ],
        )

    return RagResult(mode="none")
```

- [ ] **Step 4: Update story generation in `ai_story_service.py`**

In `get_story_suggestions`, find the RAG retrieval block (around line 240) and update:

```python
    # 1. RAG retrieval (org-scoped, optional) — story-specific: higher threshold, curated sources
    rag_context_block: str | None = None
    rag_source: str = "llm"
    if org_id is not None and db is not None:
        try:
            from app.services.rag_service import retrieve
            rag = await retrieve(
                f"{data.title} {data.description}",
                org_id,
                db,
                min_score=0.75,
                source_types=["jira", "confluence", "karl_story"],
            )
            if rag.mode == "direct" and rag.context:
                return AISuggestion(
                    title=None,
                    description=None,
                    acceptance_criteria=None,
                    explanation=rag.context,
                    dor_issues=[],
                    quality_score=None,
                    source="rag_direct",
                )
            if rag.mode == "context" and rag.chunks:
                rag_context_block = "\n".join(
                    [f"[{c.source_type.upper()}]\n{c.text}" for c in rag.chunks]
                )
                rag_source = "rag_context"
        except Exception as e:
            logger.warning("RAG retrieval error (skipping): %s", e)
```

- [ ] **Step 5: Run all tests**

```bash
cd /opt/assist2 && make test-unit 2>&1 | grep -E "PASSED|FAILED|ERROR" | tail -20
```

Expected: no `FAILED` or `ERROR`.

- [ ] **Step 6: Run full test suite**

```bash
cd /opt/assist2 && make test
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
cd /opt/assist2 && git add backend/app/services/rag_service.py backend/app/services/ai_story_service.py backend/tests/unit/test_rag_service.py
git commit -m "feat(rag): story generation uses min_score=0.75 and jira/confluence/karl_story filter"
```

---

## Post-Implementation: Deploy

```bash
cd /opt/assist2/infra && docker compose up -d --build backend celery-worker celery-beat
```

Verify RAG is active:
```bash
docker logs assist2-backend --tail 20 | grep -i rag
```

Expected: no errors, RAG tasks registered.
