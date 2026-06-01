"""Add owner_user_id to vehicle_profiles.

Revision ID: 002
Revises: 001
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vehicle_profiles",
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("idx_vehicle_profiles_owner", "vehicle_profiles", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("idx_vehicle_profiles_owner", table_name="vehicle_profiles")
    op.drop_column("vehicle_profiles", "owner_user_id")
