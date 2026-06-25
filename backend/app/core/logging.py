"""Logging configuration.

A single place to configure how the application logs. Phase 1 uses the standard
library `logging` with a readable, timestamped format and a level driven by the
`LOG_LEVEL` setting. Structured/JSON logging can replace this later without
changing any call sites, because the rest of the app just calls
`logging.getLogger(__name__)`.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging() -> None:
    """Configure the root logger once, based on the configured log level."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format=_LOG_FORMAT)
    logging.getLogger(__name__).debug("Logging configured at level %s", settings.log_level)
