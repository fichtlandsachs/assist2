"""Add tasks, risks, adrs tables

Revision ID: 0050
Revises: 0049
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("story_id", UUID(as_uuid=True), sa.ForeignKey("user_stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("assignee_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("current_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tasks_organization_id", "tasks", ["organization_id"])
    op.create_index("ix_tasks_story_id", "tasks", ["story_id"])

    op.create_table(
        "risks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("probability", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("impact", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("linked_story_id", UUID(as_uuid=True), sa.ForeignKey("user_stories.id"), nullable=True),
        sa.Column("linked_epic_id", UUID(as_uuid=True), sa.ForeignKey("epics.id"), nullable=True),
        sa.Column("current_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_risks_organization_id", "risks", ["organization_id"])
    op.create_index("ix_risks_linked_story_id", "risks", ["linked_story_id"])
    op.create_index("ix_risks_linked_epic_id", "risks", ["linked_epic_id"])

    op.create_table(
        "adrs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("consequences", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column("linked_story_id", UUID(as_uuid=True), sa.ForeignKey("user_stories.id"), nullable=True),
        sa.Column("linked_feature_id", UUID(as_uuid=True), sa.ForeignKey("features.id"), nullable=True),
        sa.Column("current_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_adrs_organization_id", "adrs", ["organization_id"])
    op.create_index("ix_adrs_linked_story_id", "adrs", ["linked_story_id"])
    op.create_index("ix_adrs_linked_feature_id", "adrs", ["linked_feature_id"])


def downgrade() -> None:
    op.drop_table("adrs")
    op.drop_table("risks")
    op.drop_table("tasks")
