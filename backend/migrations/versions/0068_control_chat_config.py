"""Control Chat Configuration tables

Revision ID: 0068
Revises: 0067
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ControlChatQuestion ───────────────────────────────────────────────────
    op.create_table("cc_questions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("control_id", UUID(as_uuid=True), sa.ForeignKey("pg_control_definitions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("primary_question", sa.Text, nullable=False),
        sa.Column("answer_type", sa.String(20), nullable=False, server_default="'free_text'"),
        sa.Column("answer_options", JSONB, nullable=False, server_default="[]"),
        sa.Column("alternative_questions", JSONB, nullable=False, server_default="[]"),
        sa.Column("followup_questions", JSONB, nullable=False, server_default="[]"),
        sa.Column("completion_conditions", JSONB, nullable=False, server_default="[]"),
        sa.Column("score_mapping_rules", JSONB, nullable=False, server_default="[]"),
        sa.Column("forbidden_terms", JSONB, nullable=False, server_default="[]"),
        sa.Column("hint_text", sa.Text, nullable=True),
        sa.Column("question_priority", sa.Integer, nullable=False, server_default="50"),
        sa.Column("always_ask", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("skippable", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("gap_label_template", sa.Text, nullable=True),
        sa.Column("risk_label_template", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_edited_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cc_questions_control_id", "cc_questions", ["control_id"])

    # ── ComplianceChatSession ─────────────────────────────────────────────────
    op.create_table("cc_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("assessment_id", UUID(as_uuid=True), sa.ForeignKey("ca_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="'active'"),
        sa.Column("context_params", JSONB, nullable=False, server_default="{}"),
        sa.Column("addressed_control_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("pending_control_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("next_question", JSONB, nullable=True),
        sa.Column("conversation_summary", sa.Text, nullable=True),
        sa.Column("turn_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cc_sessions_assessment_id", "cc_sessions", ["assessment_id"])
    op.create_index("ix_cc_sessions_org_id", "cc_sessions", ["org_id"])

    # ── ComplianceChatTurn ────────────────────────────────────────────────────
    op.create_table("cc_turns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("cc_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("role", sa.String(15), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("control_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("extracted_params", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cc_turns_session_id", "cc_turns", ["session_id"])

    # ── ComplianceChatMapping ─────────────────────────────────────────────────
    op.create_table("cc_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("cc_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_id", UUID(as_uuid=True), sa.ForeignKey("cc_turns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_id", UUID(as_uuid=True), sa.ForeignKey("pg_control_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_slug", sa.String(200), nullable=False),
        sa.Column("proposed_score", sa.Integer, nullable=False),
        sa.Column("proposed_status", sa.String(30), nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("trigger_params", JSONB, nullable=False, server_default="{}"),
        sa.Column("evidence_present", JSONB, nullable=False, server_default="[]"),
        sa.Column("evidence_required", JSONB, nullable=False, server_default="[]"),
        sa.Column("applied", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.8"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_cc_mappings_session_id", "cc_mappings", ["session_id"])


def downgrade() -> None:
    for tbl in ["cc_mappings", "cc_turns", "cc_sessions", "cc_questions"]:
        op.drop_table(tbl)
