"""
Platform Core - Permissions.

Permission helpers for platform-level access control.
"""
from typing import Any


def is_platform_owner(user: Any) -> bool:
    """Check if the user is a platform owner."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "role", None) == "PLATFORM_OWNER"
