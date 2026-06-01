"""Add prediction feedback tables and profile mileage

Revision ID: 96bea7284112
Revises: da17c01cd82a
Create Date: 2026-03-10 13:51:48.635019
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '96bea7284112'
down_revision: Union[str, None] = 'da17c01cd82a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New tables for Intelligence Engine v2
    op.create_table('fleet_learning_adjustments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('make', sa.String(length=50), nullable=False),
    sa.Column('model', sa.String(length=50), nullable=False),
    sa.Column('component', sa.String(length=50), nullable=False),
    sa.Column('adjustment_type', sa.String(length=30), nullable=True),
    sa.Column('adjustment_value', sa.Float(), nullable=True),
    sa.Column('evidence_count', sa.Integer(), nullable=True),
    sa.Column('last_updated', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('make', 'model', 'component', 'adjustment_type', name='uq_fleet_adj')
    )
    op.create_table('fleet_patterns',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('make', sa.String(length=50), nullable=False),
    sa.Column('model', sa.String(length=50), nullable=False),
    sa.Column('component', sa.String(length=50), nullable=False),
    sa.Column('pattern_type', sa.String(length=50), nullable=True),
    sa.Column('pattern_signature', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('evidence_count', sa.Integer(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('first_seen', sa.Float(), nullable=True),
    sa.Column('last_confirmed', sa.Float(), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('make', 'model', 'component', 'pattern_type', name='uq_fleet_pattern')
    )
    op.create_table('prediction_accuracy',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('vehicle_id', sa.Integer(), nullable=False),
    sa.Column('component', sa.String(length=50), nullable=False),
    sa.Column('prediction_date', sa.Float(), nullable=False),
    sa.Column('validation_date', sa.Float(), nullable=False),
    sa.Column('predicted_score', sa.Integer(), nullable=True),
    sa.Column('actual_score', sa.Integer(), nullable=True),
    sa.Column('trend_predicted', sa.String(length=20), nullable=True),
    sa.Column('trend_actual', sa.String(length=20), nullable=True),
    sa.Column('was_accurate', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prediction_accuracy_vehicle_id'), 'prediction_accuracy', ['vehicle_id'], unique=False)
    op.create_table('prediction_feedback',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('vehicle_id', sa.Integer(), nullable=False),
    sa.Column('component', sa.String(length=50), nullable=False),
    sa.Column('predicted_score', sa.Integer(), nullable=True),
    sa.Column('actual_outcome', sa.String(length=20), nullable=True),
    sa.Column('service_record_id', sa.Integer(), nullable=True),
    sa.Column('feedback_date', sa.Float(), nullable=False),
    sa.Column('make', sa.String(length=50), nullable=True),
    sa.Column('model', sa.String(length=50), nullable=True),
    sa.Column('year', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prediction_feedback_vehicle_id'), 'prediction_feedback', ['vehicle_id'], unique=False)
    op.create_table('prediction_snapshots',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('vehicle_id', sa.Integer(), nullable=False),
    sa.Column('component', sa.String(length=50), nullable=False),
    sa.Column('predicted_score', sa.Integer(), nullable=False),
    sa.Column('predicted_trend', sa.String(length=20), nullable=True),
    sa.Column('confidence_tier', sa.String(length=20), nullable=True),
    sa.Column('sensor_readings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('driving_context', sa.String(length=20), nullable=True),
    sa.Column('snapshot_date', sa.Float(), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_snapshots_vehicle_date', 'prediction_snapshots', ['vehicle_id', 'snapshot_date'], unique=False)
    op.create_index(op.f('ix_prediction_snapshots_vehicle_id'), 'prediction_snapshots', ['vehicle_id'], unique=False)

    # New columns on vehicle_profiles
    op.add_column('vehicle_profiles', sa.Column('mileage_km', sa.Integer(), nullable=True))
    op.add_column('vehicle_profiles', sa.Column('component_ages', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('vehicle_profiles', 'component_ages')
    op.drop_column('vehicle_profiles', 'mileage_km')
    op.drop_index(op.f('ix_prediction_snapshots_vehicle_id'), table_name='prediction_snapshots')
    op.drop_index('idx_snapshots_vehicle_date', table_name='prediction_snapshots')
    op.drop_table('prediction_snapshots')
    op.drop_index(op.f('ix_prediction_feedback_vehicle_id'), table_name='prediction_feedback')
    op.drop_table('prediction_feedback')
    op.drop_index(op.f('ix_prediction_accuracy_vehicle_id'), table_name='prediction_accuracy')
    op.drop_table('prediction_accuracy')
    op.drop_table('fleet_patterns')
    op.drop_table('fleet_learning_adjustments')
