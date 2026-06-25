# AI Document Intelligence Assistant

[![CI](https://github.com/jeevana-ai/document-intelligence-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/jeevana-ai/document-intelligence-assistant/actions/workflows/ci.yml)

An AI-powered document processing platform that extracts, analyzes, and enables intelligent querying of uploaded documents using OCR, vector embeddings, and LLM-powered analysis.

## Project Status

**Current phase: Phase 1 — Engineering Foundation ✅ complete.**

The foundation is in place and verified (lint + type-check + tests green). AI
features are intentionally **not** built yet — see the
[development roadmap](docs/development-roadmap.md) for the phased plan.

| Capability | Status |
|------------|--------|
| Clean Architecture project skeleton | ✅ |
| FastAPI app + `GET /health` liveness probe | ✅ |
| Configuration management (typed, env-driven) | ✅ |
| PostgreSQL + Docker Compose dev environment | ✅ |
| Alembic migration framework | ✅ (scaffold; no business tables yet) |
| Password hashing + JWT utilities | ✅ (utilities only; no login flow yet) |
| Next.js frontend skeleton + routing | ✅ |
| Testing framework (pytest + Jest) | ✅ |
| CI pipeline (GitHub Actions) | ✅ |
| Upload / OCR / embeddings / search / chat | ⏳ later phases |

## Features

> The features below describe the **target** product. Items are delivered phase
> by phase; only the foundation is implemented today.



- **Document Upload**: Support for PDF, images (JPG/PNG), and DOCX files
- **Intelligent Text Extraction**: OCR via Tesseract for scanned documents, direct extraction for digital PDFs
- **AI Analysis**: Automatic summarization, entity extraction, and document classification
- **Semantic Search**: Vector-based similarity search across all uploaded documents
- **Document Q&A**: Ask natural language questions and get answers with source citations (RAG pipeline)
- **REST API**: Versioned API with JWT authentication and OpenAPI documentation
- **Web Dashboard**: Next.js frontend for document management, search, and chat

## Architecture

```
┌─────────────────────────────────────────────┐
│              Next.js Frontend               │
│        (Dashboard, Documents, Chat)         │
└──────────────────┬──────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────┐
│              FastAPI Backend                 │
│    ┌──────────────────────────────────┐     │
│    │      API Layer (Routers)         │     │
│    ├──────────────────────────────────┤     │
│    │   Application Layer (Use Cases)  │     │
│    ├──────────────────────────────────┤     │
│    │    Domain Layer (Pure Logic)     │     │
│    ├──────────────────────────────────┤     │
│    │  Infrastructure (DB, OCR, LLM)  │     │
│    └──────────────────────────────────┘     │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┴──────────┐
   ┌────▼─────┐        ┌─────▼────┐
   │PostgreSQL│        │  Redis   │
   │+ pgvector│        │ (broker) │
   └──────────┘        └──────────┘
```

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | FastAPI + Python 3.12 | Async, typed, auto OpenAPI docs |
| Database | PostgreSQL 16 + pgvector | Single store for relational + vector data |
| Task Queue | Celery + Redis | Durable async document processing |
| OCR | Tesseract + pdfminer | Strategy pattern, handles all doc types |
| Embeddings | sentence-transformers | Local-first, no API cost, swappable |
| LLM | OpenAI API (structured output) | Reliable schema-bound responses |
| Frontend | Next.js 15 + shadcn/ui | Industry standard, typed, accessible |
| CI/CD | GitHub Actions | Lint + type-check + test + build |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/jeevana-ai/document-intelligence-assistant.git
cd document-intelligence-assistant

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# Start the entire stack
docker compose up

# Backend API:  http://localhost:8000
# API Docs:     http://localhost:8000/docs
# Frontend:     http://localhost:3000
```

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── domain/              # Pure business logic (zero framework imports)
│   │   │   ├── entities/        # Objects with identity (User, Document)
│   │   │   ├── value_objects/   # Immutable values compared by content
│   │   │   ├── exceptions/      # Domain errors (not HTTP errors)
│   │   │   └── interfaces/      # Abstract ports (Protocols)
│   │   ├── application/         # Use cases + application services
│   │   │   ├── use_cases/
│   │   │   └── services/
│   │   ├── infrastructure/      # Concrete I/O implementing the interfaces
│   │   │   ├── database/        # SQLAlchemy engine, session, Base
│   │   │   ├── repositories/    # Data access implementations
│   │   │   └── external_services/  # OCR / LLM / storage clients (later)
│   │   ├── api/                 # HTTP edge
│   │   │   ├── health.py        # GET /health liveness probe
│   │   │   └── v1/              # Versioned routers
│   │   ├── core/                # Config, security, logging
│   │   │   └── config/
│   │   └── main.py             # App factory (composition root)
│   ├── migrations/             # Alembic migration framework
│   ├── tests/{unit,integration,e2e}/
│   ├── pyproject.toml          # Dependencies + ruff/mypy/pytest config
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── app/                # Next.js App Router pages (/, dashboard, documents, chat)
│       ├── components/         # UI components
│       ├── lib/                # API client (lib/api.ts)
│       └── types/              # TypeScript types
├── docs/                       # Architecture, decisions, DB design, roadmap
├── docker-compose.yml          # PostgreSQL + backend dev environment
└── .github/workflows/ci.yml    # CI pipeline (lint, type-check, test, build)
```

## Documentation

### Design & Architecture
- [Architecture](docs/architecture.md) — System design, data flows, design patterns
- [Technology Decisions](docs/technology-decisions.md) — Every choice with reasoning and alternatives
- [Database Design](docs/database-design.md) — Schema, indexes, query patterns
- [API Contract](docs/api-contract.md) — Complete API specification with request/response examples

### Development
- [Development Roadmap](docs/development-roadmap.md) — Phased implementation plan
- [Testing Strategy](docs/testing-strategy.md) — Unit, integration, and E2E testing approach with examples
- [Deployment Guide](docs/deployment-guide.md) — Local setup, Docker, migrations, CI/CD, and production considerations

### Reference
- [Glossary](docs/glossary.md) — Every technical term explained for beginners

## Why These Choices?

This project deliberately avoids the easy path of wrapping LangChain around an API. Instead, every component is built with understanding:

1. **The domain layer has zero infrastructure imports** — dependency inversion, not just dependency injection
2. **The RAG pipeline is hand-built** — each step (embed → retrieve → prompt → generate) is a separate, testable function
3. **pgvector instead of a dedicated vector database** — because at this scale, it's the architecturally correct choice
4. **Strategy pattern for OCR** — not a giant if/else, but extensible, testable extraction strategies
5. **Celery for processing** — because durability across restarts is a correctness property, not a nice-to-have

## Development

### Run with Docker (recommended)

```bash
cp .env.example .env          # then edit values as needed
docker compose up --build     # starts PostgreSQL + backend
# Backend API:  http://localhost:8000
# Liveness:     http://localhost:8000/health
# API Docs:     http://localhost:8000/docs
```

### Backend (local, without Docker)

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
#                                  source .venv/bin/activate   # macOS/Linux
pip install -e ".[dev]"       # or: uv pip install -e ".[dev]"

pytest --cov=app              # run tests with coverage
ruff check app tests          # lint
ruff format app tests         # format
mypy app                      # type-check
uvicorn app.main:app --reload # run the API
```

### Frontend (local)

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev                   # http://localhost:3000
npm test                      # component tests
npm run lint                  # lint
npm run build                 # production build
```

> Tooling note: the backend uses **ruff** (lint + format) and **mypy** (types);
> CI runs all of these on every push. `uv` is an optional faster alternative to
> `pip` — `pyproject.toml` works with both.

## License

MIT

---

Built by **Nanepalli Jeevana** — B.Tech CSE (Data Science)
