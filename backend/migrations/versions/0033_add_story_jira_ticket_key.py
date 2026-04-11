"""Add jira_ticket_key to user_stories

Revision ID: 0033
Revises: 0032
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = '0033'
down_revision = '0032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user_stories', sa.Column('jira_ticket_key', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('user_stories', 'jira_ticket_key')
