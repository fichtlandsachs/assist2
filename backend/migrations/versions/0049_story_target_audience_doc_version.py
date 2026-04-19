"""story target_audience and doc_version fields

Revision ID: 0049
Revises: 0048
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_stories", sa.Column("target_audience", sa.Text, nullable=True))
    op.add_column("user_stories", sa.Column("doc_version", sa.String(20), nullable=True, server_default="1.0"))


def downgrade() -> None:
    op.drop_column("user_stories", "target_audience")
    op.drop_column("user_stories", "doc_version")
