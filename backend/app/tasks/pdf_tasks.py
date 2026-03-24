"""Celery task: generate PDF for a user story."""
import asyncio
import json
import logging
import uuid
from types import SimpleNamespace

from sqlalchemy import select

from app.celery_app import celery
from app.database import AsyncSessionLocal
from app.models.user_story import UserStory
from app.models.test_case import TestCase
from app.models.feature import Feature
from app.models.pdf_settings import PdfSettings
from app.services.pdf_service import pdf_service

logger = logging.getLogger(__name__)


async def _generate_pdf_async(story_id: str, org_id: str) -> None:
    """Async implementation — called from sync Celery task via asyncio.run()."""
    async with AsyncSessionLocal() as db:
        # 1. Load story
        result = await db.execute(
            select(UserStory).where(
                UserStory.id == uuid.UUID(story_id),
                UserStory.organization_id == uuid.UUID(org_id),
            )
        )
        story = result.scalar_one_or_none()
        if story is None:
            logger.warning(f"generate_story_pdf: story {story_id} not found — skipping")
            return

        # 2. Load PDF settings (fall back to defaults if none configured)
        settings_result = await db.execute(
            select(PdfSettings).where(PdfSettings.organization_id == uuid.UUID(org_id))
        )
        settings = settings_result.scalar_one_or_none()
        if settings is None:
            settings = SimpleNamespace(
                company_name=None, page_format="a4", language="de",
                header_text=None, footer_text=None,
                letterhead_filename=None, logo_filename=None,
            )

        # 3. Load related data
        tc_result = await db.execute(
            select(TestCase).where(TestCase.story_id == story.id)
        )
        test_cases = tc_result.scalars().all()

        feat_result = await db.execute(
            select(Feature).where(Feature.story_id == story.id)
        )
        features = feat_result.scalars().all()

        # 4. Generate PDF and cache it
        filename = await pdf_service.generate_and_cache(story, settings, test_cases, features)

        # 5. Update generated_docs with pdf_url
        docs: dict = {}
        if story.generated_docs:
            try:
                docs = json.loads(story.generated_docs)
            except (json.JSONDecodeError, TypeError):
                docs = {}
        docs["pdf_url"] = f"cache:{filename}"
        story.generated_docs = json.dumps(docs)
        await db.commit()

        logger.info(f"PDF generated for story {story_id}: {filename}")


@celery.task(
    name="pdf_tasks.generate_story_pdf",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def generate_story_pdf(self, story_id: str, org_id: str) -> None:
    """
    Celery task: generate a PDF summary for a user story.
    Dispatched when story status transitions to 'done'.
    """
    try:
        asyncio.run(_generate_pdf_async(story_id, org_id))
    except Exception as exc:
        logger.error(f"PDF generation failed for story {story_id}: {exc}")
        raise self.retry(exc=exc)
