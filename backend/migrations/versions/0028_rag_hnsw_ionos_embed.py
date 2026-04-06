"""RAG: migrate embedding vector(1536)→vector(1024), IVFFlat→HNSW

Revision ID: 0028
Revises: 0027
Create Date: 2026-04-06
"""
from alembic import op

revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop all IVFFlat indexes on document_chunks
    op.execute("""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'document_chunks'
                  AND (indexdef ILIKE '%ivfflat%' OR indexdef ILIKE '%vector%')
            LOOP
                EXECUTE 'DROP INDEX IF EXISTS ' || quote_ident(r.indexname);
            END LOOP;
        END $$;
    """)

    # Clear embeddings — dimension change requires full re-index
    op.execute("UPDATE document_chunks SET embedding = NULL")

    # Migrate column type: vector(1536) → vector(1024)
    op.execute(
        "ALTER TABLE document_chunks "
        "ALTER COLUMN embedding TYPE vector(1024) USING NULL::vector(1024)"
    )

    # Create HNSW index (no rebuild needed on insert, unlike IVFFlat)
    op.execute("""
        CREATE INDEX ix_document_chunks_embedding_hnsw
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.execute("UPDATE document_chunks SET embedding = NULL")
    op.execute(
        "ALTER TABLE document_chunks "
        "ALTER COLUMN embedding TYPE vector(1536) USING NULL::vector(1536)"
    )
    op.execute("""
        CREATE INDEX ix_document_chunks_embedding_ivfflat
        ON document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
