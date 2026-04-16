"""Add story_refinement_sessions table

Revision ID: 0046
Revises: 0045
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_refinement_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stage", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("messages", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("last_proposal", postgresql.JSONB(), nullable=True),
        sa.Column("quality_score", sa.SmallInteger(), nullable=True),
        sa.Column("readiness_state", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["story_id"], ["user_stories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", name="uq_refinement_session_story"),
    )
    op.create_index("ix_refinement_sessions_story_id", "story_refinement_sessions", ["story_id"])
    op.create_index("ix_refinement_sessions_org_id", "story_refinement_sessions", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_refinement_sessions_org_id", table_name="story_refinement_sessions")
    op.drop_index("ix_refinement_sessions_story_id", table_name="story_refinement_sessions")
    op.drop_table("story_refinement_sessions")
