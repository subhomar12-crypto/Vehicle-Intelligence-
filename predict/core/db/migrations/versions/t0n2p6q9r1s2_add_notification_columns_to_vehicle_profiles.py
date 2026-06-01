"""Add notification dedup + rate-limit columns to vehicle_profiles.

Revision ID: t0n2p6q9r1s2
Revises: s9n1o5j8k9l0
Create Date: 2026-03-19

Adds:
- last_notification_hash — SHA-256 hash of last critical anomaly notification
- notification_count_today — daily send counter (rate limit = 3/day)
- notification_reset_date — YYYY-MM-DD when count was last reset
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 't0n2p6q9r1s2'
down_revision: Union[str, None] = 's9n1o5j8k9l0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vehicle_profiles', sa.Column('last_notification_hash', sa.String(64), nullable=True))
    op.add_column('vehicle_profiles', sa.Column('notification_count_today', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('vehicle_profiles', sa.Column('notification_reset_date', sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column('vehicle_profiles', 'notification_reset_date')
    op.drop_column('vehicle_profiles', 'notification_count_today')
    op.drop_column('vehicle_profiles', 'last_notification_hash')
