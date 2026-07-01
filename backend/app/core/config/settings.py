"""Application configuration.

All configuration is read from environment variables (or a local `.env` file)
and validated once, at startup, by Pydantic. Two benefits over reading
`os.environ` directly:

1. Fail fast: if a required variable is missing or malformed, the app refuses
   to start with a clear error, instead of crashing later mid-request.
2. Typed access: `settings.access_token_expire_minutes` is an `int`, not a
   string you must remember to convert.

Only the settings the Phase 1 foundation actually uses are declared here.
Feature-specific settings (OpenAI keys, embedding config, storage, Redis) are
added in the phase that introduces them, so the config surface stays honest
about what the running code depends on.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """The deployment environment the app is running in."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


# The placeholder secret shipped in `.env.example`. It is convenient for local
# development, but it is public knowledge (it lives in the repo), so it must
# never be used to sign real tokens. Settings validation below refuses to start
# in production while this value is in use.
DEFAULT_JWT_SECRET_KEY = "change-me-to-a-random-secret-in-production"


class Settings(BaseSettings):
    """Strongly-typed application settings, sourced from the environment.

    Field names map to UPPER_CASE environment variables case-insensitively,
    e.g. the `database_url` field is populated from `DATABASE_URL`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # tolerate future/feature env vars not yet modelled here
    )

    # --- Application -------------------------------------------------------
    app_env: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Which environment this process is running in.",
    )
    app_debug: bool = Field(
        default=False,
        description="Enable verbose errors and auto-reload. Never true in prod.",
    )
    log_level: str = Field(
        default="INFO",
        description="Root log level: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    )

    # --- Database ----------------------------------------------------------
    # Async URL (asyncpg) is used by the application at runtime.
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/docintell",
        description="Async SQLAlchemy connection URL used by the running app.",
    )
    # Sync URL (psycopg) is used by Alembic, which runs migrations synchronously.
    database_url_sync: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/docintell",
        description="Sync SQLAlchemy connection URL used by Alembic migrations.",
    )
    db_pool_size: int = Field(
        default=5,
        ge=1,
        description="Number of persistent connections kept open in the pool.",
    )
    db_max_overflow: int = Field(
        default=10,
        ge=0,
        description="Extra connections allowed beyond pool_size under load.",
    )
    db_echo: bool = Field(
        default=False,
        description="Log every SQL statement. Useful when debugging locally.",
    )

    # --- Security / Authentication ----------------------------------------
    # NOTE: this is a structure only in Phase 1 — no login flow is wired yet.
    jwt_secret_key: str = Field(
        default=DEFAULT_JWT_SECRET_KEY,
        description="Secret used to sign JWTs. MUST be overridden in production.",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="Signing algorithm for JWTs.",
    )
    access_token_expire_minutes: int = Field(
        default=15,
        ge=1,
        description="Lifetime of a short-lived access token, in minutes.",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        description="Lifetime of a long-lived refresh token, in days.",
    )

    # --- CORS --------------------------------------------------------------
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of browser origins allowed to call the API.",
    )

    # --- Document storage --------------------------------------------------
    storage_path: str = Field(
        default="./uploads",
        description="Base directory where uploaded files are stored (local backend).",
    )
    max_file_size_mb: int = Field(
        default=50,
        ge=1,
        description="Maximum accepted upload size, in megabytes.",
    )

    # --- Async processing / embeddings (Phase 2.4) -------------------------
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL used as the Celery broker and result backend.",
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="sentence-transformers model used to embed document chunks.",
    )
    embedding_dimension: int = Field(
        default=384,
        ge=1,
        description="Vector width the embedding model produces (must match the DB column).",
    )

    @property
    def max_file_size_bytes(self) -> int:
        """The max upload size expressed in bytes, for direct length checks."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse the comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """True when running in the production environment."""
        return self.app_env is Environment.PRODUCTION

    @model_validator(mode="after")
    def _reject_default_secret_in_production(self) -> Settings:
        """Fail fast if the insecure default JWT secret is used in production.

        Signing tokens with a placeholder that lives in the public repository
        would let anyone forge valid tokens and impersonate any user. Rather
        than boot in that state, we refuse to start. This runs automatically
        whenever `Settings()` is constructed (i.e. at application startup),
        because Pydantic invokes `model_validator` during initialisation.
        """
        if self.is_production and self.jwt_secret_key == DEFAULT_JWT_SECRET_KEY:
            raise ValueError(
                "JWT_SECRET_KEY is the insecure default placeholder while "
                "APP_ENV=production. Set a strong, random JWT_SECRET_KEY in the "
                "environment before deploying to production."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance.

    Settings are read from the environment once and reused for the process
    lifetime. `lru_cache` makes this a lightweight singleton and lets tests
    override configuration by clearing the cache.
    """
    return Settings()
