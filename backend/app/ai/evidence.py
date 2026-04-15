"""Evidence model — structured layer between RAG retrieval and generation.

Each RagChunk is promoted to an EvidenceItem with additional quality scores.
The EvidenceSet represents the full qualified evidence for one request.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class EvidenceOrigin(str, Enum):
    internal = "internal"
    web = "web"


@dataclass
class EvidenceItem:
    evidence_id: str
    source_id: str                      # source_ref / source_url
    source_type: str                    # confluence | jira | karl_story | nextcloud | …
    source_name: str                    # human-readable title
    document_title: str
    excerpt: str
    excerpt_location: str | None        # URL or path
    relevance_score: float              # cosine similarity from RAG (0–1)
    freshness_score: float              # derived from indexed_at recency (0–1)
    authority_score: float              # fixed weights per source_type (0–1)
    contradiction_flags: list[str] = field(default_factory=list)
    usable_for_answer: bool = True
    origin: EvidenceOrigin = EvidenceOrigin.internal

    @property
    def composite_score(self) -> float:
        return (
            self.relevance_score * 0.6
            + self.freshness_score * 0.2
            + self.authority_score * 0.2
        )


@dataclass
class EvidenceSet:
    items: list[EvidenceItem] = field(default_factory=list)
    web_allowed: bool = False
    has_contradiction: bool = False
    insufficient: bool = False          # True when below min-evidence threshold

    @property
    def usable(self) -> list[EvidenceItem]:
        return [e for e in self.items if e.usable_for_answer]

    @property
    def avg_relevance(self) -> float:
        u = self.usable
        return sum(e.relevance_score for e in u) / len(u) if u else 0.0


# ── Authority weights per source type ────────────────────────────────────────
_AUTHORITY: dict[str, float] = {
    "confluence": 0.90,
    "jira": 0.85,
    "karl_story": 0.75,
    "nextcloud": 0.65,
    "user_action": 0.50,
}


def _freshness(indexed_at: str | None) -> float:
    """Score 1.0 for today, decays to 0.2 over 365 days."""
    if not indexed_at:
        return 0.5
    from datetime import datetime, timezone
    try:
        ts = datetime.fromisoformat(indexed_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - ts).days
        return max(0.2, 1.0 - age_days / 365)
    except Exception:
        return 0.5


def qualify_evidence(
    chunks: list,                       # list[RagChunk]
    web_allowed: bool,
    min_relevance: float = 0.50,
    min_usable: int = 1,
) -> EvidenceSet:
    """Convert RagChunks into a qualified EvidenceSet."""
    items: list[EvidenceItem] = []

    for c in chunks:
        authority = _AUTHORITY.get(c.source_type, 0.50)
        freshness = _freshness(getattr(c, "indexed_at", None))
        usable = c.score >= min_relevance

        items.append(EvidenceItem(
            evidence_id=str(uuid.uuid4()),
            source_id=c.source_url or c.source_title or c.source_type,
            source_type=c.source_type,
            source_name=c.source_title or c.source_type,
            document_title=c.source_title or "",
            excerpt=c.text[:500],
            excerpt_location=c.source_url,
            relevance_score=round(c.score, 4),
            freshness_score=round(freshness, 4),
            authority_score=authority,
            usable_for_answer=usable,
            origin=EvidenceOrigin.internal,
        ))

    # Contradiction detection: same source_type, opposite signals
    has_contradiction = _detect_contradictions(items)
    if has_contradiction:
        for item in items:
            item.contradiction_flags.append("possible_contradiction_in_source_set")

    usable_count = sum(1 for i in items if i.usable_for_answer)
    insufficient = usable_count < min_usable

    return EvidenceSet(
        items=items,
        web_allowed=web_allowed,
        has_contradiction=has_contradiction,
        insufficient=insufficient,
    )


def _detect_contradictions(items: list[EvidenceItem]) -> bool:
    """Simple heuristic: flag if two items from the same source disagree on key terms."""
    negation_words = {"nicht", "kein", "keine", "never", "not", "no", "ohne"}
    by_source: dict[str, list[str]] = {}
    for item in items:
        by_source.setdefault(item.source_type, []).append(item.excerpt.lower())

    for excerpts in by_source.values():
        if len(excerpts) < 2:
            continue
        has_negation = any(
            any(w in exc for w in negation_words) for exc in excerpts
        )
        has_positive = any(
            not any(w in exc for w in negation_words) for exc in excerpts
        )
        if has_negation and has_positive:
            return True
    return False
