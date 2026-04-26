# app/models/control_chat_config.py
"""
Control Chat Configuration Models.

Separates the governance/audit representation of a control from its
conversational representation in the chat interface.

ControlChatQuestion  — per-control chat configuration:
    • plain-language primary question
    • alternative formulations (by role / product type / phase)
    • answer type  (free_text | choice | multi_choice | scale | yes_no | evidence)
    • answer-to-score mapping rules
    • follow-up trigger conditions
    • forbidden terms (to enforce non-ISO language)

ComplianceChatSession  — one ongoing dialogue per assessment:
    • tracks which controls have been addressed
    • accumulates extracted context params
    • stores the full turn history

ComplianceChatTurn  — one user/assistant exchange in a session

ComplianceChatMapping  — result of processing one user turn:
    • which controls were affected
    • proposed score deltas / new trigger params
    • pending follow-up questions
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class AnswerType(str, enum.Enum):
    free_text    = "free_text"
    choice       = "choice"
    multi_choice = "multi_choice"
    scale        = "scale"
    yes_no       = "yes_no"
    evidence     = "evidence"


class SessionStatus(str, enum.Enum):
    active    = "active"
    completed = "completed"
    paused    = "paused"
    abandoned = "abandoned"


class TurnRole(str, enum.Enum):
    user      = "user"
    assistant = "assistant"
    system    = "system"


# ── ControlChatQuestion ───────────────────────────────────────────────────────

class ControlChatQuestion(Base):
    """
    Chat-layer configuration for a single ControlDefinition.

    One control can have exactly one ControlChatQuestion row.
    All question variants, mapping rules, and follow-up logic live here.
    The ControlDefinition itself remains unchanged and contains the
    governance / audit representation.
    """
    __tablename__ = "cc_questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pg_control_definitions.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    # ── Primary question ─────────────────────────────────────────────────────
    # The single most important, user-friendly question for this control.
    primary_question: Mapped[str] = mapped_column(Text, nullable=False)

    # Answer type drives the UI affordance in the chat widget.
    answer_type: Mapped[str] = mapped_column(
        String(20), default=AnswerType.free_text.value, nullable=False
    )

    # For choice / multi_choice / scale: list of option objects
    # [{label, value, score_hint}]
    answer_options: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # ── Variant questions (JSONB arrays) ─────────────────────────────────────
    # Each entry: {condition_type, condition_value, question}
    # condition_type: "role" | "product_type" | "phase" | "market" | "always"
    alternative_questions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # ── Follow-up questions ───────────────────────────────────────────────────
    # [{trigger_condition, question, answer_type, options}]
    # trigger_condition evaluated against accumulated context + last answer.
    followup_questions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # ── Completion conditions ─────────────────────────────────────────────────
    # Conditions under which this control is considered "sufficiently answered"
    # and no further questions need to be asked.
    # [{field, op, value}]  — same mini-DSL as trigger condition_tree leaves
    completion_conditions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # ── Answer → score mapping ────────────────────────────────────────────────
    # List of mapping rules. First match wins.
    # [{match_type, match_value, score, status, trigger_params, evidence_required}]
    # match_type: "keyword" | "exact" | "regex" | "sentiment" | "llm"
    score_mapping_rules: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # ── Language guardrails ───────────────────────────────────────────────────
    # Terms that must NOT appear in the chat-facing question text.
    forbidden_terms: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # User-facing hint text (shown below the question in the UI)
    hint_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Priority — lower value = asked sooner when multiple controls are open.
    question_priority: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    # Whether this control should always be asked regardless of context.
    always_ask: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Whether this question can be skipped by the user.
    skippable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Free-text labels for fachanwender-visible summary
    # e.g. "Für den Markteintritt fehlen noch Angaben zu den Zielmärkten."
    gap_label_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_label_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Admin metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_edited_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ── ComplianceChatSession ─────────────────────────────────────────────────────

class ComplianceChatSession(Base):
    """
    One ongoing compliance dialogue tied to a ComplianceAssessment.
    Tracks progress, accumulated context, and addressed controls.
    """
    __tablename__ = "cc_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ca_assessments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20), default=SessionStatus.active.value, nullable=False
    )

    # Accumulated context from conversation (product_type, markets, etc.)
    context_params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Control IDs that have been sufficiently addressed
    addressed_control_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Control IDs currently queued as pending questions
    pending_control_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # The next question to present (pre-generated)
    next_question: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Rolling summary of what has been established so far
    conversation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Total turn count
    turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    turns: Mapped[List["ComplianceChatTurn"]] = relationship(
        "ComplianceChatTurn",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ComplianceChatTurn.turn_index",
    )
    mappings: Mapped[List["ComplianceChatMapping"]] = relationship(
        "ComplianceChatMapping",
        back_populates="session",
        cascade="all, delete-orphan",
    )


# ── ComplianceChatTurn ────────────────────────────────────────────────────────

class ComplianceChatTurn(Base):
    """One user or assistant message in a compliance chat session."""
    __tablename__ = "cc_turns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cc_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(15), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Which control(s) this turn was primarily addressing
    control_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Structured data extracted from this turn (by the mapping service)
    extracted_params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    session: Mapped["ComplianceChatSession"] = relationship(
        "ComplianceChatSession", back_populates="turns"
    )


# ── ComplianceChatMapping ─────────────────────────────────────────────────────

class ComplianceChatMapping(Base):
    """
    Result of mapping a user's answer to governance controls.
    Created after each user turn. One row per affected control.
    """
    __tablename__ = "cc_mappings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cc_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cc_turns.id", ondelete="CASCADE"), nullable=False
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pg_control_definitions.id", ondelete="CASCADE"), nullable=False
    )
    control_slug: Mapped[str] = mapped_column(String(200), nullable=False)

    # Proposed evaluation from this turn
    proposed_score: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Trigger params extracted that should be applied to the assessment
    trigger_params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Evidence slugs the answer implies are present or required
    evidence_present: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    evidence_required: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Whether this mapping was confirmed (applied to AssessmentItem)
    applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    session: Mapped["ComplianceChatSession"] = relationship(
        "ComplianceChatSession", back_populates="mappings"
    )
