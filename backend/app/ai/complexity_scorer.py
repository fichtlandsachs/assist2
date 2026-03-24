"""
Complexity Scorer — derives a complexity class from a StoryContext.

Decision matrix (deterministic, no LLM):

  high   → risk >= 0.6  OR  complexity >= 0.65  OR  (clarity < 0.25 AND fields_filled < 2)
  low    → risk < 0.15  AND complexity < 0.30   AND clarity >= 0.50
  medium → everything else
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.ai.context_analyzer import StoryContext

ComplexityLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ComplexityScore:
    level: ComplexityLevel
    confidence: float           # 0.0–1.0 — how certain is the classification
    context: StoryContext       # original context for downstream logging

    def __str__(self) -> str:
        return f"ComplexityScore(level={self.level}, confidence={self.confidence:.2f})"


def score_complexity(context: StoryContext) -> ComplexityScore:
    """
    Derive a ComplexityLevel from a StoryContext.
    Pure function — deterministic, no side effects.
    """
    c = context
    fields_filled: int = c.signals.get("fields_filled", 0)

    # ── HIGH ───────────────────────────────────────────────────────────────
    # Any of: significant risk, high structural complexity, badly underspecified
    high_triggers = [
        c.risk >= 0.60,
        c.complexity >= 0.65,
        c.clarity < 0.25 and fields_filled < 2,
        c.domain == "security" and c.risk >= 0.40,
    ]
    if any(high_triggers):
        confidence = _confidence(
            primary=max(c.risk, c.complexity),
            opposite=c.clarity,
            direction="high",
        )
        return ComplexityScore(level="high", confidence=confidence, context=c)

    # ── LOW ────────────────────────────────────────────────────────────────
    # All of: low risk, low complexity, sufficient clarity
    if c.risk < 0.15 and c.complexity < 0.30 and c.clarity >= 0.50:
        confidence = _confidence(
            primary=c.clarity,
            opposite=max(c.risk, c.complexity),
            direction="low",
        )
        return ComplexityScore(level="low", confidence=confidence, context=c)

    # ── MEDIUM (default) ───────────────────────────────────────────────────
    distance_from_high = min(
        abs(c.risk - 0.60),
        abs(c.complexity - 0.65),
    )
    confidence = min(0.5 + distance_from_high, 0.90)
    return ComplexityScore(level="medium", confidence=round(confidence, 3), context=c)


def _confidence(primary: float, opposite: float, direction: str) -> float:
    """
    Heuristic confidence: how far primary is from its threshold,
    penalized by how close opposite is to flipping the decision.
    """
    base = min(primary * 1.2, 1.0)
    penalty = opposite * 0.3
    return round(max(base - penalty, 0.30), 3)
