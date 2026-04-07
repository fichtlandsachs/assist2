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
MAX_CHUNKS = 5


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
            f"{settings.LITELLM_URL}/v1/embeddings",
            headers=headers,
            json={"model": "ionos-embed", "input": query},
        )
        resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


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
        query:        The search query string.
        org_id:       Organization UUID — results are scoped to this org.
        db:           Async SQLAlchemy session.
        min_score:    Minimum cosine similarity score to include a chunk
                      (default: CONTEXT_THRESHOLD = 0.50). Effective minimum
                      is max(min_score, CONTEXT_THRESHOLD).
        source_types: Optional list of source_type values to filter on
                      (e.g. ["jira", "confluence", "karl_story"]).
                      When None, all source types are included.

    Returns:
        RagResult(mode='direct')  — score >= 0.92: use context as direct answer, no LLM needed
        RagResult(mode='context') — score >= effective_min: inject chunks into prompt
        RagResult(mode='none')    — score below threshold or any error: skip RAG
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
        chunks = [
            RagChunk(
                text=r.chunk_text,
                score=r.score,
                source_type=r.source_type,
                source_url=r.source_url,
                source_title=r.source_title,
            )
            for r in qualifying[:MAX_CHUNKS]
        ]
        return RagResult(mode="context", chunks=chunks)

    return RagResult(mode="none")
