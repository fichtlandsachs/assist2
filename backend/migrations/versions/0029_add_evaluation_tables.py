"""Add evaluation_runs, evaluation_findings, approval_requests

Revision ID: 0029
Revises: 0028
Create Date: 2026-04-07
"""
from alembic import op

revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE evaluation_status AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')")
    op.execute("CREATE TYPE ampel_status AS ENUM ('GREEN', 'YELLOW', 'RED')")
    op.execute("CREATE TYPE finding_severity AS ENUM ('CRITICAL', 'MAJOR', 'MINOR', 'INFO')")
    op.execute("CREATE TYPE approval_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED')")

    op.execute("""
        CREATE TABLE evaluation_runs (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            story_id        UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
            triggered_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            status          evaluation_status NOT NULL DEFAULT 'PENDING',
            score           NUMERIC(4,2),
            ampel           ampel_status,
            knockout        BOOLEAN DEFAULT FALSE,
            confidence      NUMERIC(4,3),
            result_json     JSONB,
            model_used      VARCHAR(100),
            input_tokens    INTEGER DEFAULT 0,
            output_tokens   INTEGER DEFAULT 0,
            error_message   TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at    TIMESTAMPTZ,
            deleted_at      TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX ix_evaluation_runs_org_id     ON evaluation_runs(organization_id)")
    op.execute("CREATE INDEX ix_evaluation_runs_story_id   ON evaluation_runs(story_id)")
    op.execute("CREATE INDEX ix_evaluation_runs_status     ON evaluation_runs(status)")
    op.execute("CREATE INDEX ix_evaluation_runs_created_at ON evaluation_runs(created_at DESC)")

    op.execute("""
        CREATE TABLE evaluation_findings (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            evaluation_run_id UUID NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
            finding_key       VARCHAR(20) NOT NULL,
            severity          finding_severity NOT NULL,
            category          VARCHAR(50) NOT NULL,
            title             VARCHAR(200) NOT NULL,
            description       TEXT NOT NULL,
            suggestion        TEXT NOT NULL,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_eval_findings_run_id ON evaluation_findings(evaluation_run_id)")

    op.execute("""
        CREATE TABLE approval_requests (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id   UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            story_id          UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
            evaluation_run_id UUID REFERENCES evaluation_runs(id) ON DELETE SET NULL,
            status            approval_status NOT NULL DEFAULT 'PENDING',
            reviewer_id       UUID REFERENCES users(id) ON DELETE SET NULL,
            decided_by_id     UUID REFERENCES users(id) ON DELETE SET NULL,
            decided_at        TIMESTAMPTZ,
            comment           TEXT,
            slack_message_ts  VARCHAR(50),
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX ix_approval_requests_org_id   ON approval_requests(organization_id)")
    op.execute("CREATE INDEX ix_approval_requests_story_id ON approval_requests(story_id)")
    op.execute("CREATE INDEX ix_approval_requests_status   ON approval_requests(status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS approval_requests")
    op.execute("DROP TABLE IF EXISTS evaluation_findings")
    op.execute("DROP TABLE IF EXISTS evaluation_runs")
    op.execute("DROP TYPE IF EXISTS approval_status")
    op.execute("DROP TYPE IF EXISTS finding_severity")
    op.execute("DROP TYPE IF EXISTS ampel_status")
    op.execute("DROP TYPE IF EXISTS evaluation_status")
