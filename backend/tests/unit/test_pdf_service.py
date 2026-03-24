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


@pytest.mark.asyncio
async def test_generate_and_cache_pdf(tmp_path):
    """generate_and_cache stores PDF in cache path and returns filename."""
    from app.services.pdf_service import PdfService
    service = PdfService()
    story = make_mock_story()
    settings = make_mock_settings()

    with patch("app.services.pdf_service.stirling_client") as mock_stirling, \
         patch("app.services.pdf_service.get_settings") as mock_cfg:
        mock_stirling.html_to_pdf = AsyncMock(return_value=b"%PDF-fake")
        mock_cfg.return_value.PDF_CACHE_PATH = str(tmp_path)
        mock_cfg.return_value.PDF_TEMPLATES_PATH = str(tmp_path)

        filename = await service.generate_and_cache(story, settings, test_cases=[], features=[])

    assert filename.endswith(".pdf")
    assert str(story.id)[:8] in filename
    cached = tmp_path / filename
    assert cached.read_bytes() == b"%PDF-fake"


@pytest.mark.asyncio
async def test_generate_applies_letterhead(tmp_path):
    """generate_and_cache does NOT call overlay_pdfs when letterhead_filename is None."""
    from app.services.pdf_service import PdfService
    service = PdfService()
    story = make_mock_story()
    settings = make_mock_settings()
    settings.letterhead_filename = None  # no letterhead

    with patch("app.services.pdf_service.stirling_client") as mock_stirling, \
         patch("app.services.pdf_service.get_settings") as mock_cfg:
        mock_stirling.html_to_pdf = AsyncMock(return_value=b"%PDF-fake")
        mock_stirling.overlay_pdfs = AsyncMock(return_value=b"%PDF-merged")
        mock_cfg.return_value.PDF_CACHE_PATH = str(tmp_path)
        mock_cfg.return_value.PDF_TEMPLATES_PATH = str(tmp_path)

        await service.generate_and_cache(story, settings, test_cases=[], features=[])

    mock_stirling.overlay_pdfs.assert_not_called()
