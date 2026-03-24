"""Drop user_sessions and identity_links tables.

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-24

IMPORTANT: Run migrate_to_authentik.py BEFORE applying this migration.
"""
from alembic import op

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('user_sessions')
    op.drop_table('identity_links')


def downgrade() -> None:
    # Intentionally not restoring — this migration is irreversible.
    # Restore from backup if needed.
    raise NotImplementedError("Migration 0016 is irreversible. Restore from backup.")
