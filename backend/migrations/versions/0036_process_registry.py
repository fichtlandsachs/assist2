"""Add process registry and story process changes

Revision ID: 0036
Revises: 0035
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = '0036'
down_revision = '0035'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE processchangestatus AS ENUM ('pending', 'released');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS processes (
            id UUID PRIMARY KEY,
            organization_id UUID NOT NULL REFERENCES organizations(id),
            name VARCHAR(500) NOT NULL,
            confluence_page_id VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_processes_organization_id ON processes (organization_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS story_process_changes (
            id UUID PRIMARY KEY,
            story_id UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
            process_id UUID NOT NULL REFERENCES processes(id) ON DELETE CASCADE,
            section_anchor VARCHAR(500),
            delta_text TEXT,
            status processchangestatus NOT NULL DEFAULT 'pending',
            released_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_story_process_changes_story_id ON story_process_changes (story_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_story_process_changes_process_id ON story_process_changes (process_id)")


def downgrade() -> None:
    op.drop_index('ix_story_process_changes_process_id', 'story_process_changes')
    op.drop_index('ix_story_process_changes_story_id', 'story_process_changes')
    op.drop_table('story_process_changes')
    op.drop_index('ix_processes_organization_id', 'processes')
    op.drop_table('processes')
    op.execute("DROP TYPE IF EXISTS processchangestatus;")
