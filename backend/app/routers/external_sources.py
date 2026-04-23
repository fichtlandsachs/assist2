# app/routers/external_sources.py
"""Admin API for managing external documentation sources."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
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
    await db.commit()
    return {"status": "disabled"}


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
