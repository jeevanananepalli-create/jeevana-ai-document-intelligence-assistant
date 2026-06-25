"""Application entry point (composition root).

`create_app()` is an application factory: it builds and returns a configured
FastAPI instance. A factory (rather than a module-level global) keeps the app
testable — tests can build a fresh app with overridden settings — and is the
pattern most production FastAPI setups use.

Run locally with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Run startup and shutdown logic.

    Code before `yield` runs once on startup; code after runs on shutdown. This
    is where future phases will, for example, verify the database connection or
    warm a model. Phase 1 only logs lifecycle events.
    """
    settings = get_settings()
    logger.info("Starting up in '%s' environment", settings.app_env.value)
    yield
    logger.info("Shutting down")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="Document Intelligence API",
        version="0.1.0",
        description="AI Document Intelligence Assistant — backend API.",
        lifespan=lifespan,
        # Hide interactive docs in production; expose them in dev for review.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )

    # CORS: browsers block cross-origin requests by default. The frontend runs
    # on a different origin (localhost:3000) than the API (localhost:8000), so
    # we must explicitly allow it.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root-level liveness probe (unversioned), then the versioned API.
    app.include_router(health_router)
    app.include_router(api_router)

    return app


# The ASGI application object uvicorn imports and serves.
app = create_app()
