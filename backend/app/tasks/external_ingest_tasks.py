# app/tasks/external_ingest_tasks.py
"""Celery tasks for external documentation source ingest."""
from __future__ import annotations

import asyncio
import logging
import uuid

from app.celery_app import celery
from app.database import AsyncSessionLocal
from app.models.external_source import ExternalSource, ExternalSourceRun

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery.task(name="external_ingest.run_initial", bind=True, max_retries=1)
def run_initial_ingest(self, source_id: str, run_id: str) -> dict:
    """Full initial ingest for an external source."""
    from app.services.crawl.ingest_run_service import IngestRunService

    async def _inner():
        async with AsyncSessionLocal() as db:
            source = await db.get(ExternalSource, uuid.UUID(source_id))
            if not source:
                raise ValueError(f"Source {source_id} not found")
        svc = IngestRunService(source)
        return await svc.run_initial(uuid.UUID(run_id))

    try:
        return _run_async(_inner())
    except Exception as exc:
        logger.exception("Initial ingest failed: %s", exc)
        self.retry(countdown=300, exc=exc)


@celery.task(name="external_ingest.run_refresh", bind=True, max_retries=2)
def run_refresh_ingest(self, source_id: str, run_id: str) -> dict:
    """Refresh ingest for an external source."""
    from app.services.crawl.ingest_run_service import IngestRunService

    async def _inner():
        async with AsyncSessionLocal() as db:
            source = await db.get(ExternalSource, uuid.UUID(source_id))
            if not source:
                raise ValueError(f"Source {source_id} not found")
        svc = IngestRunService(source)
        return await svc.run_refresh(uuid.UUID(run_id))

    try:
        return _run_async(_inner())
    except Exception as exc:
        logger.exception("Refresh ingest failed: %s", exc)
        self.retry(countdown=300, exc=exc)
