"""add pi5_devices table and reading_id column

Revision ID: 704f5d5b9706
Revises: 9f7565359673
Create Date: 2026-03-20 10:26:16.038843
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '704f5d5b9706'
down_revision: Union[str, None] = '9f7565359673'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Pi5 device registration and status tracking
    op.create_table('pi5_devices',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device_id', sa.String(length=64), nullable=False),
    sa.Column('vehicle_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('firmware_version', sa.String(length=32), nullable=True),
    sa.Column('last_seen', sa.Float(), nullable=False),
    sa.Column('cpu_temp', sa.Float(), nullable=True),
    sa.Column('ram_used_mb', sa.Integer(), nullable=True),
    sa.Column('sd_free_gb', sa.Float(), nullable=True),
    sa.Column('wifi_signal_dbm', sa.Integer(), nullable=True),
    sa.Column('wifi_ssid', sa.String(length=128), nullable=True),
    sa.Column('buffer_remaining', sa.Integer(), nullable=True),
    sa.Column('odometer_km', sa.Integer(), nullable=True),
    sa.Column('device_token', sa.String(length=128), nullable=True),
    sa.Column('token_expires_at', sa.Float(), nullable=True),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicle_profiles.profile_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pi5_devices_device_id'), 'pi5_devices', ['device_id'], unique=True)
    op.create_index(op.f('ix_pi5_devices_device_token'), 'pi5_devices', ['device_token'], unique=True)

    # Pi5 per-reading dedup UUID
    op.add_column('vehicle_data', sa.Column('reading_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_vehicle_data_reading_id'), 'vehicle_data', ['reading_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_vehicle_data_reading_id'), table_name='vehicle_data')
    op.drop_column('vehicle_data', 'reading_id')
    op.drop_index(op.f('ix_pi5_devices_device_token'), table_name='pi5_devices')
    op.drop_index(op.f('ix_pi5_devices_device_id'), table_name='pi5_devices')
    op.drop_table('pi5_devices')
