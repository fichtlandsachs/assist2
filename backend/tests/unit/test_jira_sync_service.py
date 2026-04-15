import pytest
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
