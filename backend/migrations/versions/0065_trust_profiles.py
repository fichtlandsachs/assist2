"""Add trust_profiles table and chunk_meta_json column + eligibility defaults

Revision ID: 0065
Revises: 0064
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── trust_profiles table ─────────────────────────────────────────────────
    op.create_table(
        "trust_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "source_id", UUID(as_uuid=True),
            sa.ForeignKey("external_sources.id", ondelete="CASCADE"),
            nullable=False, unique=True
        ),
        sa.Column("trust_class", sa.String(4), nullable=False, server_default="V3"),
        sa.Column("source_category", sa.String(30), nullable=False, server_default="internal_approved"),
        sa.Column("authority_score",    sa.Float, nullable=False, server_default="0.5"),
        sa.Column("standard_score",     sa.Float, nullable=False, server_default="0.5"),
        sa.Column("context_score",      sa.Float, nullable=False, server_default="0.5"),
        sa.Column("freshness_score",    sa.Float, nullable=False, server_default="0.5"),
        sa.Column("governance_score",   sa.Float, nullable=False, server_default="0.5"),
        sa.Column("traceability_score", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("composite_score",    sa.Float, nullable=False, server_default="0.5"),
        sa.Column(
            "eligibility", JSONB, nullable=False,
            server_default='{"security": true, "compliance": true, "general": true, "architecture": true}'
        ),
        sa.Column("admin_note", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),

        # Check constraints for dimension scores
        sa.CheckConstraint("authority_score >= 0.0 AND authority_score <= 1.0", name="ck_trust_authority"),
        sa.CheckConstraint("standard_score >= 0.0 AND standard_score <= 1.0", name="ck_trust_standard"),
        sa.CheckConstraint("context_score >= 0.0 AND context_score <= 1.0", name="ck_trust_context"),
        sa.CheckConstraint("freshness_score >= 0.0 AND freshness_score <= 1.0", name="ck_trust_freshness"),
        sa.CheckConstraint("governance_score >= 0.0 AND governance_score <= 1.0", name="ck_trust_governance"),
        sa.CheckConstraint("traceability_score >= 0.0 AND traceability_score <= 1.0", name="ck_trust_traceability"),
    )

    # Index for lookups by source_id
    op.create_index("ix_trust_profiles_source_id", "trust_profiles", ["source_id"])

    # ── chunk_meta_json column on document_chunks ────────────────────────────
    # Adds trust_class, source_category, trust_score into chunk metadata for
    # retrieval-time eligibility checks without joining trust_profiles.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_chunks'
                AND column_name = 'chunk_meta_json'
            ) THEN
                ALTER TABLE document_chunks
                ADD COLUMN chunk_meta_json JSONB NOT NULL DEFAULT '{}'::jsonb;
            END IF;
        END$$;
    """)


def downgrade() -> None:
    op.drop_table("trust_profiles")
    op.execute("""
        ALTER TABLE document_chunks DROP COLUMN IF EXISTS chunk_meta_json;
    """)
