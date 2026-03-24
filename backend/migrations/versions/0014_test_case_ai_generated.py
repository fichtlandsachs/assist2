"""Add is_ai_generated to test_cases

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_cases",
        sa.Column("is_ai_generated", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("test_cases", "is_ai_generated")
