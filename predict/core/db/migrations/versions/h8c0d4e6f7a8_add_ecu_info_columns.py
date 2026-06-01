"""Add ECU info columns to vehicle_profiles (Mode 09 data)

Revision ID: h8c0d4e6f7a8
Revises: g7b9c3d5e6f7
Create Date: 2026-02-28

Adds:
- calibration_id — ECU Calibration ID (Mode 09 PID 04)
- ecu_name      — ECU Name (Mode 09 PID 0A)
- cvn           — Calibration Verification Number (Mode 09 PID 06)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h8c0d4e6f7a8"
down_revision = ("g7b9c3d5e6f7", "ddaede4258e7")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vehicle_profiles", sa.Column("calibration_id", sa.String(50), nullable=True))
    op.add_column("vehicle_profiles", sa.Column("ecu_name", sa.String(100), nullable=True))
    op.add_column("vehicle_profiles", sa.Column("cvn", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("vehicle_profiles", "cvn")
    op.drop_column("vehicle_profiles", "ecu_name")
    op.drop_column("vehicle_profiles", "calibration_id")
