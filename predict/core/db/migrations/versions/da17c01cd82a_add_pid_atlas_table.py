"""add pid_atlas table

Revision ID: da17c01cd82a
Revises: p6k8l2g5h6i7
Create Date: 2026-03-09 18:44:29.522577
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da17c01cd82a'
down_revision: Union[str, None] = 'p6k8l2g5h6i7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('pid_atlas',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('make', sa.String(length=50), nullable=False),
    sa.Column('model', sa.String(length=100), nullable=False),
    sa.Column('year_min', sa.Integer(), nullable=False),
    sa.Column('year_max', sa.Integer(), nullable=False),
    sa.Column('service', sa.Integer(), nullable=False),
    sa.Column('pid_hex', sa.String(length=8), nullable=False),
    sa.Column('ecu_address', sa.String(length=8), nullable=False),
    sa.Column('data_byte_count', sa.Integer(), nullable=False),
    sa.Column('is_dynamic', sa.Boolean(), nullable=False),
    sa.Column('semantic_type', sa.String(length=30), nullable=False),
    sa.Column('discovery_count', sa.Integer(), nullable=False),
    sa.Column('sample_values', sa.Text(), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('formula', sa.String(length=100), nullable=True),
    sa.Column('is_verified', sa.Boolean(), nullable=False),
    sa.Column('first_discovered_at', sa.Float(), nullable=False),
    sa.Column('last_seen_at', sa.Float(), nullable=False),
    sa.Column('created_at', sa.Float(), nullable=False),
    sa.Column('updated_at', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('make', 'model', 'service', 'pid_hex', 'ecu_address', name='uq_pid_atlas_entry')
    )
    op.create_index('idx_pid_atlas_make_model', 'pid_atlas', ['make', 'model'], unique=False)
    op.create_index(op.f('ix_pid_atlas_make'), 'pid_atlas', ['make'], unique=False)
    op.create_index(op.f('ix_pid_atlas_model'), 'pid_atlas', ['model'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pid_atlas_model'), table_name='pid_atlas')
    op.drop_index(op.f('ix_pid_atlas_make'), table_name='pid_atlas')
    op.drop_index('idx_pid_atlas_make_model', table_name='pid_atlas')
    op.drop_table('pid_atlas')
