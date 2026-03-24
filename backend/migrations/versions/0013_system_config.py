"""Add system_configs and config_history tables

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("config_type", sa.String(100), nullable=False),
        sa.Column("config_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "config_type", name="uq_system_config_org_type"),
    )
    op.create_index("ix_system_configs_org_id", "system_configs", ["organization_id"])
    op.create_index("ix_system_configs_config_type", "system_configs", ["config_type"])

    op.create_table(
        "config_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("config_id", sa.UUID(), nullable=False),
        sa.Column("changed_by_id", sa.UUID(), nullable=True),
        sa.Column("previous_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["config_id"], ["system_configs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_config_history_config_id", "config_history", ["config_id"])


def downgrade() -> None:
    op.drop_index("ix_config_history_config_id", table_name="config_history")
    op.drop_table("config_history")
    op.drop_index("ix_system_configs_config_type", table_name="system_configs")
    op.drop_index("ix_system_configs_org_id", table_name="system_configs")
    op.drop_table("system_configs")
