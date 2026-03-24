"""ai_steps table

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE aistepstatus AS ENUM ('pending', 'running', 'completed', 'failed');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_steps (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            story_id UUID REFERENCES user_stories(id) ON DELETE SET NULL,
            agent_role VARCHAR(100) NOT NULL,
            model VARCHAR(100) NOT NULL DEFAULT 'claude-sonnet-4-6',
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            status aistepstatus NOT NULL DEFAULT 'pending',
            input_data TEXT,
            output_data TEXT,
            error_message TEXT,
            duration_ms INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_steps_org ON ai_steps(organization_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_steps_story ON ai_steps(story_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_steps;")
    op.execute("DROP TYPE IF EXISTS aistepstatus;")
