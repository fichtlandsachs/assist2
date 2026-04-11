# backend/migrations/versions/0041_review_tables.py
"""Add review_tasks and review_decisions tables

Revision ID: 0041
Revises: 0040
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0041'
down_revision = '0040'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'review_tasks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('evaluation_run_id', UUID(as_uuid=True),
                  sa.ForeignKey('evaluation_runs.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('story_version_id', UUID(as_uuid=True),
                  sa.ForeignKey('story_versions.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('review_type', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('assigned_to', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('requested_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('priority', sa.String(10), nullable=False, server_default='normal'),
        sa.Column('context_snapshot', JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('timeout_action', sa.String(20), nullable=False, server_default='escalate'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_review_tasks_run', 'review_tasks', ['evaluation_run_id'])
    op.create_index('idx_review_tasks_assigned', 'review_tasks', ['assigned_to', 'status'],
                    postgresql_where=sa.text(
                        "assigned_to IS NOT NULL AND status IN ('pending','in_review')"))
    op.create_index('idx_review_tasks_due', 'review_tasks', ['due_at'],
                    postgresql_where=sa.text("status IN ('pending','in_review')"))

    op.create_table(
        'review_decisions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('review_task_id', UUID(as_uuid=True),
                  sa.ForeignKey('review_tasks.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('reviewer_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('decision', sa.String(30), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('score_override', sa.Numeric(5, 4), nullable=True),
        sa.Column('decision_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('resume_trigger_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('metadata_', JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index('idx_review_decisions_task', 'review_decisions', ['review_task_id'])


def downgrade() -> None:
    op.drop_index('idx_review_decisions_task', 'review_decisions')
    op.drop_table('review_decisions')
    op.drop_index('idx_review_tasks_due', 'review_tasks')
    op.drop_index('idx_review_tasks_assigned', 'review_tasks')
    op.drop_index('idx_review_tasks_run', 'review_tasks')
    op.drop_table('review_tasks')
