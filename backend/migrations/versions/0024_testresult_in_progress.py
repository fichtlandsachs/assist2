"""add in_progress value to testresult enum

Revision ID: 0024
Revises: 0023
Create Date: 2026-04-06
"""
from alembic import op

revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE testresult ADD VALUE IF NOT EXISTS 'in_progress'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values; handled by renaming/recreating if needed
    pass
