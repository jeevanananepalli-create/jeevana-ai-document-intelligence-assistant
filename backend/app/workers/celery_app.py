"""Celery application instance.

Celery is configured from the same Settings as the app: Redis is both the broker
(the queue the API pushes tasks onto) and the result backend. The task module is
listed in `include` so the worker registers it on startup.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "document_intelligence",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,  # a task is acked only after it finishes, so a crash re-runs it
    worker_prefetch_multiplier=1,  # one heavy task at a time per worker
    task_track_started=True,  # expose a 'started' state for monitoring
)
