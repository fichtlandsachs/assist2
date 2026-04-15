"""Unit tests for the grounded chat pipeline.

Tests:
1. Internal evidence found → answer generated
2. No internal evidence → exact fallback message
3. [Web] absent, web access attempted → blocked
4. [Web] present → web_allowed=True, source_mode=internal_plus_web
5. Hallucinated citation in answer → validator blocks
6. Contradictory evidence → warning flagged
7. strict_grounded + insufficient evidence → blocked
8. draft_mode + insufficient evidence → warnings but not blocked
"""
import pytest
from dataclasses import dataclass
from typing import Optional

from app.ai.evidence import qualify_evidence, EvidenceSet, EvidenceItem, EvidenceOrigin
from app.ai.policy import PolicyEngine, PolicyConfig, FALLBACK_MESSAGE
from app.ai.validator import validate_answer, ValidationResult
from app.ai.confidence import score_confidence


# ── Helpers ───────────────────────────────────────────────────────────────────

@dataclass
class FakeChunk:
    text: str
    score: float
    source_type: str
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    indexed_at: Optional[str] = None


def make_chunk(score=0.80, source_type="confluence", title="Test Page"):
    return FakeChunk(
        text="Die Nutzeranmeldung erfolgt über OAuth2.",
        score=score,
        source_type=source_type,
        source_url="https://confluence.example.com/pages/1",
        source_title=title,
        indexed_at="2026-01-01T00:00:00",
    )


# ── Test 1: Internal evidence found → answer allowed ─────────────────────────

def test_internal_evidence_policy_allows():
    chunks = [make_chunk(score=0.85)]
    evidence = qualify_evidence(chunks, web_allowed=False)
    engine = PolicyEngine()
    decision = engine.evaluate("Wie funktioniert die Anmeldung?", evidence)
    assert decision.allowed is True
    assert decision.fallback_applied is False
    assert decision.source_mode == "internal_only"


# ── Test 2: No internal evidence → exact fallback ────────────────────────────

def test_no_evidence_returns_fallback():
    evidence = qualify_evidence([], web_allowed=False)
    engine = PolicyEngine()
    decision = engine.evaluate("Was ist das Login-Verfahren?", evidence)
    assert decision.allowed is False
    assert decision.fallback_applied is True
    assert decision.reason == "insufficient_internal_evidence"


def test_fallback_message_exact():
    assert FALLBACK_MESSAGE == "Ich konnte in den Tickets und Confluence Artikeln nichts finden."


# ── Test 3: No [Web] but web_allowed=True → policy blocks ────────────────────

def test_web_access_blocked_without_signal():
    evidence = qualify_evidence([], web_allowed=True)  # simulate incorrectly set flag
    engine = PolicyEngine()
    # user_text has no [Web] signal
    decision = engine.evaluate("Wie login?", evidence)
    assert decision.blocked is True
    assert decision.reason == "web_access_without_signal"


# ── Test 4: [Web] present → source_mode=internal_plus_web ────────────────────

def test_web_signal_enables_web_mode():
    chunks = [make_chunk(score=0.75)]
    evidence = qualify_evidence(chunks, web_allowed=True)
    engine = PolicyEngine()
    decision = engine.evaluate("Wie login? [Web]", evidence)
    assert decision.source_mode == "internal_plus_web"
    assert decision.allowed is True


# ── Test 5: Hallucinated citation → validator blocks ─────────────────────────

def test_validator_blocks_hallucinated_citation():
    evidence = qualify_evidence([], web_allowed=False)
    hallucinated = "Ich habe in der Confluence-Dokumentation zu Login folgendes gefunden: ..."
    result = validate_answer(
        answer=hallucinated,
        evidence=evidence,
        policy_mode="strict_grounded",
        web_allowed=False,
        user_text="Wie login?",
    )
    assert result.passed is False
    codes = [f.code for f in result.findings]
    assert "HALLUCINATION_DETECTED" in codes


# ── Test 6: Contradictory evidence → warning in evidence set ─────────────────

def test_contradictory_evidence_flagged():
    pos_chunk = FakeChunk(
        text="Die Anmeldung ist aktiviert.",
        score=0.80, source_type="confluence",
        source_title="Positive", indexed_at="2026-01-01T00:00:00"
    )
    neg_chunk = FakeChunk(
        text="Die Anmeldung ist nicht aktiviert und kein Feature vorhanden.",
        score=0.75, source_type="confluence",
        source_title="Negative", indexed_at="2026-01-01T00:00:00"
    )
    evidence = qualify_evidence([pos_chunk, neg_chunk], web_allowed=False)
    assert evidence.has_contradiction is True
    assert any(f for e in evidence.items for f in e.contradiction_flags)


# ── Test 7: strict_grounded + insufficient evidence → blocked ─────────────────

def test_strict_mode_blocks_insufficient_evidence():
    cfg = PolicyConfig(
        policy_mode="strict_grounded",
        fallback_on_insufficient=False,
        min_evidence_count=2,
    )
    engine = PolicyEngine(cfg)
    chunks = [make_chunk(score=0.80)]  # only 1, need 2
    evidence = qualify_evidence(chunks, web_allowed=False, min_usable=2)
    decision = engine.evaluate("Wie login?", evidence)
    assert decision.blocked is True
    assert decision.allowed is False


# ── Test 8: draft_mode passes with warnings ───────────────────────────────────

def test_draft_mode_allows_with_low_evidence():
    cfg = PolicyConfig(
        policy_mode="draft_mode",
        fallback_on_insufficient=False,
        min_evidence_count=1,
    )
    engine = PolicyEngine(cfg)
    chunks = [make_chunk(score=0.55)]  # borderline
    evidence = qualify_evidence(chunks, web_allowed=False, min_usable=1)
    decision = engine.evaluate("Wie login?", evidence)
    assert decision.allowed is True


# ── Confidence scoring ────────────────────────────────────────────────────────

def test_confidence_high_with_good_evidence():
    chunks = [make_chunk(score=0.90), make_chunk(score=0.85, source_type="jira")]
    evidence = qualify_evidence(chunks, web_allowed=False)
    score = score_confidence(evidence, validator_passed=True, policy_passed=True)
    assert score.level in ("HIGH", "MEDIUM")
    assert score.numeric > 0.5


def test_confidence_ungrounded_without_evidence():
    evidence = qualify_evidence([], web_allowed=False)
    score = score_confidence(evidence, validator_passed=False, policy_passed=False)
    assert score.level == "UNGROUNDED"
    assert score.numeric == 0.0
