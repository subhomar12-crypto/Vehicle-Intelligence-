"""Add persistent explain cache columns to vehicle_profiles

Revision ID: p6k8l2g5h6i7
Revises: o5j7k1f3g4h5
Create Date: 2026-03-09

Adds:
- vehicle_profiles.last_explain_json  (Text) — full /explain response JSON
- vehicle_profiles.last_explain_at    (Float) — Unix timestamp of last generation

One LLM call generates the health assessment; both OBD driver and Guardian
fleet admin see the same persisted result. Cleared on new OBD data upload.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p6k8l2g5h6i7'
down_revision = 'o5j7k1f3g4h5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('vehicle_profiles', sa.Column('last_explain_json', sa.Text(), nullable=True))
    op.add_column('vehicle_profiles', sa.Column('last_explain_at', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('vehicle_profiles', 'last_explain_at')
    op.drop_column('vehicle_profiles', 'last_explain_json')
