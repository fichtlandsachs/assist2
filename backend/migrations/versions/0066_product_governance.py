"""Product Governance & Control Management System tables

Revision ID: 0066
Revises: 0065
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Control Categories ────────────────────────────────────────────────────
    op.create_table("pg_control_categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── Product Scopes ────────────────────────────────────────────────────────
    op.create_table("pg_product_scopes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("pg_product_scopes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attributes", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── Market Scopes ─────────────────────────────────────────────────────────
    op.create_table("pg_market_scopes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("countries", JSONB, nullable=False, server_default="[]"),
        sa.Column("regulatory_framework", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── Customer Segments ─────────────────────────────────────────────────────
    op.create_table("pg_customer_segments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("segment_type", sa.String(50), nullable=False),
        sa.Column("attributes", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── Risk Dimensions ───────────────────────────────────────────────────────
    op.create_table("pg_risk_dimensions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("risk_type", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── Evidence Types ────────────────────────────────────────────────────────
    op.create_table("pg_evidence_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("format_guidance", sa.Text, nullable=True),
        sa.Column("template_url", sa.Text, nullable=True),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── Scoring Schemes ───────────────────────────────────────────────────────
    op.create_table("pg_scoring_schemes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("scale_min", sa.Integer, nullable=False, server_default="0"),
        sa.Column("scale_max", sa.Integer, nullable=False, server_default="3"),
        sa.Column("scale_labels", JSONB, nullable=False, server_default="[]"),
        sa.Column("traffic_light", JSONB, nullable=False, server_default="{}"),
        sa.Column("formula", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── Gate Definitions ──────────────────────────────────────────────────────
    op.create_table("pg_gate_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("phase", sa.String(4), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("min_total_score", sa.Float, nullable=True),
        sa.Column("required_fixed_control_slugs", JSONB, nullable=False, server_default="[]"),
        sa.Column("hard_stop_threshold", sa.Integer, nullable=False, server_default="1"),
        sa.Column("approver_roles", JSONB, nullable=False, server_default="[]"),
        sa.Column("escalation_path", sa.Text, nullable=True),
        sa.Column("outcomes_config", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="'approved'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table("pg_gate_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("gate_id", UUID(as_uuid=True), sa.ForeignKey("pg_gate_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("snapshot", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("change_reason", sa.Text, nullable=True),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("gate_id", "version", name="uq_gate_version"),
    )
    op.create_index("ix_pg_gate_versions_gate_id", "pg_gate_versions", ["gate_id"])

    # ── Control Definitions ───────────────────────────────────────────────────
    op.create_table("pg_control_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("system_id", sa.String(100), nullable=True, unique=True),
        sa.Column("slug", sa.String(200), nullable=False, unique=True),
        sa.Column("kind", sa.String(20), nullable=False, server_default="'dynamic'"),
        # Layer 1 - user
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("short_description", sa.Text, nullable=True),
        sa.Column("why_relevant", sa.Text, nullable=True),
        sa.Column("what_to_check", sa.Text, nullable=True),
        sa.Column("what_to_do", sa.Text, nullable=True),
        sa.Column("guiding_questions", JSONB, nullable=False, server_default="[]"),
        sa.Column("help_text", sa.Text, nullable=True),
        # Layer 2 - governance
        sa.Column("category_id", UUID(as_uuid=True), sa.ForeignKey("pg_control_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("control_objective", sa.Text, nullable=True),
        sa.Column("risk_rationale", sa.Text, nullable=True),
        sa.Column("escalation_logic", sa.Text, nullable=True),
        sa.Column("gate_phases", JSONB, nullable=False, server_default="[]"),
        sa.Column("scoring_scheme_id", UUID(as_uuid=True), sa.ForeignKey("pg_scoring_schemes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("default_weight", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("hard_stop", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("hard_stop_threshold", sa.Integer, nullable=False, server_default="1"),
        sa.Column("requires_trigger", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("trigger_config", JSONB, nullable=False, server_default="{}"),
        sa.Column("evidence_requirements", JSONB, nullable=False, server_default="[]"),
        sa.Column("product_scope_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("market_scope_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("customer_segment_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("risk_dimension_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("framework_refs", JSONB, nullable=False, server_default="[]"),
        sa.Column("review_interval_days", sa.Integer, nullable=False, server_default="365"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responsible_role", sa.String(200), nullable=True),
        sa.Column("audit_notes", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="'draft'"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_visible_in_frontend", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pg_control_definitions_org_id", "pg_control_definitions", ["org_id"])
    op.create_index("ix_pg_control_definitions_kind", "pg_control_definitions", ["kind"])
    op.create_index("ix_pg_control_definitions_status", "pg_control_definitions", ["status"])

    op.create_table("pg_control_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("control_id", UUID(as_uuid=True), sa.ForeignKey("pg_control_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("snapshot", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("change_reason", sa.Text, nullable=True),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("control_id", "version", name="uq_control_version"),
    )
    op.create_index("ix_pg_control_versions_control_id", "pg_control_versions", ["control_id"])

    # ── Trigger Rules ─────────────────────────────────────────────────────────
    op.create_table("pg_trigger_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("slug", sa.String(200), nullable=False, unique=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("condition_tree", JSONB, nullable=False, server_default="{}"),
        sa.Column("activates_control_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("conflict_resolution", sa.String(50), nullable=False, server_default="'latest_wins'"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("status", sa.String(20), nullable=False, server_default="'approved'"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_pg_trigger_rules_org_id", "pg_trigger_rules", ["org_id"])

    # ── Governance Change Log ─────────────────────────────────────────────────
    op.create_table("pg_governance_changelog",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_slug", sa.String(200), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=True),
        sa.Column("from_version", sa.Integer, nullable=True),
        sa.Column("to_version", sa.Integer, nullable=True),
        sa.Column("change_reason", sa.Text, nullable=True),
        sa.Column("diff", JSONB, nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_name", sa.String(300), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_pg_governance_changelog_entity_id", "pg_governance_changelog", ["entity_id"])
    op.create_index("ix_pg_governance_changelog_occurred_at", "pg_governance_changelog", ["occurred_at"])

    # ── Simulation Scenarios ──────────────────────────────────────────────────
    op.create_table("pg_simulation_scenarios",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("input_params", JSONB, nullable=False, server_default="{}"),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("result_computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    for tbl in [
        "pg_simulation_scenarios", "pg_governance_changelog", "pg_trigger_rules",
        "pg_control_versions", "pg_control_definitions", "pg_gate_versions",
        "pg_gate_definitions", "pg_scoring_schemes", "pg_evidence_types",
        "pg_risk_dimensions", "pg_customer_segments", "pg_market_scopes",
        "pg_product_scopes", "pg_control_categories",
    ]:
        op.drop_table(tbl)
