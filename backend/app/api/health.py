"""Liveness health check.

`GET /health` answers one question: "is this process up and able to serve
HTTP?" It deliberately does NOT touch the database or any external service, so
it stays fast and dependency-free.

Why health endpoints matter
---------------------------
Automated systems, not humans, are the main consumers:
- A container orchestrator (Docker Compose, Kubernetes) calls it to decide
  whether the container is alive; if it stops responding, the platform restarts
  it.
- A load balancer calls it to decide whether to route traffic to this instance;
  an unhealthy instance is pulled out of rotation.
- Uptime monitors call it to alert a human when the service is down.

Liveness vs. readiness
----------------------
This is a *liveness* probe (is the process alive?). A *readiness* probe (are my
dependencies — DB, cache, workers — reachable so I can actually serve work?) is
a richer, separate endpoint documented in docs/api-contract.md as the future
`GET /api/v1/health`. Keeping them separate is a deliberate, standard split.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Shape of the liveness response (also drives the OpenAPI schema)."""

    status: str
    service: str


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    """Return a static OK payload proving the process can serve requests."""
    return HealthResponse(status="healthy", service="document-intelligence-api")
