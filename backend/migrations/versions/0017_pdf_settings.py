"""Create pdf_settings table.

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pdf_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('page_format', sa.String(10), nullable=False, server_default='a4'),
        sa.Column('language', sa.String(10), nullable=False, server_default='de'),
        sa.Column('header_text', sa.String(500), nullable=True),
        sa.Column('footer_text', sa.String(500), nullable=True),
        sa.Column('letterhead_filename', sa.String(255), nullable=True),
        sa.Column('logo_filename', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', name='uq_pdf_settings_org'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_pdf_settings_organization_id', 'pdf_settings', ['organization_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_pdf_settings_organization_id', table_name='pdf_settings')
    op.drop_table('pdf_settings')
