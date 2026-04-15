"""Validation Layer — checks generated answer against evidence and policy.

All checks are deterministic heuristics. A separate LLM validation pass
can optionally be added later; this layer runs synchronously without LLM calls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.ai.evidence import EvidenceSet

Severity = Literal["info", "warning", "error", "blocking"]


@dataclass
class ValidationFinding:
    code: str
    severity: Severity
    message: str
    affected_field: str | None = None
    blocking: bool = False


@dataclass
class ValidationResult:
    passed: bool
    findings: list[ValidationFinding] = field(default_factory=list)

    @property
    def blocking_findings(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.blocking]


# ── Heuristic patterns that indicate hallucination ───────────────────────────
_HALLUCINATION_PATTERNS = [
    r"laut\s+(unserer\s+)?(dokumentation|wiki|confluence)",
    r"ich\s+habe\s+in\s+der\s+(confluence|jira|wiki|dokumentation)",
    r"in\s+unserem\s+(system|wiki|handbuch|dokument)",
    r"die\s+dokumentation\s+beschreibt",
    r"gemäß\s+(unserer\s+)?(richtlinie|dokumentation|wiki)",
    r"es\s+gibt\s+bereits\s+(einen?|eine)\s+(beschreibung|dokumentation|prozess|seite)",
]

# Invented technical entity patterns
_INVENTED_ENTITY_PATTERNS = [
    r"\b(api|endpoint|field|service|module|table|class|method)\s+['\"`]?\w+['\"`]?",
]

_NO_CITATION_PATTERNS = [
    r"ich\s+habe\s+in\s+der\s+.*?\s+folgendes\s+gefunden",
    r"laut\s+.*?:\s",
    r"gemäß\s+.*?:",
]


def validate_answer(
    answer: str,
    evidence: EvidenceSet,
    policy_mode: str,
    web_allowed: bool,
    user_text: str,
) -> ValidationResult:
    findings: list[ValidationFinding] = []
    answer_lower = answer.lower()

    # 1. Hallucination pattern check (no RAG context but model cites sources)
    if not evidence.usable:
        for pattern in _HALLUCINATION_PATTERNS:
            if re.search(pattern, answer_lower):
                findings.append(ValidationFinding(
                    code="HALLUCINATION_DETECTED",
                    severity="blocking",
                    message="Answer references internal sources but no evidence was retrieved.",
                    affected_field="answer",
                    blocking=True,
                ))
                break

    # 2. Web policy violation
    if "[web]" not in user_text.lower() and re.search(r"https?://", answer):
        findings.append(ValidationFinding(
            code="WEB_POLICY_VIOLATION",
            severity="blocking",
            message="Answer contains external URLs but [Web] was not requested.",
            affected_field="answer",
            blocking=True,
        ))

    # 3. No citations when evidence was provided
    if evidence.usable and not _has_citation(answer):
        findings.append(ValidationFinding(
            code="MISSING_CITATION",
            severity="warning",
            message="Evidence was available but answer contains no source reference.",
            affected_field="citations",
            blocking=False,
        ))

    # 4. Contradiction present in evidence
    if evidence.has_contradiction:
        findings.append(ValidationFinding(
            code="CONTRADICTORY_EVIDENCE",
            severity="warning",
            message="Evidence set contains potentially contradictory information.",
            affected_field="answer",
            blocking=policy_mode == "strict_grounded",
        ))

    # 5. Insufficient evidence — answer should not have been generated
    if evidence.insufficient and not evidence.usable:
        findings.append(ValidationFinding(
            code="ANSWER_WITHOUT_EVIDENCE",
            severity="blocking",
            message="Answer was generated despite insufficient internal evidence.",
            affected_field="answer",
            blocking=True,
        ))

    blocking = any(f.blocking for f in findings)
    return ValidationResult(passed=not blocking, findings=findings)


def _has_citation(text: str) -> bool:
    """Check whether the answer contains at least one recognizable source reference."""
    indicators = [
        "http",
        "confluence",
        "jira",
        "ticket",
        "[confluence]",
        "[jira]",
        "[dokument]",
        "[karl story]",
        "quelle:",
        "stand:",
    ]
    lower = text.lower()
    return any(ind in lower for ind in indicators)
