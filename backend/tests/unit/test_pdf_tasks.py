"""Unit tests for generate_story_pdf Celery task."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_generate_story_pdf_calls_pdf_service():
    """Task fetches story data, calls pdf_service, updates generated_docs."""
    from app.tasks.pdf_tasks import _generate_pdf_async
    import asyncio

    story_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())

    mock_story = MagicMock()
    mock_story.id = uuid.UUID(story_id)
    mock_story.organization_id = uuid.UUID(org_id)
    mock_story.generated_docs = "{}"
    mock_story.status.value = "done"

    mock_settings_row = MagicMock()
    mock_settings_row.page_format = "a4"
    mock_settings_row.language = "de"
    mock_settings_row.letterhead_filename = None
    mock_settings_row.logo_filename = None

    mock_db = MagicMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.execute = AsyncMock()

    # Story query
    story_result = MagicMock()
    story_result.scalar_one_or_none.return_value = mock_story
    # Settings query
    settings_result = MagicMock()
    settings_result.scalar_one_or_none.return_value = mock_settings_row
    # test_cases query
    tc_result = MagicMock()
    tc_result.scalars.return_value.all.return_value = []
    # features query
    feat_result = MagicMock()
    feat_result.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [story_result, settings_result, tc_result, feat_result]
    mock_db.commit = AsyncMock()

    with patch("app.tasks.pdf_tasks.AsyncSessionLocal", return_value=mock_db), \
         patch("app.tasks.pdf_tasks.pdf_service") as mock_pdf:
        mock_pdf.generate_and_cache = AsyncMock(return_value="abc_2026-03-24.pdf")

        asyncio.run(_generate_pdf_async(story_id, org_id))

    mock_pdf.generate_and_cache.assert_called_once()
    mock_db.commit.assert_called_once()
    # Check generated_docs was updated
    import json
    docs = json.loads(mock_story.generated_docs)
    assert "pdf_url" in docs


def test_generate_story_pdf_skips_if_story_not_found():
    """Task exits gracefully when story does not exist."""
    from app.tasks.pdf_tasks import _generate_pdf_async
    import asyncio

    mock_db = MagicMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.execute = AsyncMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    with patch("app.tasks.pdf_tasks.AsyncSessionLocal", return_value=mock_db), \
         patch("app.tasks.pdf_tasks.pdf_service") as mock_pdf:
        # Should not raise
        asyncio.run(_generate_pdf_async(str(uuid.uuid4()), str(uuid.uuid4())))

    mock_pdf.generate_and_cache.assert_not_called()
