"""Add user_stories table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE storystatus AS ENUM (
                'draft', 'ready', 'in_progress', 'done', 'archived'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE storypriority AS ENUM (
                'low', 'medium', 'high', 'critical'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_stories (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            created_by_id   UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
            title            VARCHAR(500) NOT NULL,
            description      TEXT,
            acceptance_criteria TEXT,
            status           storystatus NOT NULL DEFAULT 'draft',
            priority         storypriority NOT NULL DEFAULT 'medium',
            story_points     INTEGER,
            dor_passed       BOOLEAN NOT NULL DEFAULT false,
            ai_suggestions   TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_stories_organization_id
        ON user_stories(organization_id);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_stories_organization_id;")
    op.execute("DROP TABLE IF EXISTS user_stories;")
    op.execute("DROP TYPE IF EXISTS storystatus;")
    op.execute("DROP TYPE IF EXISTS storypriority;")
