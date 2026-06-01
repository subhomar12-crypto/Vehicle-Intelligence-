"""add fleets and fleet_members tables

Revision ID: b1c3f4a5d6e7
Revises: ae4fe080b7b0
Create Date: 2026-02-15 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c3f4a5d6e7'
down_revision: Union[str, None] = '9243035df623'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fleets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=True),
    )
    op.create_index('ix_fleets_owner_id', 'fleets', ['owner_id'])

    op.create_table(
        'fleet_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('fleet_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(20), server_default='driver'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('joined_at', sa.Float(), nullable=False),
    )
    op.create_index('ix_fleet_members_fleet_id', 'fleet_members', ['fleet_id'])
    op.create_index('ix_fleet_members_user_id', 'fleet_members', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_fleet_members_user_id', 'fleet_members')
    op.drop_index('ix_fleet_members_fleet_id', 'fleet_members')
    op.drop_table('fleet_members')
    op.drop_index('ix_fleets_owner_id', 'fleets')
    op.drop_table('fleets')
