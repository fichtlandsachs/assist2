# backend/migrations/versions/0038_rule_sets.py
"""Add rule_sets and rule_definitions tables

Revision ID: 0038
Revises: 0037
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0038'
down_revision = '0037'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'rule_sets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('org_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('frozen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('org_id', 'name', 'version', name='uq_rule_sets_org_name_ver'),
    )
    op.create_index('idx_rule_sets_org_status', 'rule_sets', ['org_id', 'status'])

    op.create_table(
        'rule_definitions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('rule_set_id', UUID(as_uuid=True),
                  sa.ForeignKey('rule_sets.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_type', sa.String(30), nullable=False),
        sa.Column('dimension', sa.String(50), nullable=False),
        sa.Column('weight', sa.Numeric(5, 4), nullable=False, server_default='1.0'),
        sa.Column('parameters', JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('prompt_template', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('rule_set_id', 'name', name='uq_rule_defs_ruleset_name'),
    )
    op.create_index('idx_rule_defs_active', 'rule_definitions', ['rule_set_id'],
                    postgresql_where=sa.text('is_active = true'))


def downgrade() -> None:
    op.drop_index('idx_rule_defs_active', 'rule_definitions')
    op.drop_table('rule_definitions')
    op.drop_index('idx_rule_sets_org_status', 'rule_sets')
    op.drop_table('rule_sets')
