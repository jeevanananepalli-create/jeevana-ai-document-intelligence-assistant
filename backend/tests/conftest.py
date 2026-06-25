"""Shared pytest fixtures.

`conftest.py` is auto-discovered by pytest; fixtures defined here are available
to every test without importing. Building the app per-test via the factory keeps
tests isolated from each other.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A FastAPI TestClient backed by a freshly-built app instance.

    TestClient drives the real ASGI app in-process (no network, no running
    server), so these tests are fast and deterministic.
    """
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
