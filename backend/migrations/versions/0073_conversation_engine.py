"""Conversation Engine tables.

Revision ID: 0073
Revises: 0072
Create Date: 2026-04-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Config tables ─────────────────────────────────────────────────────────
    op.create_table(
        "ce_dialog_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("mode", sa.String(30), nullable=False, server_default="story_mode"),
        sa.Column("tone", sa.String(30), nullable=False, server_default="friendly"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("config_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ce_question_blocks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("follow_up_text", sa.Text, nullable=True),
        sa.Column("priority", sa.SmallInteger, nullable=False, server_default="5"),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("condition_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ce_answer_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("fact_category", sa.String(50), nullable=False),
        sa.Column("pattern_type", sa.String(20), nullable=False, server_default="keyword"),
        sa.Column("pattern", sa.Text, nullable=False),
        sa.Column("confidence_boost", sa.Float, nullable=False, server_default="0.1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ce_prompt_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("phase", sa.String(50), nullable=False),
        sa.Column("prompt_text", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("key", "version", name="uq_ce_prompt_key_version"),
    )

    op.create_table(
        "ce_conversation_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("rule_type", sa.String(40), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("value_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ce_sizing_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("dimension", sa.String(50), nullable=False),
        sa.Column("weight", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("thresholds_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ce_readiness_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("required_category", sa.String(50), nullable=False),
        sa.Column("min_confidence", sa.Float, nullable=False, server_default="0.6"),
        sa.Column("is_blocking", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("weight", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Runtime tables ────────────────────────────────────────────────────────
    op.create_table(
        "ce_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_by_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("profile_id", UUID(as_uuid=True),
                  sa.ForeignKey("ce_dialog_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("epic_id", UUID(as_uuid=True),
                  sa.ForeignKey("epics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("story_id", UUID(as_uuid=True),
                  sa.ForeignKey("user_stories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mode", sa.String(30), nullable=False, server_default="exploration_mode"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("messages", JSONB, nullable=False, server_default="[]"),
        sa.Column("protocol_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("sizing_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("readiness_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("asked_question_keys", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ce_facts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True),
                  sa.ForeignKey("ce_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("status", sa.String(20), nullable=False, server_default="detected"),
        sa.Column("source_turn", sa.SmallInteger, nullable=True),
        sa.Column("source_quote", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ce_observer_proposals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("proposal_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("suggested_config", JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("metrics_before", JSONB, nullable=True),
        sa.Column("metrics_after", JSONB, nullable=True),
        sa.Column("validation_result", sa.String(30), nullable=True),
        sa.Column("approved_by_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ce_observer_proposals")
    op.drop_table("ce_facts")
    op.drop_table("ce_sessions")
    op.drop_table("ce_readiness_rules")
    op.drop_table("ce_sizing_rules")
    op.drop_table("ce_conversation_rules")
    op.drop_table("ce_prompt_templates")
    op.drop_table("ce_answer_signals")
    op.drop_table("ce_question_blocks")
    op.drop_table("ce_dialog_profiles")
