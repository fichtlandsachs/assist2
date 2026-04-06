"""extend document_chunks with provenance metadata

Revision ID: 0025
Revises: 0024
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename file_path → source_ref
    op.alter_column('document_chunks', 'file_path', new_column_name='source_ref')

    # Add provenance columns
    op.add_column('document_chunks', sa.Column('source_type', sa.String(32), nullable=False, server_default='nextcloud'))
    op.add_column('document_chunks', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('document_chunks', sa.Column('source_title', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('document_chunks', 'source_title')
    op.drop_column('document_chunks', 'source_url')
    op.drop_column('document_chunks', 'source_type')
    op.alter_column('document_chunks', 'source_ref', new_column_name='file_path')
