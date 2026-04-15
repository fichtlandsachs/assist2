import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.user_story import UserStory


def test_user_story_has_jira_sync_fields():
    """UserStory model must have all 7 jira sync fields."""
    story = UserStory()
    assert hasattr(story, "jira_creator")
    assert hasattr(story, "jira_reporter")
    assert hasattr(story, "jira_created_at")
    assert hasattr(story, "jira_updated_at")
    assert hasattr(story, "jira_status")
    assert hasattr(story, "jira_linked_issue_keys")
    assert hasattr(story, "jira_last_synced_at")


def test_user_story_read_schema_has_jira_fields():
    """UserStoryRead schema must include all jira sync fields."""
    from app.schemas.user_story import UserStoryRead
    fields = UserStoryRead.model_fields
    assert "jira_creator" in fields
    assert "jira_reporter" in fields
    assert "jira_created_at" in fields
    assert "jira_updated_at" in fields
    assert "jira_status" in fields
    assert "jira_linked_issue_keys" in fields
    assert "jira_last_synced_at" in fields


@pytest.mark.asyncio
async def test_get_ticket_basic_returns_extended_fields():
    """get_ticket_basic must return creator, reporter, created, updated, issue_links."""
    from app.services.jira_service import JiraService

    mock_response_data = {
        "key": "PROJ-42",
        "id": "10042",
        "fields": {
            "summary": "Test Ticket",
            "description": None,
            "status": {"name": "In Progress"},
            "priority": {"name": "High"},
            "assignee": {"displayName": "Max Muster"},
            "reporter": {"displayName": "Anna Schmidt"},
            "creator": {"displayName": "Klaus Müller"},
            "created": "2025-03-12T10:00:00.000+0000",
            "updated": "2025-03-14T15:30:00.000+0000",
            "issuelinks": [
                {"outwardIssue": {"key": "PROJ-10"}},
                {"inwardIssue": {"key": "PROJ-20"}},
            ],
        },
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data
    mock_resp.raise_for_status = MagicMock()

    svc = JiraService()
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await svc.get_ticket_basic(
            base_url="https://example.atlassian.net",
            user="user@example.com",
            api_token="secret",
            key="PROJ-42",
        )

    assert result["status"] == "In Progress"
    assert result["creator"] == "Klaus Müller"
    assert result["reporter"] == "Anna Schmidt"
    assert result["created"] == "2025-03-12T10:00:00.000+0000"
    assert result["updated"] == "2025-03-14T15:30:00.000+0000"
    assert "PROJ-10" in result["issue_links"]
    assert "PROJ-20" in result["issue_links"]


@pytest.mark.asyncio
async def test_sync_story_updates_jira_fields():
    """sync_story_from_jira must map all Jira fields onto UserStory."""
    from app.services.jira_sync_service import JiraSyncService
    from app.models.user_story import UserStory

    org_id = uuid.uuid4()
    story = UserStory()
    story.id = uuid.uuid4()
    story.organization_id = org_id
    story.jira_ticket_key = "PROJ-42"
    story.jira_last_synced_at = None

    mock_org = MagicMock()
    mock_org.id = org_id

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_org)
    mock_db.commit = AsyncMock()

    jira_data = {
        "key": "PROJ-42",
        "summary": "Test",
        "description": "Beschreibung",
        "status": "In Progress",
        "creator": "Klaus Müller",
        "reporter": "Anna Schmidt",
        "created": "2025-03-12T10:00:00.000+0000",
        "updated": "2025-03-14T15:30:00.000+0000",
        "issue_links": ["PROJ-10", "PROJ-20"],
    }

    with patch(
        "app.services.jira_sync_service.get_jira_settings",
        return_value={"base_url": "https://example.atlassian.net", "user": "u@e.com"},
    ), patch(
        "app.services.jira_sync_service.get_jira_token",
        return_value="secret-token",
    ), patch(
        "app.services.jira_sync_service.jira_service.get_ticket_basic",
        new_callable=AsyncMock,
        return_value=jira_data,
    ):
        svc = JiraSyncService()
        changed = await svc.sync_story_from_jira(story, mock_db)

    assert changed is True
    assert story.jira_status == "In Progress"
    assert story.jira_creator == "Klaus Müller"
    assert story.jira_reporter == "Anna Schmidt"
    assert story.jira_linked_issue_keys == '["PROJ-10", "PROJ-20"]'
    assert story.jira_last_synced_at is not None
    assert story.jira_created_at is not None
    assert story.jira_updated_at is not None
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sync_story_skips_without_jira_integration():
    """sync_story_from_jira returns False when org has no Jira token."""
    from app.services.jira_sync_service import JiraSyncService
    from app.models.user_story import UserStory

    story = UserStory()
    story.jira_ticket_key = "PROJ-1"
    story.organization_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_org = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_org)

    with patch("app.services.jira_sync_service.get_jira_token", return_value=None):
        svc = JiraSyncService()
        changed = await svc.sync_story_from_jira(story, mock_db)

    assert changed is False
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_sync_story_handles_jira_exception():
    """sync_story_from_jira returns False when get_ticket_basic raises."""
    from app.services.jira_sync_service import JiraSyncService
    from app.models.user_story import UserStory

    story = UserStory()
    story.jira_ticket_key = "PROJ-99"
    story.organization_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_org = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_org)
    mock_db.commit = AsyncMock()

    with patch("app.services.jira_sync_service.get_jira_settings",
               return_value={"base_url": "https://x.atlassian.net", "user": "u@e.com"}), \
         patch("app.services.jira_sync_service.get_jira_token", return_value="tok"), \
         patch("app.services.jira_sync_service.jira_service.get_ticket_basic",
               new_callable=AsyncMock, side_effect=Exception("network error")):
        svc = JiraSyncService()
        changed = await svc.sync_story_from_jira(story, mock_db)

    assert changed is False
    mock_db.commit.assert_not_called()
