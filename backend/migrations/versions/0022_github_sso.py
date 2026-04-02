"""add github sso columns

Revision ID: 0022
Revises: 0021
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'github_id', sa.BigInteger, nullable=True
    ))
    op.add_column('users', sa.Column(
        'github_username', sa.String(255), nullable=True
    ))
    op.add_column('users', sa.Column(
        'github_email', sa.String(255), nullable=True
    ))
    op.create_index(
        'ix_users_github_id',
        'users',
        ['github_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_users_github_id', table_name='users')
    op.drop_column('users', 'github_email')
    op.drop_column('users', 'github_username')
    op.drop_column('users', 'github_id')
