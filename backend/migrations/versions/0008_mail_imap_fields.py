"""Add IMAP host/port/password fields to mail_connections

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mail_connections', sa.Column('imap_host', sa.String(500), nullable=True))
    op.add_column('mail_connections', sa.Column('imap_port', sa.Integer(), nullable=True))
    op.add_column('mail_connections', sa.Column('imap_password_enc', sa.Text(), nullable=True))
    op.add_column('mail_connections', sa.Column('imap_use_ssl', sa.Boolean(), nullable=True, server_default='true'))


def downgrade() -> None:
    op.drop_column('mail_connections', 'imap_use_ssl')
    op.drop_column('mail_connections', 'imap_password_enc')
    op.drop_column('mail_connections', 'imap_port')
    op.drop_column('mail_connections', 'imap_host')
