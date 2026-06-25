"""Tests for the liveness health endpoint.

This is the first test in the project on purpose: it proves the whole app can
be built, wired, and respond to a request. If this fails, something fundamental
(imports, configuration, routing) is broken.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    """The endpoint responds successfully."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_expected_payload(client: TestClient) -> None:
    """The endpoint returns the exact documented liveness payload."""
    response = client.get("/health")
    assert response.json() == {
        "status": "healthy",
        "service": "document-intelligence-api",
    }
