"""Add model_versions, base_model_entries, and training_jobs tables

Revision ID: r8m0n4i7j8k9
Revises: q7l9m3h6i7j8
Create Date: 2026-03-17

Creates:
- model_versions     — trained TFLite models per vehicle (health/anomaly/context)
- base_model_entries — fleet-wide base models for transfer learning
- training_jobs      — training job queue and status tracker
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'r8m0n4i7j8k9'
down_revision = 'q7l9m3h6i7j8'
branch_labels = None
depends_on = None


def upgrade():
    # -- model_versions --
    op.create_table(
        'model_versions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.profile_id'), nullable=False),
        sa.Column('model_type', sa.String(30), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('training_data_points', sa.Integer(), nullable=True),
        sa.Column('training_trips', sa.Integer(), nullable=True),
        sa.Column('validation_accuracy', sa.Float(), nullable=True),
        sa.Column('float32_accuracy', sa.Float(), nullable=True),
        sa.Column('status', sa.String(20), server_default='active', nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
    )
    op.create_index('ix_model_versions_profile_id', 'model_versions', ['profile_id'])
    op.create_index('idx_mv_profile_type', 'model_versions', ['profile_id', 'model_type'])

    # -- base_model_entries --
    op.create_table(
        'base_model_entries',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('make', sa.String(50), nullable=False),
        sa.Column('model', sa.String(50), nullable=True),
        sa.Column('model_type', sa.String(30), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('training_vehicle_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
    )
    op.create_index('idx_bme_make_model_type', 'base_model_entries', ['make', 'model', 'model_type'])

    # -- training_jobs --
    op.create_table(
        'training_jobs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.profile_id'), nullable=False),
        sa.Column('model_type', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), server_default='queued', nullable=False),
        sa.Column('trigger_reason', sa.String(50), nullable=True),
        sa.Column('queued_at', sa.Float(), nullable=False),
        sa.Column('started_at', sa.Float(), nullable=True),
        sa.Column('completed_at', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_model_version_id', sa.Integer(), sa.ForeignKey('model_versions.id'), nullable=True),
    )
    op.create_index('ix_training_jobs_profile_id', 'training_jobs', ['profile_id'])
    op.create_index('idx_tj_profile_status', 'training_jobs', ['profile_id', 'status'])


def downgrade():
    op.drop_index('idx_tj_profile_status', table_name='training_jobs')
    op.drop_index('ix_training_jobs_profile_id', table_name='training_jobs')
    op.drop_table('training_jobs')

    op.drop_index('idx_bme_make_model_type', table_name='base_model_entries')
    op.drop_table('base_model_entries')

    op.drop_index('idx_mv_profile_type', table_name='model_versions')
    op.drop_index('ix_model_versions_profile_id', table_name='model_versions')
    op.drop_table('model_versions')
