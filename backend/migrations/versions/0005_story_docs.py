"""Add generated_docs and confluence_page_url to user_stories

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user_stories', sa.Column('generated_docs', sa.Text(), nullable=True))
    op.add_column('user_stories', sa.Column('confluence_page_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('user_stories', 'confluence_page_url')
    op.drop_column('user_stories', 'generated_docs')
