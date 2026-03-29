# Nextcloud RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Index Nextcloud org documents into pgvector and inject relevant chunks as context into AI story suggestions, with direct answers when similarity is very high.

**Architecture:** A Celery task `index_org_documents` downloads files from Nextcloud via WebDAV, extracts text (PDF/DOCX/TXT), chunks it, embeds it via LiteLLM, and stores vectors in a `document_chunks` table (pgvector). At suggestion time, `rag_service.retrieve()` queries the nearest chunks by cosine similarity and either returns a direct answer (score ≥ 0.92), injects context into the prompt (0.50–0.92), or skips RAG (<0.50). The indexing task is triggered after every org file upload and daily via Celery Beat.

**Tech Stack:** PostgreSQL + pgvector extension (`pgvector/pgvector:pg16` image), LiteLLM (`text-embedding-3-small`), pdfplumber, python-docx, Celery, FastAPI, SQLAlchemy async

---

## File Map

| Action | File | Purpose |
|---|---|---|
| Modify | `infra/docker-compose.yml` | Switch postgres image to `pgvector/pgvector:pg16` |
| Modify | `backend/requirements.txt` | Add pdfplumber, python-docx, pgvector |
| Modify | `backend/app/config.py` | Add `LITELLM_URL`, `LITELLM_API_KEY` settings |
| Create | `backend/migrations/versions/0019_document_chunks.py` | pgvector extension + document_chunks table |
| Create | `backend/app/models/document_chunk.py` | SQLAlchemy ORM model |
| Create | `backend/app/services/rag_service.py` | Embedding, retrieval, threshold logic |
| Create | `backend/app/tasks/rag_tasks.py` | Celery task `index_org_documents` |
| Modify | `backend/app/celery_app.py` | Include rag_tasks + Beat schedule |
| Modify | `backend/app/routers/nextcloud.py` | Trigger indexing after org file upload |
| Modify | `backend/app/services/ai_story_service.py` | Inject RAG context before LLM call |
| Create | `backend/tests/unit/test_rag_service.py` | Unit tests for retrieval logic |
| Create | `backend/tests/unit/test_rag_tasks.py` | Unit tests for index task |

---

### Task 1: Infrastructure — pgvector image + dependencies + config

**Files:**
- Modify: `infra/docker-compose.yml`
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Switch postgres image to pgvector in docker-compose.yml**

Open `infra/docker-compose.yml`. The `postgres:` service currently uses `image: postgres:16-alpine`. Change it to:

```yaml
  postgres:
    image: pgvector/pgvector:pg16
    container_name: assist2-postgres
```

Everything else in the postgres service block stays the same.

- [ ] **Step 2: Add Python dependencies to requirements.txt**

Open `backend/requirements.txt`. Add these three lines after the `Jinja2` line:

```
pdfplumber==0.11.4
python-docx==1.1.2
pgvector==0.3.6
```

- [ ] **Step 3: Add LiteLLM settings to config.py**

Open `backend/app/config.py`. After the `WHISPER_URL` line, add:

```python
    # LiteLLM (internal AI gateway)
    LITELLM_URL: str = "http://litellm:4000"
    LITELLM_API_KEY: str = ""
```

- [ ] **Step 4: Add LiteLLM placeholders to .env.example**

Open `infra/.env.example`. Add at the end:

```bash
# LiteLLM internal AI gateway
LITELLM_URL=http://litellm:4000
LITELLM_API_KEY=
```

- [ ] **Step 5: Commit**

```bash
git add infra/docker-compose.yml backend/requirements.txt backend/app/config.py infra/.env.example
git commit -m "feat(rag): add pgvector image, pdfplumber/python-docx/pgvector deps, LiteLLM config"
```

---

### Task 2: Migration 0019 + ORM model

**Files:**
- Create: `backend/migrations/versions/0019_document_chunks.py`
- Create: `backend/app/models/document_chunk.py`

- [ ] **Step 1: Create migration 0019**

Create `backend/migrations/versions/0019_document_chunks.py`:

```python
"""Add document_chunks table with pgvector embedding column.

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),  # stored via pgvector type below
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )

    # Replace text column with actual vector(1536) type
    op.execute("ALTER TABLE document_chunks DROP COLUMN embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")

    # Indexes
    op.create_index(
        "ix_document_chunks_org_file",
        "document_chunks",
        ["org_id", "file_path"],
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding ON document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists=100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.drop_index("ix_document_chunks_org_file", table_name="document_chunks")
    op.drop_table("document_chunks")
```

- [ ] **Step 2: Create ORM model document_chunk.py**

Create `backend/app/models/document_chunk.py`:

```python
"""ORM model for pgvector document chunks."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # embedding stored as vector(1536) in DB — retrieved as list[float] via pgvector
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 3: Run migration**

```bash
docker exec assist2-backend alembic upgrade head
```

Expected: `Running upgrade 0018 -> 0019, Add document_chunks table with pgvector embedding column`

Verify table exists:

```bash
docker exec assist2-postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "\d document_chunks"
```

Expected: table with columns id, org_id, file_path, file_hash, chunk_index, chunk_text, embedding (vector), created_at.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/versions/0019_document_chunks.py backend/app/models/document_chunk.py
git commit -m "feat(rag): add migration 0019 and DocumentChunk ORM model"
```

---

### Task 3: RAG service (TDD)

**Files:**
- Create: `backend/tests/unit/test_rag_service.py`
- Create: `backend/app/services/rag_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_rag_service.py`:

```python
"""Unit tests for rag_service.retrieve — LiteLLM and DB mocked."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
import uuid


def make_db_row(chunk_text: str, score: float) -> MagicMock:
    row = MagicMock()
    row.chunk_text = chunk_text
    row.score = score
    return row


@pytest.mark.asyncio
async def test_retrieve_direct_mode():
    """Score >= 0.92 → mode='direct', direct_answer set."""
    from app.services.rag_service import retrieve, RagResult

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(
        return_value=[make_db_row("Direktantwort Text", 0.95)]
    )

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1536
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "direct"
    assert result.direct_answer == "Direktantwort Text"
    assert result.chunks == []


@pytest.mark.asyncio
async def test_retrieve_context_mode():
    """Score 0.50-0.92 → mode='context', chunks filled."""
    from app.services.rag_service import retrieve, RagResult

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(
        return_value=[
            make_db_row("Chunk 1", 0.75),
            make_db_row("Chunk 2", 0.60),
        ]
    )

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1536
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "context"
    assert len(result.chunks) == 2
    assert result.direct_answer is None


@pytest.mark.asyncio
async def test_retrieve_none_mode():
    """Score < 0.50 → mode='none'."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(
        return_value=[make_db_row("Irrelevant", 0.30)]
    )

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1536
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "none"
    assert result.chunks == []


@pytest.mark.asyncio
async def test_retrieve_empty_db():
    """No chunks in DB → mode='none'."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(return_value=[])

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1536
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "none"


@pytest.mark.asyncio
async def test_retrieve_litellm_error_fallback():
    """LiteLLM not reachable → returns mode='none', no exception raised."""
    import httpx
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.side_effect = httpx.ConnectError("LiteLLM down")
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "none"


@pytest.mark.asyncio
async def test_retrieve_db_error_fallback():
    """DB error → returns mode='none', no exception raised."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("DB failure"))

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1536
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "none"
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
docker exec assist2-backend pytest backend/tests/unit/test_rag_service.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.services.rag_service'`

- [ ] **Step 3: Create rag_service.py**

Create `backend/app/services/rag_service.py`:

```python
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
class RagResult:
    mode: Literal["direct", "context", "none"]
    chunks: list[str] = field(default_factory=list)
    direct_answer: str | None = None


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
        RagResult(mode='direct')  — score >= 0.92: use direct_answer, no LLM needed
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
            SELECT chunk_text, 1 - (embedding <=> :embedding ::vector) AS score
            FROM document_chunks
            WHERE org_id = :org_id
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
        return RagResult(mode="direct", direct_answer=rows[0].chunk_text)

    if top_score >= CONTEXT_THRESHOLD:
        chunks = [r.chunk_text for r in rows[:MAX_CHUNKS] if r.score >= CONTEXT_THRESHOLD]
        return RagResult(mode="context", chunks=chunks)

    return RagResult(mode="none")
```

- [ ] **Step 4: Run tests — all should pass**

```bash
docker exec assist2-backend pytest backend/tests/unit/test_rag_service.py -v
```

Expected:
```
test_retrieve_direct_mode PASSED
test_retrieve_context_mode PASSED
test_retrieve_none_mode PASSED
test_retrieve_empty_db PASSED
test_retrieve_litellm_error_fallback PASSED
test_retrieve_db_error_fallback PASSED
6 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/rag_service.py backend/tests/unit/test_rag_service.py
git commit -m "feat(rag): add rag_service with embedding, retrieval, threshold logic + tests"
```

---

### Task 4: Celery indexing task (TDD)

**Files:**
- Create: `backend/tests/unit/test_rag_tasks.py`
- Create: `backend/app/tasks/rag_tasks.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_rag_tasks.py`:

```python
"""Unit tests for rag_tasks.index_org_documents — all IO mocked."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


@pytest.mark.asyncio
async def test_index_skips_unchanged_file():
    """File with same SHA256 hash already in DB → skip embedding call."""
    from app.tasks.rag_tasks import _index_org_documents_async

    org_id = str(uuid.uuid4())
    org_slug = "test-org"

    mock_db = AsyncMock()
    # Simulate existing hash match
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value="abc123")

    file_list = [{"href": f"/remote.php/dav/files/admin/Organizations/{org_slug}/doc.pdf",
                  "content_type": "application/pdf"}]

    with patch("app.tasks.rag_tasks._list_org_files", new_callable=AsyncMock) as mock_list, \
         patch("app.tasks.rag_tasks._download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.tasks.rag_tasks._sha256", return_value="abc123"), \
         patch("app.tasks.rag_tasks._embed_chunks", new_callable=AsyncMock) as mock_embed:

        mock_list.return_value = file_list
        mock_dl.return_value = b"pdf-bytes"

        await _index_org_documents_async(org_id, org_slug, mock_db)

    mock_embed.assert_not_called()


@pytest.mark.asyncio
async def test_index_processes_new_pdf():
    """New PDF (hash mismatch) → text extracted, chunks embedded, stored."""
    from app.tasks.rag_tasks import _index_org_documents_async

    org_id = str(uuid.uuid4())
    org_slug = "test-org"

    mock_db = AsyncMock()
    # No existing hash → file is new
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)

    file_list = [{"href": f"/remote.php/dav/files/admin/Organizations/{org_slug}/doc.pdf",
                  "content_type": "application/pdf"}]

    with patch("app.tasks.rag_tasks._list_org_files", new_callable=AsyncMock) as mock_list, \
         patch("app.tasks.rag_tasks._download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.tasks.rag_tasks._sha256", return_value="newhash"), \
         patch("app.tasks.rag_tasks._extract_text", return_value="Dokument Inhalt"), \
         patch("app.tasks.rag_tasks._chunk_text", return_value=["Chunk 1", "Chunk 2"]), \
         patch("app.tasks.rag_tasks._embed_chunks", new_callable=AsyncMock) as mock_embed:

        mock_list.return_value = file_list
        mock_dl.return_value = b"pdf-bytes"
        mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]

        await _index_org_documents_async(org_id, org_slug, mock_db)

    mock_embed.assert_called_once_with(["Chunk 1", "Chunk 2"])
    assert mock_db.add.called  # DocumentChunk rows added


@pytest.mark.asyncio
async def test_index_skips_unsupported_filetype():
    """File with unsupported extension (e.g. .xlsx) → skip without error."""
    from app.tasks.rag_tasks import _index_org_documents_async

    org_id = str(uuid.uuid4())
    org_slug = "test-org"

    mock_db = AsyncMock()

    file_list = [{"href": f"/remote.php/dav/files/admin/Organizations/{org_slug}/data.xlsx",
                  "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}]

    with patch("app.tasks.rag_tasks._list_org_files", new_callable=AsyncMock) as mock_list, \
         patch("app.tasks.rag_tasks._embed_chunks", new_callable=AsyncMock) as mock_embed:

        mock_list.return_value = file_list

        await _index_org_documents_async(org_id, org_slug, mock_db)

    mock_embed.assert_not_called()


@pytest.mark.asyncio
async def test_chunk_text_splits_correctly():
    """_chunk_text splits text into 512-token chunks with 50-token overlap."""
    from app.tasks.rag_tasks import _chunk_text

    # ~600 words → should produce 2 chunks
    word = "lorem "
    text = word * 600
    chunks = _chunk_text(text)

    assert len(chunks) >= 2
    # Each chunk must not exceed ~600 chars (512 tokens ≈ 400 words ≈ ~2400 chars — just verify non-empty)
    assert all(len(c) > 0 for c in chunks)
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
docker exec assist2-backend pytest backend/tests/unit/test_rag_tasks.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.tasks.rag_tasks'`

- [ ] **Step 3: Create rag_tasks.py**

Create `backend/app/tasks/rag_tasks.py`:

```python
"""Celery task: index Nextcloud org documents into pgvector."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery

logger = logging.getLogger(__name__)

# Chunk size in approximate characters (512 tokens ≈ 2000 chars), overlap ≈ 200 chars
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

SUPPORTED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "txt",
    "text/x-markdown": "txt",
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _extract_text(content: bytes, file_type: str) -> str:
    """Extract plain text from PDF, DOCX, or TXT bytes."""
    if file_type == "pdf":
        import pdfplumber
        import io
        text_parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)

    if file_type == "docx":
        from docx import Document
        import io
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    # txt / md
    return content.decode("utf-8", errors="replace")


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if c]


async def _list_org_files(org_slug: str) -> list[dict]:
    """PROPFIND Nextcloud for org files. Returns list of {href, content_type}."""
    from app.config import get_settings
    settings = get_settings()

    propfind_body = b"""<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:">
  <d:prop><d:getcontenttype/></d:prop>
</d:propfind>"""

    url = (
        f"{settings.NEXTCLOUD_INTERNAL_URL}/remote.php/dav/files/"
        f"{settings.NEXTCLOUD_ADMIN_USER}/Organizations/{org_slug}/"
    )
    auth = (settings.NEXTCLOUD_ADMIN_USER, settings.NEXTCLOUD_ADMIN_APP_PASSWORD)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            "PROPFIND", url, auth=auth,
            headers={"Depth": "1", "Content-Type": "application/xml"},
            content=propfind_body,
        )
        resp.raise_for_status()

    import xml.etree.ElementTree as ET
    root = ET.fromstring(resp.text)
    DAV = "DAV:"
    files = []
    for response in root.findall(f"{{{DAV}}}response"):
        href_el = response.find(f"{{{DAV}}}href")
        if href_el is None:
            continue
        href = href_el.text or ""
        # Skip root folder itself
        if href.rstrip("/").endswith(f"Organizations/{org_slug}"):
            continue
        propstat = response.find(f"{{{DAV}}}propstat")
        if propstat is None:
            continue
        prop = propstat.find(f"{{{DAV}}}prop")
        if prop is None:
            continue
        ct_el = prop.find(f"{{{DAV}}}getcontenttype")
        ct = (ct_el.text or "") if ct_el is not None else ""
        if ct and ct != "httpd/unix-directory":
            files.append({"href": href, "content_type": ct})
    return files


async def _download_file(href: str) -> bytes:
    """Download a file from Nextcloud WebDAV by full href path."""
    from app.config import get_settings
    settings = get_settings()
    url = f"{settings.NEXTCLOUD_INTERNAL_URL}{href}"
    auth = (settings.NEXTCLOUD_ADMIN_USER, settings.NEXTCLOUD_ADMIN_APP_PASSWORD)
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url, auth=auth)
        resp.raise_for_status()
    return resp.content


async def _embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Embed a list of text chunks via LiteLLM. Returns list of vectors."""
    from app.config import get_settings
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.LITELLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LITELLM_API_KEY}"

    embeddings = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for chunk in chunks:
            resp = await client.post(
                f"{settings.LITELLM_URL}/embeddings",
                headers=headers,
                json={"model": "text-embedding-3-small", "input": chunk},
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["data"][0]["embedding"])
    return embeddings


async def _index_org_documents_async(org_id: str, org_slug: str, db: AsyncSession) -> None:
    """Core indexing logic — separated for testability."""
    from app.models.document_chunk import DocumentChunk

    files = await _list_org_files(org_slug)

    for file_info in files:
        href = file_info["href"]
        content_type = file_info["content_type"]
        file_type = SUPPORTED_TYPES.get(content_type)

        if file_type is None:
            logger.warning("Skipping unsupported file type '%s': %s", content_type, href)
            continue

        try:
            content = await _download_file(href)
        except Exception as e:
            logger.warning("Failed to download %s: %s", href, e)
            continue

        file_hash = _sha256(content)

        # Check if file changed since last index
        existing_hash_result = await db.execute(
            select(DocumentChunk.file_hash)
            .where(
                DocumentChunk.org_id == uuid.UUID(org_id),
                DocumentChunk.file_path == href,
            )
            .limit(1)
        )
        existing_hash = existing_hash_result.scalar_one_or_none()
        if existing_hash == file_hash:
            logger.debug("Skipping unchanged file: %s", href)
            continue

        try:
            extracted = _extract_text(content, file_type)
        except Exception as e:
            logger.warning("Text extraction failed for %s: %s", href, e)
            continue

        chunks = _chunk_text(extracted)
        if not chunks:
            continue

        try:
            embeddings = await _embed_chunks(chunks)
        except Exception as e:
            logger.warning("Embedding failed for %s: %s", href, e)
            continue

        # Delete old chunks for this file
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.org_id == uuid.UUID(org_id),
                DocumentChunk.file_path == href,
            )
        )

        # Insert new chunks with embeddings
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            chunk = DocumentChunk(
                org_id=uuid.UUID(org_id),
                file_path=href,
                file_hash=file_hash,
                chunk_index=i,
                chunk_text=chunk_text,
                embedding=embedding_str,
            )
            db.add(chunk)

        await db.commit()
        logger.info("Indexed %d chunks for %s", len(chunks), href)


@celery.task(name="rag_tasks.index_org_documents", bind=True, max_retries=3)
def index_org_documents(self, org_id: str, org_slug: str) -> dict:
    """Celery task: index all Nextcloud org files into pgvector."""
    from app.config import get_settings

    async def run():
        engine = create_async_engine(
            get_settings().DATABASE_URL, echo=False, pool_pre_ping=True
        )
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with SessionLocal() as db:
                await _index_org_documents_async(org_id, org_slug, db)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
        return {"status": "ok", "org_id": org_id}
    except Exception as exc:
        logger.error("index_org_documents failed for org %s: %s", org_id, exc)
        raise self.retry(exc=exc, countdown=60)
```

- [ ] **Step 4: Run tests — all should pass**

```bash
docker exec assist2-backend pytest backend/tests/unit/test_rag_tasks.py -v
```

Expected:
```
test_index_skips_unchanged_file PASSED
test_index_processes_new_pdf PASSED
test_index_skips_unsupported_filetype PASSED
test_chunk_text_splits_correctly PASSED
4 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/rag_tasks.py backend/tests/unit/test_rag_tasks.py
git commit -m "feat(rag): add index_org_documents Celery task with tests"
```

---

### Task 5: Wire up — celery_app + nextcloud router trigger

**Files:**
- Modify: `backend/app/celery_app.py`
- Modify: `backend/app/routers/nextcloud.py`

- [ ] **Step 1: Add rag_tasks to celery_app.py include list and Beat schedule**

Open `backend/app/celery_app.py`. In the `include` list (currently 5 items), add `"app.tasks.rag_tasks"`:

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
    ]
)
```

In `celery.conf.beat_schedule`, add a daily fallback indexing schedule. This requires knowing which orgs to index — add a dispatcher entry:

```python
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
        "schedule": 86400.0,  # once per day
    },
}
```

- [ ] **Step 2: Add dispatch_rag_index to sync_dispatcher.py**

Open `backend/app/tasks/sync_dispatcher.py` and add at the end:

```python
@celery.task(name="sync_dispatcher.dispatch_rag_index")
def dispatch_rag_index() -> None:
    """Daily: trigger RAG indexing for all active orgs."""
    from app.tasks.rag_tasks import index_org_documents
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import get_settings
    from sqlalchemy import select

    async def get_orgs():
        from app.models.organization import Organization
        engine = create_async_engine(get_settings().DATABASE_URL, echo=False, pool_pre_ping=True)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as db:
            result = await db.execute(
                select(Organization.id, Organization.slug).where(Organization.deleted_at.is_(None))
            )
            orgs = result.fetchall()
        await engine.dispose()
        return orgs

    orgs = asyncio.run(get_orgs())
    for org_id, org_slug in orgs:
        index_org_documents.delay(str(org_id), org_slug)
```

- [ ] **Step 3: Trigger indexing after org file upload in nextcloud.py**

Open `backend/app/routers/nextcloud.py`. In `upload_nextcloud_file`, after the `resp.raise_for_status()` line (currently the last line before `return`), add the indexing trigger:

```python
        resp.raise_for_status()

    # Trigger RAG indexing for this org asynchronously
    from app.tasks.rag_tasks import index_org_documents
    index_org_documents.delay(str(org_id), org.slug)

    return NextcloudUploadResult(ok=True, path=dest_path)
```

- [ ] **Step 4: Rebuild worker and restart**

```bash
cd /opt/assist2/infra
docker compose build backend worker
docker compose up -d --no-deps backend worker
```

Verify rag_tasks registered:

```bash
docker exec assist2-worker celery -A app.celery_app inspect registered 2>&1 | grep rag
```

Expected: `rag_tasks.index_org_documents`

- [ ] **Step 5: Commit**

```bash
git add backend/app/celery_app.py backend/app/tasks/sync_dispatcher.py backend/app/routers/nextcloud.py
git commit -m "feat(rag): wire celery Beat schedule and nextcloud upload trigger for RAG indexing"
```

---

### Task 6: RAG injection into ai_story_service

**Files:**
- Modify: `backend/app/services/ai_story_service.py`
- Modify: `backend/app/routers/user_stories.py`

- [ ] **Step 1: Add org_id + db params to get_story_suggestions**

Open `backend/app/services/ai_story_service.py`. Change the signature of `get_story_suggestions` from:

```python
async def get_story_suggestions(
    data: AISuggestRequest, ai_settings: dict | None = None
) -> AISuggestion:
```

To:

```python
async def get_story_suggestions(
    data: AISuggestRequest,
    ai_settings: dict | None = None,
    org_id: "uuid.UUID | None" = None,
    db: "AsyncSession | None" = None,
) -> AISuggestion:
```

Add the missing imports at the top of the file (after existing imports):

```python
import uuid
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
```

- [ ] **Step 2: Add RAG context block inside get_story_suggestions**

Inside `get_story_suggestions`, after the comment `# 1. Context analysis (heuristic, no LLM)` block and before `# 2. Build prompt`, insert the RAG block:

```python
    # 0. RAG retrieval (org-scoped, optional)
    rag_context_block: str | None = None
    if org_id is not None and db is not None:
        try:
            from app.services.rag_service import retrieve, RagResult
            rag = await retrieve(f"{data.title} {data.description}", org_id, db)
            if rag.mode == "direct" and rag.direct_answer:
                return AISuggestion(
                    title=None,
                    description=None,
                    acceptance_criteria=None,
                    explanation=f"Aus Org-Wissensbank: {rag.direct_answer}",
                    dor_issues=[],
                    quality_score=None,
                )
            if rag.mode == "context" and rag.chunks:
                rag_context_block = "\n".join(
                    [f"[Kontext]\n{c}" for c in rag.chunks]
                )
        except Exception as e:
            logger.warning("RAG retrieval error (skipping): %s", e)
```

- [ ] **Step 3: Inject RAG context into prompt**

In `get_story_suggestions`, the existing line is:

```python
    prompt = _build_suggest_prompt(data)
```

Replace it with:

```python
    prompt = _build_suggest_prompt(data, rag_context=rag_context_block)
```

Update `_build_suggest_prompt` signature and body. The function currently starts:

```python
def _build_suggest_prompt(data: AISuggestRequest) -> str:
    return f"""Analysiere diese User Story...
```

Change to:

```python
def _build_suggest_prompt(data: AISuggestRequest, rag_context: str | None = None) -> str:
    context_section = ""
    if rag_context:
        context_section = f"""
--- Org-Wissen (aus Nextcloud) ---
{rag_context}
---------------------------------

"""
    return f"""{context_section}Analysiere diese User Story und gib Verbesserungsvorschläge zurück.

Aktuelle Story:
Titel: {data.title or "(leer)"}
Beschreibung: {data.description or "(leer)"}
Akzeptanzkriterien: {data.acceptance_criteria or "(leer)"}

Du bist ein erfahrener Scrum Master. Prüfe die Story gegen die Definition of Ready (DoR):
- Hat die Story einen klaren Titel?
- Ist die Beschreibung im Format "Als [Rolle] möchte ich [Funktion], damit [Nutzen]"?
- Sind die Akzeptanzkriterien konkret, testbar und vollständig?
- Ist die Story klein genug für einen Sprint?
- Sind Abhängigkeiten bekannt?

Antworte NUR mit einem JSON-Objekt (kein Markdown, kein Text davor oder danach):
{{
  "title": "Verbesserte Version des Titels oder null wenn gut",
  "description": "Verbesserte Beschreibung im Format 'Als [Rolle] möchte ich [Funktion], damit [Nutzen]' oder null wenn gut",
  "acceptance_criteria": "Verbesserte Akzeptanzkriterien als nummerierte Liste oder null wenn gut",
  "explanation": "Kurze Erklärung der wichtigsten Verbesserungen",
  "dor_issues": ["Liste der fehlenden DoR-Kriterien"],
  "quality_score": 75
}}"""
```

- [ ] **Step 4: Pass org_id + db in the router**

Open `backend/app/routers/user_stories.py`. In the `ai_suggest` endpoint, find:

```python
    suggestion = await get_story_suggestions(data, ai_settings=ai_settings)
```

Replace with:

```python
    org_id_for_rag = story_obj.organization_id if story_obj else None
    suggestion = await get_story_suggestions(
        data, ai_settings=ai_settings, org_id=org_id_for_rag, db=db
    )
```

- [ ] **Step 5: Run the full test suite to ensure nothing is broken**

```bash
docker exec assist2-backend pytest backend/tests/unit/ -v --tb=short 2>&1 | tail -30
```

Expected: all existing tests plus rag tests pass. No regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_story_service.py backend/app/routers/user_stories.py
git commit -m "feat(rag): inject RAG context into story suggestions (direct answer + context modes)"
```

---

### Task 7: Deploy pgvector image + run migration

**Files:** (infrastructure only, no code changes)

> **Important:** Switching the postgres image requires a container recreate. Data is preserved in the volume `assist2_postgres_data` — pgvector/pgvector:pg16 is fully compatible with postgres:16 data directories.

- [ ] **Step 1: Pull new image and recreate postgres container**

```bash
cd /opt/assist2/infra
docker compose pull postgres
docker compose up -d --no-deps postgres
```

Wait 15 seconds, then verify:

```bash
docker exec assist2-postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT extname FROM pg_extension WHERE extname='vector';" 2>&1
```

Expected before migration: `(0 rows)` (extension not yet created)

- [ ] **Step 2: Build and deploy backend + worker with new dependencies**

```bash
docker compose build backend worker
docker compose up -d --no-deps backend worker
```

- [ ] **Step 3: Run migration 0019**

```bash
docker exec assist2-backend alembic upgrade head
```

Expected: `Running upgrade 0018 -> 0019, Add document_chunks table with pgvector embedding column`

Verify vector extension active:

```bash
docker exec assist2-postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```

Expected: `vector` in output.

- [ ] **Step 4: Push to remote**

```bash
cd /opt/assist2
git push
```

---

## Smoke Test

After full deployment:

1. Upload a `.txt` or `.pdf` file to an org's Nextcloud folder via the UI
2. Check worker logs: `docker logs assist2-worker --tail 20`
   - Expected: `INFO Indexed N chunks for Organizations/...`
3. Create a story whose topic matches document content
4. Click "Vorschläge" — the suggestion explanation should mention "Aus Org-Wissensbank" if similarity is ≥ 0.92, or simply use improved context from the document
