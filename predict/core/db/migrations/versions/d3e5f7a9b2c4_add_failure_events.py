"""add failure_events table

Revision ID: d3e5f7a9b2c4
Revises: c2d4e6f8a1b3
Create Date: 2026-02-22 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e5f7a9b2c4'
down_revision: Union[str, None] = 'c2d4e6f8a1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'failure_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.profile_id'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('component', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(20), server_default='medium', nullable=False),
        sa.Column('dtc_code', sa.String(10), nullable=True),
        sa.Column('mileage_at_failure', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('obd_snapshot', sa.Text(), nullable=True),
        sa.Column('training_label', sa.String(50), nullable=True),
        sa.Column('training_exported', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('event_timestamp', sa.Float(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
    )
    op.create_index('idx_failure_events_profile', 'failure_events', ['profile_id'])
    op.create_index('idx_failure_events_type', 'failure_events', ['event_type'])
    op.create_index('idx_failure_events_component', 'failure_events', ['component'])


def downgrade() -> None:
    op.drop_index('idx_failure_events_component', table_name='failure_events')
    op.drop_index('idx_failure_events_type', table_name='failure_events')
    op.drop_index('idx_failure_events_profile', table_name='failure_events')
    op.drop_table('failure_events')
