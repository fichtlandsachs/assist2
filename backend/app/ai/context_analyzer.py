"""
Context Analyzer — heuristic-based, no LLM call, deterministic.

Analyzes an AI request input and produces a StoryContext with four
normalized scores (0.0–1.0). These feed directly into the complexity scorer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Domain keyword sets
# ---------------------------------------------------------------------------

_RISK_KEYWORDS = {
    "sicherheit", "security", "authentifizierung", "authentication",
    "passwort", "password", "zahlung", "payment", "transaktion", "transaction",
    "lösch", "delete", "migration", "kritisch", "critical", "compliance",
    "dsgvo", "gdpr", "datenschutz", "verschlüssel", "encrypt", "token",
    "berechtigung", "permission", "admin", "superuser",
}

_TECHNICAL_KEYWORDS = {
    "api", "endpoint", "datenbank", "database", "schema", "migration",
    "service", "microservice", "cache", "redis", "webhook", "oauth",
    "jwt", "docker", "kubernetes", "deployment", "pipeline", "celery",
    "async", "queue", "worker", "index", "query", "sql",
}

_BUSINESS_KEYWORDS = {
    "nutzer", "user", "kunde", "customer", "organisation", "organization",
    "dashboard", "bericht", "report", "export", "import", "workflow",
    "benachrichtigung", "notification", "email", "kalender", "calendar",
    "aufgabe", "task", "ticket", "sprint", "backlog", "story",
}

_USER_STORY_PATTERN = re.compile(
    r"\bals\b.{1,60}\bmöchte\b.{1,120}\bdamit\b",
    re.IGNORECASE | re.DOTALL,
)

_NUMBERED_LIST_PATTERN = re.compile(r"^\s*\d+[\.\)]\s+\S", re.MULTILINE)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class StoryContext:
    # Scores 0.0–1.0 — higher means more of that attribute
    clarity: float      # How clear / well-structured is the input
    complexity: float   # How technically/functionally complex
    risk: float         # How much risk / security sensitivity
    domain: Literal["technical", "business", "security", "generic"]

    # Raw signals (for debugging / audit)
    signals: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_context(
    title: str | None,
    description: str | None,
    acceptance_criteria: str | None,
) -> StoryContext:
    """
    Produce a StoryContext from story fields.
    Pure function — no side effects, no I/O.
    """
    t = (title or "").strip()
    d = (description or "").strip()
    ac = (acceptance_criteria or "").strip()
    combined = f"{t} {d} {ac}".lower()

    # ── Clarity ────────────────────────────────────────────────────────────
    title_ok = 4 <= len(t.split()) <= 20          # reasonable title length
    story_format = bool(_USER_STORY_PATTERN.search(d))
    ac_numbered = bool(_NUMBERED_LIST_PATTERN.search(ac))
    ac_count = len(_NUMBERED_LIST_PATTERN.findall(ac)) if ac else 0
    has_ac = ac_count > 0
    fields_filled = sum([bool(t), bool(d), bool(ac)])

    clarity_score = (
        (0.35 if title_ok else 0.0)
        + (0.35 if story_format else 0.0)
        + (0.20 if ac_numbered else 0.0)
        + (0.10 * (fields_filled / 3))
    )

    # ── Complexity ─────────────────────────────────────────────────────────
    ac_complexity = min(ac_count / 6, 1.0)         # 6+ criteria → max complexity
    desc_length = min(len(d.split()) / 80, 1.0)    # 80+ words → max
    tech_hits = sum(1 for kw in _TECHNICAL_KEYWORDS if kw in combined)
    tech_density = min(tech_hits / 4, 1.0)         # 4+ technical terms → max

    complexity_score = (
        0.40 * ac_complexity
        + 0.30 * desc_length
        + 0.30 * tech_density
    )

    # ── Risk ───────────────────────────────────────────────────────────────
    risk_hits = sum(1 for kw in _RISK_KEYWORDS if kw in combined)
    risk_score = min(risk_hits / 3, 1.0)           # 3+ risk terms → max risk

    # ── Domain ─────────────────────────────────────────────────────────────
    sec_hits = sum(1 for kw in _RISK_KEYWORDS if kw in combined)
    tech_hits_domain = sum(1 for kw in _TECHNICAL_KEYWORDS if kw in combined)
    biz_hits = sum(1 for kw in _BUSINESS_KEYWORDS if kw in combined)

    if sec_hits >= 2:
        domain: Literal["technical", "business", "security", "generic"] = "security"
    elif tech_hits_domain > biz_hits:
        domain = "technical"
    elif biz_hits > 0:
        domain = "business"
    else:
        domain = "generic"

    return StoryContext(
        clarity=round(clarity_score, 3),
        complexity=round(complexity_score, 3),
        risk=round(risk_score, 3),
        domain=domain,
        signals={
            "title_ok": title_ok,
            "story_format": story_format,
            "ac_numbered": ac_numbered,
            "ac_count": ac_count,
            "fields_filled": fields_filled,
            "tech_hits": tech_hits,
            "risk_hits": risk_hits,
            "biz_hits": biz_hits,
        },
    )
