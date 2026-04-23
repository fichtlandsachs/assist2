"""external source ingest tables + is_global on document_chunks

Revision ID: 0062
Revises: 0061
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add is_global to document_chunks
    op.add_column(
        "document_chunks",
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_document_chunks_is_global", "document_chunks", ["is_global"])

    # 2. external_sources
    op.create_table(
        "external_sources",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_key", sa.String(200), nullable=False, unique=True),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="external_docs"),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("config_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("visibility_scope", sa.String(20), nullable=False, server_default="global"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_external_sources_source_key", "external_sources", ["source_key"])
    op.create_index("ix_external_sources_enabled", "external_sources", ["is_enabled"])

    # 3. external_source_runs
    op.create_table(
        "external_source_runs",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", PGUUID(as_uuid=True), sa.ForeignKey("external_sources.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("run_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_external_source_runs_status", "external_source_runs", ["status"])

    # 4. external_source_pages
    op.create_table(
        "external_source_pages",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", PGUUID(as_uuid=True), sa.ForeignKey("external_sources.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("raw_url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("http_status", sa.SmallInteger(), nullable=True),
        sa.Column("fetch_method", sa.String(20), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("etag", sa.String(256), nullable=True),
        sa.Column("last_modified", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_esp_source_canonical",
        "external_source_pages",
        ["source_id", "canonical_url"],
        unique=True,
    )
    op.create_index("ix_esp_status", "external_source_pages", ["status"])
    op.create_index("ix_esp_content_hash", "external_source_pages", ["content_hash"])


def downgrade() -> None:
    op.drop_table("external_source_pages")
    op.drop_table("external_source_runs")
    op.drop_table("external_sources")
    op.drop_index("ix_document_chunks_is_global", table_name="document_chunks")
    op.drop_column("document_chunks", "is_global")
