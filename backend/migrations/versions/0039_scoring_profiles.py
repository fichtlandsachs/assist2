# backend/migrations/versions/0039_scoring_profiles.py
"""Add scoring_profiles table

Revision ID: 0039
Revises: 0038
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0039'
down_revision = '0038'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'scoring_profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('rule_set_id', UUID(as_uuid=True),
                  sa.ForeignKey('rule_sets.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('dimension_weights', JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('pass_threshold', sa.Numeric(5, 4), nullable=False,
                  server_default='0.70'),
        sa.Column('warn_threshold', sa.Numeric(5, 4), nullable=False,
                  server_default='0.50'),
        sa.Column('auto_approve_threshold', sa.Numeric(5, 4), nullable=False,
                  server_default='0.90'),
        sa.Column('require_review_below', sa.Numeric(5, 4), nullable=False,
                  server_default='0.60'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('org_id', 'rule_set_id', 'name', 'version',
                            name='uq_scoring_profiles_unique'),
    )
    op.create_index('idx_scoring_profiles_ruleset', 'scoring_profiles', ['rule_set_id'])


def downgrade() -> None:
    op.drop_index('idx_scoring_profiles_ruleset', 'scoring_profiles')
    op.drop_table('scoring_profiles')
