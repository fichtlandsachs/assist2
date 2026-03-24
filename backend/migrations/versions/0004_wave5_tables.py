"""Wave 5 tables: mail_connections, messages, calendar_connections, calendar_events, test_cases

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # mail provider enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE mailprovider AS ENUM ('gmail', 'outlook', 'imap');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    # mail_connections
    op.execute("""
        CREATE TABLE IF NOT EXISTS mail_connections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider mailprovider NOT NULL,
            email_address VARCHAR(320) NOT NULL,
            display_name VARCHAR(200),
            access_token_enc TEXT,
            refresh_token_enc TEXT,
            token_expires_at TIMESTAMPTZ,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_sync_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_mail_connections_org ON mail_connections(organization_id);")

    # message status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE messagestatus AS ENUM ('unread', 'read', 'archived', 'deleted');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    # messages
    op.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            connection_id UUID NOT NULL REFERENCES mail_connections(id) ON DELETE CASCADE,
            external_id VARCHAR(500) NOT NULL,
            thread_id VARCHAR(500),
            subject VARCHAR(1000),
            sender_email VARCHAR(320) NOT NULL,
            sender_name VARCHAR(200),
            snippet TEXT,
            body_text TEXT,
            status messagestatus NOT NULL DEFAULT 'unread',
            received_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_org ON messages(organization_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_connection ON messages(connection_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_thread ON messages(thread_id);")

    # calendar provider enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE calendarprovider AS ENUM ('google', 'outlook');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    # calendar_connections
    op.execute("""
        CREATE TABLE IF NOT EXISTS calendar_connections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider calendarprovider NOT NULL,
            email_address VARCHAR(320) NOT NULL,
            display_name VARCHAR(200),
            access_token_enc TEXT,
            refresh_token_enc TEXT,
            token_expires_at TIMESTAMPTZ,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_sync_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_calendar_connections_org ON calendar_connections(organization_id);")

    # event status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eventstatus AS ENUM ('confirmed', 'tentative', 'cancelled');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    # calendar_events
    op.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            connection_id UUID NOT NULL REFERENCES calendar_connections(id) ON DELETE CASCADE,
            external_id VARCHAR(500) NOT NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            location VARCHAR(500),
            start_at TIMESTAMPTZ NOT NULL,
            end_at TIMESTAMPTZ NOT NULL,
            all_day BOOLEAN NOT NULL DEFAULT false,
            status eventstatus NOT NULL DEFAULT 'confirmed',
            organizer_email VARCHAR(320),
            attendees_json TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_calendar_events_org ON calendar_events(organization_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_calendar_events_connection ON calendar_events(connection_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_calendar_events_start_at ON calendar_events(start_at);")

    # test result enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE testresult AS ENUM ('pending', 'passed', 'failed', 'skipped');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    # test_cases
    op.execute("""
        CREATE TABLE IF NOT EXISTS test_cases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            story_id UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
            created_by_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            steps TEXT,
            expected_result TEXT,
            result testresult NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_test_cases_org ON test_cases(organization_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_test_cases_story ON test_cases(story_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS test_cases;")
    op.execute("DROP TYPE IF EXISTS testresult;")
    op.execute("DROP TABLE IF EXISTS calendar_events;")
    op.execute("DROP TYPE IF EXISTS eventstatus;")
    op.execute("DROP TABLE IF EXISTS calendar_connections;")
    op.execute("DROP TYPE IF EXISTS calendarprovider;")
    op.execute("DROP TABLE IF EXISTS messages;")
    op.execute("DROP TYPE IF EXISTS messagestatus;")
    op.execute("DROP TABLE IF EXISTS mail_connections;")
    op.execute("DROP TYPE IF EXISTS mailprovider;")
