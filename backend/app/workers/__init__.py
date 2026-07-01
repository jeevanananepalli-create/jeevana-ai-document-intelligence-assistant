"""Celery worker: the async document-processing pipeline.

The worker runs the same `ProcessDocumentUseCase` the rest of the app defines,
wiring it to the real PostgreSQL, storage, and embedding adapters. Keeping the
Celery task a thin wrapper around the use case means the pipeline logic is
tested without a broker or worker running.
"""
