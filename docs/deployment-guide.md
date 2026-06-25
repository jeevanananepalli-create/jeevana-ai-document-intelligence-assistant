# Deployment Guide

This guide explains how to run the application — from a laptop during
development all the way to a production server — and the reasoning behind each
step. It documents the **planned deployment approach**; where something is not
built yet, it is marked _(planned)_ so the guide stays honest about what exists
today.

It pairs with [architecture.md](architecture.md) (how the system is structured),
[technology-decisions.md](technology-decisions.md) (why these tools), and
[testing-strategy.md](testing-strategy.md) (how CI verifies changes).

> **What exists today (Phase 1 foundation):** the FastAPI backend with a
> `GET /health` endpoint, a `docker compose` dev environment (PostgreSQL +
> backend), the Alembic migration framework, and a CI pipeline. Feature code
> (upload, OCR, embeddings, search, chat) and a hosted production deployment are
> later phases.

---

## 1. Local Development Setup

There are two ways to run the project locally. **Docker is the recommended path**
because it gives everyone the exact same PostgreSQL and Python versions with one
command. The manual path is useful when you want to run or debug a single piece
quickly.

### Option A — Docker (recommended)

```bash
# 1. Copy the environment template and adjust values if needed
cp .env.example .env

# 2. Start PostgreSQL + the backend together
docker compose up --build
```

What you get:

| URL | What it is |
|-----|------------|
| http://localhost:8000/health | Liveness probe — should return `{"status":"healthy",...}` |
| http://localhost:8000/docs | Interactive API documentation (Swagger UI) |
| http://localhost:5432 | PostgreSQL (inside the Compose network the host is `db`) |

The backend container waits for the database's health check to pass before
starting, so you never see connection errors from a database that isn't ready
yet.

### Option B — Backend without Docker

Useful for running tests or the linter quickly.

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate     # Windows Git Bash
# source .venv/bin/activate        # macOS / Linux
pip install -e ".[dev]"           # or: uv pip install -e ".[dev]"

uvicorn app.main:app --reload     # run the API (needs a reachable PostgreSQL)
pytest --cov=app                  # run tests with coverage
ruff check app tests              # lint
mypy app                          # type-check
```

> Note: running the API this way still needs a PostgreSQL to connect to. The
> easiest option is to start just the database with `docker compose up db`.

### Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev                       # http://localhost:3000
```

---

## 2. Docker Deployment

The backend ships as a container image so it runs identically everywhere — your
laptop, CI, and production. This removes the "works on my machine" class of
problems entirely.

### The image (`backend/Dockerfile`)

It is a **multi-stage build**:

1. **Builder stage** installs the Python dependencies (including the C toolchain
   needed to build the PostgreSQL driver) into an isolated virtualenv.
2. **Runtime stage** copies only that virtualenv and the application code — no
   compilers, no build tools — producing a smaller, cleaner image.

Two important hardening choices:

| Choice | Why it matters |
|--------|----------------|
| Runs as a **non-root** user | If the process is ever compromised, the attacker does not have root inside the container |
| Slim base image, no build tools at runtime | Smaller attack surface and faster image pulls |

### The dev stack (`docker-compose.yml`)

Compose describes the services and how they connect:

| Service | Image / build | Purpose |
|---------|---------------|---------|
| `db` | `pgvector/pgvector:pg16` | PostgreSQL 16 with the pgvector extension available |
| `backend` | builds `./backend` | The FastAPI app |

Key details:
- A **named volume** (`pgdata`) keeps database data across `docker compose down`
  (but a `down -v` wipes it).
- A **health check** on `db` gates the backend's startup.
- The backend's `DATABASE_URL` is overridden to use the host `db` (the service
  name) instead of `localhost`, because inside the Compose network that is how
  containers reach each other.

> **Building a production image** _(planned)_: the same Dockerfile is used. A
> release process tags the image with a version, pushes it to a container
> registry, and a hosting platform runs it. Redis, Celery workers, and the
> frontend are added as their own services/containers in later phases.

---

## 3. Environment Configuration

All configuration comes from environment variables, validated once at startup by
the typed `Settings` class (`app/core/config/settings.py`). See
[technology-decisions.md](technology-decisions.md) for the reasoning.

### The golden rules

1. **Never commit `.env`.** It holds real secrets and is git-ignored. Only the
   placeholder `.env.example` is committed.
2. **Never hard-code secrets** in source code or Docker images. They are injected
   at runtime by the environment / a secret manager.
3. **Different values per environment.** The same image runs in dev and
   production; only the environment variables differ.

### Variables that change between environments

| Variable | Development | Production |
|----------|-------------|------------|
| `APP_ENV` | `development` | `production` |
| `APP_DEBUG` | `true` | `false` |
| `DATABASE_URL` | local / Compose `db` | managed database host |
| `JWT_SECRET_KEY` | placeholder is fine | **must be a strong random value** |
| `CORS_ORIGINS` | `http://localhost:3000` | the real frontend domain(s) |

### The production secret guard

The application **refuses to start** if `APP_ENV=production` while
`JWT_SECRET_KEY` is still the public placeholder from `.env.example`. This turns
a dangerous misconfiguration (forgeable login tokens) into a loud, immediate
startup failure instead of a silent vulnerability. Generate a real secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

See [technology-decisions.md](technology-decisions.md) §12 for the full rationale.

---

## 4. Database Migration Process

The database schema is changed through **Alembic migrations** — version-controlled
scripts, one per change, checked into git. This is essential because creating
tables from models only works once; altering an existing production database
safely requires migrations. See [database-design.md](database-design.md) for the
schema itself.

### Why migrations (not `create_all()`)

| Approach | Problem |
|----------|---------|
| `Base.metadata.create_all()` | Only creates *missing* tables. It cannot add a column or change a type on an existing database. |
| **Alembic migrations** | Each change is a reviewed, reversible script (`upgrade()` / `downgrade()`) recorded in git history. |

### Everyday commands (run from `backend/`)

```bash
# Generate a migration by diffing your models against the database.
# (Requires ORM models to exist — none do yet in Phase 1.)
alembic revision --autogenerate -m "create users table"

# Apply all pending migrations (bring the DB up to the latest version)
alembic upgrade head

# Roll back the most recent migration
alembic downgrade -1
```

Alembic reads the database URL from the same `Settings` as the app (the **sync**
URL, `DATABASE_URL_SYNC`), so there is one source of truth and no secret lives in
a committed file.

### Where migrations run

| Environment | When migrations run |
|-------------|---------------------|
| Local dev | You run `alembic upgrade head` manually after pulling new migrations |
| CI | Migrations are applied to a throwaway test database before integration tests _(planned, when DB tests land)_ |
| Production _(planned)_ | As an explicit **release step** — `alembic upgrade head` runs **before** new app instances start serving traffic |

> Running migrations as a separate release step (not on app startup) is
> deliberate: it keeps schema changes predictable, reviewable, and decoupled from
> the number of running instances.

---

## 5. CI/CD Deployment Flow

### Continuous Integration (CI) — implemented

On every push and pull request, GitHub Actions (`.github/workflows/ci.yml`) runs
a quality gate. If anything fails, the red ✗ marks the change as unsafe to merge
— automatically, before a human reviews it.

```
push / pull request
        │
        ▼
┌──────────────────────────────────────────────┐
│ backend job                                   │
│   1. install dependencies                     │
│   2. ruff      (lint)                          │
│   3. ruff      (format check)                  │
│   4. mypy      (type check)                    │
│   5. pytest    (tests + ≥80% coverage gate)    │
├──────────────────────────────────────────────┤
│ frontend job:  lint → test → build            │
├──────────────────────────────────────────────┤
│ docker-build job:  build the backend image    │
│                    (proves the Dockerfile works)│
└──────────────────────────────────────────────┘
        │
        ▼
   ✅ green  →  safe to merge        ✗ red  →  blocked
```

The coverage gate (`--cov-fail-under=80`) enforces the project's testing standard
automatically rather than relying on a reviewer to remember it.

### Continuous Deployment (CD) — _planned_

CD is **not implemented yet** — CI currently *builds* the image but does not
*ship* it. The planned flow, once a hosting target is chosen:

```
merge to main  →  CI passes  →  build & tag image  →  push to registry
      →  run `alembic upgrade head`  →  roll out new app instances
      →  health check (/health) passes  →  traffic shifts over
```

Keeping CI and CD as separate stages means every merge is verified, while actual
releases stay a deliberate, observable step.

---

## 6. Production Considerations

A checklist of what changes when moving from a laptop to real users. Most of
these are **future** items, documented now so the path is clear.

### Configuration & security
- [ ] `APP_ENV=production` and `APP_DEBUG=false` (this also hides `/docs`).
- [ ] A strong, random `JWT_SECRET_KEY` supplied via a secret manager (the
      startup guard enforces this).
- [ ] `CORS_ORIGINS` set to the real frontend domain(s), never `*`.
- [ ] Secrets injected by the platform, never baked into the image or git.

### Database
- [ ] A **managed PostgreSQL** (e.g. RDS / Cloud SQL) with the pgvector
      extension, automated backups, and least-privilege credentials.
- [ ] Connection pool sizing (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) tuned to the
      database's connection limit and the number of app instances.
- [ ] Migrations applied as a release step before new instances start.

### Reliability & scaling
- [ ] Run multiple stateless backend instances behind a **load balancer** that
      polls `/health`; unhealthy instances are pulled from rotation. Stateless
      JWT auth means any instance can serve any request.
- [ ] A **readiness probe** (`GET /api/v1/health`, _planned_) that also checks
      the database/Redis before an instance receives traffic.
- [ ] Redis + Celery workers (Phase 2) deployed as separate scalable services.

### Observability
- [ ] Structured logs shipped to a central aggregator, with a request id on
      every entry for tracing.
- [ ] Basic metrics and alerting on error rate, latency, and queue depth.

### Cost & safety
- [ ] Resource limits on containers so one workload cannot starve others.
- [ ] A rollback plan: keep the previous image tagged so a bad release can be
      reverted quickly, and ensure migrations have working `downgrade()` paths.

---

## Summary

| Stage | Command / mechanism | Status |
|-------|--------------------|--------|
| Local dev | `docker compose up --build` | ✅ implemented |
| Run tests / lint | `pytest`, `ruff`, `mypy` | ✅ implemented |
| Build image | `backend/Dockerfile` (multi-stage) | ✅ implemented |
| Apply schema | `alembic upgrade head` | ✅ framework ready (no tables yet) |
| CI quality gate | GitHub Actions on every push | ✅ implemented |
| CD release | build → push → migrate → roll out | ⏳ planned |
| Production hosting | managed DB + load-balanced instances | ⏳ planned |
