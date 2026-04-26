"""Add external_source_id to document_chunks for callstack enforcement.

Revision ID: 0072_document_chunk_source_id
Revises: 0071_platform_components
Create Date: 2026-04-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add external_source_id FK to document_chunks so RAG can join on enabled sources
    op.add_column(
        "document_chunks",
        sa.Column(
            "external_source_id",
            UUID(as_uuid=True),
            sa.ForeignKey("external_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_document_chunks_external_source_id",
        "document_chunks",
        ["external_source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_external_source_id", table_name="document_chunks")
    op.drop_column("document_chunks", "external_source_id")
