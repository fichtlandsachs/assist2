"""Integration tests for PDF settings API and story → done trigger."""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient

from app.models.user_story import UserStory, StoryStatus


@pytest.mark.asyncio
async def test_story_done_dispatches_pdf_task(client: AsyncClient, auth_headers: dict, test_org, db):
    """When a story is updated to done, generate_story_pdf.delay is called."""
    from sqlalchemy import select
    from app.models.user import User

    # Get the test user id
    result = await db.execute(select(User).where(User.email == "testuser@example.com"))
    test_user = result.scalar_one_or_none()

    story = UserStory(
        organization_id=test_org.id,
        created_by_id=test_user.id,
        title="Test PDF Story",
        description="Test",
        acceptance_criteria="AC",
        quality_score=85,
        status=StoryStatus.in_progress,
        generated_docs="{}",
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)

    with patch("app.routers.user_stories.generate_story_pdf") as mock_task:
        response = await client.patch(
            f"/api/v1/user-stories/{story.id}",
            json={"status": "done"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    mock_task.delay.assert_called_once_with(str(story.id), str(story.organization_id))


@pytest.mark.asyncio
async def test_get_pdf_settings_returns_defaults(client: AsyncClient, auth_headers: dict, test_org):
    """GET /pdf-settings returns empty defaults when no row exists."""
    response = await client.get(
        f"/api/v1/organizations/{test_org.id}/pdf-settings",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["page_format"] == "a4"
    assert data["language"] == "de"


@pytest.mark.asyncio
async def test_put_pdf_settings_saves(client: AsyncClient, auth_headers: dict, test_org):
    """PUT /pdf-settings creates or updates settings."""
    response = await client.put(
        f"/api/v1/organizations/{test_org.id}/pdf-settings",
        json={"company_name": "Test AG", "page_format": "letter", "language": "en"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["company_name"] == "Test AG"
    assert data["page_format"] == "letter"

    # Verify persistence
    get_resp = await client.get(
        f"/api/v1/organizations/{test_org.id}/pdf-settings",
        headers=auth_headers,
    )
    assert get_resp.json()["company_name"] == "Test AG"
