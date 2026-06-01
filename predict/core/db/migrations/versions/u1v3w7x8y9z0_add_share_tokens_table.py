"""Add share_tokens table

Revision ID: u1v3w7x8y9z0
Revises: t0n2p6q9r1s2
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "u1v3w7x8y9z0"
down_revision = "t0n2p6q9r1s2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "share_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column(
            "vehicle_id",
            sa.Integer(),
            sa.ForeignKey("vehicle_profiles.profile_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("creator_user_id", sa.Integer(), nullable=False),
        sa.Column("health_data", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Float()),
        sa.Column("expires_at", sa.Float(), nullable=False),
    )
    op.create_index(
        "ix_share_vehicle_created", "share_tokens", ["vehicle_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_share_vehicle_created", table_name="share_tokens")
    op.drop_table("share_tokens")
