"""
SQLAlchemy 2.0 base model with timestamp float columns.

All models inherit from this base. Timestamps use float (time.time()) not datetime.
"""

import time
from typing import Any

from sqlalchemy import Float, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    
    pass


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at float timestamps.
    
    Uses time.time() for Unix epoch seconds (float), NOT datetime objects.
    """
    
    created_at: Mapped[float] = mapped_column(
        Float,
        default=time.time,
        nullable=False,
    )
    
    updated_at: Mapped[float] = mapped_column(
        Float,
        default=time.time,
        onupdate=time.time,
        nullable=False,
    )


# Event listener to ensure updated_at is set on every update
@event.listens_for(Base, "before_update", propagate=True)
def set_updated_at_before_update(mapper: Any, connection: Any, target: Any) -> None:
    """Set updated_at to current time before any update."""
    if hasattr(target, "updated_at"):
        target.updated_at = time.time()
