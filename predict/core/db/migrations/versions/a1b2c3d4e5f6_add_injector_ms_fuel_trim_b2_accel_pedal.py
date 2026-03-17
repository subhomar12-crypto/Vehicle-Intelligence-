"""add injector_ms fuel_trim_b2 accel_pedal to vehicle_data

Revision ID: a1b2c3d4e5f6
Revises: 6c2460f8ef38
Create Date: 2026-03-17 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6c2460f8ef38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vehicle_data', sa.Column('injector_ms', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('fuel_trim_b2', sa.Float(), nullable=True))
    op.add_column('vehicle_data', sa.Column('accel_pedal', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('vehicle_data', 'accel_pedal')
    op.drop_column('vehicle_data', 'fuel_trim_b2')
    op.drop_column('vehicle_data', 'injector_ms')
