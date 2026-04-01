"""add atlassian sso columns

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'atlassian_account_id', sa.String(64), nullable=True
    ))
    op.add_column('users', sa.Column(
        'atlassian_email', sa.String(255), nullable=True
    ))
    op.create_index(
        'ix_users_atlassian_account_id',
        'users',
        ['atlassian_account_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_users_atlassian_account_id', table_name='users')
    op.drop_column('users', 'atlassian_email')
    op.drop_column('users', 'atlassian_account_id')
