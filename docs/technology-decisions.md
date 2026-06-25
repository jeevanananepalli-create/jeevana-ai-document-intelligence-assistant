# Technology Decisions

Every technology in this project was chosen with reasoning, alternatives considered, and trade-offs documented. This document serves as a reference for understanding *why* these choices were made.

---

## 1. Backend Framework: FastAPI

### Decision
Use FastAPI as the Python web framework.

### Alternatives Considered

| Framework | Pros | Cons |
|-----------|------|------|
| **Django** | Batteries-included, mature ORM, admin panel | Synchronous by default, ORM fights dependency inversion, heavy for an API-only backend |
| **Flask** | Simple, lightweight, flexible | No async support, no built-in validation, requires assembling many extensions |
| **FastAPI** | Async-native, Pydantic validation, auto OpenAPI docs, dependency injection, type-safe | Younger ecosystem, fewer tutorials for complex patterns |

### Why FastAPI

1. **Async-native**: Document processing involves I/O-heavy operations (file storage, database queries, embedding API calls). Async handlers prevent blocking the event loop.
2. **Pydantic v2 integration**: Request/response validation happens at the framework boundary automatically. Invalid requests never reach business logic.
3. **Auto-generated OpenAPI docs**: The `/docs` endpoint serves as both developer documentation and a live API explorer. This is visible portfolio value — a reviewer can interact with your API without reading code.
4. **Dependency injection**: FastAPI's `Depends()` maps cleanly to Clean Architecture's dependency inversion. Abstract ports are resolved to concrete implementations at the router level.
5. **Type safety**: Python type hints are not just documentation — FastAPI uses them for validation, serialization, and documentation generation.

### Trade-offs Accepted
- Smaller ecosystem than Django (fewer off-the-shelf plugins)
- Must assemble authentication, admin, and ORM separately
- These trade-offs are acceptable because they force explicit architectural decisions, which is the point of this project

---

## 2. Language & Runtime: Python 3.12

### Decision
Python 3.12+ with `uv` as the package manager.

### Why Python
- Natural choice for AI/ML workloads — all major libraries (sentence-transformers, OpenAI SDK, Tesseract bindings) have first-class Python support
- Strong typing via type hints + mypy for static analysis
- Rich ecosystem for document processing (pdfminer, python-docx, Pillow)

### Why uv (not pip, not poetry)
- **pip**: No lockfile, no dependency resolution guarantees, slow
- **poetry**: Mature but slow dependency resolution, complex `pyproject.toml` format
- **uv**: 10-100x faster than pip, deterministic lockfile (`uv.lock`), compatible with `pyproject.toml` standard, backed by Astral (ruff creators), rapidly becoming industry standard

### Trade-offs
- uv is newer — some CI environments may not have it pre-installed (solved with a one-line install in CI)

---

## 3. Database: PostgreSQL 16 + pgvector

### Decision
Single PostgreSQL instance with the `pgvector` extension for both relational data and vector embeddings.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **PostgreSQL + pgvector** | Single database, SQL JOINs across relational + vector data, free, well-understood | Slower than dedicated vector DBs at millions of vectors |
| **PostgreSQL + Pinecone** | Pinecone optimized for vector search | Adds external dependency, $70+/month, splits data across two systems |
| **PostgreSQL + Qdrant** | Self-hosted, fast vector search | Additional Docker service, separate query language, operational overhead |
| **SQLite + ChromaDB** | Zero infrastructure | SQLite lacks concurrent writes, ChromaDB not production-ready |

### Why pgvector

1. **Operational simplicity**: One database to manage, backup, and monitor. No separate vector database to configure, scale, or pay for.
2. **SQL JOINs**: Filtering search results by user_id, document_type, or date range is a simple `WHERE` clause. Dedicated vector databases require metadata filtering, which is often limited or slow.
3. **Sufficient performance**: With an IVFFlat index, pgvector handles ~100K vectors with sub-10ms query latency. This project will never exceed this scale.
4. **Learning value**: Understanding that vector search is a database indexing problem (not a separate service category) demonstrates deeper knowledge than using a managed API.

### Index Strategy
- **IVFFlat** (Inverted File with Flat compression): Approximate nearest neighbor search
- Configure `lists` parameter based on dataset size: `lists = sqrt(num_vectors)`
- Trade-off: more lists = faster search but lower recall. Tune empirically.

### Trade-offs Accepted
- At >1M vectors, a dedicated vector database (Qdrant, Milvus) would be necessary
- HNSW index (available in pgvector 0.5+) could be used for better recall, at cost of more memory

---

## 4. Task Queue: Celery + Redis

### Decision
Use Celery for async document processing with Redis as the message broker.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **FastAPI BackgroundTasks** | Zero setup, built-in | Not durable — tasks lost on server restart, no retry logic, no monitoring |
| **Celery + Redis** | Durable, retries, monitoring (Flower), battle-tested | Additional dependency, complexity |
| **Celery + RabbitMQ** | RabbitMQ has better delivery guarantees | Additional Docker service, more complex setup |
| **Dramatiq** | Simpler API than Celery | Smaller ecosystem, fewer monitoring tools |
| **Huey** | Lightweight | Limited features for complex workflows |

### Why Celery + Redis

1. **Durability**: If the server restarts mid-OCR, the task remains in Redis and will be retried. BackgroundTasks would silently lose the work.
2. **Retry with backoff**: OCR and LLM calls can fail transiently. Celery provides `autoretry_for`, `retry_backoff`, and `max_retries` out of the box.
3. **Redis dual-purpose**: Redis serves as both the Celery broker and the application cache (rate limiting counters, session data). One service, two uses.
4. **Monitoring**: Celery Flower provides a web UI for task monitoring — useful for debugging and demonstrations.

### Trade-offs Accepted
- Celery adds operational complexity (worker process management)
- Redis is not as durable as RabbitMQ for message delivery (acceptable for this use case — worst case, a document is re-processed)

---

## 5. OCR Engine: Tesseract + pdfminer + python-docx

### Decision
Use a strategy pattern with multiple extraction engines selected by file type.

### Extraction Strategy

| File Type | Primary Strategy | Fallback |
|-----------|-----------------|----------|
| PDF (with embedded text) | `pdfminer.six` | Tesseract OCR |
| PDF (scanned/image-based) | `pdf2image` → Tesseract | None |
| Images (JPG, PNG, TIFF) | Tesseract via `pytesseract` | None |
| DOCX | `python-docx` | None |

### Why Not Cloud OCR (Google Vision, AWS Textract)?

- **Cost**: Cloud OCR charges per page. During development, hundreds of test documents would incur real costs.
- **Dependency**: Requires cloud credentials and network access. The project should be fully runnable offline.
- **Learning value**: Using Tesseract directly shows understanding of OCR as a technology, not just an API.
- **Easy upgrade path**: The strategy pattern makes it trivial to add a `GoogleVisionExtractionStrategy` later without changing any application logic.

### Why the strategy pattern?

The naive approach is a giant `if/elif` block that checks file type and calls different libraries. The strategy pattern:
- Makes each extraction method independently testable
- Follows Open/Closed Principle — add new formats without modifying existing code
- Is a recognized design pattern that demonstrates software engineering knowledge

---

## 6. Embeddings: sentence-transformers (Local) with OpenAI Fallback

### Decision
Use `all-MiniLM-L6-v2` from sentence-transformers as the default, with OpenAI `text-embedding-3-small` as a configurable alternative.

### Comparison

| Model | Dimensions | Speed | Cost | Quality (MTEB) |
|-------|-----------|-------|------|-----------------|
| `all-MiniLM-L6-v2` | 384 | ~14K sentences/sec on CPU | Free | Good |
| `text-embedding-3-small` | 1536 | API-limited | $0.02/1M tokens | Very good |
| `text-embedding-3-large` | 3072 | API-limited | $0.13/1M tokens | Best |

### Why Local-First

1. **Zero cost during development**: No API key required to develop, test, and demo
2. **Demonstrates understanding**: Shows that embeddings are model outputs, not magic. You chose a model, you know its dimension, you understand the quality trade-offs.
3. **Offline capability**: The full pipeline works without internet access
4. **Swappable**: The embedding port (interface) makes switching to OpenAI a one-line config change

### Architecture Implication

```python
class EmbeddingPort(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

Both `SentenceTransformerEmbedding` and `OpenAIEmbedding` implement this protocol. The application layer depends on the protocol, never on the concrete class. This is dependency inversion in practice.

---

## 7. LLM Integration: OpenAI API with Structured Output (No LangChain)

### Decision
Use the OpenAI SDK directly with structured outputs via Pydantic models. Do NOT use LangChain.

### Why Not LangChain

| Concern | LangChain | Direct SDK |
|---------|-----------|------------|
| Abstraction level | Hides pipeline details | Every step is visible and testable |
| API stability | Breaking changes across versions | Stable, versioned API |
| Debugging | Opaque chain internals | Simple function calls |
| Interview value | "I used LangChain" | "I built a RAG pipeline — let me walk you through each step" |
| Learning | Framework knowledge | Fundamental knowledge |

### Why Structured Output

The LLM returns structured data (summaries, entities, classifications) not free-form text. Using OpenAI's structured output mode with a Pydantic schema:

1. **Guarantees valid JSON** matching the schema — no parsing failures
2. **Type-safe responses** — the result is a Pydantic model, not a string
3. **Testable contracts** — the output schema is a test fixture

### RAG Pipeline (Hand-Built)

Each step is a separate, testable function:

1. **Embed query** → vector
2. **Retrieve** → pgvector cosine similarity, top-k chunks
3. **Construct prompt** → system instructions + retrieved context + user question
4. **Generate** → LLM call with structured output
5. **Format response** → answer + source citations

This is approximately 200 lines of code. It is worth more than 5 lines of `RetrievalQAChain` because you can explain every decision.

---

## 8. Frontend: Next.js 15 (App Router) + shadcn/ui

### Decision
Use Next.js with TypeScript for the web dashboard.

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **React + Vite** | Simple, fast dev server | No SSR, no file-based routing, requires manual setup |
| **Next.js** | File-based routing, SSR, industry standard | Heavier, Vercel-centric |
| **Svelte/SvelteKit** | Small bundle, reactive | Smaller ecosystem, fewer jobs |
| **Plain HTML + HTMX** | Ultra-simple | Limited interactivity for chat UI |

### Why Next.js

1. **Industry standard**: Most React projects at Google and similar companies use a meta-framework
2. **TypeScript by default**: Type safety across the entire frontend
3. **App Router**: React Server Components, layouts, and loading states built-in
4. **File-based routing**: Convention over configuration — reviewers instantly understand the URL structure from the folder structure

### Why shadcn/ui (not Material UI, not Chakra)

- **No dependency lock-in**: Components are copied into your project, not installed as a package
- **Built on Radix UI**: Accessible by default (ARIA attributes, keyboard navigation)
- **Customizable**: Tailwind CSS utility classes, not opaque component styles
- **Current industry trend**: Widely adopted in 2024-2025

---

## 9. Containerization: Docker + Docker Compose

### Decision
Full containerization with multi-stage Dockerfile builds and Docker Compose for local orchestration.

### Why Docker

- **Reproducible environments**: "Works on my machine" is eliminated
- **One-command startup**: `docker compose up` starts the entire stack
- **Portfolio impact**: A reviewer can run the project in under 5 minutes without installing Python, Node.js, PostgreSQL, or Redis locally

### Multi-Stage Builds

```dockerfile
# Stage 1: Build (includes dev deps, compilers)
FROM python:3.12-slim AS builder
# Install deps, build wheels

# Stage 2: Runtime (minimal image)
FROM python:3.12-slim AS runtime
# Copy only wheels and application code
```

This reduces image size by 60-70% and demonstrates awareness of container best practices.

---

## 10. CI/CD: GitHub Actions

### Pipeline Design

```yaml
on: [push, pull_request]

jobs:
  lint:        # ruff (format + lint) + mypy (type check)
  test:        # pytest with coverage, fail if < 80%
  build:       # docker build (verifies Dockerfile validity)
  frontend:    # npm ci + type-check + lint + build
```

### Tool Choices

| Tool | Purpose | Why This One |
|------|---------|-------------|
| **ruff** | Linting + formatting | Replaces flake8 + black + isort in one tool. 10-100x faster. |
| **mypy** | Static type checking | Catches type errors before runtime. Strictest Python type checker. |
| **pytest** | Testing | Industry standard. Fixtures, parametrize, async support. |
| **pytest-cov** | Coverage reporting | Enforce 80% minimum coverage in CI. |

---

## 11. Logging: structlog

### Decision
Use `structlog` for structured JSON logging instead of Python's built-in `logging`.

### Why
- **Structured output**: JSON logs are machine-parseable (queryable in any log aggregator)
- **Request correlation**: Add `request_id` to every log entry for tracing
- **Context binding**: Attach user_id, document_id to logs without passing them through every function
- **Development mode**: Pretty-prints colored logs in dev, JSON in production

---

## 12. Security: Fail-Fast Configuration Guards

### Decision
Validate security-critical configuration at startup and **refuse to boot** when
it is unsafe, rather than starting and hoping. The first such guard: if
`APP_ENV=production` **and** `JWT_SECRET_KEY` is still the public placeholder
shipped in `.env.example`, `Settings` raises and the application does not start.

### Why
The JWT secret is what makes a token unforgeable — it is the *only* thing
stopping an attacker from minting a token that says "I am any user I like". The
placeholder value lives in the public repository, so anyone could read it. If a
deploy accidentally ran with the default secret, the entire authentication
system would be silently worthless: tokens could be forged at will, and nothing
would look broken.

Two ways to handle a dangerous misconfiguration:

| Approach | Result |
|----------|--------|
| Warn in logs and continue | The app runs insecurely; the warning is easily missed; the vulnerability is live in production |
| **Fail fast at startup** (chosen) | The deploy visibly fails with a clear message; the insecure state can never reach users |

Failing fast turns a silent security hole into a loud, immediate deployment
error — the cheapest possible place to catch it.

### How
A Pydantic `model_validator(mode="after")` on `Settings`
(`app/core/config/settings.py`) runs automatically whenever settings are
constructed (i.e. at startup). The placeholder is defined once as
`DEFAULT_JWT_SECRET_KEY` so the field default, the guard, and the tests share a
single source of truth. The check is covered by tests asserting that
development accepts the placeholder while production rejects it.

### Trade-offs
- A developer who sets `APP_ENV=production` locally without a real secret will
  hit the error. That friction is intentional and correct — "production" should
  mean production-grade configuration.
- This is one guard, not a framework. Future security-critical settings (e.g.
  a real database password, an API key) can follow the same fail-fast pattern.

---

## Summary Decision Matrix

| Decision | Chosen | Runner-Up | Key Differentiator |
|----------|--------|-----------|-------------------|
| Backend framework | FastAPI | Django | Async + dependency injection |
| Package manager | uv | poetry | 10-100x faster, modern standard |
| Database | PostgreSQL + pgvector | PostgreSQL + Qdrant | Single system, SQL JOINs on vectors |
| Task queue | Celery + Redis | FastAPI BackgroundTasks | Durability across restarts |
| OCR | Tesseract (local) | Google Cloud Vision | Offline, free, demonstrates understanding |
| Embeddings | sentence-transformers | OpenAI text-embedding-3 | Free, local-first, swappable |
| LLM framework | Direct OpenAI SDK | LangChain | Transparency, testability, interview value |
| Frontend | Next.js + shadcn/ui | React + Vite | SSR, file routing, industry standard |
| Linter/formatter | ruff | flake8 + black | Single tool, 100x faster |
| CI | GitHub Actions | GitLab CI | Native GitHub integration |
