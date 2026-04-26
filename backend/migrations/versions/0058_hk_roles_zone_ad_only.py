"""hk_role_assignments, hk_role_zone_grants, rag_zones.ad_group_only

Revision ID: 0058
Revises: 0057
Create Date: 2026-04-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ad_group_only flag: zones marked this way cannot be opened via heyKarl role grants
    op.add_column(
        "rag_zones",
        sa.Column("ad_group_only", sa.Boolean(), server_default="false", nullable=False),
    )

    # heyKarl-internal role assignments (additive to AD roles)
    op.create_table(
        "hk_role_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_name", sa.String(100), nullable=False),
        sa.Column("scope_type", sa.String(50), nullable=True),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_hk_role_assignments_user_org",
        "hk_role_assignments",
        ["user_id", "org_id"],
    )
    # Partial unique indexes handle nullable scope_id correctly
    op.create_index(
        "uq_hk_role_assignment_org_wide",
        "hk_role_assignments",
        ["user_id", "org_id", "role_name"],
        unique=True,
        postgresql_where=sa.text("scope_id IS NULL"),
    )
    op.create_index(
        "uq_hk_role_assignment_scoped",
        "hk_role_assignments",
        ["user_id", "org_id", "role_name", "scope_id"],
        unique=True,
        postgresql_where=sa.text("scope_id IS NOT NULL"),
    )

    # Zone grants per heyKarl role (org-scoped mapping: role_name → zone)
    op.create_table(
        "hk_role_zone_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_name", sa.String(100), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["rag_zones.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("org_id", "role_name", "zone_id", name="uq_hk_role_zone_grant"),
    )
    op.create_index(
        "ix_hk_role_zone_grants_org_role",
        "hk_role_zone_grants",
        ["org_id", "role_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_hk_role_zone_grants_org_role", table_name="hk_role_zone_grants")
    op.drop_table("hk_role_zone_grants")
    op.drop_index("uq_hk_role_assignment_scoped", table_name="hk_role_assignments")
    op.drop_index("uq_hk_role_assignment_org_wide", table_name="hk_role_assignments")
    op.drop_index("ix_hk_role_assignments_user_org", table_name="hk_role_assignments")
    op.drop_table("hk_role_assignments")
    op.drop_column("rag_zones", "ad_group_only")
