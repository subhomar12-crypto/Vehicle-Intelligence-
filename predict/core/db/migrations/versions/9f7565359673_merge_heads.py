"""merge heads

Revision ID: 9f7565359673
Revises: a1b2c3d4e5f6, u1v3w7x8y9z0
Create Date: 2026-03-20 10:26:06.392762
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f7565359673'
down_revision: Union[str, None] = ('a1b2c3d4e5f6', 'u1v3w7x8y9z0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
