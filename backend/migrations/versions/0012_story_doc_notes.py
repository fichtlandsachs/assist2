"""Add doc_additional_info and doc_workarounds to user_stories

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_stories", sa.Column("doc_additional_info", sa.Text(), nullable=True))
    op.add_column("user_stories", sa.Column("doc_workarounds", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_stories", "doc_workarounds")
    op.drop_column("user_stories", "doc_additional_info")
