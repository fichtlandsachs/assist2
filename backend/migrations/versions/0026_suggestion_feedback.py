"""add suggestion_feedback table

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'suggestion_feedback',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('suggestion_type', sa.String(32), nullable=False),
        sa.Column('suggestion_text', sa.String(1000), nullable=False),
        sa.Column('feedback', sa.String(32), nullable=False, server_default='rejected'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_suggestion_feedback_org_type', 'suggestion_feedback', ['organization_id', 'suggestion_type'])


def downgrade() -> None:
    op.drop_index('ix_suggestion_feedback_org_type')
    op.drop_table('suggestion_feedback')
