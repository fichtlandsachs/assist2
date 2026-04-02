"""add projects table and project_id FK to epics and user_stories

Revision ID: 0023
Revises: 0022
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE projectstatus AS ENUM ('planning', 'active', 'done', 'archived');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE effortlevel AS ENUM ('low', 'medium', 'high', 'xl');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE complexitylevel AS ENUM ('low', 'medium', 'high', 'xl');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            created_by_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
            name VARCHAR(500) NOT NULL,
            description TEXT,
            status projectstatus NOT NULL DEFAULT 'planning',
            deadline DATE,
            color VARCHAR(7),
            effort effortlevel,
            complexity complexitylevel,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_projects_organization_id ON projects(organization_id);")

    op.execute("ALTER TABLE epics ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;")
    op.execute("CREATE INDEX IF NOT EXISTS ix_epics_project_id ON epics(project_id);")

    op.execute("ALTER TABLE user_stories ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_stories_project_id ON user_stories(project_id);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_stories_project_id;")
    op.execute("ALTER TABLE user_stories DROP COLUMN IF EXISTS project_id;")
    op.execute("DROP INDEX IF EXISTS ix_epics_project_id;")
    op.execute("ALTER TABLE epics DROP COLUMN IF EXISTS project_id;")
    op.execute("DROP INDEX IF EXISTS ix_projects_organization_id;")
    op.execute("DROP TABLE IF EXISTS projects;")
    op.execute("DROP TYPE IF EXISTS projectstatus;")
    op.execute("DROP TYPE IF EXISTS effortlevel;")
    op.execute("DROP TYPE IF EXISTS complexitylevel;")
