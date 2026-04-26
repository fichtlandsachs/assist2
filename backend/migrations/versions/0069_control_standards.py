"""Standards, Control-Standard-Mappings, and control_family column

Revision ID: 0069
Revises: 0068
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── StandardDefinition ────────────────────────────────────────────────────
    op.create_table("pg_standards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("short_name", sa.String(60), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("standard_type", sa.String(40), nullable=False, server_default="'external'"),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("icon", sa.String(60), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── ControlStandardMapping ────────────────────────────────────────────────
    op.create_table("pg_control_standard_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("control_id", UUID(as_uuid=True),
            sa.ForeignKey("pg_control_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("standard_id", UUID(as_uuid=True),
            sa.ForeignKey("pg_standards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_ref", sa.String(100), nullable=True),
        sa.Column("section_label", sa.String(500), nullable=True),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="50"),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("control_id", "standard_id", name="uq_pg_ctrl_std_mapping"),
    )
    op.create_index("ix_pg_ctrl_std_control_id", "pg_control_standard_mappings", ["control_id"])
    op.create_index("ix_pg_ctrl_std_standard_id", "pg_control_standard_mappings", ["standard_id"])

    # ── Add control_family to pg_control_definitions ──────────────────────────
    op.add_column("pg_control_definitions",
        sa.Column("control_family", sa.String(300), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("pg_control_definitions", "control_family")
    op.drop_table("pg_control_standard_mappings")
    op.drop_table("pg_standards")
