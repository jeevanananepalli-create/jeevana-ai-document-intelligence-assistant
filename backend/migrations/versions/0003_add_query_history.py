"""add query_history table

Stores every Q&A interaction (Phase 4): the question, the generated answer, and
quality metrics (confidence, source count, latency) for the history endpoint and
for performance monitoring.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "query_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_query_history_user_id", "query_history", ["user_id"])
    op.create_index("ix_query_history_created_at", "query_history", ["created_at"])


def downgrade() -> None:
    op.drop_table("query_history")
