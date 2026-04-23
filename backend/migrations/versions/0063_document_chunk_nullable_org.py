"""allow null org_id on document_chunks for global shared content

Revision ID: 0063
Revises: 0062
Create Date: 2026-04-23
"""
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("document_chunks", "org_id", nullable=True)


def downgrade() -> None:
    op.alter_column("document_chunks", "org_id", nullable=False)
