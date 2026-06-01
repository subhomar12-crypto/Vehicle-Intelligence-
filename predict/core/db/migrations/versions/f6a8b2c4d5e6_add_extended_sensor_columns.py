"""Add extended sensor columns to vehicle_data

Revision ID: f6a8b2c4d5e6
Revises: e5f7a9b1c3d5
Create Date: 2026-02-28

Adds:
- vehicle_data.ambient_temp       (Float) — PID 0146 ambient air temperature
- vehicle_data.boost_pressure     (Float) — PID 0170 turbo/supercharger boost
- vehicle_data.fuel_rate          (Float) — PID 015E fuel consumption rate L/h
- vehicle_data.torque             (Float) — PID 0163 engine torque Nm
- vehicle_data.obd_odometer       (Float) — PID 01A6 odometer km from ECU
- vehicle_data.mode06_results     (Text)  — JSON array of Mode 06 ECU test results
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a8b2c4d5e6'
down_revision = 'e5f7a9b1c3d5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('vehicle_data', sa.Column('ambient_temp', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('boost_pressure', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('fuel_rate', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('torque', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('obd_odometer', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('mode06_results', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('vehicle_data', 'mode06_results')
    op.drop_column('vehicle_data', 'obd_odometer')
    op.drop_column('vehicle_data', 'torque')
    op.drop_column('vehicle_data', 'fuel_rate')
    op.drop_column('vehicle_data', 'boost_pressure')
    op.drop_column('vehicle_data', 'ambient_temp')
