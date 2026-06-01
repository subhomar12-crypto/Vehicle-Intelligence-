"""Add image_url column to vehicle_profiles

Revision ID: m3h5i9d1e2f3
Revises: l2g4h8c0d1e2
Create Date: 2026-03-03

Adds:
- image_url for vehicle photo URL
"""
from alembic import op
import sqlalchemy as sa


revision = "m3h5i9d1e2f3"
down_revision = "l2g4h8c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vehicle_profiles", sa.Column("image_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("vehicle_profiles", "image_url")
