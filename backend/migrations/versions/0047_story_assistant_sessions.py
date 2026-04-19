"""story assistant sessions (dod + features)

Revision ID: 0047
Revises: 0046
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_assistant_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_type", sa.String(30), nullable=False),
        sa.Column("messages", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("last_proposal", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id"], ["user_stories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "session_type", name="uq_assistant_session_story_type"),
    )
    op.create_index("ix_story_assistant_sessions_story_id", "story_assistant_sessions", ["story_id"])
    op.create_index("ix_story_assistant_sessions_org_id", "story_assistant_sessions", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_story_assistant_sessions_org_id", table_name="story_assistant_sessions")
    op.drop_index("ix_story_assistant_sessions_story_id", table_name="story_assistant_sessions")
    op.drop_table("story_assistant_sessions")
