"""Configuration package.

Exposes the application `Settings` and a cached `get_settings()` accessor so the
rest of the app imports configuration from one place.
"""

from app.core.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
