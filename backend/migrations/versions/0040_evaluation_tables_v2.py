# backend/migrations/versions/0040_evaluation_tables_v2.py
"""Extend evaluation_runs, add evaluation_step_results and evaluation_results_v2

Revision ID: 0040
Revises: 0039
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0040'
down_revision = '0039'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend existing evaluation_runs with new columns (all nullable for backward compat)
    op.add_column('evaluation_runs',
        sa.Column('story_version_id', UUID(as_uuid=True),
                  sa.ForeignKey('story_versions.id', ondelete='RESTRICT'), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('rule_set_id', UUID(as_uuid=True),
                  sa.ForeignKey('rule_sets.id', ondelete='RESTRICT'), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('rule_set_snapshot', JSONB(), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('scoring_profile_id', UUID(as_uuid=True),
                  sa.ForeignKey('scoring_profiles.id', ondelete='SET NULL'), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('scoring_profile_snapshot', JSONB(), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('langgraph_thread_id', sa.Text(), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('trigger_type', sa.String(20), nullable=False, server_default='manual'))
    op.add_column('evaluation_runs',
        sa.Column('parent_run_id', UUID(as_uuid=True),
                  sa.ForeignKey('evaluation_runs.id', ondelete='SET NULL'), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('evaluation_runs',
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('evaluation_runs',
        sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('idx_eval_runs_thread', 'evaluation_runs', ['langgraph_thread_id'],
                    unique=True,
                    postgresql_where=sa.text('langgraph_thread_id IS NOT NULL'))
    op.create_index('idx_eval_runs_story_ver', 'evaluation_runs', ['story_version_id'])

    # Extend status enum to include paused and cancelled
    op.execute("ALTER TYPE evaluation_status ADD VALUE IF NOT EXISTS 'PAUSED'")
    op.execute("ALTER TYPE evaluation_status ADD VALUE IF NOT EXISTS 'CANCELLED'")

    # evaluation_step_results
    op.create_table(
        'evaluation_step_results',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('evaluation_run_id', UUID(as_uuid=True),
                  sa.ForeignKey('evaluation_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_name', sa.String(100), nullable=False),
        sa.Column('dimension', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('score', sa.Numeric(5, 4), nullable=True),
        sa.Column('findings', JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('input_snapshot', JSONB(), nullable=True),
        sa.Column('output_snapshot', JSONB(), nullable=True),
        sa.Column('llm_model', sa.String(100), nullable=True),
        sa.Column('token_usage', JSONB(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('evaluation_run_id', 'step_name',
                            name='uq_eval_step_run_step'),
    )
    op.create_index('idx_eval_step_results_run', 'evaluation_step_results', ['evaluation_run_id'])

    # evaluation_results_v2 (replaces result_json on run)
    op.create_table(
        'evaluation_results_v2',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('evaluation_run_id', UUID(as_uuid=True),
                  sa.ForeignKey('evaluation_runs.id', ondelete='CASCADE'),
                  nullable=False, unique=True),
        sa.Column('story_version_id', UUID(as_uuid=True),
                  sa.ForeignKey('story_versions.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('overall_score', sa.Numeric(5, 4), nullable=True),
        sa.Column('overall_status', sa.String(10), nullable=True),
        sa.Column('dimension_scores', JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('findings', JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('rewrite_suggestions', JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column('is_final', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('human_overridden', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('override_by', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('override_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('idx_eval_results_v2_story_ver', 'evaluation_results_v2',
                    ['story_version_id'],
                    postgresql_where=sa.text('is_final = true'))


def downgrade() -> None:
    op.drop_index('idx_eval_results_v2_story_ver', 'evaluation_results_v2')
    op.drop_table('evaluation_results_v2')
    op.drop_index('idx_eval_step_results_run', 'evaluation_step_results')
    op.drop_table('evaluation_step_results')
    op.drop_index('idx_eval_runs_story_ver', 'evaluation_runs')
    op.drop_index('idx_eval_runs_thread', 'evaluation_runs')
    for col in ['paused_at', 'started_at', 'retry_count', 'parent_run_id',
                'trigger_type', 'langgraph_thread_id', 'scoring_profile_snapshot',
                'scoring_profile_id', 'rule_set_snapshot', 'rule_set_id',
                'story_version_id']:
        op.drop_column('evaluation_runs', col)
    # Note: cannot remove enum values in PostgreSQL — leave paused/cancelled in enum
