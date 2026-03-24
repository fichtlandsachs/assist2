"""Add user_stories and test_cases tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # USER_STORIES TABLE
    # =========================================================================
    op.create_table(
        "user_stories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "priority",
            sa.String(50),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("story_points", sa.Integer, nullable=True),
        sa.Column(
            "assignee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reporter_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "parent_story_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_stories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("acceptance_criteria", postgresql.JSON, nullable=True),
        sa.Column("metadata", postgresql.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Indexes for user_stories
    op.create_index(
        "ix_user_stories_organization_id",
        "user_stories",
        ["organization_id"],
    )
    op.create_index(
        "ix_user_stories_status",
        "user_stories",
        ["status"],
    )
    op.create_index(
        "ix_user_stories_assignee_id",
        "user_stories",
        ["assignee_id"],
    )
    op.create_index(
        "ix_user_stories_org_status",
        "user_stories",
        ["organization_id", "status"],
    )

    # =========================================================================
    # TEST_CASES TABLE
    # =========================================================================
    op.create_table(
        "test_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "story_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("steps", postgresql.JSON, nullable=True),
        sa.Column("expected_result", sa.Text, nullable=True),
        sa.Column("actual_result", sa.Text, nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Indexes for test_cases
    op.create_index(
        "ix_test_cases_story_id",
        "test_cases",
        ["story_id"],
    )
    op.create_index(
        "ix_test_cases_organization_id",
        "test_cases",
        ["organization_id"],
    )
    op.create_index(
        "ix_test_cases_org_story",
        "test_cases",
        ["organization_id", "story_id"],
    )


def downgrade() -> None:
    # Drop indexes for test_cases
    op.drop_index("ix_test_cases_org_story", table_name="test_cases")
    op.drop_index("ix_test_cases_organization_id", table_name="test_cases")
    op.drop_index("ix_test_cases_story_id", table_name="test_cases")

    # Drop test_cases table
    op.drop_table("test_cases")

    # Drop indexes for user_stories
    op.drop_index("ix_user_stories_org_status", table_name="user_stories")
    op.drop_index("ix_user_stories_assignee_id", table_name="user_stories")
    op.drop_index("ix_user_stories_status", table_name="user_stories")
    op.drop_index("ix_user_stories_organization_id", table_name="user_stories")

    # Drop user_stories table
    op.drop_table("user_stories")
