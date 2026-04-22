"""capability map: nodes, assignments, org init fields, project extended fields

Revision ID: 0059
Revises: 0058
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── capability_nodes ────────────────────────────────────────────────────
    op.create_table(
        "capability_nodes",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.UUID(as_uuid=True), sa.ForeignKey("capability_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("node_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("external_import_key", sa.String(255), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_capability_nodes_org_id", "capability_nodes", ["org_id"])
    op.create_index("ix_capability_nodes_parent_id", "capability_nodes", ["parent_id"])

    # ── artifact_assignments ─────────────────────────────────────────────────
    op.create_table(
        "artifact_assignments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", sa.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_type", sa.String(20), nullable=False),
        sa.Column("artifact_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.UUID(as_uuid=True), sa.ForeignKey("capability_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(20), nullable=False, server_default="primary"),
        sa.Column("assignment_is_exception", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("assignment_exception_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_artifact_assignments_org_id", "artifact_assignments", ["org_id"])
    op.create_index("ix_artifact_assignments_artifact_id", "artifact_assignments", ["artifact_id"])
    op.create_index("ix_artifact_assignments_node_id", "artifact_assignments", ["node_id"])

    # ── organizations: init fields ───────────────────────────────────────────
    op.add_column("organizations", sa.Column("initialization_status", sa.String(50), nullable=False, server_default="not_initialized"))
    op.add_column("organizations", sa.Column("initialization_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organizations", sa.Column("capability_map_version", sa.Integer, nullable=False, server_default="0"))
    op.add_column("organizations", sa.Column("initial_setup_completed_by_id", sa.UUID(as_uuid=True), nullable=True))
    op.add_column("organizations", sa.Column("initial_setup_source", sa.String(50), nullable=True))
    op.create_foreign_key(
        "fk_organizations_setup_by",
        "organizations", "users",
        ["initial_setup_completed_by_id"], ["id"],
        ondelete="SET NULL",
    )

    # ── projects: extended fields ────────────────────────────────────────────
    op.add_column("projects", sa.Column("project_brief", sa.Text, nullable=True))
    op.add_column("projects", sa.Column("planned_start_date", sa.Date, nullable=True))
    op.add_column("projects", sa.Column("planned_end_date", sa.Date, nullable=True))
    op.add_column("projects", sa.Column("actual_start_date", sa.Date, nullable=True))
    op.add_column("projects", sa.Column("actual_end_date", sa.Date, nullable=True))
    op.add_column("projects", sa.Column("jira_project_id", sa.String(255), nullable=True))
    op.add_column("projects", sa.Column("jira_project_key", sa.String(50), nullable=True))
    op.add_column("projects", sa.Column("jira_project_name", sa.String(500), nullable=True))
    op.add_column("projects", sa.Column("jira_project_url", sa.String(2048), nullable=True))
    op.add_column("projects", sa.Column("jira_project_type", sa.String(100), nullable=True))
    op.add_column("projects", sa.Column("jira_project_lead", sa.String(255), nullable=True))
    op.add_column("projects", sa.Column("jira_board_id", sa.String(255), nullable=True))
    op.add_column("projects", sa.Column("jira_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("jira_source_metadata", sa.JSON, nullable=True))


def downgrade() -> None:
    # projects
    for col in ["jira_source_metadata", "jira_synced_at", "jira_board_id", "jira_project_lead",
                "jira_project_type", "jira_project_url", "jira_project_name", "jira_project_key",
                "jira_project_id", "actual_end_date", "actual_start_date", "planned_end_date",
                "planned_start_date", "project_brief"]:
        op.drop_column("projects", col)
    # organizations
    op.drop_constraint("fk_organizations_setup_by", "organizations", type_="foreignkey")
    for col in ["initial_setup_source", "initial_setup_completed_by_id",
                "capability_map_version", "initialization_completed_at", "initialization_status"]:
        op.drop_column("organizations", col)
    # artifact_assignments
    op.drop_index("ix_artifact_assignments_node_id", table_name="artifact_assignments")
    op.drop_index("ix_artifact_assignments_artifact_id", table_name="artifact_assignments")
    op.drop_index("ix_artifact_assignments_org_id", table_name="artifact_assignments")
    op.drop_table("artifact_assignments")
    # capability_nodes
    op.drop_index("ix_capability_nodes_parent_id", table_name="capability_nodes")
    op.drop_index("ix_capability_nodes_org_id", table_name="capability_nodes")
    op.drop_table("capability_nodes")
