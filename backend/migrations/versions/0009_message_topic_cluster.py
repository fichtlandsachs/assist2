"""Add topic_cluster to messages

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('topic_cluster', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'topic_cluster')
