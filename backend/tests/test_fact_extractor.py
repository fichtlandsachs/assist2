"""Tests for Fact Extractor module."""
from __future__ import annotations

import pytest

from app.services.fact_extractor import FactExtractor, CandidateFact
from app.services.fact_normalizer import FactNormalizer
from app.services.fact_deduplicator import FactDeduplicator


class TestFactExtractorPreprocessing:
    """Test text preprocessing."""

    def test_preprocess_basic(self):
        text = "  This is a test. It has multiple sentences!  "
        result = FactExtractor.preprocess(text)

        assert result["original"] == text
        assert result["trimmed"] == text.strip()
        assert result["lowercase"] == text.lower()
        assert len(result["sentences"]) == 2

    def test_preprocess_empty(self):
        result = FactExtractor.preprocess("")
        assert result["trimmed"] == ""
        assert result["sentences"] == []

    def test_preprocess_single_sentence(self):
        text = "Just one sentence."
        result = FactExtractor.preprocess(text)
        assert len(result["sentences"]) == 1


class TestFactExtractorEntityDetection:
    """Test entity detection."""

    def test_detect_roles(self):
        text = "Die Story ist für OrgAdmins und Fachbereichsleiter gedacht."
        entities = FactExtractor.detect_entities(text)

        assert "OrgAdmin" in entities["roles"] or "OrgAdmins" in entities["roles"]
        assert "Fachbereichsleiter" in entities["roles"]

    def test_detect_systems(self):
        text = "Integration mit JIRA und Confluence."
        entities = FactExtractor.detect_entities(text)

        assert "Jira" in entities["systems"] or "JIRA" in entities["systems"]
        assert "Confluence" in entities["systems"]

    def test_no_entities(self):
        text = "Das ist ein normaler Satz ohne spezielle Begriffe."
        entities = FactExtractor.detect_entities(text)

        assert entities["roles"] == []
        assert entities["systems"] == []


class TestFactNormalizer:
    """Test fact normalization."""

    def test_normalize_target_user(self):
        assert FactNormalizer.normalize("OrgAdmins", "target_user") == "OrgAdmin"
        assert FactNormalizer.normalize("fachbereichsleiter", "target_user") == "Fachbereichsleiter"
        assert FactNormalizer.normalize("Entwickler", "target_user") == "Entwickler"

    def test_normalize_system(self):
        assert FactNormalizer.normalize("JIRA", "affected_system") == "Jira"
        assert FactNormalizer.normalize("postgresql", "affected_system") == "PostgreSQL"

    def test_normalize_business_capability(self):
        result = FactNormalizer.normalize("kundenmanagement", "business_capability")
        assert result[0].isupper()

    def test_similarity_exact_match(self):
        sim = FactNormalizer.calculate_similarity("OrgAdmin", "OrgAdmin", "target_user")
        assert sim == 1.0

    def test_similarity_partial(self):
        sim = FactNormalizer.calculate_similarity(
            "OrgAdmins", "OrgAdmin", "target_user"
        )
        assert 0 < sim < 1.0


class TestFactDeduplicator:
    """Test deduplication logic."""

    def test_similarity_calculation(self):
        sim = FactDeduplicator.calculate_similarity(
            "OrgAdmins", "OrgAdmin", "target_user"
        )
        assert sim >= 0.8  # High similarity

    def test_similarity_different(self):
        sim = FactDeduplicator.calculate_similarity(
            "OrgAdmin", "Fachbereichsleiter", "target_user"
        )
        assert sim < 0.5  # Low similarity


class TestConfidenceScoring:
    """Test confidence scoring."""

    def test_pattern_match_base_confidence(self):
        assert FactExtractor.CONFIDENCE_PATTERN_MATCH == 0.85

    def test_synonym_match_base_confidence(self):
        assert FactExtractor.CONFIDENCE_SYNONYM_MATCH == 0.75

    def test_status_assignment_exploration_high(self):
        status = FactExtractor.assign_status(0.85, "exploration")
        assert status == "suggested"

    def test_status_assignment_exploration_low(self):
        status = FactExtractor.assign_status(0.70, "exploration")
        assert status == "detected"

    def test_status_assignment_story_confirmed(self):
        status = FactExtractor.assign_status(0.90, "story")
        assert status == "confirmed_candidate"

    def test_status_assignment_story_suggested(self):
        status = FactExtractor.assign_status(0.75, "story")
        assert status == "suggested"


class TestProtocolMapper:
    """Test protocol mapping."""

    def test_get_protocol_area_key(self):
        from app.services.protocol_mapper import ProtocolMapper

        assert ProtocolMapper.get_protocol_area_key("target_user") == "target_user"
        assert ProtocolMapper.get_protocol_area_key("target_users") == "target_user"
        assert ProtocolMapper.get_protocol_area_key("risk") == "risks"
        assert ProtocolMapper.get_protocol_area_key("dependency") == "dependencies"

    def test_calculate_fact_status_high(self):
        from app.services.protocol_mapper import ProtocolMapper

        status = ProtocolMapper.calculate_fact_status(0.90)
        assert status == "suggested"

    def test_calculate_fact_status_low(self):
        from app.services.protocol_mapper import ProtocolMapper

        status = ProtocolMapper.calculate_fact_status(0.70)
        assert status == "detected"


class TestFactReuseDetector:
    """Test fact reuse detection."""

    def test_should_ask_no_fact(self):
        from app.services.fact_reuse_detector import FactReuseDetector, ReuseCheckResult

        result = ReuseCheckResult(
            has_usable_fact=False,
            existing_fact=None,
            confidence_sufficient=False,
            needs_confirmation=True,
            can_reuse=False,
            message="",
        )
        assert FactReuseDetector.should_ask_for_category(result, "target_user") is True

    def test_should_ask_can_reuse(self):
        from app.services.fact_reuse_detector import FactReuseDetector, ReuseCheckResult

        result = ReuseCheckResult(
            has_usable_fact=True,
            existing_fact=None,
            confidence_sufficient=True,
            needs_confirmation=False,
            can_reuse=True,
            message="Du hattest bereits gesagt...",
        )
        assert FactReuseDetector.should_ask_for_category(result, "target_user") is False


# Integration tests
@pytest.mark.asyncio
async def test_full_extraction_pipeline():
    """Test the complete extraction flow."""
    # This would require a database connection
    # For now, just test the components work together

    text = "Die Story ist für OrgAdmins gedacht."

    # Preprocessing
    preprocessed = FactExtractor.preprocess(text)
    assert preprocessed["trimmed"] == text.strip()

    # Entity detection
    entities = FactExtractor.detect_entities(text)
    assert len(entities["roles"]) > 0

    # Normalization
    normalized = FactNormalizer.normalize("OrgAdmins", "target_user")
    assert normalized == "OrgAdmin"
