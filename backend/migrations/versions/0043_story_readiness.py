"""Add assignee_id to user_stories and story_readiness_evaluations table

Revision ID: 0043
Revises: 0042
Create Date: 2026-04-13
"""
from alembic import op

revision = '0043'
down_revision = '0042'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE user_stories ADD COLUMN assignee_id UUID REFERENCES users(id) ON DELETE SET NULL;
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_stories_assignee_id ON user_stories (assignee_id);
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE readiness_state AS ENUM (
                'not_ready',
                'partially_ready',
                'mostly_ready',
                'implementation_ready'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS story_readiness_evaluations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id),
            story_id UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
            evaluated_for_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            triggered_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            readiness_score INTEGER NOT NULL,
            readiness_state readiness_state NOT NULL,
            open_topics JSONB NOT NULL DEFAULT '[]',
            missing_inputs JSONB NOT NULL DEFAULT '[]',
            required_preparatory_work JSONB NOT NULL DEFAULT '[]',
            dependencies JSONB NOT NULL DEFAULT '[]',
            blockers JSONB NOT NULL DEFAULT '[]',
            risks JSONB NOT NULL DEFAULT '[]',
            recommended_next_steps JSONB NOT NULL DEFAULT '[]',
            summary TEXT,
            model_used VARCHAR(100),
            confidence NUMERIC(4, 3),
            story_snapshot JSONB,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_story_readiness_evaluations_organization_id
            ON story_readiness_evaluations (organization_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_story_readiness_evaluations_story_id
            ON story_readiness_evaluations (story_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_story_readiness_evaluations_evaluated_for_user_id
            ON story_readiness_evaluations (evaluated_for_user_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_readiness_story_created
            ON story_readiness_evaluations (story_id, created_at);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_readiness_story_created")
    op.execute("DROP TABLE IF EXISTS story_readiness_evaluations")
    op.execute("DROP TYPE IF EXISTS readiness_state")
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE user_stories DROP COLUMN assignee_id;
        EXCEPTION
            WHEN undefined_column THEN null;
        END $$;
    """)
