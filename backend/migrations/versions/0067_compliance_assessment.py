"""Compliance Assessment system tables

Revision ID: 0067
Revises: 0066
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ComplianceAssessment ──────────────────────────────────────────────────
    op.create_table("ca_assessments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_type", sa.String(30), nullable=False),
        sa.Column("object_id", UUID(as_uuid=True), nullable=False),
        sa.Column("object_name", sa.String(500), nullable=False),
        sa.Column("context_params", JSONB, nullable=False, server_default="{}"),
        sa.Column("total_controls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fulfilled_controls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deviation_controls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("not_assessed_controls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("hard_stop_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("hard_stop_critical", sa.Integer, nullable=False, server_default="0"),
        sa.Column("overall_score", sa.Float, nullable=True),
        sa.Column("traffic_light", sa.String(10), nullable=False, server_default="'grey'"),
        sa.Column("compliance_status", sa.String(30), nullable=False, server_default="'not_assessed'"),
        sa.Column("gate_readiness", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("org_id", "object_type", "object_id", name="uq_ca_assessment_object"),
    )
    op.create_index("ix_ca_assessments_org_id", "ca_assessments", ["org_id"])
    op.create_index("ix_ca_assessments_object_id", "ca_assessments", ["object_id"])

    # ── ComplianceAssessmentItem ──────────────────────────────────────────────
    op.create_table("ca_assessment_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("assessment_id", UUID(as_uuid=True), sa.ForeignKey("ca_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_id", UUID(as_uuid=True), sa.ForeignKey("pg_control_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_slug", sa.String(200), nullable=False),
        sa.Column("control_name", sa.String(500), nullable=False),
        sa.Column("control_kind", sa.String(20), nullable=False),
        sa.Column("category_name", sa.String(300), nullable=True),
        sa.Column("gate_phases", JSONB, nullable=False, server_default="[]"),
        sa.Column("hard_stop", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("hard_stop_threshold", sa.Integer, nullable=False, server_default="1"),
        sa.Column("default_weight", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("control_objective", sa.Text, nullable=True),
        sa.Column("why_relevant", sa.Text, nullable=True),
        sa.Column("what_to_check", sa.Text, nullable=True),
        sa.Column("guiding_questions", JSONB, nullable=False, server_default="[]"),
        sa.Column("required_evidence_types", JSONB, nullable=False, server_default="[]"),
        sa.Column("responsible_role", sa.String(200), nullable=True),
        sa.Column("control_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("activation_source", sa.String(20), nullable=False, server_default="'fixed'"),
        sa.Column("activating_trigger_id", UUID(as_uuid=True), sa.ForeignKey("pg_trigger_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("activating_trigger_name", sa.String(500), nullable=True),
        sa.Column("activating_gate", sa.String(4), nullable=True),
        sa.Column("score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="'open'"),
        sa.Column("traffic_light", sa.String(10), nullable=False, server_default="'grey'"),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("residual_risk", sa.Text, nullable=True),
        sa.Column("evidence_status", sa.String(20), nullable=False, server_default="'missing'"),
        sa.Column("evidence_comment", sa.Text, nullable=True),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assessed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assessed_by_name", sa.String(300), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocks_gate", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("assessment_id", "control_id", name="uq_ca_item_control"),
    )
    op.create_index("ix_ca_assessment_items_assessment_id", "ca_assessment_items", ["assessment_id"])
    op.create_index("ix_ca_assessment_items_control_id", "ca_assessment_items", ["control_id"])

    # ── ComplianceScoreEntry ──────────────────────────────────────────────────
    op.create_table("ca_score_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("ca_assessment_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_score", sa.Integer, nullable=False),
        sa.Column("to_score", sa.Integer, nullable=False),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=True),
        sa.Column("rationale", sa.Text, nullable=True),
        sa.Column("gate_impact", sa.Text, nullable=True),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_by_name", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ca_score_entries_item_id", "ca_score_entries", ["item_id"])

    # ── ComplianceEvidenceLink ────────────────────────────────────────────────
    op.create_table("ca_evidence_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("ca_assessment_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_type_slug", sa.String(100), nullable=True),
        sa.Column("evidence_type_name", sa.String(300), nullable=True),
        sa.Column("file_name", sa.String(500), nullable=True),
        sa.Column("file_url", sa.Text, nullable=True),
        sa.Column("external_ref", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_mandatory", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ca_evidence_links_item_id", "ca_evidence_links", ["item_id"])

    # ── ComplianceAction ──────────────────────────────────────────────────────
    op.create_table("ca_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("ca_assessment_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="'open'"),
        sa.Column("priority", sa.String(10), nullable=False, server_default="'medium'"),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_name", sa.String(300), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalation_note", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ca_actions_item_id", "ca_actions", ["item_id"])

    # ── ComplianceStatusSnapshot ──────────────────────────────────────────────
    op.create_table("ca_status_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("assessment_id", UUID(as_uuid=True), sa.ForeignKey("ca_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger_reason", sa.String(100), nullable=False),
        sa.Column("compliance_status", sa.String(30), nullable=False),
        sa.Column("overall_score", sa.Float, nullable=True),
        sa.Column("traffic_light", sa.String(10), nullable=False),
        sa.Column("gate_readiness", JSONB, nullable=False, server_default="{}"),
        sa.Column("summary", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ca_status_snapshots_assessment_id", "ca_status_snapshots", ["assessment_id"])


def downgrade() -> None:
    for tbl in [
        "ca_status_snapshots", "ca_actions", "ca_evidence_links",
        "ca_score_entries", "ca_assessment_items", "ca_assessments",
    ]:
        op.drop_table(tbl)
