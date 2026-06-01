"""Add extended AI sensor columns to vehicle_data

Revision ID: o5j7k1f3g4h5
Revises: n4i6j0e2f3g4
Create Date: 2026-03-09

Adds:
- vehicle_data.intake_manifold_pressure  (Float) — PID 010B MAP sensor kPa
- vehicle_data.baro_pressure             (Float) — PID 0133 barometric pressure kPa
- vehicle_data.o2_sensor_b1s1            (Float) — PID 0114/0124 O2 bank 1 sensor 1
- vehicle_data.o2_sensor_b1s2            (Float) — PID 0115/0125 O2 bank 1 sensor 2
- vehicle_data.catalyst_temp_b1s1        (Float) — PID 013C catalyst temp bank 1 sensor 1
- vehicle_data.catalyst_temp_b1s2        (Float) — PID 013E catalyst temp bank 1 sensor 2
- vehicle_data.oil_pressure              (Float) — oil pressure sensor
- vehicle_data.dtc_active_count          (Integer) — active DTC count at this timestamp
- vehicle_data.dtc_pending_count         (Integer) — pending DTC count at this timestamp
- vehicle_data.mode06_total              (Integer) — total Mode 06 tests count
- vehicle_data.mode06_passed             (Integer) — passed Mode 06 tests count
- vehicle_data.mode06_failed             (Integer) — failed Mode 06 tests count
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o5j7k1f3g4h5'
down_revision = 'n4i6j0e2f3g4'
branch_labels = None
depends_on = None


def upgrade():
    # Extended PIDs for AI training
    op.add_column('vehicle_data', sa.Column('intake_manifold_pressure', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('baro_pressure', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('o2_sensor_b1s1', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('o2_sensor_b1s2', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('catalyst_temp_b1s1', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('catalyst_temp_b1s2', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('oil_pressure', sa.Float(), nullable=True))
    # DTC event counts for AI timeline correlation
    op.add_column('vehicle_data', sa.Column('dtc_active_count', sa.Integer(), nullable=True))
    op.add_column('vehicle_data', sa.Column('dtc_pending_count', sa.Integer(), nullable=True))
    # Mode 06 summary counts
    op.add_column('vehicle_data', sa.Column('mode06_total', sa.Integer(), nullable=True))
    op.add_column('vehicle_data', sa.Column('mode06_passed', sa.Integer(), nullable=True))
    op.add_column('vehicle_data', sa.Column('mode06_failed', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('vehicle_data', 'mode06_failed')
    op.drop_column('vehicle_data', 'mode06_passed')
    op.drop_column('vehicle_data', 'mode06_total')
    op.drop_column('vehicle_data', 'dtc_pending_count')
    op.drop_column('vehicle_data', 'dtc_active_count')
    op.drop_column('vehicle_data', 'oil_pressure')
    op.drop_column('vehicle_data', 'catalyst_temp_b1s2')
    op.drop_column('vehicle_data', 'catalyst_temp_b1s1')
    op.drop_column('vehicle_data', 'o2_sensor_b1s2')
    op.drop_column('vehicle_data', 'o2_sensor_b1s1')
    op.drop_column('vehicle_data', 'baro_pressure')
    op.drop_column('vehicle_data', 'intake_manifold_pressure')
