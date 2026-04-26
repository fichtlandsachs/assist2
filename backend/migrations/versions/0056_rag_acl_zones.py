"""RAG ACL: rag_zones, rag_zone_memberships tables and document_chunks.zone_id FK

Revision ID: 0056
Revises: 0054
Create Date: 2026-04-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0056"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("organization_id", "slug", name="uq_rag_zones_org_slug"),
    )
    op.create_index("ix_rag_zones_organization_id", "rag_zones", ["organization_id"])

    op.create_table(
        "rag_zone_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ad_group_name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["zone_id"], ["rag_zones.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "zone_id", "ad_group_name", name="uq_rag_zone_memberships_zone_group"
        ),
    )
    op.create_index(
        "ix_rag_zone_memberships_zone_id", "rag_zone_memberships", ["zone_id"]
    )

    op.add_column(
        "document_chunks",
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_chunks_zone_id",
        "document_chunks",
        "rag_zones",
        ["zone_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_document_chunks_zone_id", "document_chunks", ["zone_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_zone_id", table_name="document_chunks")
    op.drop_constraint(
        "fk_document_chunks_zone_id", "document_chunks", type_="foreignkey"
    )
    op.drop_column("document_chunks", "zone_id")
    op.drop_index("ix_rag_zone_memberships_zone_id", table_name="rag_zone_memberships")
    op.drop_table("rag_zone_memberships")
    op.drop_index("ix_rag_zones_organization_id", table_name="rag_zones")
    op.drop_table("rag_zones")
