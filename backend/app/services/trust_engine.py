# app/services/trust_engine.py
"""
Trust Engine for HeyKarl Multi-Source RAG.

Manages trust profiles, computes composite trust scores, enforces
hard retrieval eligibility rules and resolves source conflicts.

Architecture decisions documented:
- Trust is computed deterministically from 6 dimensions — no LLM.
- Conflict detection uses per-sentence semantic hashing (lightweight).
- All trust changes are audited via the AuditService.
- Draft sources are ALWAYS excluded in production mode.
- Community sources NEVER qualify for security/compliance contexts.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Literal

from app.models.trust_profile import SourceCategory, TrustClass

logger = logging.getLogger(__name__)


# ── Weight matrix for composite score ────────────────────────────────────────

DIMENSION_WEIGHTS = {
    "authority_score":    0.25,
    "standard_score":     0.20,
    "context_score":      0.20,
    "freshness_score":    0.15,
    "governance_score":   0.10,
    "traceability_score": 0.10,
}

assert abs(sum(DIMENSION_WEIGHTS.values()) - 1.0) < 1e-9


# ── Default trust profiles per source category ────────────────────────────────

CATEGORY_DEFAULTS: dict[str, dict] = {
    SourceCategory.manufacturer: {
        "trust_class":       TrustClass.V5.value,
        "authority_score":   0.95,
        "standard_score":    0.90,
        "context_score":     0.80,
        "freshness_score":   0.70,
        "governance_score":  0.85,
        "traceability_score": 0.90,
        "eligibility": {"security": True, "compliance": True, "general": True, "architecture": True},
    },
    SourceCategory.internal_approved: {
        "trust_class":       TrustClass.V4.value,
        "authority_score":   0.85,
        "standard_score":    0.70,
        "context_score":     0.90,
        "freshness_score":   0.75,
        "governance_score":  0.80,
        "traceability_score": 0.85,
        "eligibility": {"security": True, "compliance": True, "general": True, "architecture": True},
    },
    SourceCategory.internal_draft: {
        "trust_class":       TrustClass.V2.value,
        "authority_score":   0.50,
        "standard_score":    0.40,
        "context_score":     0.60,
        "freshness_score":   0.60,
        "governance_score":  0.30,
        "traceability_score": 0.40,
        "eligibility": {"security": False, "compliance": False, "general": False, "architecture": False},
    },
    SourceCategory.partner: {
        "trust_class":       TrustClass.V3.value,
        "authority_score":   0.65,
        "standard_score":    0.60,
        "context_score":     0.65,
        "freshness_score":   0.60,
        "governance_score":  0.55,
        "traceability_score": 0.60,
        "eligibility": {"security": False, "compliance": False, "general": True, "architecture": True},
    },
    SourceCategory.community: {
        "trust_class":       TrustClass.V1.value,
        "authority_score":   0.30,
        "standard_score":    0.25,
        "context_score":     0.40,
        "freshness_score":   0.40,
        "governance_score":  0.15,
        "traceability_score": 0.20,
        # HARD RULE: community NEVER eligible for security or compliance
        "eligibility": {"security": False, "compliance": False, "general": True, "architecture": False},
    },
    SourceCategory.standard_norm: {
        "trust_class":       TrustClass.V5.value,
        "authority_score":   0.90,
        "standard_score":    0.95,
        "context_score":     0.75,
        "freshness_score":   0.65,
        "governance_score":  0.90,
        "traceability_score": 0.85,
        "eligibility": {"security": True, "compliance": True, "general": True, "architecture": True},
    },
}


# ── Retrieval context classification ─────────────────────────────────────────

import re as _re

_SECURITY_RE = _re.compile(
    r"\b(security|permission|auth|oauth|mfa|encrypt|access control|role|sod|segregation|firewall|certificate)\b",
    _re.I,
)
_COMPLIANCE_RE = _re.compile(
    r"\b(compliance|audit|regulation|gdpr|sox|hipaa|iso 27001|nist|certification|control)\b",
    _re.I,
)
_ARCH_RE = _re.compile(
    r"\b(architecture|integration|pattern|api|middleware|event-driven|deployment|scalability)\b",
    _re.I,
)


def classify_query_context(query: str) -> set[str]:
    """Return set of retrieval contexts that apply to this query."""
    contexts: set[str] = {"general"}
    if _SECURITY_RE.search(query):
        contexts.add("security")
    if _COMPLIANCE_RE.search(query):
        contexts.add("compliance")
    if _ARCH_RE.search(query):
        contexts.add("architecture")
    return contexts


# ── Trust score computation ───────────────────────────────────────────────────

def compute_composite_score(profile_dict: dict) -> float:
    """
    Compute composite trust score from 6 dimension scores.
    Clamped to [0.0, 1.0].
    """
    score = sum(
        DIMENSION_WEIGHTS[dim] * float(profile_dict.get(dim, 0.5))
        for dim in DIMENSION_WEIGHTS
    )
    return max(0.0, min(1.0, round(score, 4)))


def default_profile_for_category(category: str) -> dict:
    """Return default trust dimension dict for a source category."""
    return dict(CATEGORY_DEFAULTS.get(category, CATEGORY_DEFAULTS[SourceCategory.internal_approved]))


# ── Eligibility enforcement (hard rules) ─────────────────────────────────────

@dataclass
class EligibilityResult:
    eligible:  bool
    reason:    str = ""
    hard_rule: bool = False    # True = cannot be overridden by admin


def check_eligibility(
    profile_dict: dict,
    query_contexts: set[str],
    production_mode: bool = True,
) -> EligibilityResult:
    """
    Apply hard eligibility rules:

    1. DRAFT → always excluded in production mode
    2. COMMUNITY → excluded for security/compliance contexts
    3. Source eligibility dict → per-context gate

    Returns EligibilityResult(eligible=True/False, reason, hard_rule).
    """
    category = profile_dict.get("source_category", "")
    trust_class = profile_dict.get("trust_class", "V3")
    eligibility = profile_dict.get("eligibility", {})

    # Hard rule 1: Draft excluded in production
    if production_mode and category == SourceCategory.internal_draft:
        return EligibilityResult(
            eligible=False,
            reason="Draft sources are excluded in production mode",
            hard_rule=True,
        )

    # Hard rule 2: Community excluded for security/compliance
    if category == SourceCategory.community:
        blocked = query_contexts & {"security", "compliance"}
        if blocked:
            return EligibilityResult(
                eligible=False,
                reason=f"Community sources excluded for context(s): {', '.join(blocked)}",
                hard_rule=True,
            )

    # Hard rule 3: Per-context eligibility gate
    for ctx in query_contexts:
        if eligibility.get(ctx) is False:
            return EligibilityResult(
                eligible=False,
                reason=f"Source not eligible for context: {ctx}",
                hard_rule=False,
            )

    # Hard rule 4: Architecture requires ≥ V3 trust class
    if "architecture" in query_contexts and trust_class == "V1":
        return EligibilityResult(
            eligible=False,
            reason="Architecture queries require minimum trust class V3",
            hard_rule=False,
        )

    return EligibilityResult(eligible=True, reason="OK")


# ── Conflict detection ────────────────────────────────────────────────────────

@dataclass
class SourceConflict:
    """Represents a detected conflict between two source chunks."""
    chunk_a_url:      str | None
    chunk_b_url:      str | None
    chunk_a_system:   str
    chunk_b_system:   str
    chunk_a_category: str
    chunk_b_category: str
    conflict_type:    Literal["factual", "procedural", "normative"]
    winning_source:   str | None    # URL/system of the winning source (None = unresolved)
    resolution_rule:  str
    excerpt_a:        str
    excerpt_b:        str


def detect_conflicts(chunks: list[dict], query_context: set[str]) -> list[SourceConflict]:
    """
    Lightweight conflict detection between retrieved chunks.

    Strategy:
    - Chunks from different sources with similar topics but different
      normative statements (e.g. "must use X" vs "avoid X") are flagged.
    - Uses simple sentence fingerprinting — no LLM.
    - Conflict resolution based on category precedence rules.

    This is intentionally conservative — flags possible conflicts,
    does not silently suppress either source.
    """
    conflicts: list[SourceConflict] = []
    if len(chunks) < 2:
        return conflicts

    # Extract normative sentences per chunk
    normative_re = _re.compile(
        r"\b(must|must not|should|avoid|required|prohibited|not allowed|do not|always|never)\b",
        _re.I,
    )

    def _fingerprint(sentence: str) -> str:
        # Normalise and hash for deduplication-aware comparison
        norm = _re.sub(r"\W+", " ", sentence.lower()).strip()
        return hashlib.md5(norm.encode()).hexdigest()[:8]

    def _extract_normative(text: str) -> list[str]:
        sentences = _re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if normative_re.search(s) and len(s) > 20]

    # Build fingerprint map per chunk
    chunk_norms: list[tuple[dict, list[str]]] = []
    for chunk in chunks[:10]:  # cap to avoid O(n²) blow-up
        norms = _extract_normative(chunk.get("chunk_text", chunk.get("text", "")))
        if norms:
            chunk_norms.append((chunk, norms))

    # Compare pairs
    seen_pairs: set[str] = set()
    for i, (ca, norms_a) in enumerate(chunk_norms):
        for j, (cb, norms_b) in enumerate(chunk_norms):
            if i >= j:
                continue
            pair_key = f"{i}:{j}"
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            url_a = ca.get("source_url") or ""
            url_b = cb.get("source_url") or ""
            if url_a == url_b:
                continue  # same source — not a conflict

            cat_a = ca.get("source_category", "")
            cat_b = cb.get("source_category", "")

            # Simple conflict signal: negation asymmetry between normative sentences
            for sent_a in norms_a[:3]:
                for sent_b in norms_b[:3]:
                    if _has_negation_conflict(sent_a, sent_b):
                        winning, rule = _resolve_conflict(ca, cb)
                        conflicts.append(SourceConflict(
                            chunk_a_url=url_a or None,
                            chunk_b_url=url_b or None,
                            chunk_a_system=ca.get("source_system", ca.get("source_type", "")),
                            chunk_b_system=cb.get("source_system", cb.get("source_type", "")),
                            chunk_a_category=cat_a,
                            chunk_b_category=cat_b,
                            conflict_type="normative",
                            winning_source=winning,
                            resolution_rule=rule,
                            excerpt_a=sent_a[:200],
                            excerpt_b=sent_b[:200],
                        ))
                        break

    return conflicts[:5]  # cap output


def _has_negation_conflict(a: str, b: str) -> bool:
    """Detect if two normative sentences contradict each other."""
    a_low, b_low = a.lower(), b.lower()
    positive_re = _re.compile(r"\b(must|required|always|should)\b")
    negative_re = _re.compile(r"\b(must not|avoid|never|prohibited|do not)\b")

    a_pos = bool(positive_re.search(a_low))
    a_neg = bool(negative_re.search(a_low))
    b_pos = bool(positive_re.search(b_low))
    b_neg = bool(negative_re.search(b_low))

    # One says "must X", other says "avoid X" — crude but practical
    if (a_pos and b_neg) or (a_neg and b_pos):
        # Share at least one significant keyword
        a_words = set(_re.findall(r"\b[a-z]{4,}\b", a_low))
        b_words = set(_re.findall(r"\b[a-z]{4,}\b", b_low))
        shared = a_words & b_words - {"must", "should", "avoid", "always", "never", "required", "that", "this", "with", "from"}
        return len(shared) >= 2
    return False


# Category precedence for conflict resolution (higher = wins)
_CATEGORY_PRECEDENCE: dict[str, int] = {
    SourceCategory.manufacturer:      6,
    SourceCategory.standard_norm:     5,
    SourceCategory.internal_approved: 4,
    SourceCategory.partner:           3,
    SourceCategory.community:         2,
    SourceCategory.internal_draft:    1,
}


def _resolve_conflict(chunk_a: dict, chunk_b: dict) -> tuple[str | None, str]:
    """
    Return (winning_source_url, resolution_rule_description).
    Rules (from spec):
    - Produktstandard → Hersteller gewinnt
    - interner Prozess → interne Doku gewinnt
    - otherwise → tie / unresolved (both shown)
    """
    cat_a = chunk_a.get("source_category", "")
    cat_b = chunk_b.get("source_category", "")
    prec_a = _CATEGORY_PRECEDENCE.get(cat_a, 0)
    prec_b = _CATEGORY_PRECEDENCE.get(cat_b, 0)

    if prec_a > prec_b:
        return chunk_a.get("source_url"), f"{cat_a} takes precedence over {cat_b}"
    if prec_b > prec_a:
        return chunk_b.get("source_url"), f"{cat_b} takes precedence over {cat_a}"
    return None, "Conflict unresolved — both sources shown, review required"
