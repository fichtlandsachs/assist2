# app/routers/external_sources.py
"""Admin API for managing external documentation sources."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document_chunk import DocumentChunk
from app.models.external_source import ExternalSource, ExternalSourcePage, ExternalSourceRun
from app.models.user import User
from app.routers.superadmin import get_admin_user
from app.schemas.external_source import (
    ExternalSourceCreate,
    ExternalSourcePageRead,
    ExternalSourceRead,
    ExternalSourceRunRead,
    IngestStartResponse,
    PreviewResponse,
)

router = APIRouter(prefix="/knowledge-sources/external", tags=["external-sources-admin"])
rag_meta_router = APIRouter(prefix="/knowledge-sources", tags=["rag-meta"])


def _source_to_read(source: ExternalSource) -> ExternalSourceRead:
    return ExternalSourceRead(
        id=source.id,
        source_key=source.source_key,
        display_name=source.display_name,
        source_type=source.source_type,
        base_url=source.base_url,
        config_json=source.config_json,
        visibility_scope=source.visibility_scope,
        is_enabled=source.is_enabled,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.post("", response_model=ExternalSourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: ExternalSourceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> ExternalSourceRead:
    existing = await db.execute(
        select(ExternalSource).where(ExternalSource.source_key == body.source_key)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Source key already exists")

    source = ExternalSource(
        source_key=body.source_key,
        display_name=body.display_name,
        base_url=body.base_url,
        visibility_scope=body.visibility_scope,
        config_json=body.config.model_dump(),
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return _source_to_read(source)


@router.get("", response_model=list[ExternalSourceRead])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[ExternalSourceRead]:
    result = await db.execute(
        select(ExternalSource).order_by(ExternalSource.created_at.desc())
    )
    return [_source_to_read(s) for s in result.scalars().all()]


@router.get("/{source_id}", response_model=ExternalSourceRead)
async def get_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> ExternalSourceRead:
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_to_read(source)


@router.post("/{source_id}/ingest", response_model=IngestStartResponse)
async def start_ingest(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> IngestStartResponse:
    source = await db.get(ExternalSource, source_id)
    if not source or not source.is_enabled:
        raise HTTPException(status_code=404, detail="Source not found or disabled")

    run = ExternalSourceRun(
        source_id=source_id,
        run_type="initial",
        status="pending",
        triggered_by=admin.email,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    from app.tasks.external_ingest_tasks import run_initial_ingest
    run_initial_ingest.delay(str(source_id), str(run.id))

    return IngestStartResponse(
        run_id=run.id,
        status="pending",
        message="Initial ingest started",
    )


@router.post("/{source_id}/refresh", response_model=IngestStartResponse)
async def start_refresh(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> IngestStartResponse:
    source = await db.get(ExternalSource, source_id)
    if not source or not source.is_enabled:
        raise HTTPException(status_code=404, detail="Source not found or disabled")

    run = ExternalSourceRun(
        source_id=source_id,
        run_type="refresh",
        status="pending",
        triggered_by=admin.email,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    from app.tasks.external_ingest_tasks import run_refresh_ingest
    run_refresh_ingest.delay(str(source_id), str(run.id))

    return IngestStartResponse(
        run_id=run.id,
        status="pending",
        message="Refresh ingest started",
    )


@router.post("/{source_id}/disable", status_code=status.HTTP_200_OK)
async def disable_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> dict:
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.is_enabled = False

    # Callstack enforcement: remove all indexed chunks for this source from the
    # document_chunks vector index so they are immediately invisible to RAG and
    # Hybrid Retrieval — even before the is_enabled gate would filter them.
    result = await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.external_source_id == source_id
        )
    )
    chunks_removed = result.rowcount
    await db.commit()

    return {"status": "disabled", "chunks_removed": chunks_removed}


@router.post("/{source_id}/enable", status_code=status.HTTP_200_OK)
async def enable_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict:
    """Re-enable a source. Chunks are only available again after a re-ingest."""
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.is_enabled = True
    await db.commit()

    # Automatically trigger a refresh ingest to rebuild the index
    run = ExternalSourceRun(
        source_id=source_id,
        run_type="refresh",
        status="pending",
        triggered_by=admin.email,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    from app.tasks.external_ingest_tasks import run_refresh_ingest
    run_refresh_ingest.delay(str(source_id), str(run.id))

    return {"status": "enabled", "run_id": str(run.id), "message": "Re-ingest started to rebuild index"}


@router.get("/{source_id}/runs", response_model=list[ExternalSourceRunRead])
async def list_runs(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[ExternalSourceRunRead]:
    result = await db.execute(
        select(ExternalSourceRun)
        .where(ExternalSourceRun.source_id == source_id)
        .order_by(desc(ExternalSourceRun.created_at))
        .limit(50)
    )
    return [ExternalSourceRunRead.model_validate(r) for r in result.scalars().all()]


@router.get("/{source_id}/pages", response_model=list[ExternalSourcePageRead])
async def list_pages(
    source_id: uuid.UUID,
    page_status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[ExternalSourcePageRead]:
    stmt = select(ExternalSourcePage).where(ExternalSourcePage.source_id == source_id)
    if page_status:
        stmt = stmt.where(ExternalSourcePage.status == page_status)
    stmt = stmt.order_by(ExternalSourcePage.canonical_url).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [ExternalSourcePageRead.model_validate(p) for p in result.scalars().all()]


@router.get("/{source_id}/failures", response_model=list[ExternalSourcePageRead])
async def list_failures(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[ExternalSourcePageRead]:
    result = await db.execute(
        select(ExternalSourcePage)
        .where(
            ExternalSourcePage.source_id == source_id,
            ExternalSourcePage.status == "failed",
        )
        .order_by(desc(ExternalSourcePage.updated_at))
        .limit(200)
    )
    return [ExternalSourcePageRead.model_validate(p) for p in result.scalars().all()]


@router.post("/{source_id}/retry-failures", response_model=IngestStartResponse)
async def retry_failures(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> IngestStartResponse:
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    result = await db.execute(
        select(ExternalSourcePage).where(
            ExternalSourcePage.source_id == source_id,
            ExternalSourcePage.status == "failed",
        )
    )
    pages = result.scalars().all()
    for page in pages:
        page.status = "pending"
    await db.commit()

    run = ExternalSourceRun(
        source_id=source_id,
        run_type="retry",
        status="pending",
        triggered_by=admin.email,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    from app.tasks.external_ingest_tasks import run_refresh_ingest
    run_refresh_ingest.delay(str(source_id), str(run.id))

    return IngestStartResponse(
        run_id=run.id,
        status="pending",
        message=f"Retrying {len(pages)} failed pages",
    )


@router.get("/{source_id}/preview", response_model=PreviewResponse)
async def preview_page(
    source_id: uuid.UUID,
    page_url: str = Query(...),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PreviewResponse:
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    from app.services.crawl.chunking_service import ChunkingService
    from app.services.crawl.extraction_service import ExtractionService
    from app.services.crawl.fetch_service import FetchService
    from app.services.crawl.url_canonicalizer import UrlCanonicalizer

    cfg = source.config_json
    canon = UrlCanonicalizer(
        required_params=cfg.get("required_query_params", {}),
        dropped_params=set(cfg.get("dropped_query_params", [])),
        allowed_prefixes=cfg.get("include_url_prefixes", []),
        allowed_domains=cfg.get("allowed_domains", []),
    )
    canonical_url = canon.canonicalize(page_url) or page_url

    fetcher = FetchService()
    fetch_result = await fetcher.fetch(page_url, canonical_url)
    if fetch_result.error:
        raise HTTPException(status_code=422, detail=f"Fetch failed: {fetch_result.error}")

    extractor = ExtractionService()
    extracted = extractor.extract(fetch_result.html, canonical_url, fetch_result.fetch_method)

    chunker = ChunkingService()
    chunks = chunker.chunk_page(
        canonical_url=canonical_url,
        page_title=extracted.title,
        sections=extracted.structured_sections,
        plain_text=extracted.plain_text,
        source_metadata={},
    )

    return PreviewResponse(
        canonical_url=canonical_url,
        title=extracted.title,
        breadcrumb=extracted.breadcrumb,
        headings=[f"H{level}: {text}" for level, text in extracted.headings[:10]],
        plain_text_preview=extracted.plain_text[:500],
        chunk_count=len(chunks),
        fetch_method=fetch_result.fetch_method,
        extraction_quality_score=extracted.extraction_quality_score,
    )


@router.get("/{source_id}/chunk-stats")
async def chunk_stats(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> dict:
    """Return indexed chunk count for this source (callstack integrity check)."""
    from sqlalchemy import func as sa_func, select as sa_select
    result = await db.execute(
        sa_select(sa_func.count()).where(
            DocumentChunk.external_source_id == source_id
        )
    )
    count = result.scalar() or 0
    return {"source_id": str(source_id), "indexed_chunks": count}


@router.post("/{source_id}/deindex", status_code=status.HTTP_200_OK)
async def deindex_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> dict:
    """Remove all indexed chunks for this source without disabling it.
    Use before a full re-ingest to ensure clean state.
    """
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    result = await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.external_source_id == source_id
        )
    )
    chunks_removed = result.rowcount
    await db.commit()
    return {"status": "deindexed", "chunks_removed": chunks_removed}


# ── Global stats ──────────────────────────────────────────────────────────────

@rag_meta_router.get("/stats")
async def global_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> dict:
    """System-wide RAG stats: source count, total chunks, enabled/disabled."""
    total_sources = (await db.execute(select(func.count()).select_from(ExternalSource))).scalar() or 0
    enabled_sources = (await db.execute(
        select(func.count()).select_from(ExternalSource).where(ExternalSource.is_enabled == True)
    )).scalar() or 0
    total_chunks = (await db.execute(select(func.count()).select_from(DocumentChunk))).scalar() or 0
    chunks_with_embedding = (await db.execute(
        select(func.count()).select_from(DocumentChunk).where(DocumentChunk.embedding.isnot(None))
    )).scalar() or 0
    pending_runs = (await db.execute(
        select(func.count()).select_from(ExternalSourceRun).where(ExternalSourceRun.status == "pending")
    )).scalar() or 0
    running_runs = (await db.execute(
        select(func.count()).select_from(ExternalSourceRun).where(ExternalSourceRun.status == "running")
    )).scalar() or 0

    # Per-source chunk counts
    per_source = await db.execute(
        select(
            ExternalSource.id,
            ExternalSource.display_name,
            ExternalSource.source_key,
            ExternalSource.is_enabled,
            func.count(DocumentChunk.id).label("chunk_count"),
        )
        .outerjoin(DocumentChunk, DocumentChunk.external_source_id == ExternalSource.id)
        .group_by(ExternalSource.id)
        .order_by(desc(func.count(DocumentChunk.id)))
    )
    source_stats = [
        {
            "id": str(r.id),
            "display_name": r.display_name,
            "source_key": r.source_key,
            "is_enabled": r.is_enabled,
            "chunk_count": r.chunk_count,
        }
        for r in per_source.fetchall()
    ]

    return {
        "total_sources": total_sources,
        "enabled_sources": enabled_sources,
        "disabled_sources": total_sources - enabled_sources,
        "total_chunks": total_chunks,
        "chunks_with_embedding": chunks_with_embedding,
        "chunks_missing_embedding": total_chunks - chunks_with_embedding,
        "pending_runs": pending_runs,
        "running_runs": running_runs,
        "per_source": source_stats,
    }


# ── Chunk browser ─────────────────────────────────────────────────────────────

@router.get("/{source_id}/chunks")
async def list_chunks(
    source_id: uuid.UUID,
    q: Optional[str] = Query(None, description="Filter by text content (ILIKE)"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> dict:
    """Browse indexed chunks for a source. Supports text search."""
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    stmt = select(DocumentChunk).where(DocumentChunk.external_source_id == source_id)
    count_stmt = select(func.count()).select_from(DocumentChunk).where(
        DocumentChunk.external_source_id == source_id
    )

    if q:
        stmt = stmt.where(DocumentChunk.chunk_text.ilike(f"%{q}%"))
        count_stmt = count_stmt.where(DocumentChunk.chunk_text.ilike(f"%{q}%"))

    stmt = stmt.order_by(DocumentChunk.created_at.desc()).limit(limit).offset(offset)

    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "chunks": [
            {
                "id": str(c.id),
                "source_ref": c.source_ref,
                "source_url": c.source_url,
                "source_title": c.source_title,
                "chunk_index": c.chunk_index,
                "chunk_text": c.chunk_text[:500],
                "chunk_text_length": len(c.chunk_text),
                "has_embedding": c.embedding is not None,
                "is_global": c.is_global,
                "created_at": c.created_at.isoformat(),
            }
            for c in rows
        ],
    }


# ── Search test console ───────────────────────────────────────────────────────

@rag_meta_router.post("/search-test")
async def search_test(
    body: dict,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> dict:
    """
    Hybrid search test endpoint. Runs semantic+BM25 retrieval against all
    orgs visible to superadmin (or restricted to a specific org_id).
    Returns ranked chunks with scores for debugging.
    """
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is required")

    org_id_str = body.get("org_id")
    source_types = body.get("source_types")
    use_hybrid = body.get("use_hybrid", True)
    min_score = float(body.get("min_score", 0.20))
    max_chunks = int(body.get("max_chunks", 8))

    if org_id_str:
        try:
            org_id = uuid.UUID(org_id_str)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid org_id")
    else:
        # Default: use a synthetic org_id = nil UUID to match global chunks only
        org_id = uuid.UUID("00000000-0000-0000-0000-000000000000")

    try:
        if use_hybrid:
            from app.services.hybrid_retrieval_service import hybrid_retrieve
            result = await hybrid_retrieve(
                query=query,
                org_id=org_id,
                db=db,
                source_systems=source_types,
                min_score=min_score,
                max_chunks=max_chunks,
            )
            chunks = [
                {
                    "text": c.text[:600],
                    "source_system": c.source_system,
                    "source_type": c.source_type,
                    "source_url": c.source_url,
                    "source_title": c.source_title,
                    "chunk_type": c.chunk_type,
                    "semantic_score": round(c.semantic_score, 4),
                    "bm25_score": round(c.bm25_score, 4),
                    "final_score": round(c.final_score, 4),
                    "trust_class": c.trust_class,
                    "trust_score": round(c.trust_score, 4),
                    "evidence_type": c.evidence_type,
                    "is_global": c.is_global,
                    "indexed_at": c.indexed_at,
                }
                for c in result.chunks
            ]
            return {
                "mode": result.mode,
                "query": query,
                "chunk_count": len(chunks),
                "chunks": chunks,
                "conflicts": [
                    {"type": c.conflict_type, "description": c.description}
                    for c in result.conflicts
                ],
                "guardrail_warnings": result.guardrail_warnings,
                "retrieval_type": "hybrid",
            }
        else:
            from app.services.rag_service import retrieve
            result = await retrieve(
                query=query,
                org_id=org_id,
                db=db,
                min_score=min_score,
                source_types=source_types,
            )
            return {
                "mode": result.mode,
                "query": query,
                "chunk_count": len(result.chunks),
                "chunks": [
                    {
                        "text": c.text[:600],
                        "score": round(c.score, 4),
                        "source_type": c.source_type,
                        "source_url": c.source_url,
                        "source_title": c.source_title,
                        "indexed_at": c.indexed_at,
                    }
                    for c in result.chunks
                ],
                "retrieval_type": "semantic",
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")
