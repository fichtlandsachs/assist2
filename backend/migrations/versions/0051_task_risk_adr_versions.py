"""Add task_versions, risk_versions, adr_versions tables

Revision ID: 0051
Revises: 0050
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def _version_table_columns(artifact_col: str, artifact_table: str):
    """Return common columns for a *_versions table."""
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(artifact_col, UUID(as_uuid=True), sa.ForeignKey(f"{artifact_table}.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_string", sa.String(20), nullable=False),
        sa.Column("prev_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("next_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("changed_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("change_description", sa.Text(), nullable=True),
        sa.Column("change_type", sa.String(30), nullable=False),
        sa.Column("major_minor_patch", sa.String(10), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("content_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("delta", sa.JSON(), nullable=True),
        sa.Column("impact", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    for table_name, artifact_col, artifact_table in [
        ("task_versions", "task_id", "tasks"),
        ("risk_versions", "risk_id", "risks"),
        ("adr_versions", "adr_id", "adrs"),
    ]:
        op.create_table(table_name, *_version_table_columns(artifact_col, artifact_table))
        op.create_index(f"ix_{table_name}_{artifact_col}", table_name, [artifact_col])
        op.create_index(f"ix_{table_name}_organization_id", table_name, ["organization_id"])
        # Add self-referential FKs after table creation to avoid forward references
        op.create_foreign_key(
            f"fk_{table_name}_prev", table_name, table_name,
            ["prev_version_id"], ["id"], ondelete="SET NULL"
        )
        op.create_foreign_key(
            f"fk_{table_name}_next", table_name, table_name,
            ["next_version_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    for table_name in ["adr_versions", "risk_versions", "task_versions"]:
        op.drop_table(table_name)
