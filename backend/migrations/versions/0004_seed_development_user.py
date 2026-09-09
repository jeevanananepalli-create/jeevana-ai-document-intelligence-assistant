"""seed the fixed development user used by the temporary auth dependency

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.execute(
        "INSERT INTO users (id, email, password_hash, full_name) "
        f"VALUES ('{_DEV_USER_ID}', 'development@example.com', "
        "'!development-only-placeholder!', 'Development User') "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM users WHERE id = '{_DEV_USER_ID}'")
