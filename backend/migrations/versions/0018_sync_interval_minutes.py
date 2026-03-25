"""Add sync_interval_minutes to mail and calendar connections.

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mail_connections",
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="15"),
    )
    op.add_column(
        "calendar_connections",
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="30"),
    )


def downgrade() -> None:
    op.drop_column("mail_connections", "sync_interval_minutes")
    op.drop_column("calendar_connections", "sync_interval_minutes")
