"""Add quality_score column to user_stories

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user_stories', sa.Column('quality_score', sa.Integer(), nullable=True))
    op.create_index('ix_user_stories_quality_score', 'user_stories', ['quality_score'])


def downgrade() -> None:
    op.drop_index('ix_user_stories_quality_score', 'user_stories')
    op.drop_column('user_stories', 'quality_score')
