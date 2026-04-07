from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.evaluation_run import EvaluationRun, EvaluationStatus, AmpelStatus
from app.models.user_story import UserStory
from app.core.exceptions import NotFoundException

logger = logging.getLogger(__name__)


async def start_evaluation(
    story_id: uuid.UUID,
    org_id: uuid.UUID,
    triggered_by_id: uuid.UUID,
    db: AsyncSession,
) -> EvaluationRun:
    """
    1. Load story from DB (verify org_id matches)
    2. Create evaluation_run (PENDING)
    3. Call LangGraph service synchronously
    4. Update run with result (COMPLETED or FAILED)
    5. Return run
    """
    settings = get_settings()

    story = await db.get(UserStory, story_id)
    if story is None or story.organization_id != org_id:
        raise NotFoundException("Story not found")

    run_id = uuid.uuid4()
    run = EvaluationRun(
        id=run_id,
        organization_id=org_id,
        story_id=story_id,
        triggered_by_id=triggered_by_id,
        status=EvaluationStatus.PENDING,
        knockout=False,
        input_tokens=0,
        output_tokens=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    payload = {
        "run_id": str(run_id),
        "story_id": str(story_id),
        "org_id": str(org_id),
        "title": story.title,
        "description": story.description or "",
        "acceptance_criteria": story.acceptance_criteria or "",
    }

    try:
        async with httpx.AsyncClient(timeout=float(settings.LANGGRAPH_TIMEOUT)) as client:
            response = await client.post(
                f"{settings.LANGGRAPH_BASE_URL}/workflows/evaluate",
                json=payload,
                headers={"X-API-Key": settings.LANGGRAPH_API_KEY},
            )
            response.raise_for_status()
            data = response.json()

        run.status = EvaluationStatus.COMPLETED
        run.score = data.get("score")
        run.ampel = AmpelStatus(data["ampel"]) if data.get("ampel") else None
        run.knockout = data.get("knockout", False)
        run.confidence = data.get("confidence")
        run.result_json = data
        run.model_used = data.get("model_used")
        run.input_tokens = data.get("input_tokens", 0)
        run.output_tokens = data.get("output_tokens", 0)
        run.completed_at = datetime.now(timezone.utc)

    except httpx.TimeoutException as e:
        logger.error("LangGraph timeout for run %s: %s", run_id, e)
        run.status = EvaluationStatus.FAILED
        run.error_message = f"Timeout nach {settings.LANGGRAPH_TIMEOUT}s"
        run.completed_at = datetime.now(timezone.utc)

    except httpx.HTTPStatusError as e:
        logger.error("LangGraph HTTP error for run %s: %s", run_id, e)
        run.status = EvaluationStatus.FAILED
        run.error_message = f"LangGraph HTTP {e.response.status_code}"
        run.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        logger.error("Unexpected error for run %s: %s", run_id, e)
        run.status = EvaluationStatus.FAILED
        run.error_message = str(e)[:500]
        run.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(run)
    return run


async def get_latest_evaluation(
    story_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> EvaluationRun | None:
    stmt = (
        select(EvaluationRun)
        .where(
            EvaluationRun.story_id == story_id,
            EvaluationRun.organization_id == org_id,
            EvaluationRun.deleted_at.is_(None),
            EvaluationRun.status == EvaluationStatus.COMPLETED,
        )
        .order_by(EvaluationRun.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
