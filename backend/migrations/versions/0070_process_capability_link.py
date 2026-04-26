"""Add capability_node_id to processes; add process_request table

Revision ID: 0070
Revises: 0069
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Link processes to a capability node
    op.add_column("processes",
        sa.Column("capability_node_id", UUID(as_uuid=True),
            sa.ForeignKey("capability_nodes.id", ondelete="SET NULL"),
            nullable=True)
    )
    op.create_index("ix_processes_capability_node_id", "processes", ["capability_node_id"])

    # New-process requests that automatically create an epic + story stub
    op.create_table("process_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("requested_by_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("capability_node_id", UUID(as_uuid=True),
            sa.ForeignKey("capability_nodes.id", ondelete="SET NULL"), nullable=True),
        # The name the user suggested for the new process
        sa.Column("proposed_name", sa.String(500), nullable=False),
        # Auto-created artifacts
        sa.Column("epic_id", UUID(as_uuid=True),
            sa.ForeignKey("epics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("story_id", UUID(as_uuid=True),
            sa.ForeignKey("user_stories.id", ondelete="SET NULL"), nullable=True),
        # Status: pending_description → approved → rejected
        sa.Column("status", sa.String(30), nullable=False, server_default="'pending_description'"),
        sa.Column("chat_session_id", sa.String(200), nullable=True),  # assistant session reference
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("process_requests")
    op.drop_index("ix_processes_capability_node_id", "processes")
    op.drop_column("processes", "capability_node_id")
