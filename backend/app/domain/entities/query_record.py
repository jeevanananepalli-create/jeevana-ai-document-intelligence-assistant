"""The QueryRecord entity — one past Q&A interaction.

Stored so users can revisit previous questions and so latency/confidence can be
monitored over time. Immutable: a history record never changes after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class QueryRecord:
    """A user's past question and the answer they received."""

    id: UUID
    user_id: UUID
    question: str
    answer: str
    confidence: float
    source_count: int
    model_used: str
    latency_ms: int
    created_at: datetime
