"""web search cost logs

Revision ID: 0048
Revises: 0047
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "web_search_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_web_search_logs_organization_id",
        "web_search_logs",
        ["organization_id"],
    )
    op.create_index(
        "ix_web_search_logs_created_at",
        "web_search_logs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("web_search_logs")
