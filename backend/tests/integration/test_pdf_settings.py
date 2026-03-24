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
