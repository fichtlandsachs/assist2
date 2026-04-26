# app/services/crawl/ingest_run_service.py
"""Orchestrates a complete or refresh ingest run for an external source."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.external_source import ExternalSource, ExternalSourcePage, ExternalSourceRun
from app.services.crawl.chunking_service import ChunkingService
from app.services.crawl.discovery_service import DiscoveryService
from app.services.crawl.embedding_index_service import EmbeddingIndexService
from app.services.crawl.extraction_service import ExtractionService
from app.services.crawl.fetch_service import FetchService
from app.services.crawl.universal_entity_service import UniversalEntityExtractor
from app.services.crawl.url_canonicalizer import UrlCanonicalizer

logger = logging.getLogger(__name__)


class IngestRunService:
    def __init__(self, source: ExternalSource) -> None:
        self.source = source
        cfg = source.config_json
        crawl_cfg = cfg.get("crawl_policy", {})
        chunk_cfg = cfg.get("chunking_policy", {})
        embed_cfg = cfg.get("embedding_policy", {})
        extract_cfg = cfg.get("extraction_policy", {})

        self.canonicalizer = UrlCanonicalizer(
            required_params=cfg.get("required_query_params", {}),
            dropped_params=set(cfg.get("dropped_query_params", [])),
            allowed_prefixes=cfg.get("include_url_prefixes", [source.base_url]),
            allowed_domains=cfg.get("allowed_domains", []),
        )
        self.discovery = DiscoveryService(
            canonicalizer=self.canonicalizer,
            seed_urls=cfg.get("seed_urls", [source.base_url]),
            allowed_prefixes=cfg.get("include_url_prefixes", []),
            crawl_delay=crawl_cfg.get("request_delay_seconds", 1.0),
        )
        self.fetcher = FetchService(
            timeout=crawl_cfg.get("request_timeout_seconds", 30),
            max_retries=crawl_cfg.get("max_retries", 3),
            delay_between_requests=crawl_cfg.get("request_delay_seconds", 1.0),
            thin_threshold=crawl_cfg.get("thin_content_threshold", 200),
        )
        self.extractor = ExtractionService(
            content_selectors=extract_cfg.get("content_selectors", []),
            exclude_selectors=extract_cfg.get("exclude_selectors", []),
            min_content_length=extract_cfg.get("min_content_length", 100),
        )
        self.chunker = ChunkingService(
            target_tokens=chunk_cfg.get("target_chunk_tokens", 800),
            overlap_tokens=chunk_cfg.get("overlap_tokens", 120),
            max_tokens=chunk_cfg.get("max_chunk_tokens", 1200),
        )
        self.embedder = EmbeddingIndexService(
            batch_size=embed_cfg.get("batch_size", 32),
        )
        self.entity_extractor = UniversalEntityExtractor()
        self.metadata_defaults = cfg.get("metadata_defaults", {})
        self.max_concurrency = crawl_cfg.get("max_concurrency", 2)

    async def run_initial(self, run_id: uuid.UUID) -> dict:
        """Full discovery + ingest of all pages."""
        stats: dict = {
            "discovered": 0, "fetched": 0, "rendered": 0,
            "extracted": 0, "chunked": 0, "embedded": 0,
            "skipped_unchanged": 0, "failed": 0,
        }
        async with AsyncSessionLocal() as db:
            run = await db.get(ExternalSourceRun, run_id)
            if not run:
                raise ValueError(f"Run {run_id} not found")
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

        try:
            logger.info("Starting discovery for source %s", self.source.source_key)
            canonical_urls = await self.discovery.discover_all()
            stats["discovered"] = len(canonical_urls)
            logger.info("Discovered %d URLs", len(canonical_urls))

            async with AsyncSessionLocal() as db:
                for canon_url in canonical_urls:
                    await self._upsert_page_record(db, canon_url)
                await db.commit()

            semaphore = asyncio.Semaphore(self.max_concurrency)
            tasks = [
                self._process_page(canon_url, stats, semaphore, is_refresh=False)
                for canon_url in canonical_urls
            ]
            await asyncio.gather(*tasks)

        except Exception as exc:
            logger.exception("Run %s failed: %s", run_id, exc)
            async with AsyncSessionLocal() as db:
                run = await db.get(ExternalSourceRun, run_id)
                if run:
                    run.status = "failed"
                    run.finished_at = datetime.now(timezone.utc)
                    run.error_summary = str(exc)
                    run.stats_json = stats
                    await db.commit()
            raise

        async with AsyncSessionLocal() as db:
            run = await db.get(ExternalSourceRun, run_id)
            if run:
                run.status = "completed"
                run.finished_at = datetime.now(timezone.utc)
                run.stats_json = stats
                await db.commit()

        logger.info("Run %s complete: %s", run_id, stats)
        return stats

    async def run_refresh(self, run_id: uuid.UUID) -> dict:
        """Refresh run: check existing pages for changes, discover new ones."""
        stats: dict = {
            "discovered": 0, "fetched": 0, "rendered": 0,
            "extracted": 0, "chunked": 0, "embedded": 0,
            "skipped_unchanged": 0, "failed": 0,
        }
        async with AsyncSessionLocal() as db:
            run = await db.get(ExternalSourceRun, run_id)
            if run:
                run.status = "running"
                run.started_at = datetime.now(timezone.utc)
                await db.commit()

            result = await db.execute(
                select(ExternalSourcePage).where(
                    ExternalSourcePage.source_id == self.source.id,
                    ExternalSourcePage.is_active == True,  # noqa: E712
                )
            )
            existing_pages = result.scalars().all()

        canonical_urls = await self.discovery.discover_all()
        stats["discovered"] = len(canonical_urls)

        existing_map = {p.canonical_url: p for p in existing_pages}
        all_urls = set(canonical_urls) | set(existing_map.keys())

        semaphore = asyncio.Semaphore(self.max_concurrency)
        tasks = [
            self._process_page(
                url, stats, semaphore, is_refresh=True,
                existing_page=existing_map.get(url),
            )
            for url in all_urls
        ]
        await asyncio.gather(*tasks)

        async with AsyncSessionLocal() as db:
            run = await db.get(ExternalSourceRun, run_id)
            if run:
                run.status = "completed"
                run.finished_at = datetime.now(timezone.utc)
                run.stats_json = stats
                await db.commit()

        return stats

    async def _process_page(
        self,
        canonical_url: str,
        stats: dict,
        semaphore: asyncio.Semaphore,
        is_refresh: bool,
        existing_page: Optional[ExternalSourcePage] = None,
    ) -> None:
        async with semaphore:
            try:
                etag = existing_page.etag if existing_page else None
                last_mod = existing_page.last_modified if existing_page else None

                fetch_result = await self.fetcher.fetch(
                    canonical_url, canonical_url, etag=etag, last_modified=last_mod
                )
                stats["fetched"] += 1
                if fetch_result.fetch_method == "rendered":
                    stats["rendered"] += 1

                if fetch_result.http_status == 304:
                    stats["skipped_unchanged"] += 1
                    return

                if fetch_result.error or fetch_result.http_status >= 400:
                    stats["failed"] += 1
                    await self._mark_page_failed(
                        canonical_url,
                        fetch_result.error or f"HTTP {fetch_result.http_status}",
                    )
                    return

                if is_refresh and existing_page and existing_page.content_hash == fetch_result.content_hash:
                    stats["skipped_unchanged"] += 1
                    return

                extracted = self.extractor.extract(
                    fetch_result.html, canonical_url, fetch_result.fetch_method
                )
                stats["extracted"] += 1

                # Run universal entity extraction and merge into chunk metadata
                entity_result = self.entity_extractor.extract(
                    text=extracted.plain_text,
                    page_title=extracted.title,
                    breadcrumb=extracted.breadcrumb,
                    source_key=self.source.source_key,
                    metadata_defaults=self.metadata_defaults,
                )
                chunk_metadata = {
                    **self.metadata_defaults,
                    **entity_result.to_chunk_meta(
                        vendor=self.metadata_defaults.get("vendor", ""),
                        doc_category=self.metadata_defaults.get("doc_category", ""),
                        language=self.metadata_defaults.get("language", "en"),
                    ),
                }

                chunks = self.chunker.chunk_page(
                    canonical_url=canonical_url,
                    page_title=extracted.title,
                    sections=extracted.structured_sections,
                    plain_text=extracted.plain_text,
                    source_metadata=chunk_metadata,
                )
                stats["chunked"] += len(chunks)

                async with AsyncSessionLocal() as db:
                    count = await self.embedder.embed_and_upsert(
                        db=db,
                        source_id=self.source.id,
                        page_canonical_url=canonical_url,
                        chunks=chunks,
                        source_key=self.source.source_key,
                        external_source_id=self.source.id,
                    )
                    stats["embedded"] += count

                    await self._update_page_record(
                        db, canonical_url, fetch_result, extracted.extraction_quality_score
                    )

            except Exception as exc:
                logger.warning("Failed to process %s: %s", canonical_url, exc)
                stats["failed"] += 1
                await self._mark_page_failed(canonical_url, str(exc))

    async def _upsert_page_record(self, db: AsyncSession, canonical_url: str) -> None:
        result = await db.execute(
            select(ExternalSourcePage).where(
                ExternalSourcePage.source_id == self.source.id,
                ExternalSourcePage.canonical_url == canonical_url,
            )
        )
        page = result.scalar_one_or_none()
        if not page:
            db.add(ExternalSourcePage(
                source_id=self.source.id,
                raw_url=canonical_url,
                canonical_url=canonical_url,
                status="pending",
                discovered_at=datetime.now(timezone.utc),
            ))

    async def _update_page_record(
        self,
        db: AsyncSession,
        canonical_url: str,
        fetch_result,
        quality_score: float,
    ) -> None:
        result = await db.execute(
            select(ExternalSourcePage).where(
                ExternalSourcePage.source_id == self.source.id,
                ExternalSourcePage.canonical_url == canonical_url,
            )
        )
        page = result.scalar_one_or_none()
        if not page:
            page = ExternalSourcePage(
                source_id=self.source.id,
                raw_url=canonical_url,
                canonical_url=canonical_url,
                discovered_at=datetime.now(timezone.utc),
            )
            db.add(page)

        page.status = "embedded"
        page.fetched_at = fetch_result.fetched_at
        page.extracted_at = datetime.now(timezone.utc)
        page.http_status = fetch_result.http_status
        page.fetch_method = fetch_result.fetch_method
        page.content_hash = fetch_result.content_hash
        page.etag = fetch_result.etag
        page.last_modified = fetch_result.last_modified
        page.last_changed_at = datetime.now(timezone.utc)
        page.metadata_json = {"quality_score": quality_score}
        await db.commit()

    async def _mark_page_failed(self, canonical_url: str, error: str) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExternalSourcePage).where(
                    ExternalSourcePage.source_id == self.source.id,
                    ExternalSourcePage.canonical_url == canonical_url,
                )
            )
            page = result.scalar_one_or_none()
            if page:
                page.status = "failed"
                page.error_detail = error
                await db.commit()
