"""Unit tests for PdfService template rendering."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
import uuid


def make_mock_story():
    story = MagicMock()
    story.id = uuid.uuid4()
    story.title = "Als Nutzer möchte ich mich einloggen"
    story.description = "Mit E-Mail und Passwort"
    story.acceptance_criteria = "Login funktioniert"
    story.status.value = "done"
    story.priority.value = "high"
    story.story_points = 3
    story.quality_score = 92
    story.created_at = datetime(2026, 3, 24, tzinfo=timezone.utc)
    story.definition_of_done = '["Tests grün", "Code reviewed"]'
    story.doc_additional_info = None
    story.generated_docs = '{"summary": "Eine Login-Story.", "technical_notes": "JWT-basiert.", "changelog": "v1.0"}'
    return story


def make_mock_settings():
    s = MagicMock()
    s.company_name = "Acme GmbH"
    s.page_format = "a4"
    s.language = "de"
    s.header_text = None
    s.footer_text = "Vertraulich"
    s.letterhead_filename = None
    s.logo_filename = None
    return s


def test_render_html_contains_title():
    """Rendered HTML contains the story title."""
    from app.services.pdf_service import PdfService
    service = PdfService()
    story = make_mock_story()
    settings = make_mock_settings()

    html = service.render_html(story, settings, test_cases=[], features=[])

    assert "Als Nutzer möchte ich mich einloggen" in html
    assert "Acme GmbH" in html
    assert "Vertraulich" in html


def test_render_html_contains_test_cases():
    """Rendered HTML includes test case table when test_cases provided."""
    from app.services.pdf_service import PdfService
    service = PdfService()
    story = make_mock_story()
    settings = make_mock_settings()

    tc = MagicMock()
    tc.title = "Login mit gültigen Daten"
    tc.status.value = "passed"
    tc.expected_result = "Redirect zu Dashboard"

    html = service.render_html(story, settings, test_cases=[tc], features=[])

    assert "Login mit gültigen Daten" in html
    assert "Redirect zu Dashboard" in html


def test_render_html_no_crash_with_empty_docs():
    """render_html works when generated_docs is None or empty."""
    from app.services.pdf_service import PdfService
    service = PdfService()
    story = make_mock_story()
    story.generated_docs = None
    settings = make_mock_settings()

    html = service.render_html(story, settings, test_cases=[], features=[])
    assert "Als Nutzer" in html
