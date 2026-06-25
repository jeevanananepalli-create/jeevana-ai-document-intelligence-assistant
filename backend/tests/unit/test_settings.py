"""Tests for application settings, focused on the production secret guard.

The guard refuses to construct Settings in production while the JWT secret is
still the public placeholder. Because Settings is built at startup, a failure
here means the application refuses to boot — exactly the intended behaviour.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config.settings import (
    DEFAULT_JWT_SECRET_KEY,
    Environment,
    Settings,
)

# A realistic, non-default secret used for the "happy path" production case.
STRONG_SECRET = "f3a9c1e7b2d84a06b5e0c9d1a7f4e2b8c6d0a3f1e9b7c5d2"


def _build_settings(**overrides: object) -> Settings:
    """Construct Settings deterministically for tests.

    `_env_file=None` disables reading a local `.env`, and the explicit keyword
    overrides take priority over any ambient OS environment variables, so these
    tests behave identically on every machine and in CI.
    """
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_development_allows_placeholder_secret() -> None:
    """In development, the placeholder secret is acceptable (no error)."""
    settings = _build_settings(
        app_env=Environment.DEVELOPMENT,
        jwt_secret_key=DEFAULT_JWT_SECRET_KEY,
    )
    assert settings.is_production is False
    assert settings.jwt_secret_key == DEFAULT_JWT_SECRET_KEY


def test_production_rejects_placeholder_secret() -> None:
    """In production, the placeholder secret must abort startup."""
    with pytest.raises(ValidationError) as exc_info:
        _build_settings(
            app_env=Environment.PRODUCTION,
            jwt_secret_key=DEFAULT_JWT_SECRET_KEY,
        )
    # The error message must clearly name the offending variable.
    assert "JWT_SECRET_KEY" in str(exc_info.value)


def test_production_allows_a_real_secret() -> None:
    """In production with a strong secret, startup succeeds."""
    settings = _build_settings(
        app_env=Environment.PRODUCTION,
        jwt_secret_key=STRONG_SECRET,
    )
    assert settings.is_production is True
    assert settings.jwt_secret_key == STRONG_SECRET
