"""Migrate story_versions from integer version_number to semver string

Revision ID: 0052
Revises: 0051
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new semver columns
    op.add_column("story_versions", sa.Column("version_string", sa.String(20), nullable=True))
    op.add_column("story_versions", sa.Column("prev_version_id", UUID(as_uuid=True), nullable=True))
    op.add_column("story_versions", sa.Column("next_version_id", UUID(as_uuid=True), nullable=True))
    op.add_column("story_versions", sa.Column("changed_by_id", UUID(as_uuid=True), nullable=True))
    op.add_column("story_versions", sa.Column("change_reason", sa.Text(), nullable=True))
    op.add_column("story_versions", sa.Column("change_description", sa.Text(), nullable=True))
    op.add_column("story_versions", sa.Column("change_type", sa.String(30), nullable=True))
    op.add_column("story_versions", sa.Column("major_minor_patch", sa.String(10), nullable=True))
    op.add_column("story_versions", sa.Column("review_required", sa.Boolean(), nullable=True))
    op.add_column("story_versions", sa.Column("approval_required", sa.Boolean(), nullable=True))
    op.add_column("story_versions", sa.Column("content_snapshot", sa.JSON(), nullable=True))
    op.add_column("story_versions", sa.Column("delta", sa.JSON(), nullable=True))

    # Populate version_string from version_number using Python loop (SQLite compat)
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, version_number FROM story_versions ORDER BY story_id, version_number")
    ).fetchall()
    for row in rows:
        vid = row[0]
        vnum = row[1]
        version_str = f"0.{vnum}.0"
        bind.execute(
            sa.text("UPDATE story_versions SET version_string = :vs, review_required = false, approval_required = false WHERE id = :vid"),
            {"vs": version_str, "vid": str(vid) if hasattr(vid, 'hex') else vid},
        )

    # Make version_string NOT NULL after population
    op.alter_column("story_versions", "version_string", nullable=False)

    # Drop legacy unique constraint and version_number column
    op.drop_constraint("uq_story_versions_story_ver", "story_versions", type_="unique")
    op.drop_column("story_versions", "version_number")

    # Add self-referential FKs for the linked list
    op.create_foreign_key(
        "fk_story_versions_prev", "story_versions", "story_versions",
        ["prev_version_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_story_versions_next", "story_versions", "story_versions",
        ["next_version_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_story_versions_next", "story_versions", type_="foreignkey")
    op.drop_constraint("fk_story_versions_prev", "story_versions", type_="foreignkey")
    op.add_column("story_versions", sa.Column("version_number", sa.Integer(), nullable=True))
    op.drop_column("story_versions", "version_string")
    op.drop_column("story_versions", "prev_version_id")
    op.drop_column("story_versions", "next_version_id")
    op.drop_column("story_versions", "changed_by_id")
    op.drop_column("story_versions", "change_reason")
    op.drop_column("story_versions", "change_description")
    op.drop_column("story_versions", "change_type")
    op.drop_column("story_versions", "major_minor_patch")
    op.drop_column("story_versions", "review_required")
    op.drop_column("story_versions", "approval_required")
    op.drop_column("story_versions", "content_snapshot")
    op.drop_column("story_versions", "delta")
