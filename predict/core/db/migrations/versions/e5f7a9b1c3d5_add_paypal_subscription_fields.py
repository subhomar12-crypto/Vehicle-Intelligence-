"""add paypal subscription fields

Revision ID: e5f7a9b1c3d5
Revises: d3e5f7a9b2c4
Create Date: 2026-02-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f7a9b1c3d5'
down_revision: Union[str, None] = 'd3e5f7a9b2c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('subscriptions',
        sa.Column('payment_source', sa.String(20), nullable=True))
    op.add_column('subscriptions',
        sa.Column('paypal_subscription_id', sa.String(100), nullable=True))
    op.add_column('subscriptions',
        sa.Column('paypal_plan_id', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('subscriptions', 'paypal_plan_id')
    op.drop_column('subscriptions', 'paypal_subscription_id')
    op.drop_column('subscriptions', 'payment_source')
