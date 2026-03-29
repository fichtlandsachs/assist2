"""Unit tests for story scoring logic (deterministic, no DB, no LLM)."""
import pytest

from app.ai.context_analyzer import analyze_context
from app.ai.complexity_scorer import score_complexity


def test_score_well_specified_story_is_low_or_medium():
    """A clear, simple story should not score high."""
    ctx = analyze_context(
        title="Button Farbe ändern",
        description="Der primäre Button soll blau statt grün sein.",
        acceptance_criteria="1. Button ist blau\n2. Hover-Effekt bleibt erhalten",
    )
    score = score_complexity(ctx)
    assert score.level in ("low", "medium")
    assert 0.0 <= score.confidence <= 1.0
    assert 0.0 <= ctx.clarity <= 1.0
    assert 0.0 <= ctx.complexity <= 1.0
    assert 0.0 <= ctx.risk <= 1.0
    assert ctx.domain in ("technical", "business", "security", "generic")


def test_score_security_story_scores_high():
    """A story with security keywords and risk terms should score high."""
    ctx = analyze_context(
        title="Passwort Reset mit Token Validierung",
        description=(
            "Nutzer können ihr Passwort zurücksetzen. "
            "Ein sicherer Token wird per Email verschickt. "
            "DSGVO-konforme Speicherung. Admin-Permission erforderlich."
        ),
        acceptance_criteria=(
            "1. Token ist 24h gültig\n"
            "2. Token wird nach Verwendung invalidiert\n"
            "3. Compliance-Log wird geschrieben"
        ),
    )
    score = score_complexity(ctx)
    assert score.level == "high"
    assert ctx.domain == "security"


def test_score_empty_story_fields():
    """Empty fields should not raise — and should produce valid output."""
    ctx = analyze_context(title="", description=None, acceptance_criteria=None)
    score = score_complexity(ctx)
    assert score.level in ("low", "medium", "high")
    assert ctx.domain in ("technical", "business", "security", "generic")


def test_score_response_fields_are_floats():
    """All score fields must be floats in 0.0–1.0 range."""
    ctx = analyze_context(
        title="API Endpoint für Dateiupload",
        description="REST-Endpoint der Dateien via Multipart akzeptiert und in S3 speichert.",
        acceptance_criteria="1. Max 10MB\n2. Nur PDF und PNG",
    )
    score = score_complexity(ctx)
    for val in (ctx.clarity, ctx.complexity, ctx.risk, score.confidence):
        assert isinstance(val, float)
        assert 0.0 <= val <= 1.0
