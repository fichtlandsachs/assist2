"""Initial schema with all core tables and seed data

Revision ID: 0001
Revises:
Create Date: 2026-03-17 00:00:00.000000

"""
from typing import Sequence, Union
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # USERS TABLE
    # =========================================================================
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(2048), nullable=True),
        sa.Column("locale", sa.String(10), nullable=False, server_default="de"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Berlin"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # =========================================================================
    # IDENTITY LINKS TABLE
    # =========================================================================
    op.create_table(
        "identity_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(255), nullable=True),
        sa.Column("access_token", sa.String(2048), nullable=True),
        sa.Column("refresh_token", sa.String(2048), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_identity_links_user_id", "identity_links", ["user_id"])
    op.create_unique_constraint("uq_identity_links_user_provider", "identity_links", ["user_id", "provider"])
    op.create_unique_constraint("uq_identity_links_provider_user", "identity_links", ["provider", "provider_user_id"])

    # =========================================================================
    # USER SESSIONS TABLE
    # =========================================================================
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_refresh_token_hash", "user_sessions", ["refresh_token_hash"])

    # =========================================================================
    # ORGANIZATIONS TABLE
    # =========================================================================
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column("logo_url", sa.String(2048), nullable=True),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("max_members", sa.Integer, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # =========================================================================
    # ROLES TABLE
    # =========================================================================
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_roles_organization_id", "roles", ["organization_id"])

    # =========================================================================
    # PERMISSIONS TABLE
    # =========================================================================
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
    )
    op.create_unique_constraint("uq_permissions_resource_action", "permissions", ["resource", "action"])

    # =========================================================================
    # ROLE PERMISSIONS TABLE
    # =========================================================================
    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_unique_constraint("uq_role_permissions_role_perm", "role_permissions", ["role_id", "permission_id"])

    # =========================================================================
    # MEMBERSHIPS TABLE
    # =========================================================================
    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])
    op.create_unique_constraint("uq_memberships_user_org", "memberships", ["user_id", "organization_id"])

    # =========================================================================
    # MEMBERSHIP ROLES TABLE
    # =========================================================================
    op.create_table(
        "membership_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_membership_roles_membership_id", "membership_roles", ["membership_id"])

    # =========================================================================
    # AGENTS TABLE
    # =========================================================================
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False, server_default="claude-sonnet-4-6"),
        sa.Column("system_prompt_ref", sa.String(512), nullable=True),
        sa.Column("config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agents_organization_id", "agents", ["organization_id"])

    # =========================================================================
    # GROUPS TABLE
    # =========================================================================
    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("parent_group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_groups_organization_id", "groups", ["organization_id"])

    # =========================================================================
    # GROUP MEMBERS TABLE
    # =========================================================================
    op.create_table(
        "group_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("member_type", sa.String(20), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_group_members_group_id", "group_members", ["group_id"])

    # =========================================================================
    # PLUGINS TABLE
    # =========================================================================
    op.create_table(
        "plugins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("manifest", sa.JSON, nullable=False),
        sa.Column("entry_point", sa.String(512), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("requires_config", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_plugins_slug", "plugins", ["slug"], unique=True)

    # =========================================================================
    # ORG PLUGIN ACTIVATIONS TABLE
    # =========================================================================
    op.create_table(
        "org_plugin_activations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plugin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("config", sa.JSON, nullable=True),
        sa.Column("activated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_org_plugin_activations_organization_id", "org_plugin_activations", ["organization_id"])
    op.create_unique_constraint("uq_org_plugin_activations_org_plugin", "org_plugin_activations", ["organization_id", "plugin_id"])

    # =========================================================================
    # WORKFLOW DEFINITIONS TABLE
    # =========================================================================
    op.create_table(
        "workflow_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("n8n_workflow_id", sa.String(255), nullable=False),
        sa.Column("definition", sa.JSON, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_definitions_organization_id", "workflow_definitions", ["organization_id"])
    op.create_unique_constraint("uq_workflow_definitions_org_slug", "workflow_definitions", ["organization_id", "slug"])

    # =========================================================================
    # WORKFLOW EXECUTIONS TABLE
    # =========================================================================
    op.create_table(
        "workflow_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("definition_version", sa.Integer, nullable=False),
        sa.Column("n8n_execution_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("input_snapshot", sa.JSON, nullable=True),
        sa.Column("context_snapshot", sa.JSON, nullable=True),
        sa.Column("result_snapshot", sa.JSON, nullable=True),
        sa.Column("error_message", sa.String(2048), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workflow_executions_organization_id", "workflow_executions", ["organization_id"])
    op.create_index("ix_workflow_executions_definition_id", "workflow_executions", ["definition_id"])

    # =========================================================================
    # SEED DATA: SYSTEM PERMISSIONS
    # =========================================================================
    permissions_table = sa.table(
        "permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("resource", sa.String),
        sa.column("action", sa.String),
        sa.column("description", sa.String),
    )

    system_permissions = [
        # org
        ("org", "read", "Read organization details"),
        ("org", "update", "Update organization details"),
        ("org", "delete", "Delete organization"),
        # membership
        ("membership", "read", "Read membership list"),
        ("membership", "invite", "Invite members"),
        ("membership", "update", "Update membership"),
        ("membership", "delete", "Remove members"),
        # role
        ("role", "read", "Read roles"),
        ("role", "create", "Create roles"),
        ("role", "update", "Update roles"),
        ("role", "delete", "Delete roles"),
        ("role", "assign", "Assign roles to members"),
        # group
        ("group", "read", "Read groups"),
        ("group", "create", "Create groups"),
        ("group", "update", "Update groups"),
        ("group", "delete", "Delete groups"),
        ("group", "manage", "Manage group members"),
        # plugin
        ("plugin", "read", "Read plugins"),
        ("plugin", "activate", "Activate plugins"),
        ("plugin", "configure", "Configure plugins"),
        ("plugin", "deactivate", "Deactivate plugins"),
        # workflow
        ("workflow", "read", "Read workflows"),
        ("workflow", "create", "Create workflows"),
        ("workflow", "update", "Update workflows"),
        ("workflow", "delete", "Delete workflows"),
        ("workflow", "execute", "Execute workflows"),
        # agent
        ("agent", "read", "Read agents"),
        ("agent", "create", "Create agents"),
        ("agent", "update", "Update agents"),
        ("agent", "delete", "Delete agents"),
        ("agent", "invoke", "Invoke agents"),
        # story
        ("story", "read", "Read stories"),
        ("story", "create", "Create stories"),
        ("story", "update", "Update stories"),
        ("story", "delete", "Delete stories"),
        # inbox
        ("inbox", "read", "Read inbox"),
        ("inbox", "manage", "Manage inbox"),
        ("inbox", "update", "Update inbox items"),
        # calendar
        ("calendar", "read", "Read calendar"),
        ("calendar", "manage", "Manage calendar"),
        ("calendar", "create", "Create calendar events"),
    ]

    permission_ids = {}
    perm_rows = []
    for resource, action, description in system_permissions:
        perm_id = uuid.uuid4()
        permission_ids[f"{resource}:{action}"] = perm_id
        perm_rows.append({
            "id": perm_id,
            "resource": resource,
            "action": action,
            "description": description,
        })

    op.bulk_insert(permissions_table, perm_rows)

    # =========================================================================
    # SEED DATA: SYSTEM ROLES
    # =========================================================================
    roles_table = sa.table(
        "roles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("organization_id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_system", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    now = datetime.now(timezone.utc)

    role_ids = {
        "org_owner": uuid.uuid4(),
        "org_admin": uuid.uuid4(),
        "org_member": uuid.uuid4(),
        "org_guest": uuid.uuid4(),
    }

    op.bulk_insert(roles_table, [
        {
            "id": role_ids["org_owner"],
            "organization_id": None,
            "name": "org_owner",
            "description": "Organization Owner - full access to all resources",
            "is_system": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": role_ids["org_admin"],
            "organization_id": None,
            "name": "org_admin",
            "description": "Organization Admin - all access except delete organization",
            "is_system": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": role_ids["org_member"],
            "organization_id": None,
            "name": "org_member",
            "description": "Organization Member - read access to most resources",
            "is_system": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": role_ids["org_guest"],
            "organization_id": None,
            "name": "org_guest",
            "description": "Organization Guest - minimal read access",
            "is_system": True,
            "created_at": now,
            "updated_at": now,
        },
    ])

    # =========================================================================
    # SEED DATA: ROLE PERMISSIONS
    # =========================================================================
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("role_id", postgresql.UUID(as_uuid=True)),
        sa.column("permission_id", postgresql.UUID(as_uuid=True)),
    )

    all_permissions = list(permission_ids.keys())

    # org_admin: all except org:delete
    admin_permissions = [p for p in all_permissions if p != "org:delete"]

    # org_member: read permissions + story:create + inbox:update + calendar:create
    member_permissions = [
        "org:read",
        "membership:read",
        "group:read",
        "plugin:read",
        "workflow:read",
        "agent:read",
        "story:read",
        "story:create",
        "story:update",
        "inbox:read",
        "inbox:update",
        "calendar:read",
        "calendar:create",
    ]

    # org_guest: minimal read
    guest_permissions = [
        "org:read",
        "membership:read",
    ]

    role_perm_rows = []

    # org_owner: ALL permissions
    for perm_key in all_permissions:
        role_perm_rows.append({
            "id": uuid.uuid4(),
            "role_id": role_ids["org_owner"],
            "permission_id": permission_ids[perm_key],
        })

    # org_admin: all except org:delete
    for perm_key in admin_permissions:
        role_perm_rows.append({
            "id": uuid.uuid4(),
            "role_id": role_ids["org_admin"],
            "permission_id": permission_ids[perm_key],
        })

    # org_member
    for perm_key in member_permissions:
        role_perm_rows.append({
            "id": uuid.uuid4(),
            "role_id": role_ids["org_member"],
            "permission_id": permission_ids[perm_key],
        })

    # org_guest
    for perm_key in guest_permissions:
        role_perm_rows.append({
            "id": uuid.uuid4(),
            "role_id": role_ids["org_guest"],
            "permission_id": permission_ids[perm_key],
        })

    op.bulk_insert(role_permissions_table, role_perm_rows)


def downgrade() -> None:
    op.drop_table("workflow_executions")
    op.drop_table("workflow_definitions")
    op.drop_table("org_plugin_activations")
    op.drop_table("plugins")
    op.drop_table("group_members")
    op.drop_table("groups")
    op.drop_table("agents")
    op.drop_table("membership_roles")
    op.drop_table("memberships")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("organizations")
    op.drop_table("user_sessions")
    op.drop_table("identity_links")
    op.drop_table("users")
