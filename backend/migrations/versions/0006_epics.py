"""Add epics table and epic_id / parent_story_id to user_stories

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'epics',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('created_by_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_epics_organization_id', 'epics', ['organization_id'])

    op.add_column('user_stories', sa.Column('epic_id', sa.UUID(), sa.ForeignKey('epics.id'), nullable=True))
    op.add_column('user_stories', sa.Column('parent_story_id', sa.UUID(), sa.ForeignKey('user_stories.id'), nullable=True))
    op.add_column('user_stories', sa.Column('is_split', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('user_stories', 'is_split')
    op.drop_column('user_stories', 'parent_story_id')
    op.drop_column('user_stories', 'epic_id')
    op.drop_index('ix_epics_organization_id', 'epics')
    op.drop_table('epics')
