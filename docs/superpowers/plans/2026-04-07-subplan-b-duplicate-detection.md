# Sub-Plan B: Duplicate Detection + pgvector Search

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic story embedding generation and duplicate detection to assist2, enabling users to check whether a story already exists or is semantically similar to existing stories.

**Architecture:** Stories are embedded (BAAI/bge-m3 via LiteLLM) asynchronously by a Celery task triggered on create/update. The `/check-duplicates` endpoint performs pgvector cosine similarity search in the backend, then passes top candidates to a LangGraph workflow for LLM-based semantic comparison. Results are returned as structured `{duplicates, similar}` response.

**Tech Stack:** FastAPI, SQLAlchemy (asyncpg), pgvector (vector cosine ops), Celery, httpx, LiteLLM (ionos-embed alias), LangGraph 0.2.x, Pydantic v2

---

## File Map

| Status | Path | Responsibility |
|--------|------|----------------|
| **Create** | `backend/app/models/story_embedding.py` | SQLAlchemy ORM model for `story_embeddings` table |
| **Create** | `backend/app/services/embedding_service.py` | Async logic: compute content, SHA256, call LiteLLM, upsert row, pgvector similarity query |
| **Create** | `backend/app/tasks/embedding_tasks.py` | Celery task `embed_story_task` (asyncio.run wrapper around embedding_service) |
| **Create** | `langgraph-service/app/nodes/semantic_comparator.py` | LangGraph node: LLM-based pairwise comparison of story candidates |
| **Create** | `langgraph-service/app/workflows/duplicate_check.py` | LangGraph StateGraph: semantic_comparator → format_results → END |
| **Create** | `langgraph-service/tests/test_duplicate_check.py` | Tests for schemas, workflow, and endpoint |
| **Modify** | `backend/app/models/__init__.py` (or equivalent import) | Import StoryEmbedding so SQLAlchemy registers the model |
| **Modify** | `backend/app/routers/user_stories.py` | Fire `embed_story_task.delay()` on create and on update when title/description/acceptance_criteria change |
| **Modify** | `backend/app/routers/evaluations.py` | Add `POST /evaluations/stories/{story_id}/check-duplicates` |
| **Modify** | `backend/app/schemas/evaluation.py` | Add `DuplicateCandidate`, `DuplicateCheckResponse` |
| **Modify** | `backend/app/celery_app.py` | Add `"app.tasks.embedding_tasks"` to `include` list |
| **Modify** | `langgraph-service/app/schemas/evaluation.py` | Add `DuplicateCheckRequest`, `DuplicateCheckResponse`, `DuplicateCandidate` |
| **Modify** | `langgraph-service/app/routers/workflows.py` | Add `POST /workflows/check-duplicates` |

---

## Task 1: StoryEmbedding ORM Model

**Files:**
- Create: `backend/app/models/story_embedding.py`

The `story_embeddings` table already exists (migration 0030). This model maps to it using the same `Text`-as-proxy pattern as `DocumentChunk.embedding`.

- [ ] **Step 1: Write the model**

Create `backend/app/models/story_embedding.py`:

```python
"""ORM model for pgvector story embeddings."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StoryEmbedding(Base):
    __tablename__ = "story_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True
    )
    # DB type is vector(1024) — ORM uses Text as proxy; raw SQL with ::vector cast for similarity ops
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_used: Mapped[str] = mapped_column(
        String(100), nullable=False, default="ionos-embed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 2: Verify the model imports cleanly**

```bash
cd infra && docker compose -f docker-compose.dev.yml exec backend python -c "from app.models.story_embedding import StoryEmbedding; print('OK', StoryEmbedding.__tablename__)"
```

Expected output: `OK story_embeddings`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/story_embedding.py
git commit -m "feat(embeddings): add StoryEmbedding ORM model (Text proxy for vector(1024))"
```

---

## Task 2: Embedding Service (Async Core Logic)

**Files:**
- Create: `backend/app/services/embedding_service.py`

This module contains two pure async functions:
1. `embed_story(story_id, org_id, db)` — compute content → SHA256 → skip if unchanged → call LiteLLM → upsert `story_embeddings`
2. `find_similar_stories(story_id, org_id, db)` — load embedding for a story → pgvector cosine similarity query → return list of `(story_id, similarity)` tuples

- [ ] **Step 1: Write the service**

Create `backend/app/services/embedding_service.py`:

```python
"""Service: generate story embeddings and run pgvector similarity search."""
from __future__ import annotations

import hashlib
import logging
import uuid

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.story_embedding import StoryEmbedding
from app.models.user_story import UserStory

logger = logging.getLogger(__name__)

EMBED_MODEL = "ionos-embed"
EMBED_DIMS = 1024
DUPLICATE_THRESHOLD = 0.85
SIMILAR_THRESHOLD = 0.70
TOP_K = 10


def _content_for_story(story: UserStory) -> str:
    """Build the text that gets embedded for a story."""
    return f"{story.title}\n{story.description or ''}\n{story.acceptance_criteria or ''}"


def _sha256(text_: str) -> str:
    return hashlib.sha256(text_.encode()).hexdigest()


async def _call_litellm_embed(text_: str) -> list[float]:
    """Call LiteLLM /v1/embeddings synchronously via httpx. Returns 1024-dim vector."""
    settings = get_settings()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.LITELLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LITELLM_API_KEY}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.LITELLM_URL}/v1/embeddings",
            headers=headers,
            json={"model": EMBED_MODEL, "input": [text_]},
        )
        resp.raise_for_status()

    data = resp.json()["data"]
    embedding: list[float] = data[0]["embedding"]
    return embedding


async def embed_story(story_id: str, org_id: str, db: AsyncSession) -> None:
    """
    Generate and upsert the embedding for a story.
    Skips silently if the content has not changed since the last embedding.
    """
    story_uuid = uuid.UUID(story_id)
    org_uuid = uuid.UUID(org_id)

    result = await db.execute(select(UserStory).where(UserStory.id == story_uuid))
    story = result.scalar_one_or_none()
    if story is None:
        logger.warning("embed_story: story %s not found, skipping", story_id)
        return

    content = _content_for_story(story)
    content_hash = _sha256(content)

    # Check existing embedding — skip if content unchanged
    existing_result = await db.execute(
        select(StoryEmbedding).where(StoryEmbedding.story_id == story_uuid)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None and existing.content_hash == content_hash:
        logger.debug("embed_story: content unchanged for story %s, skipping", story_id)
        return

    try:
        embedding_floats = await _call_litellm_embed(content)
    except Exception as e:
        logger.error("embed_story: LiteLLM call failed for story %s: %s", story_id, e)
        raise

    embedding_str = "[" + ",".join(str(x) for x in embedding_floats) + "]"

    if existing is None:
        row = StoryEmbedding(
            organization_id=org_uuid,
            story_id=story_uuid,
            embedding=embedding_str,
            content_hash=content_hash,
            model_used=EMBED_MODEL,
        )
        db.add(row)
    else:
        existing.embedding = embedding_str
        existing.content_hash = content_hash
        existing.model_used = EMBED_MODEL

    await db.commit()
    logger.info("embed_story: upserted embedding for story %s", story_id)


async def find_similar_stories(
    story_id: str, org_id: str, db: AsyncSession
) -> list[tuple[uuid.UUID, float]]:
    """
    Run pgvector cosine similarity search against story_embeddings.
    Returns up to TOP_K results as (story_id_uuid, similarity_float) tuples,
    ordered by descending similarity, excluding the query story itself.
    Only returns rows with similarity >= SIMILAR_THRESHOLD.
    """
    story_uuid = uuid.UUID(story_id)
    org_uuid = uuid.UUID(org_id)

    # Load the query embedding
    emb_result = await db.execute(
        select(StoryEmbedding.embedding).where(StoryEmbedding.story_id == story_uuid)
    )
    embedding_str = emb_result.scalar_one_or_none()
    if embedding_str is None:
        logger.warning("find_similar_stories: no embedding for story %s", story_id)
        return []

    result = await db.execute(
        text("""
            SELECT story_id, 1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
            FROM story_embeddings
            WHERE organization_id = :org_id
              AND story_id != :exclude_id
              AND 1 - (embedding <=> CAST(:query_vec AS vector)) >= :threshold
            ORDER BY similarity DESC
            LIMIT :limit
        """),
        {
            "query_vec": embedding_str,
            "org_id": str(org_uuid),
            "exclude_id": str(story_uuid),
            "threshold": SIMILAR_THRESHOLD,
            "limit": TOP_K,
        },
    )
    rows = result.fetchall()
    return [(uuid.UUID(str(row[0])), float(row[1])) for row in rows]
```

- [ ] **Step 2: Verify the service imports**

```bash
cd infra && docker compose -f docker-compose.dev.yml exec backend python -c "from app.services.embedding_service import embed_story, find_similar_stories; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/embedding_service.py
git commit -m "feat(embeddings): add embedding_service with embed_story and find_similar_stories"
```

---

## Task 3: Celery Task for Story Embedding

**Files:**
- Create: `backend/app/tasks/embedding_tasks.py`
- Modify: `backend/app/celery_app.py`

The Celery task wraps the async `embed_story` service using the same `asyncio.run + create_async_engine` pattern as `rag_tasks.py`.

- [ ] **Step 1: Write the Celery task**

Create `backend/app/tasks/embedding_tasks.py`:

```python
"""Celery task: generate and upsert story embedding via LiteLLM ionos-embed."""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="embedding_tasks.embed_story", bind=True, max_retries=3)
def embed_story_task(self, story_id: str, org_id: str) -> dict:
    """Celery task: embed a single story and upsert into story_embeddings."""
    from app.config import get_settings

    async def run() -> None:
        from app.services.embedding_service import embed_story

        engine = create_async_engine(
            get_settings().DATABASE_URL, echo=False, pool_pre_ping=True
        )
        SessionLocal = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        try:
            async with SessionLocal() as db:
                await embed_story(story_id, org_id, db)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
        return {"status": "ok", "story_id": story_id}
    except Exception as exc:
        logger.error("embed_story_task failed for story %s: %s", story_id, exc)
        raise self.retry(exc=exc, countdown=60)
```

- [ ] **Step 2: Register the task in celery_app.py**

In `backend/app/celery_app.py`, add `"app.tasks.embedding_tasks"` to the `include` list:

```python
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
        "app.tasks.embedding_tasks",
    ]
)
```

- [ ] **Step 3: Verify the task registers**

```bash
cd infra && docker compose -f docker-compose.dev.yml exec celery python -c "from app.tasks.embedding_tasks import embed_story_task; print('OK', embed_story_task.name)"
```

Expected output: `OK embedding_tasks.embed_story`

- [ ] **Step 4: Commit**

```bash
git add backend/app/tasks/embedding_tasks.py backend/app/celery_app.py
git commit -m "feat(embeddings): add embed_story_task Celery task and register in celery_app"
```

---

## Task 4: Trigger Embedding on Story Create and Update

**Files:**
- Modify: `backend/app/routers/user_stories.py`

Add `embed_story_task.delay()` to `create_user_story` (always) and to `update_user_story` (only when `title`, `description`, or `acceptance_criteria` change — the `needs_regen` flag already detects this).

- [ ] **Step 1: Add the import at the top of user_stories.py**

Find the existing import block that includes `analyze_story_task` and add the new import on the next line:

```python
from app.tasks.agent_tasks import analyze_story_task
from app.tasks.embedding_tasks import embed_story_task   # add this line
```

- [ ] **Step 2: Fire embed on story create**

In `create_user_story`, after the existing `analyze_story_task.delay(...)` call, add:

```python
    analyze_story_task.delay(str(story.id), str(org_id))
    embed_story_task.delay(str(story.id), str(org_id))   # add this line
    return UserStoryRead.model_validate(story)
```

- [ ] **Step 3: Fire embed on story update when content fields change**

In `update_user_story`, the `needs_regen` variable is already computed as:

```python
    update_data = data.model_dump(exclude_unset=True)
    doc_fields = {"title", "description", "acceptance_criteria"}
    needs_regen = bool(doc_fields & update_data.keys())
```

At the bottom of `update_user_story`, just before `return UserStoryRead.model_validate(story)`, add the conditional embed dispatch inside the existing `if needs_regen:` block:

```python
    if needs_regen:
        background_tasks.add_task(
            _regenerate_docs_bg, story.id, story.organization_id, story.title, story.description, story.acceptance_criteria
        )
        embed_story_task.delay(str(story.id), str(story.organization_id))   # add this line

    return UserStoryRead.model_validate(story)
```

- [ ] **Step 4: Verify no syntax errors**

```bash
cd infra && docker compose -f docker-compose.dev.yml exec backend python -c "from app.routers.user_stories import router; print('OK')"
```

Expected output: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/user_stories.py
git commit -m "feat(embeddings): trigger embed_story_task on story create and content update"
```

---

## Task 5: Backend Schemas for Duplicate Check Response

**Files:**
- Modify: `backend/app/schemas/evaluation.py`

Add two new Pydantic models to the existing schema file. `DuplicateCandidate` represents one matching story; `DuplicateCheckResponse` is the endpoint's return type.

- [ ] **Step 1: Append the new schemas to backend/app/schemas/evaluation.py**

Open `backend/app/schemas/evaluation.py` and append at the bottom:

```python

class DuplicateCandidate(BaseModel):
    story_id: uuid.UUID
    title: str
    similarity_score: float
    explanation: str


class DuplicateCheckResponse(BaseModel):
    duplicates: list[DuplicateCandidate]
    similar: list[DuplicateCandidate]
```

- [ ] **Step 2: Verify import**

```bash
cd infra && docker compose -f docker-compose.dev.yml exec backend python -c "from app.schemas.evaluation import DuplicateCandidate, DuplicateCheckResponse; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/evaluation.py
git commit -m "feat(embeddings): add DuplicateCandidate and DuplicateCheckResponse schemas"
```

---

## Task 6: LangGraph Schemas for Duplicate Check

**Files:**
- Modify: `langgraph-service/app/schemas/evaluation.py`

Add `DuplicateCandidate`, `DuplicateCheckRequest`, and `DuplicateCheckResponse` to the LangGraph service's schema file.

- [ ] **Step 1: Append the new schemas to langgraph-service/app/schemas/evaluation.py**

Open `langgraph-service/app/schemas/evaluation.py` and append at the bottom:

```python

class DuplicateCandidate(BaseModel):
    story_id: str
    title: str
    description: str = ""
    acceptance_criteria: str = ""
    similarity_score: float


class DuplicateCheckRequest(BaseModel):
    story_id: str
    org_id: str
    title: str
    description: str = ""
    acceptance_criteria: str = ""
    candidates: list[DuplicateCandidate]


class DuplicateCheckResponse(BaseModel):
    duplicates: list[DuplicateCandidate]
    similar: list[DuplicateCandidate]
```

Note: `DuplicateCandidate` in the LangGraph service uses `str` (not `uuid.UUID`) for `story_id` because LangGraph nodes work with plain dicts and the boundary serialization is JSON strings.

- [ ] **Step 2: Verify import**

```bash
docker run --rm \
  -v "$(pwd)/langgraph-service:/app" \
  -w /app \
  python:3.12-slim \
  sh -c "pip install -q pydantic==2.10.4 && python -c 'from app.schemas.evaluation import DuplicateCandidate, DuplicateCheckRequest, DuplicateCheckResponse; print(\"OK\")'"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add langgraph-service/app/schemas/evaluation.py
git commit -m "feat(embeddings): add DuplicateCandidate, DuplicateCheckRequest, DuplicateCheckResponse to LangGraph schemas"
```

---

## Task 7: LangGraph Node — semantic_comparator

**Files:**
- Create: `langgraph-service/app/nodes/semantic_comparator.py`

This node receives the full `DuplicateCheckRequest` candidates from state and uses LLM (claude-sonnet-4-6 via LiteLLM) to classify each candidate as `duplicate` or `similar`, enriching each with a human-readable `explanation`. It writes back `comparison_results: list[dict]` to state.

- [ ] **Step 1: Write the failing test first**

Create `langgraph-service/tests/test_duplicate_check.py` with just the node test initially:

```python
"""Tests for duplicate detection workflow and node."""
import json
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Task 7: semantic_comparator node
# ---------------------------------------------------------------------------

def _make_comparator_response(results: list[dict]) -> tuple[str, dict]:
    return json.dumps({"comparisons": results}), {
        "input_tokens": 150,
        "output_tokens": 80,
        "model": "claude-sonnet-4-6",
    }


def test_semantic_comparator_classifies_candidates():
    from app.nodes.semantic_comparator import semantic_comparator

    state = {
        "story_id": "story-001",
        "org_id": "org-001",
        "title": "Als Nutzer möchte ich mein Passwort zurücksetzen",
        "description": "Über einen E-Mail-Link kann ich ein neues Passwort setzen",
        "acceptance_criteria": "Gegeben ich bin ausgeloggt, wenn ich 'Passwort vergessen' klicke, dann erhalte ich eine E-Mail",
        "candidates": [
            {
                "story_id": "story-002",
                "title": "Passwort-Reset per E-Mail",
                "description": "User kann Passwort über E-Mail zurücksetzen",
                "acceptance_criteria": "Reset-Link per E-Mail",
                "similarity_score": 0.91,
            },
            {
                "story_id": "story-003",
                "title": "Passwort ändern im Profil",
                "description": "User kann Passwort im Profil ändern",
                "acceptance_criteria": "Formular mit altem und neuem Passwort",
                "similarity_score": 0.74,
            },
        ],
        "comparison_results": [],
    }

    llm_response = _make_comparator_response([
        {
            "story_id": "story-002",
            "classification": "duplicate",
            "explanation": "Beide Stories beschreiben denselben Passwort-Reset via E-Mail.",
        },
        {
            "story_id": "story-003",
            "classification": "similar",
            "explanation": "Ähnliches Thema, aber anderer Kontext (Profil vs. vergessenes Passwort).",
        },
    ])

    with patch("app.llm.client.LiteLLMClient.chat", return_value=llm_response):
        result = semantic_comparator(state)

    assert "comparison_results" in result
    assert len(result["comparison_results"]) == 2
    classifications = {r["story_id"]: r["classification"] for r in result["comparison_results"]}
    assert classifications["story-002"] == "duplicate"
    assert classifications["story-003"] == "similar"
    for r in result["comparison_results"]:
        assert r["explanation"] != ""


def test_semantic_comparator_handles_empty_candidates():
    from app.nodes.semantic_comparator import semantic_comparator

    state = {
        "story_id": "story-001",
        "org_id": "org-001",
        "title": "Neues Feature",
        "description": "",
        "acceptance_criteria": "",
        "candidates": [],
        "comparison_results": [],
    }

    result = semantic_comparator(state)
    assert result["comparison_results"] == []


def test_semantic_comparator_handles_llm_failure():
    from app.nodes.semantic_comparator import semantic_comparator
    from app.llm.client import LLMCallError

    state = {
        "story_id": "story-001",
        "org_id": "org-001",
        "title": "Test",
        "description": "",
        "acceptance_criteria": "",
        "candidates": [
            {
                "story_id": "story-002",
                "title": "Test 2",
                "description": "",
                "acceptance_criteria": "",
                "similarity_score": 0.88,
            }
        ],
        "comparison_results": [],
    }

    with patch("app.llm.client.LiteLLMClient.chat", side_effect=LLMCallError("timeout")):
        result = semantic_comparator(state)

    # On LLM failure: each candidate is kept with classification="similar" and a fallback explanation
    assert len(result["comparison_results"]) == 1
    assert result["comparison_results"][0]["story_id"] == "story-002"
    assert result["comparison_results"][0]["classification"] in ("duplicate", "similar")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
docker run --rm \
  -v "$(pwd)/langgraph-service:/app" \
  -w /app \
  python:3.12-slim \
  sh -c "pip install -q fastapi==0.115.6 langgraph==0.2.73 langchain-core==0.3.28 httpx==0.27.2 pydantic==2.10.4 pydantic-settings==2.7.0 pytest==8.3.4 pytest-mock==3.14.0 && python -m pytest tests/test_duplicate_check.py::test_semantic_comparator_classifies_candidates -v"
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.nodes.semantic_comparator'`

- [ ] **Step 3: Implement the node**

Create `langgraph-service/app/nodes/semantic_comparator.py`:

```python
"""LangGraph node: LLM-based semantic comparison of pgvector candidates."""
from __future__ import annotations

import json
import logging

from app.llm.client import LiteLLMClient, LLMCallError

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are an expert in requirements engineering. Your task is to compare a query user story
against a list of candidate stories to detect duplicates.

For each candidate, classify it as:
- "duplicate": The candidate covers the same user need and would be redundant with the query story
- "similar": The candidate is related or overlapping but covers a meaningfully different scope

Respond ONLY with a JSON object in exactly this format (no extra characters):
{
  "comparisons": [
    {
      "story_id": "<story_id from input>",
      "classification": "duplicate" | "similar",
      "explanation": "<1-2 sentences explaining the classification>"
    }
  ]
}
"""


def semantic_comparator(state: dict) -> dict:
    """
    LangGraph node — LLM pairwise comparison of story candidates.
    Input state keys: story_id, org_id, title, description, acceptance_criteria, candidates
    Output state keys: comparison_results
    """
    candidates: list[dict] = state.get("candidates", [])

    if not candidates:
        return {"comparison_results": []}

    query_text = (
        f"Query Story:\n"
        f"Title: {state.get('title', '')}\n"
        f"Description: {state.get('description', '')}\n"
        f"Acceptance Criteria: {state.get('acceptance_criteria', '')}\n\n"
        f"Candidates:\n"
    )
    for c in candidates:
        query_text += (
            f"- story_id: {c['story_id']}\n"
            f"  Title: {c['title']}\n"
            f"  Description: {c.get('description', '')}\n"
            f"  Acceptance Criteria: {c.get('acceptance_criteria', '')}\n"
            f"  Vector similarity: {c['similarity_score']:.3f}\n\n"
        )

    client = LiteLLMClient()
    try:
        text, _usage = client.chat(
            model="claude-sonnet-4-6",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": query_text},
            ],
            max_tokens=1024,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        data = json.loads(text)
        comparisons: list[dict] = data.get("comparisons", [])
        # Ensure all candidates are present even if LLM omitted some
        returned_ids = {c["story_id"] for c in comparisons}
        for candidate in candidates:
            if candidate["story_id"] not in returned_ids:
                comparisons.append({
                    "story_id": candidate["story_id"],
                    "classification": "similar",
                    "explanation": "Classification unavailable — defaulting to similar.",
                })
        return {"comparison_results": comparisons}

    except LLMCallError as e:
        logger.error("semantic_comparator: LLM call failed: %s", e)
        # Fallback: return all candidates as "similar" with error explanation
        fallback = [
            {
                "story_id": c["story_id"],
                "classification": "similar",
                "explanation": f"LLM comparison unavailable: {e}",
            }
            for c in candidates
        ]
        return {"comparison_results": fallback}

    except Exception as e:
        logger.error("semantic_comparator: unexpected error: %s", e)
        fallback = [
            {
                "story_id": c["story_id"],
                "classification": "similar",
                "explanation": f"Comparison failed: {e}",
            }
            for c in candidates
        ]
        return {"comparison_results": fallback}
```

- [ ] **Step 4: Run the node tests to verify they pass**

```bash
docker run --rm \
  -v "$(pwd)/langgraph-service:/app" \
  -w /app \
  python:3.12-slim \
  sh -c "pip install -q fastapi==0.115.6 langgraph==0.2.73 langchain-core==0.3.28 httpx==0.27.2 pydantic==2.10.4 pydantic-settings==2.7.0 pytest==8.3.4 pytest-mock==3.14.0 && python -m pytest tests/test_duplicate_check.py::test_semantic_comparator_classifies_candidates tests/test_duplicate_check.py::test_semantic_comparator_handles_empty_candidates tests/test_duplicate_check.py::test_semantic_comparator_handles_llm_failure -v"
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add langgraph-service/app/nodes/semantic_comparator.py langgraph-service/tests/test_duplicate_check.py
git commit -m "feat(embeddings): add semantic_comparator LangGraph node with tests"
```

---

## Task 8: LangGraph Workflow — duplicate_check

**Files:**
- Create: `langgraph-service/app/workflows/duplicate_check.py`

Two-node graph: `semantic_comparator` → `format_results` → END. `format_results` is a pure formatting node that splits `comparison_results` into `duplicates` and `similar` lists using the `similarity_score` from the input candidates.

- [ ] **Step 1: Write the failing workflow test**

Append to `langgraph-service/tests/test_duplicate_check.py`:

```python
# ---------------------------------------------------------------------------
# Task 8: duplicate_check workflow
# ---------------------------------------------------------------------------

def test_run_duplicate_check_returns_structured_response():
    from app.workflows.duplicate_check import run_duplicate_check
    from app.schemas.evaluation import DuplicateCheckRequest, DuplicateCandidate

    request = DuplicateCheckRequest(
        story_id="story-001",
        org_id="org-001",
        title="Passwort zurücksetzen",
        description="User kann Passwort via E-Mail zurücksetzen",
        acceptance_criteria="Reset-Link wird per E-Mail gesendet",
        candidates=[
            DuplicateCandidate(
                story_id="story-002",
                title="Passwort-Reset",
                description="Reset via E-Mail",
                acceptance_criteria="E-Mail mit Link",
                similarity_score=0.92,
            ),
            DuplicateCandidate(
                story_id="story-003",
                title="Passwort ändern",
                description="Passwort im Profil ändern",
                acceptance_criteria="Formular mit altem Passwort",
                similarity_score=0.75,
            ),
        ],
    )

    llm_response = _make_comparator_response([
        {
            "story_id": "story-002",
            "classification": "duplicate",
            "explanation": "Selber Anwendungsfall.",
        },
        {
            "story_id": "story-003",
            "classification": "similar",
            "explanation": "Anderer Kontext.",
        },
    ])

    with patch("app.llm.client.LiteLLMClient.chat", return_value=llm_response):
        response = run_duplicate_check(request)

    assert len(response.duplicates) == 1
    assert response.duplicates[0].story_id == "story-002"
    assert response.duplicates[0].similarity_score == 0.92
    assert "Selber Anwendungsfall" in response.duplicates[0].explanation

    assert len(response.similar) == 1
    assert response.similar[0].story_id == "story-003"


def test_run_duplicate_check_empty_candidates():
    from app.workflows.duplicate_check import run_duplicate_check
    from app.schemas.evaluation import DuplicateCheckRequest

    request = DuplicateCheckRequest(
        story_id="story-001",
        org_id="org-001",
        title="Ganz neue Story",
        description="Kein Treffer erwartet",
        acceptance_criteria="",
        candidates=[],
    )

    response = run_duplicate_check(request)
    assert response.duplicates == []
    assert response.similar == []
```

- [ ] **Step 2: Run the workflow tests to verify they fail**

```bash
docker run --rm \
  -v "$(pwd)/langgraph-service:/app" \
  -w /app \
  python:3.12-slim \
  sh -c "pip install -q fastapi==0.115.6 langgraph==0.2.73 langchain-core==0.3.28 httpx==0.27.2 pydantic==2.10.4 pydantic-settings==2.7.0 pytest==8.3.4 pytest-mock==3.14.0 && python -m pytest tests/test_duplicate_check.py::test_run_duplicate_check_returns_structured_response tests/test_duplicate_check.py::test_run_duplicate_check_empty_candidates -v"
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.workflows.duplicate_check'`

- [ ] **Step 3: Implement the workflow**

Create `langgraph-service/app/workflows/duplicate_check.py`:

```python
"""LangGraph workflow: semantic duplicate detection."""
from __future__ import annotations

import logging
from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.nodes.semantic_comparator import semantic_comparator
from app.schemas.evaluation import (
    DuplicateCandidate,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)

logger = logging.getLogger(__name__)


class DuplicateCheckState(TypedDict):
    # Input
    story_id: str
    org_id: str
    title: str
    description: str
    acceptance_criteria: str
    candidates: list[dict]
    # Intermediate: candidate lookup by story_id for enrichment
    candidate_map: dict  # story_id -> DuplicateCandidate dict
    # Output
    comparison_results: list[dict]
    duplicates: list[dict]
    similar: list[dict]


def format_results(state: DuplicateCheckState) -> dict:
    """
    Pure formatting node.
    Splits comparison_results into duplicates and similar lists,
    enriching each entry with the original similarity_score from candidate_map.
    """
    candidate_map: dict = state.get("candidate_map", {})
    comparison_results: list[dict] = state.get("comparison_results", [])

    duplicates: list[dict] = []
    similar: list[dict] = []

    for result in comparison_results:
        sid = result["story_id"]
        original = candidate_map.get(sid, {})
        enriched = {
            "story_id": sid,
            "title": original.get("title", ""),
            "similarity_score": original.get("similarity_score", 0.0),
            "explanation": result.get("explanation", ""),
        }
        if result.get("classification") == "duplicate":
            duplicates.append(enriched)
        else:
            similar.append(enriched)

    return {"duplicates": duplicates, "similar": similar}


def _build_graph() -> StateGraph:
    g = StateGraph(DuplicateCheckState)
    g.add_node("semantic_comparator", semantic_comparator)
    g.add_node("format_results", format_results)
    g.set_entry_point("semantic_comparator")
    g.add_edge("semantic_comparator", "format_results")
    g.add_edge("format_results", END)
    return g


_compiled_graph = _build_graph().compile()


def run_duplicate_check(request: DuplicateCheckRequest) -> DuplicateCheckResponse:
    """
    Execute the duplicate check StateGraph synchronously.
    Accepts a DuplicateCheckRequest with pre-fetched candidates (from pgvector search).
    Returns a DuplicateCheckResponse with classified duplicates and similar stories.
    """
    candidates_as_dicts = [c.model_dump() for c in request.candidates]
    candidate_map = {c["story_id"]: c for c in candidates_as_dicts}

    initial_state: DuplicateCheckState = {
        "story_id": request.story_id,
        "org_id": request.org_id,
        "title": request.title,
        "description": request.description,
        "acceptance_criteria": request.acceptance_criteria,
        "candidates": candidates_as_dicts,
        "candidate_map": candidate_map,
        "comparison_results": [],
        "duplicates": [],
        "similar": [],
    }

    logger.info(
        "Starting duplicate check workflow story_id=%s org_id=%s candidates=%d",
        request.story_id,
        request.org_id,
        len(request.candidates),
    )
    final_state = _compiled_graph.invoke(initial_state)
    logger.info(
        "Completed duplicate check story_id=%s duplicates=%d similar=%d",
        request.story_id,
        len(final_state["duplicates"]),
        len(final_state["similar"]),
    )

    duplicates = [DuplicateCandidate(**d) for d in final_state["duplicates"]]
    similar = [DuplicateCandidate(**s) for s in final_state["similar"]]

    return DuplicateCheckResponse(duplicates=duplicates, similar=similar)
```

- [ ] **Step 4: Run all duplicate check tests**

```bash
docker run --rm \
  -v "$(pwd)/langgraph-service:/app" \
  -w /app \
  python:3.12-slim \
  sh -c "pip install -q fastapi==0.115.6 langgraph==0.2.73 langchain-core==0.3.28 httpx==0.27.2 pydantic==2.10.4 pydantic-settings==2.7.0 pytest==8.3.4 pytest-mock==3.14.0 && python -m pytest tests/test_duplicate_check.py -v"
```

Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add langgraph-service/app/workflows/duplicate_check.py langgraph-service/tests/test_duplicate_check.py
git commit -m "feat(embeddings): add duplicate_check LangGraph workflow with format_results node"
```

---

## Task 9: LangGraph Endpoint — POST /workflows/check-duplicates

**Files:**
- Modify: `langgraph-service/app/routers/workflows.py`

Add the endpoint. Same pattern as `POST /workflows/evaluate`: `_verify_api_key` dependency, sync handler, delegates to `run_duplicate_check`.

- [ ] **Step 1: Write the failing endpoint test**

Append to `langgraph-service/tests/test_duplicate_check.py`:

```python
# ---------------------------------------------------------------------------
# Task 9: /workflows/check-duplicates endpoint
# ---------------------------------------------------------------------------

def test_check_duplicates_endpoint_returns_200():
    import os
    os.environ["LANGGRAPH_API_KEY"] = "test-secret"

    from fastapi.testclient import TestClient
    from app.main import app

    llm_response = _make_comparator_response([
        {
            "story_id": "story-abc",
            "classification": "duplicate",
            "explanation": "Selber Anwendungsfall.",
        },
    ])

    payload = {
        "story_id": "story-999",
        "org_id": "org-001",
        "title": "Passwort zurücksetzen",
        "description": "via E-Mail",
        "acceptance_criteria": "E-Mail wird gesendet",
        "candidates": [
            {
                "story_id": "story-abc",
                "title": "Passwort Reset",
                "description": "via E-Mail",
                "acceptance_criteria": "",
                "similarity_score": 0.91,
            }
        ],
    }

    with patch("app.llm.client.LiteLLMClient.chat", return_value=llm_response):
        client = TestClient(app)
        response = client.post(
            "/workflows/check-duplicates",
            json=payload,
            headers={"X-API-Key": "test-secret"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "duplicates" in data
    assert "similar" in data
    assert data["duplicates"][0]["story_id"] == "story-abc"


def test_check_duplicates_endpoint_rejects_missing_api_key():
    from fastapi.testclient import TestClient
    from app.main import app

    payload = {
        "story_id": "story-999",
        "org_id": "org-001",
        "title": "Test",
        "description": "",
        "acceptance_criteria": "",
        "candidates": [],
    }

    client = TestClient(app)
    response = client.post("/workflows/check-duplicates", json=payload)
    assert response.status_code == 401
```

- [ ] **Step 2: Run the endpoint tests to verify they fail**

```bash
docker run --rm \
  -v "$(pwd)/langgraph-service:/app" \
  -w /app \
  python:3.12-slim \
  sh -c "pip install -q fastapi==0.115.6 httpx==0.27.2 langgraph==0.2.73 langchain-core==0.3.28 pydantic==2.10.4 pydantic-settings==2.7.0 pytest==8.3.4 pytest-mock==3.14.0 && python -m pytest tests/test_duplicate_check.py::test_check_duplicates_endpoint_returns_200 tests/test_duplicate_check.py::test_check_duplicates_endpoint_rejects_missing_api_key -v"
```

Expected: FAIL (no route `/workflows/check-duplicates`)

- [ ] **Step 3: Add the endpoint to langgraph-service/app/routers/workflows.py**

Open `langgraph-service/app/routers/workflows.py`. Add imports and the new route. The file should look like this after editing:

```python
from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Header

from app.config import get_settings
from app.schemas.evaluation import (
    EvaluateRequest,
    EvaluationResult,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)
from app.workflows.evaluate import run_evaluation
from app.workflows.duplicate_check import run_duplicate_check

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()
    if x_api_key != settings.langgraph_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@router.post("/workflows/evaluate", response_model=EvaluationResult)
def evaluate_story(
    request: EvaluateRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> EvaluationResult:
    """
    Execute story evaluation workflow synchronously.
    Called by Backend only — not publicly exposed.
    """
    _verify_api_key(x_api_key)
    logger.info("evaluate_story run_id=%s story_id=%s", request.run_id, request.story_id)
    return run_evaluation(request)


@router.post("/workflows/check-duplicates", response_model=DuplicateCheckResponse)
def check_duplicates(
    request: DuplicateCheckRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> DuplicateCheckResponse:
    """
    Execute duplicate detection workflow synchronously.
    Candidates come pre-fetched from the Backend's pgvector search.
    Called by Backend only — not publicly exposed.
    """
    _verify_api_key(x_api_key)
    logger.info(
        "check_duplicates story_id=%s candidates=%d",
        request.story_id,
        len(request.candidates),
    )
    return run_duplicate_check(request)
```

- [ ] **Step 4: Run all endpoint tests**

```bash
docker run --rm \
  -v "$(pwd)/langgraph-service:/app" \
  -w /app \
  python:3.12-slim \
  sh -c "pip install -q fastapi==0.115.6 httpx==0.27.2 langgraph==0.2.73 langchain-core==0.3.28 pydantic==2.10.4 pydantic-settings==2.7.0 pytest==8.3.4 pytest-mock==3.14.0 && python -m pytest tests/test_duplicate_check.py -v"
```

Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add langgraph-service/app/routers/workflows.py langgraph-service/tests/test_duplicate_check.py
git commit -m "feat(embeddings): add POST /workflows/check-duplicates LangGraph endpoint"
```

---

## Task 10: Backend Endpoint — POST /evaluations/stories/{story_id}/check-duplicates

**Files:**
- Modify: `backend/app/routers/evaluations.py`

This endpoint:
1. Verifies membership (reuse `_get_story_and_verify_membership`)
2. Calls `find_similar_stories` (pgvector) to get up to 10 candidates split by threshold
3. Loads story titles/descriptions for each candidate from `user_stories` table
4. Calls LangGraph `POST /workflows/check-duplicates` (only for `similarity >= 0.85` candidates + all `0.70–0.84` candidates; the LangGraph node does the final split)
5. Returns `DuplicateCheckResponse`

**Threshold logic:**
- `similarity >= 0.85`: send to LangGraph as candidates
- `0.70 <= similarity < 0.85`: include as candidates (LangGraph may classify as `similar`)
- `find_similar_stories` already filters `< 0.70` out

The backend sends ALL results from `find_similar_stories` to LangGraph as candidates; LangGraph classifies each as `duplicate` or `similar`. The `similarity_score` is included in the payload so LangGraph's node can use it as context.

- [ ] **Step 1: Implement the endpoint in evaluations.py**

Open `backend/app/routers/evaluations.py`. Add imports and the new endpoint. Add the following after the existing imports block and `_run_to_read` helper:

```python
# New imports to add at the top of the file:
import httpx
from app.services.embedding_service import find_similar_stories
from app.schemas.evaluation import DuplicateCandidate, DuplicateCheckResponse
```

Then add this endpoint at the bottom of the file, after the existing `get_run_status` route:

```python
@router.post(
    "/evaluations/stories/{story_id}/check-duplicates",
    response_model=DuplicateCheckResponse,
)
async def check_duplicates(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DuplicateCheckResponse:
    """
    1. pgvector similarity search for the story's embedding
    2. Load story details for each candidate
    3. Call LangGraph /workflows/check-duplicates for LLM-based classification
    4. Return {duplicates, similar}
    """
    from sqlalchemy import select as sa_select
    settings = get_settings()

    story = await _get_story_and_verify_membership(story_id, current_user, db)

    # Step 1: vector search
    candidates_raw = await find_similar_stories(
        story_id=str(story_id),
        org_id=str(story.organization_id),
        db=db,
    )
    if not candidates_raw:
        return DuplicateCheckResponse(duplicates=[], similar=[])

    # Step 2: load story details for each candidate
    from app.models.user_story import UserStory as UserStoryModel
    candidate_ids = [cid for cid, _ in candidates_raw]
    stories_result = await db.execute(
        sa_select(UserStoryModel).where(UserStoryModel.id.in_(candidate_ids))
    )
    story_map = {s.id: s for s in stories_result.scalars().all()}

    candidates_payload = []
    for cid, sim in candidates_raw:
        s = story_map.get(cid)
        if s is None:
            continue
        candidates_payload.append({
            "story_id": str(cid),
            "title": s.title or "",
            "description": s.description or "",
            "acceptance_criteria": s.acceptance_criteria or "",
            "similarity_score": sim,
        })

    if not candidates_payload:
        return DuplicateCheckResponse(duplicates=[], similar=[])

    # Step 3: call LangGraph
    langgraph_payload = {
        "story_id": str(story_id),
        "org_id": str(story.organization_id),
        "title": story.title or "",
        "description": story.description or "",
        "acceptance_criteria": story.acceptance_criteria or "",
        "candidates": candidates_payload,
    }

    try:
        async with httpx.AsyncClient(timeout=float(settings.LANGGRAPH_TIMEOUT)) as client:
            response = await client.post(
                f"{settings.LANGGRAPH_BASE_URL}/workflows/check-duplicates",
                json=langgraph_payload,
                headers={"X-API-Key": settings.LANGGRAPH_API_KEY},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as e:
        logger.error("check_duplicates: LangGraph timeout for story %s: %s", story_id, e)
        raise HTTPException(status_code=504, detail=f"LangGraph timeout: {e}")
    except httpx.HTTPStatusError as e:
        logger.error("check_duplicates: LangGraph error for story %s: %s", story_id, e)
        raise HTTPException(status_code=502, detail=f"LangGraph error: {e.response.status_code}")

    # Step 4: parse and return
    duplicates = [DuplicateCandidate(**d) for d in data.get("duplicates", [])]
    similar = [DuplicateCandidate(**s) for s in data.get("similar", [])]
    return DuplicateCheckResponse(duplicates=duplicates, similar=similar)
```

Also add the missing imports at the top of `backend/app/routers/evaluations.py`. The full import block should be:

```python
from __future__ import annotations
import uuid
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models.evaluation_run import EvaluationRun
from app.models.membership import Membership
from app.models.user import User
from app.models.user_story import UserStory
from app.schemas.evaluation import (
    StartEvaluationResponse, EvaluationRunRead, EvaluationResultRead,
    EvaluationStatusEnum, AmpelEnum,
    DuplicateCandidate, DuplicateCheckResponse,
)
from app.services.embedding_service import find_similar_stories
from app.services.evaluation_service import start_evaluation, get_latest_evaluation
from app.core.exceptions import NotFoundException
```

- [ ] **Step 2: Verify the router imports cleanly**

```bash
cd infra && docker compose -f docker-compose.dev.yml exec backend python -c "from app.routers.evaluations import router; print('OK', [r.path for r in router.routes])"
```

Expected: output includes `/evaluations/stories/{story_id}/check-duplicates`

- [ ] **Step 3: Restart the backend and run a smoke test**

```bash
cd infra && docker compose -f docker-compose.dev.yml restart backend
```

Wait a few seconds, then:

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/evaluations/stories/00000000-0000-0000-0000-000000000000/check-duplicates \
  -H "Authorization: Bearer invalid"
```

Expected HTTP status: `401` (auth check works, route exists)

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/evaluations.py
git commit -m "feat(embeddings): add POST /evaluations/stories/{story_id}/check-duplicates endpoint"
```

---

## Task 11: Final Integration Test Run

This task verifies the complete flow by running all LangGraph tests (existing + new) to confirm no regressions.

- [ ] **Step 1: Run the full LangGraph test suite**

```bash
docker run --rm \
  -v "$(pwd)/langgraph-service:/app" \
  -w /app \
  python:3.12-slim \
  sh -c "pip install -q fastapi==0.115.6 langgraph==0.2.73 langchain-core==0.3.28 httpx==0.27.2 pydantic==2.10.4 pydantic-settings==2.7.0 pytest==8.3.4 pytest-mock==3.14.0 && python -m pytest tests/ -v"
```

Expected: all tests PASS (including pre-existing `test_evaluate_workflow.py`, `test_nodes.py`, `test_schemas.py`, `test_llm_client.py`, `test_workflow_endpoint.py`, `test_health.py`, and new `test_duplicate_check.py`)

- [ ] **Step 2: Verify backend linting**

```bash
cd infra && docker compose -f docker-compose.dev.yml exec backend python -m ruff check app/models/story_embedding.py app/services/embedding_service.py app/tasks/embedding_tasks.py app/routers/evaluations.py app/routers/user_stories.py app/schemas/evaluation.py
```

Expected: no errors

- [ ] **Step 3: Commit integration checkpoint**

```bash
git add .
git commit -m "test(embeddings): verify full LangGraph test suite passes after Sub-Plan B"
```

---

## Summary of Changes

| File | Change Type | What Changed |
|------|-------------|-------------|
| `backend/app/models/story_embedding.py` | **New** | ORM model for `story_embeddings` table |
| `backend/app/services/embedding_service.py` | **New** | `embed_story()` + `find_similar_stories()` async functions |
| `backend/app/tasks/embedding_tasks.py` | **New** | `embed_story_task` Celery task |
| `backend/app/celery_app.py` | **Modified** | Added `app.tasks.embedding_tasks` to include list |
| `backend/app/schemas/evaluation.py` | **Modified** | Added `DuplicateCandidate`, `DuplicateCheckResponse` |
| `backend/app/routers/user_stories.py` | **Modified** | Fire `embed_story_task.delay()` on create/content update |
| `backend/app/routers/evaluations.py` | **Modified** | Added `POST /evaluations/stories/{story_id}/check-duplicates` |
| `langgraph-service/app/schemas/evaluation.py` | **Modified** | Added `DuplicateCandidate`, `DuplicateCheckRequest`, `DuplicateCheckResponse` |
| `langgraph-service/app/nodes/semantic_comparator.py` | **New** | LLM-based story comparison node |
| `langgraph-service/app/workflows/duplicate_check.py` | **New** | `DuplicateCheckState` TypedDict + 2-node graph + `run_duplicate_check()` |
| `langgraph-service/app/routers/workflows.py` | **Modified** | Added `POST /workflows/check-duplicates` |
| `langgraph-service/tests/test_duplicate_check.py` | **New** | 7 tests covering node, workflow, and endpoint |
