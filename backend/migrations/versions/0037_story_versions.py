# backend/migrations/versions/0037_story_versions.py
"""Add story_versions table and current_version_id to user_stories

Revision ID: 0037
Revises: 0036
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'story_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('story_id', UUID(as_uuid=True),
                  sa.ForeignKey('user_stories.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('org_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('as_a', sa.Text(), nullable=True),
        sa.Column('i_want', sa.Text(), nullable=True),
        sa.Column('so_that', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('acceptance_criteria', JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column('priority', sa.String(20), nullable=True),
        sa.Column('story_points', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='draft'),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('external_ref', sa.Text(), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('story_id', 'version_number', name='uq_story_versions_story_ver'),
    )
    op.create_index('idx_story_versions_story', 'story_versions', ['story_id'])
    op.create_index('idx_story_versions_hash', 'story_versions', ['story_id', 'content_hash'])
    op.create_index(
        'idx_story_versions_pending',
        'story_versions', ['status'],
        postgresql_where=sa.text("status IN ('pending_evaluation','evaluating')")
    )

    # Add current_version_id to user_stories (deferred FK to avoid circular dependency)
    op.add_column(
        'user_stories',
        sa.Column('current_version_id', UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_stories_current_version',
        'user_stories', 'story_versions',
        ['current_version_id'], ['id'],
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint('fk_stories_current_version', 'user_stories', type_='foreignkey')
    op.drop_column('user_stories', 'current_version_id')
    op.drop_index('idx_story_versions_pending', 'story_versions')
    op.drop_index('idx_story_versions_hash', 'story_versions')
    op.drop_index('idx_story_versions_story', 'story_versions')
    op.drop_table('story_versions')
