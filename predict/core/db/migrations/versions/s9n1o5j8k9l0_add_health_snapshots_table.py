"""Add health_snapshots table for health trend charts.

Revision ID: s9n1o5j8k9l0
Revises: r8m0n4i7j8k9
Create Date: 2026-03-19

Creates:
- health_snapshots — periodic health assessment snapshots (max 1 per 6h per vehicle, 365-day retention)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 's9n1o5j8k9l0'
down_revision = 'r8m0n4i7j8k9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'health_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('vehicle_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.profile_id', ondelete='CASCADE'), nullable=False),
        sa.Column('health_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('components', sa.Text(), nullable=True),
        sa.Column('intelligence_level', sa.String(20), server_default='basic'),
        sa.Column('anomaly_count', sa.Integer(), server_default='0'),
        sa.Column('pattern_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.Float(), nullable=True),
    )
    op.create_index('ix_health_snap_vehicle_date', 'health_snapshots', ['vehicle_id', 'created_at'])
    op.create_index('ix_health_snapshots_vehicle_id', 'health_snapshots', ['vehicle_id'])


def downgrade():
    op.drop_index('ix_health_snap_vehicle_date', table_name='health_snapshots')
    op.drop_index('ix_health_snapshots_vehicle_id', table_name='health_snapshots')
    op.drop_table('health_snapshots')
