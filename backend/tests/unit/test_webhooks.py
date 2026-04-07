"""Unit tests for webhook endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


@pytest.mark.asyncio
async def test_confluence_webhook_missing_secret():
    """No X-Webhook-Secret header → 401."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/webhooks/confluence",
            json={"event": "page_updated", "page": {"id": "12345"}},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_confluence_webhook_invalid_secret():
    """Wrong X-Webhook-Secret → 401."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.deps import get_db

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/webhooks/confluence",
                json={"event": "page_updated", "page": {"id": "12345"}},
                headers={"X-Webhook-Secret": "wrong-secret"},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_confluence_webhook_valid_queues_task():
    """Valid secret → 200, index_confluence_space task queued."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.deps import get_db

    org_id = uuid.uuid4()
    mock_org = MagicMock()
    mock_org.id = org_id
    mock_org.metadata_ = {"webhook_secrets": {"confluence": "test-secret-conf"}}

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_org]

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("app.routers.webhooks.index_confluence_space") as mock_task:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/webhooks/confluence",
                    json={"event": "page_updated", "page": {"id": "12345"}},
                    headers={"X-Webhook-Secret": "test-secret-conf"},
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"
        mock_task.delay.assert_called_once_with(str(org_id))
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_jira_webhook_valid_queues_task():
    """Valid Jira secret → 200, index_jira_ticket task queued."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.deps import get_db

    org_id = uuid.uuid4()
    mock_org = MagicMock()
    mock_org.id = org_id
    mock_org.metadata_ = {"webhook_secrets": {"jira": "test-secret-jira"}}

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_org]

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch("app.routers.webhooks.index_jira_ticket") as mock_task:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/webhooks/jira",
                    json={"issue": {"key": "PROJ-42"}},
                    headers={"X-Webhook-Secret": "test-secret-jira"},
                )
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"
        mock_task.delay.assert_called_once_with("PROJ-42", str(org_id))
    finally:
        app.dependency_overrides.pop(get_db, None)
