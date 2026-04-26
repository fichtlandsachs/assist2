"""Add current_version_id FK constraints to epics, features, test_cases, tasks, risks, adrs

Revision ID: 0054
Revises: 0053
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add current_version_id + FK to epics, features, test_cases
    # (tasks/risks/adrs already have the column from migration 0050;
    #  user_stories already has it from migration 0037)
    for table, version_table in [
        ("epics", "epic_versions"),
        ("features", "feature_versions"),
        ("test_cases", "test_case_versions"),
    ]:
        op.add_column(table, sa.Column("current_version_id", UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_current_version",
            table, version_table,
            ["current_version_id"], ["id"],
            ondelete="SET NULL",
            use_alter=True,
        )

    # Add only the FK (column already exists) for tasks, risks, adrs
    for table, version_table in [
        ("tasks", "task_versions"),
        ("risks", "risk_versions"),
        ("adrs", "adr_versions"),
    ]:
        op.create_foreign_key(
            f"fk_{table}_current_version",
            table, version_table,
            ["current_version_id"], ["id"],
            ondelete="SET NULL",
            use_alter=True,
        )


def downgrade() -> None:
    for table in ["adrs", "risks", "tasks", "test_cases", "features", "epics"]:
        op.drop_constraint(f"fk_{table}_current_version", table, type_="foreignkey")
    # Remove the column only from tables where we added it in this migration
    for table in ["test_cases", "features", "epics"]:
        op.drop_column(table, "current_version_id")
