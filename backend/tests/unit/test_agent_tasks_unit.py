"""Unit tests for agent_tasks."""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_analyze_story_task_calls_ai_service():
    """analyze_story persists an AIStep with the AI response."""
    story_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())

    mock_story = MagicMock()
    mock_story.id = uuid.UUID(story_id)
    mock_story.title = "Login Feature"
    mock_story.description = "As a user I want to log in"
    mock_story.acceptance_criteria = "- Can log in with email"

    mock_suggestions = MagicMock()
    mock_suggestions.model_dump_json.return_value = '{"suggestions": []}'

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_story
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    with patch("app.tasks.agent_tasks.create_async_engine", return_value=mock_engine), \
         patch("app.tasks.agent_tasks.async_sessionmaker") as mock_sm, \
         patch("app.tasks.agent_tasks.get_story_suggestions", return_value=mock_suggestions) as mock_ai:

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.tasks.agent_tasks import _analyze_story
        result = await _analyze_story(story_id, org_id)

    assert result["status"] == "completed"
    assert result["story_id"] == story_id
    mock_ai.assert_called_once()
    mock_db.add.assert_called_once()  # AIStep was added


@pytest.mark.asyncio
async def test_analyze_story_task_story_not_found():
    """Returns error dict when story is missing."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    with patch("app.tasks.agent_tasks.create_async_engine", return_value=mock_engine), \
         patch("app.tasks.agent_tasks.async_sessionmaker") as mock_sm:

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.tasks.agent_tasks import _analyze_story
        result = await _analyze_story(str(uuid.uuid4()), str(uuid.uuid4()))

    assert result["status"] == "error"
    assert "not found" in result["detail"]


@pytest.mark.asyncio
async def test_trigger_ai_delivery_calls_n8n():
    """trigger_ai_delivery finds the workflow, creates an execution, calls n8n."""
    story_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())

    mock_workflow = MagicMock()
    mock_workflow.id = uuid.uuid4()
    mock_workflow.n8n_workflow_id = "ai-delivery-webhook-id"
    mock_workflow.version = 1

    mock_db = AsyncMock()
    mock_result_wf = MagicMock()
    mock_result_wf.scalar_one_or_none.return_value = mock_workflow
    mock_db.execute = AsyncMock(return_value=mock_result_wf)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    mock_n8n = AsyncMock(return_value={"executionId": "n8n-123"})

    with patch("app.tasks.agent_tasks.create_async_engine", return_value=mock_engine), \
         patch("app.tasks.agent_tasks.async_sessionmaker") as mock_sm, \
         patch("app.tasks.agent_tasks.n8n_client") as mock_client:

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.trigger_workflow = mock_n8n

        from app.tasks.agent_tasks import _trigger_ai_delivery
        result = await _trigger_ai_delivery(story_id, org_id)

    assert result["status"] == "triggered"
    mock_n8n.assert_called_once()
