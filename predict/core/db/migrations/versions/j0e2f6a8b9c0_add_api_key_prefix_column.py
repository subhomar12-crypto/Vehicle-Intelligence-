"""Add key_prefix column to api_keys table

Revision ID: j0e2f6a8b9c0
Revises: i9d1e5f7a8b9
Create Date: 2026-03-01

Adds:
- key_prefix column (first 8 chars of API key for admin lookup)
- Index on key_prefix for fast lookups
- Backfills existing rows with 'unknown_' placeholder
"""
from alembic import op
import sqlalchemy as sa


revision = "j0e2f6a8b9c0"
down_revision = "i9d1e5f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add column as nullable first, backfill, then set NOT NULL
    op.add_column(
        "api_keys",
        sa.Column("key_prefix", sa.String(8), nullable=True),
    )
    # Backfill existing rows — we can't recover the original prefix,
    # so use a placeholder. New logins will overwrite with real prefix.
    op.execute("UPDATE api_keys SET key_prefix = 'unknown_' WHERE key_prefix IS NULL")
    op.alter_column("api_keys", "key_prefix", nullable=False)
    op.create_index("idx_api_keys_prefix", "api_keys", ["key_prefix"])


def downgrade() -> None:
    op.drop_index("idx_api_keys_prefix", table_name="api_keys")
    op.drop_column("api_keys", "key_prefix")
