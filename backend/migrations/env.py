"""Alembic migration environment.

Alembic runs migrations *synchronously*, so this environment uses the sync
database URL (`DATABASE_URL_SYNC`) from the application settings rather than the
async URL the app uses at runtime. This avoids pulling async drivers into the
migration tooling and is the standard, simplest setup.

`target_metadata` points at the application's declarative `Base.metadata`. When
ORM models are added in later phases, importing them here lets
`alembic revision --autogenerate` detect new tables and columns by diffing the
models against the live database.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.infrastructure.database.base import Base

# IMPORTANT (later phases): import model modules here so their tables register
# on Base.metadata and autogenerate can see them, e.g.:
#   from app.infrastructure.database import models  # noqa: F401

config = context.config

# Inject the connection URL from our single source of truth (the environment),
# overriding the empty value in alembic.ini.
config.set_main_option("sqlalchemy.url", get_settings().database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (emits SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detect column type changes during autogenerate
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
