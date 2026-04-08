"""Fix parent_story_id FK to SET NULL on delete

Revision ID: 0032
Revises: 0031
Create Date: 2026-04-08
"""
from alembic import op

revision = '0032'
down_revision = '0031'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE user_stories
        DROP CONSTRAINT user_stories_parent_story_id_fkey
    """)
    op.execute("""
        ALTER TABLE user_stories
        ADD CONSTRAINT user_stories_parent_story_id_fkey
        FOREIGN KEY (parent_story_id)
        REFERENCES user_stories(id)
        ON DELETE SET NULL
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE user_stories
        DROP CONSTRAINT user_stories_parent_story_id_fkey
    """)
    op.execute("""
        ALTER TABLE user_stories
        ADD CONSTRAINT user_stories_parent_story_id_fkey
        FOREIGN KEY (parent_story_id)
        REFERENCES user_stories(id)
    """)
