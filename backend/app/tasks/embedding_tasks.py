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
