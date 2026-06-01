"""Add component_accuracy_stats and fleet_penalty_adjustments tables

Revision ID: 6c2460f8ef38
Revises: 96bea7284112
Create Date: 2026-03-10 18:58:26.116634
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c2460f8ef38'
down_revision: Union[str, None] = '96bea7284112'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('component_accuracy_stats',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('component', sa.String(length=50), nullable=False),
    sa.Column('mean_absolute_error', sa.Float(), nullable=True),
    sa.Column('directional_accuracy', sa.Float(), nullable=True),
    sa.Column('sample_count', sa.Integer(), nullable=True),
    sa.Column('last_updated', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_component_accuracy_stats_component'), 'component_accuracy_stats', ['component'], unique=True)
    op.create_table('fleet_penalty_adjustments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('component', sa.String(length=50), nullable=False),
    sa.Column('penalty_multiplier', sa.Float(), nullable=True),
    sa.Column('sample_count', sa.Integer(), nullable=True),
    sa.Column('directional_accuracy', sa.Float(), nullable=True),
    sa.Column('mean_absolute_error', sa.Float(), nullable=True),
    sa.Column('last_updated', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fleet_penalty_adjustments_component'), 'fleet_penalty_adjustments', ['component'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_fleet_penalty_adjustments_component'), table_name='fleet_penalty_adjustments')
    op.drop_table('fleet_penalty_adjustments')
    op.drop_index(op.f('ix_component_accuracy_stats_component'), table_name='component_accuracy_stats')
    op.drop_table('component_accuracy_stats')
