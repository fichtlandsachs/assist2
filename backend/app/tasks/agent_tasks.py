"""Celery tasks for AI agent invocation."""
import asyncio
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery
import app.models  # noqa: F401


async def _analyze_story(story_id: str, org_id: str) -> dict:
    from app.config import get_settings
    from app.models.user_story import UserStory
    from app.models.ai_step import AIStep, AIStepStatus
    from app.schemas.user_story import AISuggestRequest
    from app.services.ai_story_service import get_story_suggestions

    engine = create_async_engine(get_settings().DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            stmt = select(UserStory).where(UserStory.id == uuid.UUID(story_id))
            result = await db.execute(stmt)
            story = result.scalar_one_or_none()
            if story is None:
                return {"status": "error", "detail": "story not found"}

            req = AISuggestRequest(
                title=story.title,
                description=story.description or "",
                acceptance_criteria=story.acceptance_criteria or "",
            )
            suggestions = await get_story_suggestions(req)

            ai_step = AIStep(
                organization_id=uuid.UUID(org_id),
                story_id=uuid.UUID(story_id),
                agent_role="story_analyzer",
                model="claude-sonnet-4-6",
                status=AIStepStatus.completed,
                input_data=json.dumps({"title": story.title}),
                output_data=suggestions.model_dump_json()
                if hasattr(suggestions, "model_dump_json")
                else json.dumps(str(suggestions)),
            )
            db.add(ai_step)
            await db.commit()
    finally:
        await engine.dispose()

    return {"status": "completed", "story_id": story_id}


@celery.task(name="agent_tasks.analyze_story", bind=True, max_retries=3)
def analyze_story_task(self, story_id: str, org_id: str):
    """Run AI story analysis and persist the result as an AIStep."""
    try:
        return asyncio.run(_analyze_story(story_id, org_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


async def _trigger_ai_delivery(story_id: str, org_id: str) -> dict:
    from app.config import get_settings
    from app.models.workflow import WorkflowDefinition, WorkflowExecution
    from app.services.n8n_client import n8n_client

    engine = create_async_engine(get_settings().DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    execution_id = None
    try:
        async with SessionLocal() as db:
            stmt = select(WorkflowDefinition).where(
                WorkflowDefinition.slug == "ai-delivery",
                WorkflowDefinition.organization_id == uuid.UUID(org_id),
                WorkflowDefinition.is_active.is_(True),
            )
            result = await db.execute(stmt)
            workflow = result.scalar_one_or_none()
            if workflow is None:
                return {"status": "error", "detail": "ai-delivery workflow not found for org"}

            execution = WorkflowExecution(
                organization_id=uuid.UUID(org_id),
                definition_id=workflow.id,
                definition_version=workflow.version,
                n8n_execution_id="pending",
                status="pending",
                trigger_type="celery",
                input_snapshot={"story_id": story_id, "org_id": org_id},
                context_snapshot={"workflow_slug": "ai-delivery"},
            )
            db.add(execution)
            await db.flush()
            execution_id = str(execution.id)

            try:
                n8n_resp = await n8n_client.trigger_workflow(
                    workflow.n8n_workflow_id,
                    {"execution_id": execution_id, "story_id": story_id, "org_id": org_id},
                )
                execution.n8n_execution_id = str(n8n_resp.get("executionId", execution.id))
                execution.status = "running"
            except Exception as e:
                execution.status = "failed"
                execution.error_message = str(e)

            await db.commit()
    finally:
        await engine.dispose()

    return {"status": "triggered", "execution_id": execution_id}


@celery.task(name="agent_tasks.trigger_ai_delivery", bind=True, max_retries=3)
def trigger_ai_delivery_task(self, story_id: str, org_id: str):
    """Trigger the n8n ai-delivery workflow for a story."""
    try:
        return asyncio.run(_trigger_ai_delivery(story_id, org_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
