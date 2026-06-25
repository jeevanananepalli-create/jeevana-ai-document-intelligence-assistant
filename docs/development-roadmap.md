# Development Roadmap

## Overview

This roadmap breaks the project into 6 phases, each building on the previous. Every phase produces a working, testable increment. The project is designed so that even Phase 1 alone demonstrates engineering quality.

**Estimated total effort**: 4-5 weeks (part-time, ~3-4 hours/day)

---

## Phase 1: Foundation & Infrastructure (Week 1)

### Goal
Set up the project skeleton with CI, database, Docker, and the security
primitives — before writing any feature code.

### Why start here
A Google reviewer will look at your project structure, CI pipeline, and Docker setup before reading any business logic. If these are clean, you've already passed the first filter.

> **Scope note (important).** Phase 1 is deliberately split into the *engineering
> foundation* (everything below that is checked) and the *authentication
> feature* (login/register endpoints, the `users` table, protected routes, rate
> limiting). Only the foundation is built now. The authentication **utilities**
> (password hashing + JWT helpers) ship here as tested building blocks; the
> login **flow** and the first business migration move to the start of the
> feature phases. This keeps the foundation free of premature feature code.

### Tasks

#### 1.1 Project Skeleton ✅
- [x] Initialize `backend/` with `pyproject.toml` (installable with `uv` or `pip`)
- [x] Configure `ruff` (linting + formatting) and `mypy` (type checking)
- [x] Create the Clean Architecture folder structure:
  ```
  app/{domain, application, infrastructure, api, core}/ + main.py
  # domain/{entities, value_objects, exceptions, interfaces}
  # (workers/ is added with Celery in Phase 2)
  ```
- [x] Set up `pytest` with `conftest.py` and basic test structure
- [x] Create `.env.example` with all required environment variables

#### 1.2 Database & Config ✅ (foundation) / ⏳ (first migration)
- [x] Write `docker-compose.yml` with PostgreSQL 16 + pgvector (Redis added in Phase 2)
- [x] Configure SQLAlchemy async engine with `asyncpg` + connection pooling
- [x] Set up Alembic migration framework (`migrations/`, `env.py`, `alembic.ini`)
- [x] Write Pydantic Settings class (`app/core/config/settings.py`)
- [ ] Create initial migration: `users` table, pgvector extension *(deferred — first feature phase, no business tables in the foundation)*

#### 1.3 Authentication
- [x] Add password hashing with bcrypt (`app/core/security.py`)
- [x] Add JWT create/decode utilities + configuration structure
- [ ] Implement user registration endpoint (`POST /auth/register`) *(deferred — feature phase)*
- [ ] Implement login endpoint (`POST /auth/login`) returning JWT *(deferred)*
- [ ] Implement token refresh (`POST /auth/refresh`) *(deferred)*
- [ ] Add `get_current_user` dependency for protected routes *(deferred)*
- [ ] Rate limiting on auth endpoints via Redis + slowapi *(deferred — needs Redis, Phase 2)*

#### 1.4 CI Pipeline ✅
- [x] GitHub Actions workflow: lint (ruff), format check, type-check (mypy), test (pytest)
- [x] Fail pipeline if test coverage < 80% (`--cov-fail-under=80`)
- [x] Docker build step (validates the backend Dockerfile)
- [x] Frontend job: lint + test + build
- [x] Add CI badge to README

#### 1.5 Tests for Phase 1 ✅ (unit) / ⏳ (integration)
- [x] Unit tests: password hashing, JWT creation/validation/expiry
- [x] API test: `GET /health` liveness endpoint
- [x] Frontend component test (home page renders)
- [x] Verify 80%+ coverage on Phase 1 code (currently ~85%)
- [ ] Integration tests: user registration, login, token refresh (real DB via testcontainers) *(deferred — arrives with the auth feature)*

### Deliverable ✅
A running API with a health endpoint, security utilities, CI green (lint +
type-check + tests + Docker build), Docker Compose dev environment, a Next.js
frontend skeleton, and a clean Clean-Architecture project structure. Zero
feature code, but the foundation is production-grade.

---

## Phase 2: Document Upload & Processing Pipeline (Week 2)

### Goal
Implement the core document processing pipeline: upload → store → OCR → chunk → embed → store vectors.

### Why this is the technical core
This phase contains the most technically interesting code: the strategy pattern for extraction, the chunking algorithm, and the embedding pipeline. Invest the most time and care here.

### Tasks

#### 2.1 Domain Layer
- [ ] Define `Document` and `DocumentChunk` domain models (dataclasses)
- [ ] Define Ports: `DocumentRepository`, `StoragePort`, `EmbeddingPort`
- [ ] Implement `TextChunker` service (recursive splitting with configurable chunk size/overlap)
- [ ] Unit tests for `TextChunker` with various input sizes and edge cases

#### 2.2 File Upload
- [ ] `POST /documents/upload` endpoint
- [ ] File validation: MIME type checking, size limit (50MB default)
- [ ] Store raw file to local disk (with `StoragePort` abstraction)
- [ ] Create `Document` record with `status = uploaded`
- [ ] Return `202 Accepted` with `document_id`

#### 2.3 Extraction Strategies
- [ ] `ExtractionStrategy` protocol
- [ ] `PDFTextExtractionStrategy` — using pdfminer.six
- [ ] `PDFOCRExtractionStrategy` — pdf2image + pytesseract
- [ ] `ImageOCRExtractionStrategy` — pytesseract
- [ ] `DocxExtractionStrategy` — python-docx
- [ ] Strategy factory that selects based on MIME type
- [ ] Detection: is a PDF text-based or scanned?

#### 2.4 Celery Worker Pipeline
- [ ] Configure Celery app with Redis broker
- [ ] `process_document` task:
  1. Load document record
  2. Select extraction strategy
  3. Extract text
  4. Chunk text using `TextChunker`
  5. Generate embeddings (sentence-transformers)
  6. Store chunks + vectors in PostgreSQL
  7. Update document status to `completed` or `failed`
- [ ] Retry configuration with exponential backoff

#### 2.5 Document Retrieval
- [ ] `GET /documents` — paginated list for current user
- [ ] `GET /documents/{id}` — document detail with extracted text
- [ ] `GET /documents/{id}/status` — processing status check
- [ ] `DELETE /documents/{id}` — delete document and associated chunks

#### 2.6 Database Migration
- [ ] Alembic migration for `documents` and `document_chunks` tables
- [ ] IVFFlat index on `embedding` column

#### 2.7 Tests for Phase 2
- [ ] Unit tests: text chunker (various sizes, overlap, edge cases)
- [ ] Unit tests: strategy factory (correct strategy selection)
- [ ] Integration tests: document upload, processing pipeline (testcontainers)
- [ ] E2E tests: upload → process → retrieve flow via TestClient

### Deliverable
Upload a PDF, it gets processed (OCR + chunked + embedded), and you can retrieve the extracted text and chunks. The core pipeline works end-to-end.

---

## Phase 3: AI Analysis Layer (Week 3, Days 1-3)

### Goal
Add LLM-powered document analysis: summarization, entity extraction, and document classification.

### Tasks

#### 3.1 LLM Port & Implementation
- [ ] Define `LLMPort` protocol (structured output method)
- [ ] Implement `OpenAILLM` with structured output via Pydantic models
- [ ] Define output schemas:
  ```python
  class DocumentAnalysis(BaseModel):
      summary: str
      key_entities: list[Entity]
      document_type: Literal["contract", "research", "invoice", "report", "letter", "other"]
      language: str
      confidence: float
  ```

#### 3.2 Analysis Use Case
- [ ] `AnalyzeDocumentUseCase` — called after text extraction in the Celery pipeline
- [ ] Send extracted text (or first N tokens if too long) to LLM
- [ ] Store analysis results in `documents` table (summary, entities, document_type)
- [ ] Handle LLM failures gracefully — document is still `completed` even if analysis fails

#### 3.3 API Endpoints
- [ ] `GET /documents/{id}/analysis` — returns summary, entities, classification
- [ ] Analysis data included in document detail response

#### 3.4 Tests
- [ ] Unit tests: analysis use case with mocked LLM port
- [ ] Unit tests: output schema validation
- [ ] Integration tests: full pipeline including analysis step

### Deliverable
Uploaded documents are automatically summarized, entities are extracted, and the document type is classified. All results are available via API.

---

## Phase 4: Semantic Search & RAG Q&A (Week 3, Days 4-7)

### Goal
Implement the RAG pipeline: semantic search across documents and natural language Q&A with source citations.

### Tasks

#### 4.1 Semantic Search
- [ ] `SemanticSearchUseCase`:
  1. Embed user query
  2. pgvector cosine similarity search across user's chunks
  3. Return top-k results with similarity scores
- [ ] `POST /search` endpoint (query string + optional filters)
- [ ] Filter by document type, date range
- [ ] Pagination for search results

#### 4.2 Document Q&A (RAG Pipeline)
- [ ] `DocumentQAUseCase`:
  1. Embed user question
  2. Retrieve top-k relevant chunks (configurable, default k=5)
  3. Construct prompt: system instructions + retrieved context + question
  4. Call LLM with structured output
  5. Return answer with source citations (chunk ID, document name, page number)
- [ ] `POST /qa` endpoint (question + optional document_id filter)
- [ ] Response schema:
  ```python
  class QAResponse(BaseModel):
      answer: str
      sources: list[SourceCitation]
      confidence: float
      model_used: str
  ```

#### 4.3 Query History
- [ ] Store every Q&A interaction in `query_history` table
- [ ] `GET /qa/history` — paginated query history
- [ ] Track latency for performance monitoring

#### 4.4 Tests
- [ ] Unit tests: RAG pipeline with mocked embedding + LLM ports
- [ ] Unit tests: prompt construction logic
- [ ] Integration tests: end-to-end Q&A flow
- [ ] Test: source citations correctly reference chunks

### Deliverable
Users can search across all their documents semantically and ask natural language questions with cited answers. The RAG pipeline is hand-built and every step is testable.

---

## Phase 5: Frontend Dashboard (Week 4)

### Goal
Build a clean, functional web dashboard for interacting with the document intelligence system.

### Tasks

#### 5.1 Next.js Setup
- [ ] Initialize Next.js 15 with App Router and TypeScript
- [ ] Configure shadcn/ui components
- [ ] Create typed API client (`lib/api-client.ts`)
- [ ] Set up authentication flow (JWT storage, refresh, protected routes)

#### 5.2 Pages
- [ ] **Login/Register** — forms with validation
- [ ] **Dashboard** (`/`) — document list with status indicators, upload button
- [ ] **Document Detail** (`/documents/[id]`) — extracted text, summary, entities, classification
- [ ] **Search** (`/search`) — semantic search with result cards showing relevance scores
- [ ] **Q&A Chat** (`/chat`) — chat interface for document Q&A with source citations

#### 5.3 Components
- [ ] `DocumentUploader` — drag-and-drop file upload with progress indicator
- [ ] `DocumentCard` — status badge, type icon, summary preview
- [ ] `SearchResultCard` — chunk content, similarity score, source document link
- [ ] `ChatInterface` — message history, streaming response display, source links
- [ ] `EntityBadge` — visual display of extracted entities

#### 5.4 UX Details
- [ ] Loading states for all async operations
- [ ] Error handling with user-friendly messages
- [ ] Responsive layout (mobile + desktop)
- [ ] Empty states ("No documents yet — upload your first document")

#### 5.5 Frontend Dockerfile
- [ ] Multi-stage build for Next.js
- [ ] Add to `docker-compose.yml`

#### 5.6 Tests
- [ ] Component tests for critical UI (upload, search, chat)
- [ ] API client tests with mocked responses

### Deliverable
A complete web interface where users can upload documents, view analysis results, search semantically, and chat with their documents. Clean, functional, responsive.

---

## Phase 6: Polish & Portfolio Readiness (Week 5)

### Goal
Bring the project to portfolio-ready quality: documentation, test coverage, performance, and presentation.

### Tasks

#### 6.1 Documentation
- [ ] README with:
  - Architecture diagram (Mermaid)
  - Quick start (< 5 minutes with Docker)
  - Feature screenshots/GIFs
  - "Why these choices?" section
  - API documentation link (auto-generated `/docs`)
- [ ] API documentation review (OpenAPI descriptions on all endpoints)

#### 6.2 Test Coverage Audit
- [ ] Verify 80%+ coverage across all layers
- [ ] Add missing edge case tests
- [ ] Ensure test pyramid is correct (more unit tests than integration, more integration than E2E)

#### 6.3 Observability
- [ ] `GET /health` endpoint (database + Redis connectivity check)
- [ ] Structured logging with `structlog` (request ID correlation)
- [ ] Basic Prometheus metrics via `prometheus-fastapi-instrumentator`

#### 6.4 Performance
- [ ] Profile embedding generation pipeline
- [ ] Optimize chunk batch processing (batch embed, batch insert)
- [ ] Add database query EXPLAIN analysis for key queries

#### 6.5 Security Hardening
- [ ] CORS configuration review
- [ ] File upload validation hardening
- [ ] Rate limiting on all public endpoints
- [ ] Dependency vulnerability scan (`pip-audit`)

#### 6.6 Docker Optimization
- [ ] Multi-stage builds for both backend and frontend
- [ ] `.dockerignore` files
- [ ] docker-compose health checks
- [ ] Verify one-command startup: `docker compose up`

### Deliverable
A portfolio-ready project that a Google engineer can clone, run in 5 minutes, and be impressed by the engineering quality, architecture decisions, and technical depth.

---

## Milestone Summary

| Phase | Duration | Key Deliverable | Demonstrates |
|-------|----------|----------------|--------------|
| 1 | Week 1 | Auth + CI + Docker + clean structure | Engineering fundamentals |
| 2 | Week 2 | Document processing pipeline | System design, design patterns |
| 3 | Week 3a | AI analysis (summary, entities) | LLM integration, structured output |
| 4 | Week 3b | RAG search + Q&A | ML/AI pipeline, retrieval systems |
| 5 | Week 4 | Frontend dashboard | Full-stack capability |
| 6 | Week 5 | Polish + documentation | Production readiness, communication |

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tesseract quality poor on scanned docs | Low OCR accuracy | Add pre-processing (deskew, binarize) with Pillow; document quality requirements |
| OpenAI API costs during development | Budget overrun | Default to local sentence-transformers; mock LLM in tests; use `gpt-4o-mini` for dev |
| pgvector performance at scale | Slow search | Tune IVFFlat `lists` parameter; benchmark with realistic data; document scaling path |
| Frontend scope creep | Delayed delivery | Keep frontend thin — it calls the API, it doesn't contain logic. Prioritize function over polish |
| Test coverage falling below 80% | CI failures | Write tests alongside implementation (TDD), not after. Mock external services in unit tests |

## Definition of Done (Per Phase)

- [ ] All tests pass
- [ ] CI pipeline green
- [ ] Coverage ≥ 80% for new code
- [ ] No ruff or mypy errors
- [ ] Docker Compose starts cleanly
- [ ] Code reviewed (self-review against checklist or code-reviewer agent)
- [ ] Alembic migration tested (upgrade + downgrade)
