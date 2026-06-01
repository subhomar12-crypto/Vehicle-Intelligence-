"""Add vin_hash column to vehicle_profiles

Revision ID: k1f3g7b9c0d1
Revises: j0e2f6a8b9c0
Create Date: 2026-03-01

Adds:
- vin_hash column for indexed VIN equality searches without exposing plaintext
"""
from alembic import op
import sqlalchemy as sa


revision = "k1f3g7b9c0d1"
down_revision = "j0e2f6a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vehicle_profiles",
        sa.Column("vin_hash", sa.String(64), nullable=True),
    )
    op.create_index("idx_vehicle_profiles_vin_hash", "vehicle_profiles", ["vin_hash"])


def downgrade() -> None:
    op.drop_index("idx_vehicle_profiles_vin_hash", table_name="vehicle_profiles")
    op.drop_column("vehicle_profiles", "vin_hash")
