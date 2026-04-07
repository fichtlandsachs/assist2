"""Add integration_events table for Jira/ServiceNow webhook audit

Revision ID: 0031
Revises: 0030
Create Date: 2026-04-07
"""
from alembic import op

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE integration_events (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            source          VARCHAR(50) NOT NULL,
            event_type      VARCHAR(100) NOT NULL,
            external_id     VARCHAR(200),
            payload_json    JSONB NOT NULL,
            processed       BOOLEAN NOT NULL DEFAULT FALSE,
            error_message   TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (source, external_id, organization_id)
        )
    """)
    op.execute("CREATE INDEX ix_integration_events_org_id     ON integration_events(organization_id)")
    op.execute("CREATE INDEX ix_integration_events_source     ON integration_events(source)")
    op.execute("CREATE INDEX ix_integration_events_created_at ON integration_events(created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS integration_events")
