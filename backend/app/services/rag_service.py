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
