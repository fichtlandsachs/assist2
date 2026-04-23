"""Unit tests for structure-aware chunking."""
import pytest

from app.services.crawl.chunking_service import ChunkingService


@pytest.fixture
def chunker():
    return ChunkingService(target_tokens=100, overlap_tokens=20, max_tokens=150)


def test_single_section_produces_chunk(chunker):
    sections = [{"heading": "Intro", "level": 1, "body_text": "Short content about intro."}]
    chunks = chunker.chunk_page("http://x.com/p", "Page", sections, "Short content about intro.", {})
    assert len(chunks) >= 1
    assert any("Intro" in c.text for c in chunks)


def test_section_path_in_metadata(chunker):
    sections = [{"heading": "Features", "level": 1, "body_text": "Feature list here."}]
    chunks = chunker.chunk_page("http://x.com/p", "Page", sections, "Feature list here.", {})
    assert chunks[0].metadata["section_path"] == "Features"


def test_chunk_uid_is_deterministic(chunker):
    sections = [{"heading": "X", "level": 1, "body_text": "Body text here."}]
    chunks1 = chunker.chunk_page("http://x.com/p", "Page", sections, "Body text here.", {})
    chunks2 = chunker.chunk_page("http://x.com/p", "Page", sections, "Body text here.", {})
    assert chunks1[0].chunk_uid == chunks2[0].chunk_uid


def test_long_text_splits_into_multiple_chunks(chunker):
    # target_chars = 100 * 4 = 400; max_chars = 150 * 4 = 600
    # 800 chars exceeds max_chars, forcing a split
    long_text = ("word " * 160).strip()  # ~800 chars > 600 max
    sections = [{"heading": "Long Section", "level": 1, "body_text": long_text}]
    chunks = chunker.chunk_page("http://x.com/p", "Page", sections, long_text, {})
    assert len(chunks) > 1


def test_total_chunks_metadata_consistent(chunker):
    long_text = ("word " * 160).strip()
    sections = [{"heading": "A", "level": 1, "body_text": long_text}]
    chunks = chunker.chunk_page("http://x.com/p", "Page", sections, long_text, {})
    for c in chunks:
        assert c.metadata["total_chunks_for_page"] == len(chunks)
        assert c.total_chunks == len(chunks)


def test_source_metadata_preserved(chunker):
    sections = [{"heading": "S", "level": 1, "body_text": "Content."}]
    meta = {"vendor": "SAP", "locale": "en-US"}
    chunks = chunker.chunk_page("http://x.com/p", "Page", sections, "Content.", meta)
    for c in chunks:
        assert c.metadata["vendor"] == "SAP"
        assert c.metadata["locale"] == "en-US"


def test_empty_sections_falls_back_to_plain_text(chunker):
    chunks = chunker.chunk_page("http://x.com/p", "Page", [], "Just plain text content.", {})
    assert len(chunks) >= 1
    assert "Just plain text" in chunks[0].text
