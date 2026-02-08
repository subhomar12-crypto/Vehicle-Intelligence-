"""
SQLAlchemy declarative base for all ORM models.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""
    
    created_at: Mapped[float] = mapped_column(
        Float, 
        default=lambda: datetime.utcnow().timestamp(),
        nullable=False
    )
    updated_at: Mapped[Optional[float]] = mapped_column(
        Float,
        default=lambda: datetime.utcnow().timestamp(),
        onupdate=lambda: datetime.utcnow().timestamp(),
        nullable=True
    )
