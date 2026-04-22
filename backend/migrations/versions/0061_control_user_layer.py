"""add user layer fields to controls

Revision ID: 0061
Revises: 0060
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("controls", sa.Column("user_title", sa.String(500), nullable=True))
    op.add_column("controls", sa.Column("user_explanation", sa.Text(), nullable=True))
    op.add_column("controls", sa.Column("user_action", sa.Text(), nullable=True))
    op.add_column(
        "controls",
        sa.Column(
            "user_guiding_questions",
            JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "controls",
        sa.Column(
            "user_evidence_needed",
            JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("controls", "user_evidence_needed")
    op.drop_column("controls", "user_guiding_questions")
    op.drop_column("controls", "user_action")
    op.drop_column("controls", "user_explanation")
    op.drop_column("controls", "user_title")
