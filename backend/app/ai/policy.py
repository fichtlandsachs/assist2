"""Policy Engine — enforces source and grounding rules.

Determines whether a request may proceed, must use fallback, or is blocked.
All decisions are rule-based and deterministic (no LLM involved).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from app.ai.evidence import EvidenceSet

PolicyMode = Literal[
    "strict_grounded",
    "grounded_with_explicit_uncertainty",
    "draft_mode",
    "block_on_insufficient_evidence",
]

SourceMode = Literal["internal_only", "internal_plus_web"]

FALLBACK_MESSAGE = "Ich konnte in den Tickets und Confluence Artikeln nichts finden."


@dataclass
class PolicyDecision:
    allowed: bool
    source_mode: SourceMode
    policy_mode: PolicyMode
    fallback_applied: bool
    blocked: bool
    reason: str | None = None


@dataclass
class PolicyConfig:
    web_requires_signal: bool = True        # /WEB must be explicit
    web_signal: str = "/WEB"
    default_sources: list[str] = None       # None = all internal sources
    min_evidence_count: int = 1
    min_relevance_score: float = 0.50
    fallback_on_insufficient: bool = True
    policy_mode: PolicyMode = "strict_grounded"
    confidence_threshold_for_block: float = 0.0  # 0.0 = never block by confidence alone

    def __post_init__(self):
        if self.default_sources is None:
            self.default_sources = ["confluence", "jira", "karl_story", "nextcloud"]


# Default config — can be overridden per assistant or org
DEFAULT_POLICY = PolicyConfig()


class PolicyEngine:
    def __init__(self, config: PolicyConfig = DEFAULT_POLICY):
        self.config = config

    def source_mode(self, user_text: str) -> SourceMode:
        if self.config.web_requires_signal and self.config.web_signal in user_text:
            return "internal_plus_web"
        return "internal_only"

    def evaluate(self, user_text: str, evidence: EvidenceSet) -> PolicyDecision:
        mode = self.source_mode(user_text)
        web_in_request = self.config.web_signal in user_text

        # Hard rule: web access only if [Web] signal present
        if evidence.web_allowed and not web_in_request:
            return PolicyDecision(
                allowed=False,
                source_mode=mode,
                policy_mode=self.config.policy_mode,
                fallback_applied=False,
                blocked=True,
                reason="web_access_without_signal",
            )

        # Check evidence sufficiency
        usable = evidence.usable
        if len(usable) < self.config.min_evidence_count:
            if self.config.fallback_on_insufficient:
                return PolicyDecision(
                    allowed=False,
                    source_mode=mode,
                    policy_mode=self.config.policy_mode,
                    fallback_applied=True,
                    blocked=False,
                    reason="insufficient_internal_evidence",
                )
            if self.config.policy_mode in ("strict_grounded", "block_on_insufficient_evidence"):
                return PolicyDecision(
                    allowed=False,
                    source_mode=mode,
                    policy_mode=self.config.policy_mode,
                    fallback_applied=False,
                    blocked=True,
                    reason="blocked_insufficient_evidence",
                )

        return PolicyDecision(
            allowed=True,
            source_mode=mode,
            policy_mode=self.config.policy_mode,
            fallback_applied=False,
            blocked=False,
        )
