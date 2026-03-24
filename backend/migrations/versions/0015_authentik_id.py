"""Add authentik_id to users table.

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('authentik_id', sa.String(255), nullable=True, unique=True)
    )
    op.create_index('ix_users_authentik_id', 'users', ['authentik_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_authentik_id', table_name='users')
    op.drop_column('users', 'authentik_id')
