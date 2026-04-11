# backend/migrations/versions/0042_audit_logs.py
"""Add audit_logs table (partitioned by occurred_at)

Revision ID: 0042
Revises: 0041
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET

revision = '0042'
down_revision = '0041'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create partitioned parent table
    op.execute("""
        CREATE TABLE audit_logs (
            id          BIGSERIAL,
            org_id      UUID NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id   UUID NOT NULL,
            action      TEXT NOT NULL,
            actor_id    UUID,
            actor_type  TEXT NOT NULL DEFAULT 'user',
            old_value   JSONB,
            new_value   JSONB,
            diff        JSONB,
            ip_address  INET,
            session_id  TEXT,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata_   JSONB NOT NULL DEFAULT '{}',
            PRIMARY KEY (id, occurred_at)
        ) PARTITION BY RANGE (occurred_at)
    """)
    # Default partition catches everything until monthly partitions are added
    op.execute("""
        CREATE TABLE audit_logs_default
        PARTITION OF audit_logs DEFAULT
    """)
    op.execute("""
        CREATE INDEX idx_audit_entity
        ON audit_logs (entity_type, entity_id, occurred_at DESC)
    """)
    op.execute("""
        CREATE INDEX idx_audit_org_time
        ON audit_logs (org_id, occurred_at DESC)
    """)
    # Append-only policy: app_role can INSERT but not UPDATE/DELETE
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_role') THEN
                EXECUTE 'CREATE POLICY audit_append_only ON audit_logs
                    FOR INSERT TO app_role WITH CHECK (true)';
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
