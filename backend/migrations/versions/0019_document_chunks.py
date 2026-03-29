"""Add document_chunks table with pgvector embedding column.

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=True),  # stored via pgvector type below
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
    )

    # Replace text column with actual vector(1536) type
    op.execute("ALTER TABLE document_chunks DROP COLUMN embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")

    # Indexes
    op.create_index(
        "ix_document_chunks_org_file",
        "document_chunks",
        ["org_id", "file_path"],
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding ON document_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists=100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.drop_index("ix_document_chunks_org_file", table_name="document_chunks")
    op.drop_table("document_chunks")
