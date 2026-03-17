"""Add parts_prices and service_prices tables

Revision ID: q7l9m3h6i7j8
Revises: p6k8l2g5h6i7
Create Date: 2026-03-17

Creates:
- parts_prices   — individual auto part prices (oil, filters, batteries, etc.)
- service_prices — service/labor prices (oil change, brake job, etc.)

Both tables track Qatar market pricing from three sources:
admin manual entry, LLM web search, and mechanic feedback.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'q7l9m3h6i7j8'
down_revision = 'p6k8l2g5h6i7'
branch_labels = None
depends_on = None


def upgrade():
    # -- parts_prices --
    op.create_table(
        'parts_prices',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('component_id', sa.String(50), nullable=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('brand', sa.String(100), nullable=True),
        sa.Column('part_number', sa.String(100), nullable=True),
        sa.Column('vehicle_make', sa.String(50), nullable=True),
        sa.Column('vehicle_model', sa.String(50), nullable=True),
        sa.Column('year_min', sa.Integer(), nullable=True),
        sa.Column('year_max', sa.Integer(), nullable=True),
        sa.Column('price_qar', sa.Float(), nullable=False),
        sa.Column('price_type', sa.String(20), server_default='retail', nullable=False),
        sa.Column('supplier', sa.String(200), nullable=True),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('confidence', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('price_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
        sa.UniqueConstraint(
            'category', 'name', 'supplier', 'vehicle_make', 'vehicle_model',
            name='uq_parts_price',
        ),
    )
    op.create_index('idx_parts_component', 'parts_prices', ['component_id'])
    op.create_index('idx_parts_vehicle', 'parts_prices', ['vehicle_make', 'vehicle_model'])

    # -- service_prices --
    op.create_table(
        'service_prices',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('service_type', sa.String(100), nullable=False),
        sa.Column('component_id', sa.String(50), nullable=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('labor_qar', sa.Float(), nullable=True),
        sa.Column('parts_qar', sa.Float(), nullable=True),
        sa.Column('total_qar', sa.Float(), nullable=False),
        sa.Column('vehicle_make', sa.String(50), nullable=True),
        sa.Column('vehicle_model', sa.String(50), nullable=True),
        sa.Column('year_min', sa.Integer(), nullable=True),
        sa.Column('year_max', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(200), nullable=True),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('confidence', sa.Float(), server_default='1.0', nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('price_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.Float(), nullable=False),
    )
    op.create_index('idx_service_component', 'service_prices', ['component_id'])
    op.create_index('idx_service_vehicle', 'service_prices', ['vehicle_make', 'vehicle_model'])


def downgrade():
    op.drop_index('idx_service_vehicle', table_name='service_prices')
    op.drop_index('idx_service_component', table_name='service_prices')
    op.drop_table('service_prices')

    op.drop_index('idx_parts_vehicle', table_name='parts_prices')
    op.drop_index('idx_parts_component', table_name='parts_prices')
    op.drop_table('parts_prices')
