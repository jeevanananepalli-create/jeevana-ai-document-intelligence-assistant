"""End-to-end test for the readiness probe.

Runs with or without a reachable database: the endpoint must always answer 200
(the probe itself works) and report a status consistent with its checks. When
the test database IS reachable (locally via Docker or in CI), it must report
ready/up.
"""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.main import create_app


def test_readiness_reports_consistent_status() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200  # always 200; LBs read the body
    body = response.json()
    database = body["checks"]["database"]["status"]
    assert database in {"up", "down"}
    expected = "ready" if database == "up" else "degraded"
    assert body["status"] == expected

    # When the suite runs with a real database configured (CI, local Docker),
    # readiness must actually pass.
    if os.environ.get("DATABASE_URL"):
        assert body == {"status": "ready", "checks": {"database": {"status": "up"}}}
