"""Add process_mapping_suggestions table

Revision ID: 0064
Revises: 0063
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'process_suggestion_status_enum') THEN
                CREATE TYPE process_suggestion_status_enum AS ENUM ('pending', 'confirmed', 'rejected', 'reassigned');
            END IF;
        END$$
    """)
    op.create_table(
        "process_mapping_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("process_name", sa.String(500), nullable=False),
        sa.Column("detected_context", sa.Text, nullable=True),
        sa.Column("suggested_node_id", UUID(as_uuid=True), sa.ForeignKey("capability_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suggested_node_title", sa.String(500), nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("source_reference", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("admin_note", sa.Text, nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_process_suggestions_org_status", "process_mapping_suggestions", ["org_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_process_suggestions_org_status", table_name="process_mapping_suggestions")
    op.drop_table("process_mapping_suggestions")
    op.execute("DROP TYPE IF EXISTS process_suggestion_status_enum")
