"""add jira_stories table

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jira_stories",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("ticket_key", sa.String(50), nullable=False),
        sa.Column("project", sa.String(50), nullable=False),
        sa.Column("source_summary", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_jira_stories_org_project", "jira_stories", ["organization_id", "project"])
    op.create_index("ix_jira_stories_ticket_key", "jira_stories", ["ticket_key"])


def downgrade() -> None:
    op.drop_index("ix_jira_stories_ticket_key", table_name="jira_stories")
    op.drop_index("ix_jira_stories_org_project", table_name="jira_stories")
    op.drop_table("jira_stories")
