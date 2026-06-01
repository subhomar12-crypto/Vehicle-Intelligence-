"""
Re-export auth dependencies from predict.core.api.deps.

Many routers import from this path. The actual implementations
live in predict.core.api.deps.
"""

from predict.core.api.deps import get_current_user, get_optional_user, require_admin

# Alias used by billing.py
get_current_user_optional = get_optional_user

__all__ = [
    "get_current_user",
    "get_optional_user",
    "get_current_user_optional",
    "require_admin",
]
