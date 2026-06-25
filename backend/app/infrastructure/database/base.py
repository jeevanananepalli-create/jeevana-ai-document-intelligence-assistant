"""SQLAlchemy declarative base.

Every ORM model (added in later phases) will inherit from `Base`. Alembic
inspects `Base.metadata` to discover the tables it should generate migrations
for, so this single base ties the models and the migration system together.

It lives in its own tiny module to avoid import cycles: both the models and the
Alembic environment import `Base` from here without pulling in the engine.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""
