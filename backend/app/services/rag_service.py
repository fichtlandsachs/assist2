"""RAG service — embedding, retrieval, threshold logic."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

if TYPE_CHECKING:
    from app.core.identity import AccessContext

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
    indexed_at:   str | None = None  # created_at from DB, ISO string


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
    access_context: "AccessContext | None" = None,
) -> RagResult:
    """
    Embed query, find top-5 most similar chunks for this org, apply thresholds.

    Args:
        query:          The search query string.
        org_id:         Organization UUID — results are scoped to this org.
        db:             Async SQLAlchemy session.
        min_score:      Minimum cosine similarity score (default: 0.50).
        source_types:   Optional list of source_type values to filter on.
        access_context: When provided (and not superuser), restricts results to
                        chunks with zone_id IS NULL or zone_id in the user's
                        allowed zones. Superusers bypass zone filtering entirely.

    Returns:
        RagResult(mode='direct')  — score >= 0.92: direct answer, no LLM needed
        RagResult(mode='context') — score >= effective_min: inject into prompt
        RagResult(mode='none')    — below threshold or any error: skip RAG
    """
    try:
        embedding = await _embed_query(query)
    except Exception as e:
        logger.warning("RAG embedding failed, skipping: %s", e)
        return RagResult(mode="none")

    # Build zone ACL clause — three tiers when user is not a superuser:
    # 1. NULL zone (public content, always visible)
    # 2. Active zone grants (current AD membership + active heyKarl role grants)
    # 3. Soft-revoked grants: docs ingested BEFORE revoked_at remain visible
    zone_clause = ""
    zone_params: dict = {}
    if access_context is not None and not access_context.identity.is_superuser:
        active_ids = [str(z) for z in access_context.identity.zone_ids]
        revoked = access_context.revoked_grants
        if revoked:
            zone_clause = (
                "AND (\n"
                "    dc.zone_id IS NULL\n"
                "    OR dc.zone_id = ANY(:active_zone_ids)\n"
                "    OR EXISTS (\n"
                "        SELECT 1\n"
                "        FROM unnest(\n"
                "            :revoked_zone_ids ::uuid[],\n"
                "            :revoked_at_vals  ::timestamptz[]\n"
                "        ) AS rg(zone_id, revoked_at)\n"
                "        WHERE rg.zone_id   = dc.zone_id\n"
                "          AND dc.created_at < rg.revoked_at\n"
                "    )\n"
                ")\n"
            )
            zone_params["active_zone_ids"] = active_ids
            zone_params["revoked_zone_ids"] = [str(z) for z, _ in revoked]
            zone_params["revoked_at_vals"] = [ts.isoformat() for _, ts in revoked]
        else:
            zone_clause = "AND (dc.zone_id IS NULL OR dc.zone_id = ANY(:active_zone_ids))\n"
            zone_params["active_zone_ids"] = active_ids

    try:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        if source_types:
            sql = text(f"""
                SELECT dc.chunk_text,
                       dc.source_type,
                       dc.source_url,
                       dc.source_title,
                       dc.created_at,
                       1 - (dc.embedding <=> :embedding ::vector) AS score
                FROM document_chunks dc
                WHERE (dc.org_id = :org_id
                  AND dc.embedding IS NOT NULL
                  AND dc.source_type = ANY(:source_types)
                  {zone_clause})
                  OR dc.is_global = TRUE
                ORDER BY score DESC
                LIMIT 5
            """)
            params = {
                "embedding": embedding_str,
                "org_id": str(org_id),
                "source_types": source_types,
                **zone_params,
            }
        else:
            sql = text(f"""
                SELECT dc.chunk_text,
                       dc.source_type,
                       dc.source_url,
                       dc.source_title,
                       dc.created_at,
                       1 - (dc.embedding <=> :embedding ::vector) AS score
                FROM document_chunks dc
                WHERE (dc.org_id = :org_id
                  AND dc.embedding IS NOT NULL
                  {zone_clause})
                  OR dc.is_global = TRUE
                ORDER BY score DESC
                LIMIT 5
            """)
            params = {
                "embedding": embedding_str,
                "org_id": str(org_id),
                **zone_params,
            }
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
                indexed_at=top.created_at.isoformat() if top.created_at else None,
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
                indexed_at=r.created_at.isoformat() if r.created_at else None,
            )
            for r in qualifying[:MAX_CHUNKS]
        ]
        return RagResult(mode="context", chunks=chunks)

    return RagResult(mode="none")
