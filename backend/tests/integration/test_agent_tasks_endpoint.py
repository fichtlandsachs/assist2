"""Integration test: invoking an agent dispatches the celery task."""
import pytest
import pytest_asyncio
import uuid
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent


@pytest_asyncio.fixture
async def test_agent(db: AsyncSession, test_user, test_org) -> Agent:
    agent = Agent(
        organization_id=test_org.id,
        name="TestAgent",
        role="story_analyzer",
        model="claude-sonnet-4-6",
        config={},
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@pytest.mark.asyncio
async def test_invoke_agent_dispatches_analyze_task(
    client: AsyncClient, auth_headers: dict, test_agent: Agent, test_org
):
    """POST /organizations/{org_id}/agents/{agent_id}/invoke triggers analyze_story_task.delay."""
    story_id = str(uuid.uuid4())

    with patch("app.routers.agents.analyze_story_task") as mock_task:
        mock_task.delay = MagicMock()
        resp = await client.post(
            f"/api/v1/organizations/{test_org.id}/agents/{test_agent.id}/invoke",
            json={"input": {"story_id": story_id}},
            headers=auth_headers,
        )

    assert resp.status_code in (200, 202)
    body = resp.json()
    assert "invocation_id" in body
    assert body["status"] == "running"
    mock_task.delay.assert_called_once_with(story_id, str(test_org.id))


@pytest.mark.asyncio
async def test_invoke_agent_without_story_id_does_not_dispatch(
    client: AsyncClient, auth_headers: dict, test_agent: Agent, test_org
):
    """Invoke without story_id in input should not call analyze_story_task.delay."""
    with patch("app.routers.agents.analyze_story_task") as mock_task:
        mock_task.delay = MagicMock()
        resp = await client.post(
            f"/api/v1/organizations/{test_org.id}/agents/{test_agent.id}/invoke",
            json={"input": {"some_other_key": "value"}},
            headers=auth_headers,
        )

    assert resp.status_code in (200, 202)
    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_invoke_agent_inactive_returns_404(
    client: AsyncClient, auth_headers: dict, db: AsyncSession, test_org
):
    """Invoking an inactive agent should return 404."""
    inactive_agent = Agent(
        organization_id=test_org.id,
        name="InactiveAgent",
        role="story_analyzer",
        model="claude-sonnet-4-6",
        config={},
        is_active=False,
    )
    db.add(inactive_agent)
    await db.commit()
    await db.refresh(inactive_agent)

    resp = await client.post(
        f"/api/v1/organizations/{test_org.id}/agents/{inactive_agent.id}/invoke",
        json={"input": {"story_id": str(uuid.uuid4())}},
        headers=auth_headers,
    )

    assert resp.status_code == 404
