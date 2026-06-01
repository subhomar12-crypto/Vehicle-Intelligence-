"""Add last known location columns to vehicle_profiles

Revision ID: l2g4h8c0d1e2
Revises: k1f3g7b9c0d1
Create Date: 2026-03-03

Adds:
- last_latitude, last_longitude for GPS snapshot on OBD disconnect
- last_location_accuracy for GPS accuracy in meters
- last_location_at for Unix timestamp of when location was saved
"""
from alembic import op
import sqlalchemy as sa


revision = "l2g4h8c0d1e2"
down_revision = "k1f3g7b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vehicle_profiles", sa.Column("last_latitude", sa.Float, nullable=True))
    op.add_column("vehicle_profiles", sa.Column("last_longitude", sa.Float, nullable=True))
    op.add_column("vehicle_profiles", sa.Column("last_location_accuracy", sa.Float, nullable=True))
    op.add_column("vehicle_profiles", sa.Column("last_location_at", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("vehicle_profiles", "last_location_at")
    op.drop_column("vehicle_profiles", "last_location_accuracy")
    op.drop_column("vehicle_profiles", "last_longitude")
    op.drop_column("vehicle_profiles", "last_latitude")
