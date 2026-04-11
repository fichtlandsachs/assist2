"""Add jira_ticket_url to user_stories

Revision ID: 0034
Revises: 0033
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user_stories', sa.Column('jira_ticket_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('user_stories', 'jira_ticket_url')
