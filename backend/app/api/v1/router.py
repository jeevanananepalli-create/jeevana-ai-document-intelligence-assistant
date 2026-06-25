"""Version 1 API router aggregator.

This is the single place where all `/api/v1` sub-routers are collected and
mounted. Feature routers (auth, documents, search, qa) will be `include_router`-ed
here as later phases add them. It is intentionally empty of business endpoints in
Phase 1, but wiring it now means new features plug in with a single line.
"""

from __future__ import annotations

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")

# Later phases:
# from app.api.v1 import auth, documents, search, qa
# api_router.include_router(auth.router)
# api_router.include_router(documents.router)
