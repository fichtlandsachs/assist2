from app.celery_app import celery


@celery.task(name="agent_tasks.invoke_agent", bind=True, max_retries=3)
def invoke_agent_task(self, agent_id: str, story_id: str, context: dict):
    """Invoke an AI agent asynchronously."""
    import asyncio
    from app.database import AsyncSessionLocal
    from app.services.ai_story_service import get_story_suggestions
    from app.schemas.user_story import AISuggestRequest
    try:
        # Placeholder for full agent invocation
        return {"status": "completed", "agent_id": agent_id, "story_id": story_id}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
