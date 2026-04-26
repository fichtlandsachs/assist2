"""Platform components, feature flags, org licensing, soft-delete on user_stories

Revision ID: 0071
Revises: 0070
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Platform components ───────────────────────────────────────────────────
    op.create_table("platform_components",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(60), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="'active'"),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="50"),
        sa.Column("is_core", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── Feature flags ─────────────────────────────────────────────────────────
    op.create_table("platform_features",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("component_id", UUID(as_uuid=True),
            sa.ForeignKey("platform_components.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("default_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("override_policy", sa.String(30), nullable=False, server_default="'overridable'"),
        sa.Column("config_schema", JSONB, nullable=True),
        sa.Column("default_config", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_platform_features_component_id", "platform_features", ["component_id"])

    # ── Org components (licensing) ────────────────────────────────────────────
    op.create_table("org_components",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_id", UUID(as_uuid=True),
            sa.ForeignKey("platform_components.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'active'"),
        sa.Column("licensed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.UniqueConstraint("org_id", "component_id", name="uq_org_component"),
    )
    op.create_index("ix_org_components_org_id", "org_components", ["org_id"])

    # ── Org feature overrides ─────────────────────────────────────────────────
    op.create_table("org_feature_overrides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_id", UUID(as_uuid=True),
            sa.ForeignKey("platform_features.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=True),
        sa.Column("config_override", JSONB, nullable=True),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="'approved'"),
        sa.Column("changed_by_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("org_id", "feature_id", name="uq_org_feature_override"),
    )
    op.create_index("ix_org_feature_overrides_org_id", "org_feature_overrides", ["org_id"])

    # ── Soft-delete on user_stories ───────────────────────────────────────────
    op.add_column("user_stories",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("user_stories",
        sa.Column("deleted_by_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    )
    op.add_column("user_stories",
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false")
    )
    op.create_index("ix_user_stories_is_deleted", "user_stories", ["is_deleted"])
    # Partial index for fast active-story queries
    op.execute("""
        CREATE INDEX ix_user_stories_active
        ON user_stories (organization_id, updated_at DESC)
        WHERE is_deleted = false
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_stories_active")
    op.drop_index("ix_user_stories_is_deleted", "user_stories")
    op.drop_column("user_stories", "is_deleted")
    op.drop_column("user_stories", "deleted_by_id")
    op.drop_column("user_stories", "deleted_at")
    op.drop_table("org_feature_overrides")
    op.drop_table("org_components")
    op.drop_table("platform_features")
    op.drop_table("platform_components")
