"""add analysis language and confidence to documents

The AI analysis layer (Phase 3) stores the detected document language and the
model's self-reported confidence alongside the existing summary/document_type/
entities columns from the initial schema. Both are nullable: documents analyzed
before this feature (or with analysis disabled) simply have no values.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("language", sa.String(10), nullable=True))
    op.add_column("documents", sa.Column("analysis_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "analysis_confidence")
    op.drop_column("documents", "language")
