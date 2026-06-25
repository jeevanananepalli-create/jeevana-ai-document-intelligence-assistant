# Architecture: AI Document Intelligence Assistant

## System Overview

An AI-powered document processing platform that extracts, analyzes, and enables intelligent querying of uploaded documents (PDF, images, DOCX). The system uses OCR for text extraction, vector embeddings for semantic search, and LLM-powered analysis for summarization, entity extraction, and document Q&A.

## Architecture Pattern: Clean Architecture (Monolith)

### Why Monolith, Not Microservices

A monolith with clean internal boundaries was chosen over microservices for these reasons:

| Criteria | Monolith | Microservices |
|----------|----------|---------------|
| Operational complexity | Low — single deployment | High — service discovery, distributed tracing, network partitioning |
| Development speed | Fast — shared types, no API contracts between services | Slow — versioned contracts, inter-service testing |
| Debugging | Single process, simple stack traces | Distributed tracing required |
| Deployment | One Docker image | Orchestration (Kubernetes) needed |
| Scalability ceiling | Sufficient for 10K+ documents | Needed at millions of concurrent users |

**Key insight**: The architectural discipline that matters is *internal modularity*, not deployment topology. A clean monolith with enforced layer boundaries demonstrates the same design thinking as microservices — without the operational tax.

### Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                   │
│              HTTP concerns: routing, auth,               │
│            validation, serialization                     │
├─────────────────────────────────────────────────────────┤
│                Application Layer (Use Cases)             │
│           Orchestrates domain logic + ports              │
│     UploadDocument, ProcessDocument, SemanticSearch,     │
│                   DocumentQA                             │
├─────────────────────────────────────────────────────────┤
│                   Domain Layer (Pure Logic)              │
│          Models, Ports (interfaces), Services            │
│    *** ZERO infrastructure imports — this is the        │
│        core architectural invariant ***                  │
├─────────────────────────────────────────────────────────┤
│              Infrastructure Layer (I/O)                  │
│     Database repos, OCR engines, embedding clients,     │
│          LLM clients, file storage adapters             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  Workers (Celery)                        │
│    Async document processing: OCR → chunk → embed       │
│         Runs in separate process(es)                    │
└─────────────────────────────────────────────────────────┘
```

### The Core Invariant

The `domain/` directory must have **zero imports** from any infrastructure or framework library. This means:

- No `import sqlalchemy`
- No `import fastapi`
- No `import openai`
- No `import celery`

This is verifiable by running:
```bash
grep -r "import sqlalchemy\|import fastapi\|import openai\|import celery" backend/app/domain/
# Must return empty
```

The domain layer defines **Ports** (Python `Protocol` classes) that describe *what* the system needs (e.g., "store a document", "generate embeddings") without specifying *how*. The infrastructure layer provides concrete implementations.

## Data Flow: Document Processing Pipeline

```
User uploads document
        │
        ▼
┌──────────────────┐     ┌──────────────────┐
│  POST /documents │────▶│  Store raw file   │
│     /upload      │     │  (local/S3)       │
└──────────────────┘     └──────────────────┘
        │
        ▼
┌──────────────────┐
│ Create Document  │  status = uploaded
│ record in DB     │
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ Enqueue Celery   │  Return 202 Accepted
│ task             │  with document_id
└──────────────────┘
        │
        ▼  (async, in worker process)
┌──────────────────┐
│ Detect file type │  status = processing
│ Select strategy  │
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ Extract text     │  OCR / pdfminer / python-docx
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ Chunk text       │  Recursive splitting, 512 tokens
│                  │  64 token overlap
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ Generate         │  sentence-transformers or
│ embeddings       │  OpenAI text-embedding-3-small
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ Store chunks +   │  PostgreSQL + pgvector
│ vectors in DB    │
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ Run LLM analysis │  Summary, entities, classification
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ Update status    │  status = completed
└──────────────────┘
```

## Data Flow: RAG Query Pipeline

```
User asks question about documents
        │
        ▼
┌──────────────────┐
│ Embed the query  │  Same model as document embedding
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ pgvector         │  Cosine similarity search
│ similarity search│  Top-k chunks (k=5 default)
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ Construct prompt │  System prompt + retrieved chunks
│ with context     │  + user question
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ LLM generates    │  Structured output with
│ answer           │  source citations
└──────────────────┘
        │
        ▼
┌──────────────────┐
│ Return answer +  │  Each claim linked to
│ source chunks    │  source document + page
└──────────────────┘
```

## Infrastructure Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Docker Compose                         │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ FastAPI  │  │ Celery   │  │ Next.js  │              │
│  │ App      │  │ Worker   │  │ Frontend │              │
│  │ :8000    │  │          │  │ :3000    │              │
│  └────┬─────┘  └────┬─────┘  └──────────┘              │
│       │              │                                   │
│       ▼              ▼                                   │
│  ┌──────────┐  ┌──────────┐                             │
│  │PostgreSQL│  │  Redis   │                             │
│  │+ pgvector│  │  :6379   │                             │
│  │  :5432   │  │          │                             │
│  └──────────┘  └──────────┘                             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Design Patterns Used

### 1. Strategy Pattern — Document Extraction

Different document types require different extraction methods. The strategy pattern encapsulates each algorithm:

```
ExtractionStrategy (Protocol)
    ├── PDFTextExtractionStrategy   — embedded text PDFs (pdfminer)
    ├── PDFOCRExtractionStrategy    — scanned PDFs (Tesseract)
    ├── ImageOCRExtractionStrategy  — JPG/PNG (Tesseract)
    └── DocxExtractionStrategy      — Word documents (python-docx)
```

A factory function inspects the file type and selects the appropriate strategy.

### 2. Repository Pattern — Data Access

All database operations are behind repository interfaces (Ports). The application layer never constructs SQL queries directly:

```
DocumentRepository (Protocol)
    └── PostgresDocumentRepository (implementation)
```

### 3. Dependency Injection — FastAPI Dependencies

FastAPI's built-in `Depends()` system wires concrete implementations to abstract ports at the API boundary:

```python
def get_document_repo(db: Session = Depends(get_db)) -> DocumentRepository:
    return PostgresDocumentRepository(db)
```

### 4. Use Case Pattern — Application Logic

Each user-facing operation is a single class with one public method:

- `UploadDocumentUseCase.execute(file, user_id) → Document`
- `ProcessDocumentUseCase.execute(document_id) → None`
- `SemanticSearchUseCase.execute(query, user_id) → list[SearchResult]`
- `DocumentQAUseCase.execute(question, document_ids) → QAResponse`

## Security Architecture

- **Authentication**: JWT access tokens (15-min expiry) + refresh tokens (httpOnly cookie, 7-day expiry)
- **Authorization**: User-scoped documents — users can only access their own documents
- **Rate limiting**: Redis-backed, per-IP and per-user limits on auth and API endpoints
- **File validation**: MIME type checking, file size limits, no executable uploads
- **Secrets**: Environment variables via Pydantic `SecretStr`, never hardcoded
- **CORS**: Explicitly configured allowed origins

## Observability

- **Logging**: `structlog` for structured JSON logs with request correlation IDs
- **Health check**: `GET /health` verifies database and Redis connectivity
- **Metrics**: `prometheus-fastapi-instrumentator` for request latency, error rates
- **Error tracking**: Structured error responses with correlation IDs for debugging
