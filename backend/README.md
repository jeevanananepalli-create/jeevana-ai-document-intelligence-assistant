# Document Intelligence API

FastAPI backend for the AI Document Intelligence Assistant, built with Clean
Architecture.

The top-level repository README covers the full project overview, setup, and
development workflow. This backend README exists so packaging and container
builds that run from the `backend/` directory can resolve the project metadata
referenced by `pyproject.toml`.

## Layout

```text
app/
|-- domain/          # Pure business logic (entities, value objects, ports)
|-- application/     # Use cases
|-- infrastructure/  # DB, storage, extraction, embeddings, repositories
|-- api/             # FastAPI routers + dependencies
|-- core/            # Config, security, logging
|-- workers/         # Celery task pipeline
migrations/          # Alembic migrations
tests/               # unit / integration / e2e
```

## Common Commands

```bash
pip install -e ".[dev]"      # install (add ".[dev,ml]" for the embedding model)
uvicorn app.main:app --reload
alembic upgrade head
pytest --cov=app
ruff check app tests && ruff format --check app tests
mypy app
```

Configuration is read from environment variables (see the root `.env.example`).
