"""Add daily/weekly sensor summary tables for GDPR-safe aggregation

Revision ID: g7b9c3d5e6f7
Revises: f6a8b2c4d5e6
Create Date: 2026-02-28

Adds:
- daily_sensor_summary — per-vehicle per-sensor per-day min/max/avg/count
- prediction_outcomes  — tracks prediction accuracy (confirmed/false_positive)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g7b9c3d5e6f7'
down_revision = 'f6a8b2c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'daily_sensor_summary',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vehicle_id', sa.Integer(), nullable=False, index=True),
        sa.Column('date', sa.String(10), nullable=False),  # YYYY-MM-DD
        sa.Column('sensor', sa.String(50), nullable=False),
        sa.Column('min_value', sa.Float()),
        sa.Column('max_value', sa.Float()),
        sa.Column('avg_value', sa.Float()),
        sa.Column('reading_count', sa.Integer()),
        sa.Column('quality_score', sa.Float()),
        sa.UniqueConstraint('vehicle_id', 'date', 'sensor', name='uq_daily_sensor'),
    )

    op.create_table(
        'prediction_outcomes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vehicle_id', sa.Integer(), nullable=False, index=True),
        sa.Column('component', sa.String(50), nullable=False),
        sa.Column('pattern_name', sa.String(100)),
        sa.Column('predicted_health_pct', sa.Float()),
        sa.Column('outcome', sa.String(20), nullable=False),  # confirmed, false_positive, missed
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('service_record_id', sa.Integer()),
    )


def downgrade() -> None:
    op.drop_table('prediction_outcomes')
    op.drop_table('daily_sensor_summary')
