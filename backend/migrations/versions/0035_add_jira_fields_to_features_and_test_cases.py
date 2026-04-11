"""Add jira_ticket_key and jira_ticket_url to features and test_cases

Revision ID: 0035
Revises: 0034
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('features', sa.Column('jira_ticket_key', sa.String(50), nullable=True))
    op.add_column('features', sa.Column('jira_ticket_url', sa.Text(), nullable=True))
    op.add_column('test_cases', sa.Column('jira_ticket_key', sa.String(50), nullable=True))
    op.add_column('test_cases', sa.Column('jira_ticket_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('features', 'jira_ticket_key')
    op.drop_column('features', 'jira_ticket_url')
    op.drop_column('test_cases', 'jira_ticket_key')
    op.drop_column('test_cases', 'jira_ticket_url')
