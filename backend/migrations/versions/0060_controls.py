"""controls and control_capability_assignments tables

Revision ID: 0060
Revises: 0059
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── controls ────────────────────────────────────────────────────────────
    op.create_table(
        "controls",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", PGUUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("control_type", sa.String(20), nullable=False),
        sa.Column("implementation_status", sa.String(20), nullable=False, server_default="not_started"),
        sa.Column("owner_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_interval_days", sa.Integer, nullable=False, server_default="365"),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_due", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("framework_refs", JSONB, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_controls_org", "controls", ["org_id"])
    op.create_index("idx_controls_org_status", "controls", ["org_id", "implementation_status"])

    # ── control_capability_assignments ───────────────────────────────────────
    op.create_table(
        "control_capability_assignments",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", PGUUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_id", PGUUID(as_uuid=True), sa.ForeignKey("controls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability_node_id", PGUUID(as_uuid=True), sa.ForeignKey("capability_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("maturity_level", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("effectiveness", sa.String(32), nullable=False, server_default="not_assessed"),
        sa.Column("coverage_note", sa.Text, nullable=True),
        sa.Column("gap_description", sa.Text, nullable=True),
        sa.Column("assessor_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("last_assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_assessment_due", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_inherited", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("inherited_from_id", PGUUID(as_uuid=True), sa.ForeignKey("control_capability_assignments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("control_id", "capability_node_id", name="uq_cca_control_node"),
        sa.CheckConstraint("maturity_level BETWEEN 1 AND 5", name="ck_cca_maturity_level"),
    )
    op.create_index("idx_cca_control", "control_capability_assignments", ["control_id"])
    op.create_index("idx_cca_node", "control_capability_assignments", ["capability_node_id"])
    op.create_index("idx_cca_org_review", "control_capability_assignments", ["org_id", "next_assessment_due"])


def downgrade() -> None:
    op.drop_index("idx_cca_org_review", table_name="control_capability_assignments")
    op.drop_index("idx_cca_node", table_name="control_capability_assignments")
    op.drop_index("idx_cca_control", table_name="control_capability_assignments")
    op.drop_table("control_capability_assignments")

    op.drop_index("idx_controls_org_status", table_name="controls")
    op.drop_index("idx_controls_org", table_name="controls")
    op.drop_table("controls")
