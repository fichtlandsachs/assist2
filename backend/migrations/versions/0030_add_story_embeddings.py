"""Add story_embeddings table with pgvector HNSW index

Revision ID: 0030
Revises: 0029
Create Date: 2026-04-07
"""
from alembic import op

revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE story_embeddings (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            story_id        UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
            embedding       vector(1024),
            content_hash    VARCHAR(64) NOT NULL,
            model_used      VARCHAR(100) NOT NULL DEFAULT 'ionos-embed',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (story_id)
        )
    """)
    op.execute("CREATE INDEX ix_story_embeddings_org_id ON story_embeddings(organization_id)")
    op.execute("""
        CREATE INDEX ix_story_embeddings_hnsw
        ON story_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_story_embeddings_hnsw")
    op.execute("DROP TABLE IF EXISTS story_embeddings")
