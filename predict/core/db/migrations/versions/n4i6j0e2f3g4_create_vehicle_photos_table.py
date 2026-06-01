"""Create vehicle_photos table

Revision ID: n4i6j0e2f3g4
Revises: m3h5i9d1e2f3
Create Date: 2026-03-04

Creates:
- vehicle_photos table for pre-uploaded vehicle photos
"""
from alembic import op
import sqlalchemy as sa


revision = "n4i6j0e2f3g4"
down_revision = "m3h5i9d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicle_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("vin", sa.String(17), nullable=True),
        sa.Column("license_plate", sa.String(20), nullable=True),
        sa.Column("make", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("color", sa.String(50), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("original_url", sa.String(500), nullable=True),
        sa.Column("uploaded_by", sa.String(20), server_default="admin"),
        sa.Column("assigned_to_profile_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Float(), server_default=sa.text("extract(epoch from now())")),
        sa.Column("updated_at", sa.Float(), server_default=sa.text("extract(epoch from now())")),
    )


def downgrade() -> None:
    op.drop_table("vehicle_photos")
