"""add vehicle_research table and displacement/cylinders to vehicle_profiles

Revision ID: c2d4e6f8a1b3
Revises: b1c3f4a5d6e7
Create Date: 2026-02-20 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d4e6f8a1b3'
down_revision: Union[str, None] = 'b1c3f4a5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add displacement and cylinders to vehicle_profiles
    op.add_column('vehicle_profiles', sa.Column('displacement', sa.String(10), nullable=True))
    op.add_column('vehicle_profiles', sa.Column('cylinders', sa.Integer(), nullable=True))

    # Create vehicle_research table
    op.create_table(
        'vehicle_research',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('vehicle_profiles.profile_id'), unique=True, nullable=False),
        sa.Column('research_status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('common_problems', sa.Text(), nullable=True),
        sa.Column('failure_prone_parts', sa.Text(), nullable=True),
        sa.Column('recalls', sa.Text(), nullable=True),
        sa.Column('tsbs', sa.Text(), nullable=True),
        sa.Column('owner_reviews_summary', sa.Text(), nullable=True),
        sa.Column('reliability_score', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('ai_features', sa.Text(), nullable=True),
        sa.Column('raw_search_results', sa.Text(), nullable=True),
        sa.Column('sources', sa.Text(), nullable=True),
        sa.Column('vin_status', sa.String(20), server_default='unknown', nullable=False),
        sa.Column('researched_at', sa.Float(), nullable=True),
        sa.Column('created_at', sa.Float(), nullable=True),
        sa.Column('updated_at', sa.Float(), nullable=True),
    )
    op.create_index('idx_vehicle_research_profile', 'vehicle_research', ['profile_id'])
    op.create_index('idx_vehicle_research_status', 'vehicle_research', ['research_status'])


def downgrade() -> None:
    op.drop_index('idx_vehicle_research_status', table_name='vehicle_research')
    op.drop_index('idx_vehicle_research_profile', table_name='vehicle_research')
    op.drop_table('vehicle_research')
    op.drop_column('vehicle_profiles', 'cylinders')
    op.drop_column('vehicle_profiles', 'displacement')
