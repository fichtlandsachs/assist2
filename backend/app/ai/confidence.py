"""Confidence Scorer — rule-based, never model-generated.

Derives a confidence level from evidence quality, validation results,
and policy compliance. No LLM is involved.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.ai.evidence import EvidenceSet

ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW", "UNGROUNDED"]


@dataclass
class ConfidenceScore:
    level: ConfidenceLevel
    numeric: float          # 0.0–1.0
    factors: dict[str, float]


def score_confidence(
    evidence: EvidenceSet,
    validator_passed: bool,
    policy_passed: bool,
) -> ConfidenceScore:
    usable = evidence.usable

    if not usable or not policy_passed:
        return ConfidenceScore(
            level="UNGROUNDED",
            numeric=0.0,
            factors={"evidence_count": 0, "policy_passed": float(policy_passed)},
        )

    # Factor: evidence count (capped at 5)
    count_score = min(len(usable) / 5, 1.0)

    # Factor: average relevance
    avg_relevance = evidence.avg_relevance

    # Factor: source quality (avg authority)
    avg_authority = sum(e.authority_score for e in usable) / len(usable)

    # Factor: consistency (penalise contradictions)
    consistency = 0.5 if evidence.has_contradiction else 1.0

    # Factor: freshness (avg)
    avg_freshness = sum(e.freshness_score for e in usable) / len(usable)

    # Factor: validator result
    validator_score = 1.0 if validator_passed else 0.3

    numeric = (
        count_score     * 0.20
        + avg_relevance * 0.30
        + avg_authority * 0.20
        + consistency   * 0.10
        + avg_freshness * 0.10
        + validator_score * 0.10
    )
    numeric = round(min(numeric, 1.0), 4)

    if numeric >= 0.75:
        level: ConfidenceLevel = "HIGH"
    elif numeric >= 0.50:
        level = "MEDIUM"
    else:
        level = "LOW"

    return ConfidenceScore(
        level=level,
        numeric=numeric,
        factors={
            "evidence_count_score": round(count_score, 3),
            "avg_relevance": round(avg_relevance, 3),
            "avg_authority": round(avg_authority, 3),
            "consistency": consistency,
            "avg_freshness": round(avg_freshness, 3),
            "validator_score": validator_score,
        },
    )
