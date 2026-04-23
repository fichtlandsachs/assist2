"""Unit tests for HTML content extraction."""
import pytest

from app.services.crawl.extraction_service import ExtractionService

SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>SAP Test Page</title></head>
<body>
  <header>Global Navigation Here</header>
  <nav>Breadcrumb Nav</nav>
  <main>
    <h1>Main Feature Title</h1>
    <p>First paragraph about the feature with enough content to pass minimum length check.</p>
    <h2>Sub-section Title</h2>
    <p>Sub-section content with additional details about this topic.</p>
    <ul><li>Item Alpha</li><li>Item Beta</li></ul>
  </main>
  <footer>Footer content here</footer>
</body>
</html>
"""

THIN_HTML = """
<!DOCTYPE html>
<html><head><title>Thin</title></head>
<body><div>Hi</div></body>
</html>
"""


@pytest.fixture
def extractor():
    return ExtractionService()


def test_extracts_h1_as_main_heading(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert page.main_heading == "Main Feature Title"


def test_excludes_header_content(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert "Global Navigation Here" not in page.plain_text


def test_excludes_footer_content(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert "Footer content here" not in page.plain_text


def test_includes_main_body_text(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert "First paragraph" in page.plain_text


def test_extracts_both_headings(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    headings_text = [h for _, h in page.headings]
    assert "Main Feature Title" in headings_text
    assert "Sub-section Title" in headings_text


def test_language_detection(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert "en" in page.language


def test_quality_score_positive(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert page.extraction_quality_score > 0.0


def test_thin_content_low_score(extractor):
    page = extractor.extract(THIN_HTML, "http://x.com/p", "http")
    assert page.extraction_quality_score < 0.5


def test_sections_extracted(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert len(page.structured_sections) >= 1


def test_canonical_url_preserved(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/test", "http")
    assert page.canonical_url == "http://x.com/test"
