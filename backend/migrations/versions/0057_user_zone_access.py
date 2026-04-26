"""user_zone_access: soft-revocable, project-scoped zone grants

Revision ID: 0057
Revises: 0056
Create Date: 2026-04-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_zone_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_scope", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("granted_via", sa.String(50), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["rag_zones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_user_zone_access_user_org",
        "user_zone_access",
        ["user_id", "org_id"],
    )
    op.create_index(
        "ix_user_zone_access_zone",
        "user_zone_access",
        ["zone_id"],
    )
    # Partial unique indexes handle nullable project_scope correctly in PostgreSQL
    op.create_index(
        "uq_user_zone_access_org_wide",
        "user_zone_access",
        ["user_id", "zone_id", "org_id"],
        unique=True,
        postgresql_where=sa.text("project_scope IS NULL"),
    )
    op.create_index(
        "uq_user_zone_access_project",
        "user_zone_access",
        ["user_id", "zone_id", "org_id", "project_scope"],
        unique=True,
        postgresql_where=sa.text("project_scope IS NOT NULL"),
    )
    # Partial index for fast active-grants lookup
    op.create_index(
        "ix_user_zone_access_active",
        "user_zone_access",
        ["user_id", "org_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_user_zone_access_active", table_name="user_zone_access")
    op.drop_index("uq_user_zone_access_project", table_name="user_zone_access")
    op.drop_index("uq_user_zone_access_org_wide", table_name="user_zone_access")
    op.drop_index("ix_user_zone_access_zone", table_name="user_zone_access")
    op.drop_index("ix_user_zone_access_user_org", table_name="user_zone_access")
    op.drop_table("user_zone_access")
