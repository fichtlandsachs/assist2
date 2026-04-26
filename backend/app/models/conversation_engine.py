# app/models/conversation_engine.py
"""ORM models for the HeyKarl Conversation Engine."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# ── Configuration models (Superadmin-managed) ─────────────────────────────────

class DialogProfile(Base):
    """A named conversation profile that drives the Engine's tone and focus."""
    __tablename__ = "ce_dialog_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="story_mode")
    tone: Mapped[str] = mapped_column(String(30), nullable=False, default="friendly")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class QuestionBlock(Base):
    """A reusable question block for the Question Planner."""
    __tablename__ = "ce_question_blocks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. context, problem, benefit, scope, ac
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    follow_up_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=5)  # 1=critical, 10=optional
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    condition_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class AnswerSignal(Base):
    """Regex/keyword patterns that map user text to Fact categories."""
    __tablename__ = "ce_answer_signals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    fact_category: Mapped[str] = mapped_column(String(50), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(20), nullable=False, default="keyword")  # keyword|regex|llm
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_boost: Mapped[float] = mapped_column(nullable=False, default=0.1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class PromptTemplate(Base):
    """Versioned LLM prompt templates for different engine phases."""
    __tablename__ = "ce_prompt_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), nullable=False)  # exploration_mode|story_mode|review_mode
    phase: Mapped[str] = mapped_column(String(50), nullable=False)  # system|fact_extract|question_plan|size|readiness
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_ce_prompt_key_version"),
    )


class ConversationRule(Base):
    """Guards and rules controlling Engine behaviour (max questions, mode switch, etc.)."""
    __tablename__ = "ce_conversation_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False)  # question_limit|fact_reuse|mode_switch|...
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    value_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class StorySizingRule(Base):
    """Thresholds controlling story-size scoring (XS/S/M/L/XL → story count)."""
    __tablename__ = "ce_sizing_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    dimension: Mapped[str] = mapped_column(String(50), nullable=False)  # user_groups|functions|systems|acs|risks
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0)
    thresholds_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class ReadinessRule(Base):
    """Rules that determine if a story is ready to be written."""
    __tablename__ = "ce_readiness_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    required_category: Mapped[str] = mapped_column(String(50), nullable=False)
    min_confidence: Mapped[float] = mapped_column(nullable=False, default=0.6)
    is_blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


# ── Runtime models ────────────────────────────────────────────────────────────

class ConversationSession(Base):
    """A Conversation Engine session (not bound to a story until one is created)."""
    __tablename__ = "ce_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("ce_dialog_profiles.id", ondelete="SET NULL"), nullable=True
    )
    # Linked artefacts (nullable — set when known)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    epic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("epics.id", ondelete="SET NULL"), nullable=True
    )
    story_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("user_stories.id", ondelete="SET NULL"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="exploration_mode")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Accumulated protocol sections (living document on the right panel)
    protocol_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Current sizing state
    sizing_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Readiness state
    readiness_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Questions already asked (keys of QuestionBlocks)
    asked_question_keys: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )



class ConversationFact(Base):
    """A single extracted fact from a conversation (runtime table)."""
    __tablename__ = "conversation_fact"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("conversation_message.id", ondelete="SET NULL"), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="detected")
    used_in: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confirmed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("conversation_fact.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ── Conversation Quality Observer ─────────────────────────────────────────────

class ObserverProposal(Base):
    """Improvement proposal generated by the Conversation Quality Observer."""
    __tablename__ = "ce_observer_proposals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # fact_rule | question | category | prompt_optimization
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    # draft|approved|active_validation|validated_success|validated_failed|rollback
    metrics_before: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    metrics_after: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    validation_result: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # keep_active|rollback|extend_validation
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


# ── New Runtime Models (Migration 0074) ───────────────────────────────────────

class Conversation(Base):
    """Core conversation entity for the HeyKarl Conversation Engine."""
    __tablename__ = "conversation"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    current_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="exploration")
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="workspace")
    linked_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    linked_epic_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("epics.id", ondelete="SET NULL"), nullable=True)
    linked_process_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)  # process not yet implemented
    linked_capability_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)  # capability not yet implemented
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationMessage(Base):
    """A message within a conversation (user or assistant)."""
    __tablename__ = "conversation_message"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user|assistant|system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    token_input: Mapped[int] = mapped_column(nullable=False, default=0)
    token_output: Mapped[int] = mapped_column(nullable=False, default=0)
    token_total: Mapped[int] = mapped_column(nullable=False, default=0)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ConversationState(Base):
    """Current state of a conversation (singleton per conversation)."""
    __tablename__ = "conversation_state"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, unique=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="exploration")
    current_step: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    complexity_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    context_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unassigned")
    known_facts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    missing_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    next_questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    story_size_score: Mapped[int] = mapped_column(nullable=False, default=0)
    recommended_story_count: Mapped[int] = mapped_column(nullable=False, default=1)
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ConversationProtocolArea(Base):
    """A protocol area (section) for the conversation protocol."""
    __tablename__ = "conversation_protocol_area"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    help_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
    is_required: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    role_visibility: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    validation_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "key", name="uq_protocol_area_org_key"),
    )


class ConversationProtocolEntry(Base):
    """An entry in the conversation protocol (maps facts to protocol areas)."""
    __tablename__ = "conversation_protocol_entry"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    protocol_area_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation_protocol_area.id"), nullable=False, index=True)
    fact_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("conversation_fact.id", ondelete="SET NULL"), nullable=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="suggested")
    confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ConversationStorySizingResult(Base):
    """Result of a story sizing calculation."""
    __tablename__ = "conversation_story_sizing_result"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    size_score: Mapped[int] = mapped_column(nullable=False)
    size_label: Mapped[str] = mapped_column(String(10), nullable=False)
    recommended_story_count: Mapped[int] = mapped_column(nullable=False, default=1)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    detected_subtopics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    detected_functions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    detected_user_groups: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    detected_systems: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ConversationReadinessResult(Base):
    """Result of a readiness evaluation."""
    __tablename__ = "conversation_readiness_result"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[int] = mapped_column(nullable=False, default=0)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    missing_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    findings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ConversationStructureProposal(Base):
    """Proposal for structuring the conversation output (e.g., split into stories)."""
    __tablename__ = "conversation_structure_proposal"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    source_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="exploration")
    target_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="story")
    recommended_artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    story_size_score: Mapped[int] = mapped_column(nullable=False, default=0)
    recommended_story_count: Mapped[int] = mapped_column(nullable=False, default=1)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    accepted_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ConversationObserverFinding(Base):
    """Finding from the Conversation Quality Observer."""
    __tablename__ = "conversation_observer_finding"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("conversation.id", ondelete="CASCADE"), nullable=True)
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("conversation_message.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_improvement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_rule_change: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    suggested_question_change: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    token_cost_estimate: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ConversationObserverProposalNew(Base):
    """Proposal generated from an observer finding."""
    __tablename__ = "conversation_observer_proposal_new"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("conversation_observer_finding.id", ondelete="SET NULL"), nullable=True)
    proposal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected_config_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    affected_config_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    proposed_change: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expected_impact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationObserverValidation(Base):
    """Validation run for an observer proposal."""
    __tablename__ = "conversation_observer_validation"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation_observer_proposal_new.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    metrics_before: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metrics_after: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    success_rate: Mapped[Optional[float]] = mapped_column(nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    side_effects: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    token_cost_delta: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationConfigVersion(Base):
    """Version history for conversation engine configuration changes."""
    __tablename__ = "conversation_config_version"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    config_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_config_version_config", "config_type", "config_id"),
    )


class ConversationAuditLog(Base):
    """Audit log for conversation engine events."""
    __tablename__ = "conversation_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("conversation.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    before_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    data_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_audit_log_org_id", "org_id"),
        Index("idx_audit_log_conversation_id", "conversation_id"),
        Index("idx_audit_log_action", "action"),
        Index("idx_audit_log_created_at", "created_at"),
    )
