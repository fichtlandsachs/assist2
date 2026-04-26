"""Conversation Engine runtime tables.

Revision ID: 0074
Revises: 0073
Create Date: 2026-04-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Core Conversation ─────────────────────────────────────────────────────
    op.create_table(
        "conversation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("current_mode", sa.String(30), nullable=False, server_default="exploration"),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="workspace"),
        sa.Column("linked_project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("linked_epic_id", UUID(as_uuid=True), sa.ForeignKey("epics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("linked_process_id", UUID(as_uuid=True), nullable=True),  # process not yet implemented
        sa.Column("linked_capability_id", UUID(as_uuid=True), nullable=True),  # capability not yet implemented
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_conversation_org_id", "conversation", ["org_id"])
    op.create_index("idx_conversation_user_id", "conversation", ["user_id"])
    op.create_index("idx_conversation_status", "conversation", ["status"])
    op.create_index("idx_conversation_current_mode", "conversation", ["current_mode"])

    # ── Conversation Messages ────────────────────────────────────────────────
    op.create_table(
        "conversation_message",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),  # user|assistant|system
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("token_input", sa.Integer, server_default="0", nullable=False),
        sa.Column("token_output", sa.Integer, server_default="0", nullable=False),
        sa.Column("token_total", sa.Integer, server_default="0", nullable=False),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_conversation_message_conversation_id", "conversation_message", ["conversation_id"])
    op.create_index("idx_conversation_message_org_id", "conversation_message", ["org_id"])
    op.create_index("idx_conversation_message_created_at", "conversation_message", ["created_at"])

    # ── Conversation State ───────────────────────────────────────────────────
    op.create_table(
        "conversation_state",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False, server_default="exploration"),
        sa.Column("current_step", sa.String(50), nullable=True),
        sa.Column("complexity_level", sa.String(20), nullable=True),
        sa.Column("context_status", sa.String(20), nullable=False, server_default="unassigned"),
        sa.Column("known_facts", JSONB, nullable=False, server_default="{}"),
        sa.Column("missing_fields", JSONB, nullable=False, server_default="[]"),
        sa.Column("next_questions", JSONB, nullable=False, server_default="[]"),
        sa.Column("story_size_score", sa.Integer, server_default="0", nullable=False),
        sa.Column("recommended_story_count", sa.Integer, server_default="1", nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_conversation_state_org_id", "conversation_state", ["org_id"])
    op.create_index("idx_conversation_state_mode", "conversation_state", ["mode"])

    # ── Conversation Fact ────────────────────────────────────────────────────
    op.create_table(
        "conversation_fact",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_message_id", UUID(as_uuid=True), sa.ForeignKey("conversation_message.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("normalized_value", sa.Text, nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="detected"),  # detected|suggested|confirmed|rejected
        sa.Column("used_in", JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("confirmed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by", UUID(as_uuid=True), sa.ForeignKey("conversation_fact.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_conversation_fact_conversation_id", "conversation_fact", ["conversation_id"])
    op.create_index("idx_conversation_fact_org_id", "conversation_fact", ["org_id"])
    op.create_index("idx_conversation_fact_category", "conversation_fact", ["category"])
    op.create_index("idx_conversation_fact_status", "conversation_fact", ["status"])

    # ── Protocol Area ────────────────────────────────────────────────────────
    op.create_table(
        "conversation_protocol_area",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),  # NULL = global
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("help_text", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, server_default="0", nullable=False),
        sa.Column("is_required", sa.Boolean, server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("role_visibility", JSONB, nullable=False, server_default="[]"),
        sa.Column("validation_rules", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("org_id", "key", name="uq_protocol_area_org_key"),
    )

    # ── Protocol Entry ───────────────────────────────────────────────────────
    op.create_table(
        "conversation_protocol_entry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("protocol_area_id", UUID(as_uuid=True), sa.ForeignKey("conversation_protocol_area.id"), nullable=False),
        sa.Column("fact_id", UUID(as_uuid=True), sa.ForeignKey("conversation_fact.id", ondelete="SET NULL"), nullable=True),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="suggested"),  # suggested|confirmed|rejected
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_protocol_entry_conversation_id", "conversation_protocol_entry", ["conversation_id"])
    op.create_index("idx_protocol_entry_area_id", "conversation_protocol_entry", ["protocol_area_id"])

    # ── Configuration Tables (extend existing) ─────────────────────────────────
    # These extend the ce_* tables from 0073 with additional fields for org-specific overrides
    
    # ── Sizing Result ──────────────────────────────────────────────────────────
    op.create_table(
        "conversation_story_sizing_result",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("size_score", sa.Integer, nullable=False),
        sa.Column("size_label", sa.String(10), nullable=False),  # XS|S|M|L|XL
        sa.Column("recommended_story_count", sa.Integer, server_default="1", nullable=False),
        sa.Column("recommendation", sa.Text, nullable=False),
        sa.Column("detected_subtopics", JSONB, nullable=False, server_default="[]"),
        sa.Column("detected_functions", JSONB, nullable=False, server_default="[]"),
        sa.Column("detected_user_groups", JSONB, nullable=False, server_default="[]"),
        sa.Column("detected_systems", JSONB, nullable=False, server_default="[]"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Readiness Result ─────────────────────────────────────────────────────
    op.create_table(
        "conversation_readiness_result",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),  # not_ready|ready|excellent
        sa.Column("score", sa.Integer, server_default="0", nullable=False),
        sa.Column("recommendation", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("missing_fields", JSONB, nullable=False, server_default="[]"),
        sa.Column("findings", JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Structure Proposal ───────────────────────────────────────────────────
    op.create_table(
        "conversation_structure_proposal",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_mode", sa.String(30), nullable=False, server_default="exploration"),
        sa.Column("target_mode", sa.String(30), nullable=False, server_default="story"),
        sa.Column("recommended_artifact_type", sa.String(50), nullable=False),  # story|epic|process
        sa.Column("story_size_score", sa.Integer, server_default="0", nullable=False),
        sa.Column("recommended_story_count", sa.Integer, server_default="1", nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("items", JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),  # draft|accepted|rejected
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accepted_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_structure_proposal_conversation_id", "conversation_structure_proposal", ["conversation_id"])
    op.create_index("idx_structure_proposal_status", "conversation_structure_proposal", ["status"])

    # ── Observer Finding ─────────────────────────────────────────────────────
    op.create_table(
        "conversation_observer_finding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=True),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("conversation_message.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),  # low|medium|high|critical
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("suggested_improvement", sa.Text, nullable=True),
        sa.Column("suggested_rule_change", JSONB, nullable=True),
        sa.Column("suggested_question_change", JSONB, nullable=True),
        sa.Column("token_cost_estimate", sa.Integer, server_default="0", nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),  # open|reviewed|fixed|wontfix
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    # ── Observer Proposal ────────────────────────────────────────────────────
    op.create_table(
        "conversation_observer_proposal_new",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", UUID(as_uuid=True), sa.ForeignKey("conversation_observer_finding.id", ondelete="SET NULL"), nullable=True),
        sa.Column("proposal_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("affected_config_type", sa.String(50), nullable=True),
        sa.Column("affected_config_id", UUID(as_uuid=True), nullable=True),
        sa.Column("proposed_change", JSONB, nullable=False, server_default="{}"),
        sa.Column("expected_impact", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),  # draft|approved|rejected|activated|rolled_back
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Observer Validation ────────────────────────────────────────────────
    op.create_table(
        "conversation_observer_validation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("proposal_id", UUID(as_uuid=True), sa.ForeignKey("conversation_observer_proposal_new.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("baseline_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("baseline_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),  # running|completed|failed
        sa.Column("metrics_before", JSONB, nullable=False, server_default="{}"),
        sa.Column("metrics_after", JSONB, nullable=False, server_default="{}"),
        sa.Column("success_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("side_effects", JSONB, nullable=False, server_default="[]"),
        sa.Column("token_cost_delta", sa.Integer, server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Config Version ───────────────────────────────────────────────────────
    op.create_table(
        "conversation_config_version",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("config_type", sa.String(50), nullable=False),
        sa.Column("config_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("change_reason", sa.Text, nullable=True),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(30), server_default="manual", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_config_version_config", "conversation_config_version", ["config_type", "config_id"])

    # ── Audit Log ────────────────────────────────────────────────────────────
    op.create_table(
        "conversation_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversation.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_type", sa.String(20), server_default="user", nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("before_state", JSONB, nullable=True),
        sa.Column("after_state", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_audit_log_org_id", "conversation_audit_log", ["org_id"])
    op.create_index("idx_audit_log_conversation_id", "conversation_audit_log", ["conversation_id"])
    op.create_index("idx_audit_log_action", "conversation_audit_log", ["action"])
    op.create_index("idx_audit_log_created_at", "conversation_audit_log", ["created_at"])


def downgrade() -> None:
    tables = [
        "conversation_audit_log",
        "conversation_config_version",
        "conversation_observer_validation",
        "conversation_observer_proposal_new",
        "conversation_observer_finding",
        "conversation_structure_proposal",
        "conversation_readiness_result",
        "conversation_story_sizing_result",
        "conversation_protocol_entry",
        "conversation_protocol_area",
        "conversation_fact",
        "conversation_state",
        "conversation_message",
        "conversation",
    ]
    for table in tables:
        op.drop_table(table)
