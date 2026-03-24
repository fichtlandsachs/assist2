"""Add definition_of_done to user_stories

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user_stories', sa.Column('definition_of_done', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('user_stories', 'definition_of_done')
