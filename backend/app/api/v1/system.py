"""System endpoints (v1): the readiness probe.

Complements the unversioned liveness probe (`GET /health`, which never touches
dependencies). Readiness answers "can this instance actually serve work?" by
checking the database. Per the API contract it always returns 200 — the endpoint
itself is working — and reports per-dependency status in the body; load
balancers and orchestrators inspect the `status` field.

The check uses its own short-lived connection from the engine rather than the
request-scoped session dependency, so a dead database can never break the
probe's own request teardown.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.infrastructure.database.session import engine

router = APIRouter(tags=["health"])


class DependencyCheck(BaseModel):
    status: Literal["up", "down"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, DependencyCheck]


async def _database_is_up() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/health", response_model=ReadinessResponse, summary="Readiness probe")
async def readiness() -> ReadinessResponse:
    """Report whether this instance's dependencies are reachable.

    Redis/Celery checks are added when a feature depends on them at request
    time; today the API itself only needs the database.
    """
    database_up = await _database_is_up()
    return ReadinessResponse(
        status="ready" if database_up else "degraded",
        checks={"database": DependencyCheck(status="up" if database_up else "down")},
    )
