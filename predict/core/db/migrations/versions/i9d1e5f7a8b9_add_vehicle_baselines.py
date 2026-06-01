"""Add vehicle_baselines table for per-vehicle AI learning

Revision ID: i9d1e5f7a8b9
Revises: h8c0d4e6f7a8
Create Date: 2026-03-01

Adds:
- vehicle_baselines table — per-vehicle learned baseline (sensor stats,
  weekly trends, autoencoder weights). Progresses through phases:
  collecting → baseline_ready → autoencoder_ready.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "i9d1e5f7a8b9"
down_revision = "h8c0d4e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicle_baselines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("vehicle_profiles.profile_id"), nullable=False),
        sa.Column("trip_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("data_points", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sensor_stats", sa.Text(), nullable=True),
        sa.Column("weekly_trends", sa.Text(), nullable=True),
        sa.Column("autoencoder_weights", sa.LargeBinary(), nullable=True),
        sa.Column("autoencoder_trained_at", sa.Float(), nullable=True),
        sa.Column("autoencoder_loss", sa.Float(), nullable=True),
        sa.Column("phase", sa.String(20), server_default="collecting", nullable=False),
        sa.Column("updated_at", sa.Float(), nullable=True),
        sa.Column("created_at", sa.Float(), nullable=True),
    )
    op.create_index("idx_vehicle_baselines_profile", "vehicle_baselines", ["profile_id"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_vehicle_baselines_profile", table_name="vehicle_baselines")
    op.drop_table("vehicle_baselines")
