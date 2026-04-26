# app/services/hybrid_retrieval_service.py
"""
Hybrid Retrieval Service for HeyKarl Multi-Source RAG.

Combines 6 retrieval/ranking dimensions per spec:

  final_score = semantic*0.35 + keyword*0.15 + entity*0.15
              + trust*0.20 + context*0.10 + freshness*0.05

Hard eligibility rules (enforced before scoring):
  - Draft sources ALWAYS excluded in production mode
  - Community sources NEVER eligible for security/compliance queries
  - Architecture queries require ≥2 sources with trust_class >= V3
  - Conflict detection runs post-retrieval and is surfaced explicitly

Output: HybridRetrievalResult — structured for WorkspaceResponseService.
"""
from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.trust_engine import (
    SourceConflict,
    check_eligibility,
    classify_query_context,
    detect_conflicts,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ── Score weights (spec §6.2) ─────────────────────────────────────────────────

SEMANTIC_WEIGHT  = 0.35   # was 0.60 — adjusted to spec
KEYWORD_WEIGHT   = 0.15   # BM25
ENTITY_WEIGHT    = 0.15
TRUST_WEIGHT     = 0.20
CONTEXT_WEIGHT   = 0.10
FRESHNESS_WEIGHT = 0.05

assert abs(SEMANTIC_WEIGHT + KEYWORD_WEIGHT + ENTITY_WEIGHT +
           TRUST_WEIGHT + CONTEXT_WEIGHT + FRESHNESS_WEIGHT - 1.0) < 1e-9

# Legacy aliases for RRF fusion (internal)
BM25_WEIGHT = KEYWORD_WEIGHT

MAX_CHUNKS       = 8
MIN_SCORE        = 0.20
DIRECT_THRESHOLD = 0.85

# Minimum distinct high-trust sources for architecture answers
ARCH_MIN_SOURCES = 2
ARCH_MIN_TRUST_CLASS = "V3"

# Chunk type priority (higher = more relevant for workspace context)
CHUNK_TYPE_PRIORITY: dict[str, int] = {
    "process_overview":    10,
    "workflow":             9,
    "process_step":         8,
    "integration_pattern":  8,
    "permission":           7,
    "api_reference":        6,
    "object_overview":      5,
    "rule":                 5,
    "best_practice":        5,
    "constraint":           4,
    "object_field":         3,
    "knowledge_object":     2,
    "general":              1,
}

SOURCE_SYSTEM_PRIORITY: dict[str, int] = {
    "salesforce": 4,
    "sap":        4,
    "jira":       3,
    "confluence": 2,
}


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class HybridChunk:
    text:               str
    semantic_score:     float
    bm25_score:         float
    final_score:        float
    source_system:      str
    source_type:        str
    source_url:         str | None
    source_title:       str | None
    chunk_type:         str
    canonical_type:     str
    entities:           dict
    indexed_at:         str | None = None
    is_global:          bool = True
    # Trust dimensions (from TrustProfile, loaded at retrieval time)
    trust_class:        str = "V3"
    trust_score:        float = 0.5
    source_category:    str = ""
    evidence_type:      Literal["primary", "supporting"] = "supporting"


@dataclass
class HybridRetrievalResult:
    mode:      Literal["direct", "context", "none"]
    chunks:    list[HybridChunk] = field(default_factory=list)
    conflicts: list[SourceConflict] = field(default_factory=list)
    guardrail_warnings: list[str] = field(default_factory=list)

    @property
    def has_results(self) -> bool:
        return bool(self.chunks)

    def has_conflicts(self) -> bool:
        return bool(self.conflicts)

    def top_source_systems(self) -> list[str]:
        seen: dict[str, float] = {}
        for c in self.chunks:
            seen[c.source_system] = max(seen.get(c.source_system, 0), c.final_score)
        return [k for k, _ in sorted(seen.items(), key=lambda x: -x[1])]

    def primary_evidence_count(self) -> int:
        return sum(1 for c in self.chunks if c.evidence_type == "primary")

    def entities_union(self) -> dict:
        """Merge entity sets across all chunks — used by WorkspaceResponseService."""
        merged: dict[str, list[str]] = {}
        for chunk in self.chunks:
            for key, vals in chunk.entities.items():
                if isinstance(vals, list):
                    merged.setdefault(key, [])
                    merged[key].extend(v for v in vals if v not in merged[key])
        return merged


# ── Embedding helper ──────────────────────────────────────────────────────────

async def _embed(query: str) -> list[float] | None:
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.LITELLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LITELLM_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.LITELLM_URL}/v1/embeddings",
                headers=headers,
                json={"model": "ionos-embed", "input": query},
            )
            resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
    except Exception as exc:
        logger.warning("Embedding failed: %s", exc)
        return None


# ── Semantic retrieval ────────────────────────────────────────────────────────

async def _semantic_retrieve(
    embedding: list[float],
    org_id: uuid.UUID,
    db: AsyncSession,
    source_systems: list[str] | None,
    canonical_types: list[str] | None,
    limit: int = 20,
) -> list[dict]:
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    filters = ""
    params: dict = {"embedding": embedding_str, "org_id": str(org_id)}

    if source_systems:
        filters += " AND meta->>'source_system' = ANY(:source_systems)"
        params["source_systems"] = source_systems
    if canonical_types:
        filters += " AND meta->>'canonical_type' = ANY(:canonical_types)"
        params["canonical_types"] = canonical_types

    # Callstack gate: global external-doc chunks are only visible when their
    # Integration Layer source (ExternalSource) is active (is_enabled=TRUE).
    # Chunks without external_source_id are org-internal — always allowed.
    global_gate = (
        "dc.is_global = TRUE "
        "AND (dc.external_source_id IS NULL "
        "     OR EXISTS ("
        "         SELECT 1 FROM external_sources es "
        "         WHERE es.id = dc.external_source_id AND es.is_enabled = TRUE"
        "     ))"
    )
    sql = text(f"""
        SELECT
            dc.chunk_text,
            dc.source_type,
            dc.source_url,
            dc.source_title,
            dc.created_at,
            dc.is_global,
            COALESCE(dc.chunk_meta_json, '{{}}'::jsonb) AS meta,
            1 - (dc.embedding <=> :embedding ::vector) AS score
        FROM document_chunks dc
        WHERE dc.embedding IS NOT NULL
          AND (dc.org_id = :org_id OR ({global_gate}))
          {filters}
        ORDER BY score DESC
        LIMIT {limit}
    """)
    try:
        result = await db.execute(sql, params)
        rows = result.fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception as exc:
        logger.warning("Semantic retrieve failed: %s", exc)
        return []


# ── BM25 / full-text retrieval ────────────────────────────────────────────────

async def _bm25_retrieve(
    query: str,
    org_id: uuid.UUID,
    db: AsyncSession,
    source_systems: list[str] | None,
    limit: int = 20,
) -> list[dict]:
    """
    PostgreSQL full-text search using ts_rank against chunk_text.
    Automatically handles multi-word queries via plainto_tsquery.
    """
    filters = ""
    params: dict = {"org_id": str(org_id), "query": query}

    if source_systems:
        filters += " AND meta->>'source_system' = ANY(:source_systems)"
        params["source_systems"] = source_systems

    # Callstack gate: same as semantic retrieve — disabled sources are excluded
    global_gate_bm25 = (
        "dc.is_global = TRUE "
        "AND (dc.external_source_id IS NULL "
        "     OR EXISTS ("
        "         SELECT 1 FROM external_sources es "
        "         WHERE es.id = dc.external_source_id AND es.is_enabled = TRUE"
        "     ))"
    )
    sql = text(f"""
        SELECT
            dc.chunk_text,
            dc.source_type,
            dc.source_url,
            dc.source_title,
            dc.created_at,
            dc.is_global,
            COALESCE(dc.chunk_meta_json, '{{}}'::jsonb) AS meta,
            ts_rank(
                to_tsvector('english', dc.chunk_text),
                plainto_tsquery('english', :query)
            ) AS score
        FROM document_chunks dc
        WHERE (dc.org_id = :org_id OR ({global_gate_bm25}))
          AND to_tsvector('english', dc.chunk_text) @@ plainto_tsquery('english', :query)
          {filters}
        ORDER BY score DESC
        LIMIT {limit}
    """)
    try:
        result = await db.execute(sql, params)
        rows = result.fetchall()
        return [dict(r._mapping) for r in rows]
    except Exception as exc:
        logger.warning("BM25 retrieve failed: %s", exc)
        return []


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank + 1)


def _fuse(
    semantic_rows: list[dict],
    bm25_rows: list[dict],
    query_entities: dict | None,
) -> list[dict]:
    """
    Merge semantic + BM25 results via RRF.
    Key = (source_url or chunk_text[:80]) for deduplication.
    """
    scores: dict[str, dict] = {}

    def _key(row: dict) -> str:
        return row.get("source_url") or row["chunk_text"][:80]

    for rank, row in enumerate(semantic_rows):
        k = _key(row)
        if k not in scores:
            scores[k] = {**row, "sem_score": 0.0, "bm25_score": 0.0, "rrf": 0.0}
        scores[k]["sem_score"]  = float(row["score"])
        scores[k]["rrf"]       += SEMANTIC_WEIGHT * _rrf_score(rank)

    for rank, row in enumerate(bm25_rows):
        k = _key(row)
        if k not in scores:
            scores[k] = {**row, "sem_score": 0.0, "bm25_score": 0.0, "rrf": 0.0}
        scores[k]["bm25_score"] = float(row["score"])
        scores[k]["rrf"]       += BM25_WEIGHT * _rrf_score(rank)

    # Entity match bonus
    if query_entities:
        all_query_terms = set()
        for vals in query_entities.values():
            if isinstance(vals, list):
                all_query_terms.update(v.lower() for v in vals)

        for k, entry in scores.items():
            text_lower = entry["chunk_text"].lower()
            matches = sum(1 for term in all_query_terms if term in text_lower)
            scores[k]["rrf"] += ENTITY_WEIGHT * min(matches, 5) / 5.0

    # Sort by RRF descending
    return sorted(scores.values(), key=lambda x: -x["rrf"])


# ── Chunk type / source system ranking boost ──────────────────────────────────

_TRUST_CLASS_SCORE: dict[str, float] = {
    "V5": 1.0, "V4": 0.85, "V3": 0.70, "V2": 0.45, "V1": 0.25
}


def _apply_ranking_boosts(rows: list[dict], query_contexts: set[str]) -> list[dict]:
    import json
    now = datetime.now(timezone.utc)

    for row in rows:
        meta = row.get("meta") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}

        chunk_type    = meta.get("chunk_type", "general")
        source_system = meta.get("source_system", "")
        is_global     = row.get("is_global", False)

        # Trust score from profile (loaded into meta during ingest)
        trust_class  = meta.get("trust_class", "V3")
        trust_score  = meta.get("trust_score", _TRUST_CLASS_SCORE.get(trust_class, 0.5))

        # Freshness score (decay over time, max 1.0 = just indexed)
        created_at = row.get("created_at")
        freshness = 0.5
        if created_at:
            try:
                if isinstance(created_at, str):
                    from dateutil.parser import parse as _parse
                    created_at = _parse(created_at)
                age_days = max(0, (now - created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else now - created_at).days)
                freshness = max(0.1, 1.0 - age_days / 365.0)
            except Exception:
                freshness = 0.5

        # Context score: does chunk type match query context?
        context_match = 0.5
        if "security" in query_contexts and chunk_type in ("permission", "rule"):
            context_match = 1.0
        elif "architecture" in query_contexts and chunk_type in ("integration_pattern", "api_reference"):
            context_match = 1.0
        elif "general" in query_contexts:
            context_match = 0.7

        # Compute spec-compliant final score
        sem   = float(row.get("sem_score", 0.0))
        kw    = float(row.get("bm25_score", 0.0))
        ent   = ENTITY_WEIGHT * float(row.get("entity_bonus", 0.0))
        trust = TRUST_WEIGHT * trust_score
        ctx   = CONTEXT_WEIGHT * context_match
        fresh = FRESHNESS_WEIGHT * freshness

        spec_score = (
            SEMANTIC_WEIGHT * sem +
            KEYWORD_WEIGHT * kw +
            ent + trust + ctx + fresh
        )

        # Boost global (authoritative) sources slightly
        if is_global:
            spec_score += 0.02

        row["rrf"] = spec_score
        row["_meta"] = meta
        row["_trust_class"] = trust_class
        row["_trust_score"] = trust_score
        row["_source_category"] = meta.get("source_category", "")
        row["_freshness"] = freshness

    return sorted(rows, key=lambda x: -x["rrf"])


# ── Public API ────────────────────────────────────────────────────────────────

async def hybrid_retrieve(
    query: str,
    org_id: uuid.UUID,
    db: AsyncSession,
    source_systems: list[str] | None = None,
    canonical_types: list[str] | None = None,
    query_entities: dict | None = None,
    min_score: float = MIN_SCORE,
    max_chunks: int = MAX_CHUNKS,
) -> HybridRetrievalResult:
    """
    Execute hybrid retrieval (Semantic + BM25 + Entity Filter).

    Args:
        query:           Natural language query.
        org_id:          Org UUID for scoping.
        db:              Async DB session.
        source_systems:  Filter to specific systems (e.g. ['salesforce', 'sap']).
        canonical_types: Filter by canonical entity type.
        query_entities:  Entity dict for match boosting (from entity extractor).
        min_score:       Minimum RRF threshold for inclusion.
        max_chunks:      Maximum chunks to return.

    Returns:
        HybridRetrievalResult with mode 'direct' | 'context' | 'none'.
    """
    embedding = await _embed(query)

    semantic_rows: list[dict] = []
    if embedding:
        semantic_rows = await _semantic_retrieve(
            embedding, org_id, db, source_systems, canonical_types
        )

    bm25_rows = await _bm25_retrieve(query, org_id, db, source_systems)

    if not semantic_rows and not bm25_rows:
        return HybridRetrievalResult(mode="none")

    # Classify query context for eligibility enforcement
    query_contexts = classify_query_context(query)

    fused = _fuse(semantic_rows, bm25_rows, query_entities)
    ranked = _apply_ranking_boosts(fused, query_contexts)

    # ── Hard eligibility filter ───────────────────────────────────────────────
    guardrail_warnings: list[str] = []
    eligible_rows = []
    for row in ranked:
        meta = row.get("_meta") or {}
        profile_dict = {
            "source_category": row.get("_source_category", ""),
            "trust_class":     row.get("_trust_class", "V3"),
            "eligibility":     meta.get("eligibility", {}),
        }
        result = check_eligibility(profile_dict, query_contexts, production_mode=True)
        if result.eligible:
            eligible_rows.append(row)
        else:
            if result.hard_rule:
                warn = f"Source excluded (hard rule): {result.reason}"
                if warn not in guardrail_warnings:
                    guardrail_warnings.append(warn)

    # Filter by minimum score
    qualifying = [r for r in eligible_rows if r.get("rrf", 0) >= min_score]

    if not qualifying:
        return HybridRetrievalResult(
            mode="none",
            guardrail_warnings=guardrail_warnings,
        )

    # ── Architecture guard: require ≥2 high-trust sources ────────────────────
    _TC_ORDER = {"V5": 5, "V4": 4, "V3": 3, "V2": 2, "V1": 1}
    if "architecture" in query_contexts:
        high_trust = [
            r for r in qualifying
            if _TC_ORDER.get(r.get("_trust_class", "V1"), 0) >= 3  # >= V3
        ]
        if len(high_trust) < ARCH_MIN_SOURCES:
            guardrail_warnings.append(
                f"Architecture query: only {len(high_trust)} high-trust source(s) found "
                f"(minimum {ARCH_MIN_SOURCES} required). Answer may be incomplete."
            )

    chunks: list[HybridChunk] = []
    for row in qualifying[:max_chunks]:
        meta = row.get("_meta") or {}
        trust_class = row.get("_trust_class", "V3")
        trust_score = row.get("_trust_score", 0.5)
        # Evidence type: primary if V4/V5 or manufacturer/internal_approved
        category = row.get("_source_category", "")
        is_primary = (
            _TC_ORDER.get(trust_class, 0) >= 4
            or category in ("manufacturer", "internal_approved", "standard_norm")
        )
        chunks.append(HybridChunk(
            text=row["chunk_text"],
            semantic_score=float(row.get("sem_score", 0.0)),
            bm25_score=float(row.get("bm25_score", 0.0)),
            final_score=float(row.get("rrf", 0.0)),
            source_system=meta.get("source_system", row.get("source_type", "")),
            source_type=row.get("source_type", ""),
            source_url=row.get("source_url"),
            source_title=row.get("source_title"),
            chunk_type=meta.get("chunk_type", "general"),
            canonical_type=meta.get("canonical_type", ""),
            entities=meta.get("entities", {}),
            indexed_at=row["created_at"].isoformat() if row.get("created_at") else None,
            is_global=bool(row.get("is_global", False)),
            trust_class=trust_class,
            trust_score=trust_score,
            source_category=category,
            evidence_type="primary" if is_primary else "supporting",
        ))

    # ── Conflict detection (post-retrieval, always surfaces if detected) ──────
    chunk_dicts = [
        {
            "chunk_text": c.text,
            "source_url": c.source_url,
            "source_system": c.source_system,
            "source_category": c.source_category,
        }
        for c in chunks
    ]
    conflicts = detect_conflicts(chunk_dicts, query_contexts)

    top_score = chunks[0].semantic_score if chunks else 0.0
    mode: Literal["direct", "context", "none"] = (
        "direct" if top_score >= DIRECT_THRESHOLD else "context"
    )

    return HybridRetrievalResult(
        mode=mode,
        chunks=chunks,
        conflicts=conflicts,
        guardrail_warnings=guardrail_warnings,
    )
