"""Add jira sync fields to user_stories

Revision ID: 0045_jira_sync_fields
Revises: 0044
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_stories", sa.Column("jira_creator", sa.String(255), nullable=True))
    op.add_column("user_stories", sa.Column("jira_reporter", sa.String(255), nullable=True))
    op.add_column("user_stories", sa.Column("jira_created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_stories", sa.Column("jira_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_stories", sa.Column("jira_status", sa.String(100), nullable=True))
    op.add_column("user_stories", sa.Column("jira_linked_issue_keys", sa.Text(), nullable=True))
    op.add_column("user_stories", sa.Column("jira_last_synced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("user_stories", "jira_creator")
    op.drop_column("user_stories", "jira_reporter")
    op.drop_column("user_stories", "jira_created_at")
    op.drop_column("user_stories", "jira_updated_at")
    op.drop_column("user_stories", "jira_status")
    op.drop_column("user_stories", "jira_linked_issue_keys")
    op.drop_column("user_stories", "jira_last_synced_at")
