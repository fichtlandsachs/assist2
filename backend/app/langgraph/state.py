"""LangGraph State Definition for Conversation Engine."""
from __future__ import annotations

from typing import Any, TypedDict


class ConversationState(TypedDict, total=False):
    """State object for the Conversation Engine LangGraph."""

    # Identifiers
    conversation_id: str
    org_id: str
    user_id: str

    # Input
    input_message: str
    previous_mode: str | None
    mode: str  # exploration | story | review | correction
    intent: str | None

    # Loaded Data
    conversation: dict[str, Any]
    messages: list[dict[str, Any]]
    facts: list[dict[str, Any]]
    protocol: dict[str, Any]
    config: dict[str, Any]

    # Analysis
    complexity_level: str | None
    has_context: bool
    user_provided_structure: bool

    # Story Sizing
    story_size_score: int
    recommended_story_count: int
    size_label: str
    sizing_recommendation: str

    # Readiness
    readiness_score: int
    readiness_max_score: int
    readiness_status: str | None  # not_ready | ready | excellent
    readiness_recommendation: str
    missing_fields: list[str]

    # Structure Proposal
    structure_proposal_required: bool
    structure_proposal: dict[str, Any] | None

    # Questions
    next_questions: list[dict[str, Any]]
    max_questions_per_turn: int

    # Response
    response_text: str
    facts_reused_in_response: list[str]

    # Error Handling
    errors: list[str]

    # Audit
    audit_events: list[dict[str, Any]]

    # Feature Flags
    observer_enabled: bool
