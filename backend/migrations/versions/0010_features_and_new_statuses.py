"""Add features table, new story statuses, epic status

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-18
"""
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New StoryStatus values (ADD VALUE is auto-transactional in PG 12+)
    op.execute("ALTER TYPE storystatus ADD VALUE IF NOT EXISTS 'in_review'")
    op.execute("ALTER TYPE storystatus ADD VALUE IF NOT EXISTS 'testing'")

    # Epic status enum + column
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE epicstatus AS ENUM ('planning', 'in_progress', 'done', 'archived');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("ALTER TABLE epics ADD COLUMN IF NOT EXISTS status epicstatus NOT NULL DEFAULT 'planning'")

    # Feature status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE featurestatus AS ENUM ('draft', 'in_progress', 'testing', 'done', 'archived');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    # Features table
    op.execute("""
        CREATE TABLE IF NOT EXISTS features (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id),
            story_id UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
            epic_id UUID REFERENCES epics(id) ON DELETE SET NULL,
            created_by_id UUID NOT NULL REFERENCES users(id),
            title VARCHAR(500) NOT NULL,
            description TEXT,
            status featurestatus NOT NULL DEFAULT 'draft',
            priority storypriority NOT NULL DEFAULT 'medium',
            story_points INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_features_organization_id ON features(organization_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_features_story_id ON features(story_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_features_epic_id ON features(epic_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS features")
    op.execute("DROP TYPE IF EXISTS featurestatus")
    op.execute("ALTER TABLE epics DROP COLUMN IF EXISTS status")
    op.execute("DROP TYPE IF EXISTS epicstatus")
