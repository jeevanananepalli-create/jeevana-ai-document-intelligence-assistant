# API Contract

All endpoints are prefixed with `/api/v1`. Responses use a consistent envelope format. Authentication is via JWT Bearer token unless marked as public.

---

## Response Envelope

Every response follows this structure:

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

On error:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "File type not supported",
    "details": { "allowed_types": ["pdf", "png", "jpg", "docx"] }
  }
}
```

Paginated responses include metadata:

```json
{
  "success": true,
  "data": {
    "items": [ ... ],
    "total": 42,
    "page": 1,
    "limit": 20,
    "has_next": true
  },
  "error": null
}
```

---

## Authentication Endpoints

### POST /api/v1/auth/register

**Public** — No authentication required.

Create a new user account.

**Request**:
```json
{
  "email": "jeevana@example.com",
  "password": "SecurePass123!",
  "full_name": "Nanepalli Jeevana"
}
```

**Validation**:
- `email`: valid email format, unique
- `password`: minimum 8 characters, at least 1 uppercase, 1 lowercase, 1 digit
- `full_name`: 1-255 characters

**Response** `201 Created`:
```json
{
  "success": true,
  "data": {
    "id": "a3f2b1c4-5678-4def-9012-abcdef123456",
    "email": "jeevana@example.com",
    "full_name": "Nanepalli Jeevana",
    "created_at": "2026-06-24T10:30:00Z"
  },
  "error": null
}
```

**Errors**:
- `409 Conflict` — Email already registered
- `422 Unprocessable Entity` — Validation failed

---

### POST /api/v1/auth/login

**Public** — No authentication required.

Authenticate and receive tokens.

**Request**:
```json
{
  "email": "jeevana@example.com",
  "password": "SecurePass123!"
}
```

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 900
  },
  "error": null
}
```

The refresh token is set as an `httpOnly` cookie (not in the response body).

**Errors**:
- `401 Unauthorized` — Invalid email or password
- `429 Too Many Requests` — Rate limit exceeded (5 attempts per 5 minutes per IP)

---

### POST /api/v1/auth/refresh

**Public** — Uses refresh token cookie (not Bearer token).

Get a new access token using the refresh token.

**Request**: No body. The refresh token is read from the `httpOnly` cookie.

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 900
  },
  "error": null
}
```

**Errors**:
- `401 Unauthorized` — Refresh token missing, expired, or revoked

---

### POST /api/v1/auth/logout

**Authenticated** — Requires Bearer token.

Revoke the refresh token.

**Request**: No body.

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "message": "Logged out successfully"
  },
  "error": null
}
```

---

## Document Endpoints

### POST /api/v1/documents/upload

**Authenticated**

Upload a document for processing.

**Request**: `multipart/form-data`
- `file` (required): The document file (PDF, JPG, PNG, DOCX)
- Max file size: 50 MB

**Response** `202 Accepted`:
```json
{
  "success": true,
  "data": {
    "id": "d1e2f3a4-5678-4bcd-9012-fedcba654321",
    "original_filename": "contract.pdf",
    "file_type": "pdf",
    "file_size_bytes": 245760,
    "status": "uploaded",
    "created_at": "2026-06-24T10:35:00Z"
  },
  "error": null
}
```

**Why `202 Accepted`**: The file is received but processing (OCR, chunking, embedding) happens asynchronously via Celery. The client should poll the status endpoint.

**Errors**:
- `400 Bad Request` — No file provided
- `413 Content Too Large` — File exceeds 50 MB limit
- `415 Unsupported Media Type` — File type not in [pdf, jpg, png, docx]
- `422 Unprocessable Entity` — File is corrupted or empty

---

### GET /api/v1/documents

**Authenticated**

List the current user's documents (paginated).

**Query Parameters**:
- `page` (int, default: 1): Page number
- `limit` (int, default: 20, max: 100): Items per page
- `status` (string, optional): Filter by status (`uploaded`, `processing`, `completed`, `failed`)
- `document_type` (string, optional): Filter by AI-classified type (`contract`, `invoice`, `research`, `report`, `letter`, `other`)
- `sort_by` (string, default: `created_at`): Sort field (`created_at`, `original_filename`)
- `sort_order` (string, default: `desc`): Sort direction (`asc`, `desc`)

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "d1e2f3a4-5678-4bcd-9012-fedcba654321",
        "original_filename": "contract.pdf",
        "file_type": "pdf",
        "file_size_bytes": 245760,
        "status": "completed",
        "document_type": "contract",
        "summary": "A service agreement between Acme Corp and...",
        "page_count": 12,
        "created_at": "2026-06-24T10:35:00Z"
      }
    ],
    "total": 42,
    "page": 1,
    "limit": 20,
    "has_next": true
  },
  "error": null
}
```

---

### GET /api/v1/documents/{document_id}

**Authenticated**

Get full details of a specific document, including extracted text and analysis.

**Path Parameters**:
- `document_id` (UUID): The document's unique identifier

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "id": "d1e2f3a4-5678-4bcd-9012-fedcba654321",
    "original_filename": "contract.pdf",
    "file_type": "pdf",
    "file_size_bytes": 245760,
    "status": "completed",
    "extracted_text": "SERVICE AGREEMENT\n\nThis agreement is entered into...",
    "page_count": 12,
    "analysis": {
      "summary": "A 12-page service agreement between Acme Corp and Beta LLC covering software development services. Key terms include a $150,000 fixed fee, 6-month duration, and 30-day payment terms.",
      "document_type": "contract",
      "language": "en",
      "entities": [
        {
          "name": "Acme Corp",
          "type": "organization",
          "mentions": 15
        },
        {
          "name": "Beta LLC",
          "type": "organization",
          "mentions": 8
        },
        {
          "name": "$150,000",
          "type": "monetary_value",
          "mentions": 3
        },
        {
          "name": "2026-01-15",
          "type": "date",
          "mentions": 2
        }
      ],
      "confidence": 0.92
    },
    "chunk_count": 47,
    "created_at": "2026-06-24T10:35:00Z",
    "updated_at": "2026-06-24T10:36:30Z"
  },
  "error": null
}
```

**Errors**:
- `404 Not Found` — Document doesn't exist or belongs to another user

---

### GET /api/v1/documents/{document_id}/status

**Authenticated**

Check processing status of a document. Lightweight endpoint for polling.

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "id": "d1e2f3a4-5678-4bcd-9012-fedcba654321",
    "status": "processing",
    "progress": {
      "step": "embedding",
      "steps_completed": 3,
      "total_steps": 5,
      "message": "Generating embeddings for 47 chunks..."
    }
  },
  "error": null
}
```

Processing steps (in order):
1. `extracting` — Running OCR or text extraction
2. `chunking` — Splitting text into chunks
3. `embedding` — Generating vector embeddings
4. `analyzing` — Running LLM analysis (summary, entities)
5. `complete` — All processing finished

If processing failed:
```json
{
  "success": true,
  "data": {
    "id": "d1e2f3a4-5678-4bcd-9012-fedcba654321",
    "status": "failed",
    "progress": {
      "step": "extracting",
      "steps_completed": 0,
      "total_steps": 5,
      "message": "OCR extraction failed: image resolution too low"
    }
  },
  "error": null
}
```

---

### DELETE /api/v1/documents/{document_id}

**Authenticated**

Delete a document, its chunks, embeddings, and stored file.

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "message": "Document deleted successfully"
  },
  "error": null
}
```

**Errors**:
- `404 Not Found` — Document doesn't exist or belongs to another user

---

### GET /api/v1/documents/{document_id}/chunks

**Authenticated**

Retrieve all text chunks for a document (for debugging and transparency).

**Query Parameters**:
- `page` (int, default: 1)
- `limit` (int, default: 50, max: 200)

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "c1d2e3f4-0000-0000-0000-000000000001",
        "chunk_index": 0,
        "content": "SERVICE AGREEMENT\n\nThis agreement is entered into as of January 15, 2026...",
        "page_number": 1,
        "token_count": 487
      },
      {
        "id": "c1d2e3f4-0000-0000-0000-000000000002",
        "chunk_index": 1,
        "content": "...as of January 15, 2026, by and between Acme Corp (\"Provider\") and Beta LLC...",
        "page_number": 1,
        "token_count": 512
      }
    ],
    "total": 47,
    "page": 1,
    "limit": 50,
    "has_next": false
  },
  "error": null
}
```

Note: chunk 0 and chunk 1 overlap (the "as of January 15, 2026" text appears in both). This is the 64-token overlap in action.

---

### POST /api/v1/documents/{document_id}/reanalyze

**Authenticated**

Re-run the **AI analysis** stage (summary, entity extraction, classification) on an already-processed document, without re-uploading or re-extracting the text.

**When to use this**:
- The AI analysis previously failed (`status: failed`) but the text was extracted successfully.
- The analysis prompt or LLM model has been upgraded and you want fresher results.
- The user edited document metadata and wants the summary regenerated.

This endpoint **reuses the existing extracted text and chunks** — it does not re-run OCR or re-embed. It enqueues a Celery task that starts at the `analyzing` step.

**Request**: No body.

**Response** `202 Accepted`:
```json
{
  "success": true,
  "data": {
    "id": "d1e2f3a4-5678-4bcd-9012-fedcba654321",
    "status": "processing",
    "message": "Re-analysis queued. Poll the status endpoint for progress."
  },
  "error": null
}
```

The document's `status` transitions back to `processing` while re-analysis runs, then returns to `completed`. Poll `GET /documents/{id}/status` as with initial processing.

**Why `202 Accepted`**: Like upload, analysis is asynchronous. The LLM call takes seconds, so it runs in a Celery worker, not in the request.

**Errors**:
- `404 Not Found` — Document doesn't exist or belongs to another user
- `409 Conflict` — Document is currently `processing` (wait for the in-flight job to finish before re-analyzing)
- `422 Unprocessable Entity` — Document has no extracted text to analyze (e.g., extraction itself failed; re-upload instead)

---

## Document Processing States

Every document moves through a small, well-defined state machine. These four values are the **single source of truth** for document state — the same enum is stored in the database (`documents.status`, see [database-design.md](database-design.md)) and returned by every document endpoint.

```
                ┌──────────────┐
   upload  ───▶ │   uploaded   │   File stored, queued. Nothing processed yet.
                └──────┬───────┘
                       │ worker picks up the job
                       ▼
                ┌──────────────┐
                │  processing  │   OCR → chunk → embed → analyze, in order.
                └──────┬───────┘
              success  │   failure (any step)
            ┌──────────┴──────────┐
            ▼                     ▼
    ┌──────────────┐      ┌──────────────┐
    │  completed   │      │    failed    │   processing_error explains why.
    └──────────────┘      └──────────────┘
```

| State | Meaning | What the client can do |
|-------|---------|------------------------|
| `uploaded` | The file is received and stored; a processing job is queued but hasn't started. | Poll status; delete. |
| `processing` | A Celery worker is actively running the pipeline (extraction, chunking, embedding, analysis). | Poll status to see the current step. |
| `completed` | All processing succeeded. Extracted text, chunks, embeddings, and analysis are available. | Search, ask questions, view chunks, re-analyze. |
| `failed` | A processing step failed. `processing_error` contains a human-readable reason. | Read the error; delete and re-upload, or `reanalyze` if only analysis failed. |

**State vs. step**: `status` is the coarse, persisted state above. While `status` is `processing`, the lightweight `GET /documents/{id}/status` endpoint also reports a finer-grained `step` (`extracting → chunking → embedding → analyzing → complete`) for progress display. The step is transient progress detail; the four states are the contract.

**Valid transitions** (anything else is a bug):
- `uploaded → processing` (worker starts)
- `uploaded → failed` (processing failed before/at the start, e.g. the file could not be read)
- `processing → completed` (all steps succeed)
- `processing → failed` (any step errors)
- `failed → processing` (via `reanalyze`, when text already exists)
- `completed → processing` (via `reanalyze`, to refresh analysis)

Notably, a document never goes directly from `uploaded` to `completed` — it must pass through `processing`.

---

## Live Processing Updates

Because processing is asynchronous, the client needs a way to learn when a document becomes `completed`. There are three standard mechanisms. **Today the API uses Option 1 (polling)**; Options 2 and 3 are documented here as a deliberate, planned scalability path — they are **not implemented yet**.

### Option 1 — Polling *(current implementation)*

The client repeatedly calls `GET /documents/{id}/status` (e.g., every 1–2 seconds) until `status` is `completed` or `failed`.

- **When to use**: Default choice. Correct, trivial to implement, works through any proxy, firewall, or load balancer with no special infrastructure. Ideal when processing finishes in seconds and a handful of users are active.
- **Trade-offs**:
  - 👍 Dead simple; stateless on the server; no persistent connections.
  - 👎 Wasteful — most polls return "still processing." Latency is bounded by the poll interval (a document ready at t=0.1s isn't seen until the next 2s poll).
  - 👎 At scale, N clients polling every 2s is N/2 requests per second of pure overhead.
- **Recommendation for this project**: keep it. At our scale and processing times, polling is the right amount of engineering.

### Option 2 — Server-Sent Events (SSE) *(future)*

The client opens a single long-lived HTTP connection to a `GET /documents/{id}/events` endpoint; the server pushes status updates as they happen, then closes the stream when the document reaches a terminal state.

- **When to use**: When you want push-based, real-time progress (a live progress bar) but updates flow in **one direction** — server → client. This is exactly the document-processing case: the client doesn't send anything mid-stream, it just listens.
- **Trade-offs**:
  - 👍 Real-time; no polling waste; built on plain HTTP (works with standard infrastructure and auto-reconnects via the browser's `EventSource`).
  - 👍 Simpler than WebSocket — unidirectional, text-based, no separate protocol upgrade to manage.
  - 👎 One-directional only (fine here). Holds an open connection per active client, which consumes server resources and needs proxy/timeout tuning.
  - 👎 Limited to a capped number of concurrent connections per browser over HTTP/1.1 (mitigated by HTTP/2).
- **Why it's the natural next step**: Q&A answer streaming (a planned future improvement) would use SSE too, so the same mechanism serves two features.

### Option 3 — WebSocket *(future, only if needed)*

A full-duplex, persistent connection upgraded from HTTP. Both client and server can send messages at any time.

- **When to use**: When you need **bidirectional, low-latency** communication — collaborative editing, live chat, multiplayer, a dashboard where the client also sends commands over the same channel. For one-way status push, WebSocket is more machinery than the problem requires.
- **Trade-offs**:
  - 👍 True two-way, lowest-latency real-time channel.
  - 👎 Heavier: a separate protocol (`ws://`/`wss://`), connection-state management, manual reconnection/heartbeat logic, and load balancers / proxies must explicitly support the upgrade.
  - 👎 Harder to scale horizontally — connections are stateful and sticky; broadcasting across multiple server instances needs a shared backplane (e.g., Redis pub/sub).
- **Decision**: **Not implemented, and not planned for processing updates.** Document status is inherently one-directional, so SSE (Option 2) covers it with far less complexity. WebSocket is recorded here only as the right tool *if* a future feature needs genuine two-way real-time messaging.

### Summary

| Mechanism | Direction | Complexity | Use here |
|-----------|-----------|-----------|----------|
| Polling | Client pulls | Lowest | ✅ Current — correct at this scale |
| SSE | Server pushes | Low–medium | 🔜 Planned for live progress + Q&A streaming |
| WebSocket | Both ways | Highest | ❌ Overkill for one-way status; reserved for future two-way features |

> **Guiding principle**: match the transport to the communication pattern. Status updates are one-directional, so the progression is polling → SSE. Reach for WebSocket only when the client genuinely needs to *talk back* over the same channel.

---

## Search Endpoints

### POST /api/v1/search

**Authenticated**

Semantic search across all user's documents.

**Request**:
```json
{
  "query": "payment terms and deadlines",
  "top_k": 5,
  "filters": {
    "document_type": "contract",
    "document_ids": null,
    "date_from": null,
    "date_to": null
  }
}
```

**Field descriptions**:
- `query` (string, required): Natural language search query
- `top_k` (int, default: 5, max: 20): Number of results to return
- `filters` (object, optional): Narrow search scope
  - `document_type`: Only search within a specific document type
  - `document_ids`: Only search within specific documents (list of UUIDs)
  - `date_from` / `date_to`: Only search documents uploaded within a date range

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "query": "payment terms and deadlines",
    "results": [
      {
        "chunk_id": "c1d2e3f4-0000-0000-0000-000000000015",
        "content": "Payment shall be made within 30 calendar days of receipt of invoice. Late payments shall accrue interest at 1.5% per month...",
        "similarity": 0.847,
        "document": {
          "id": "d1e2f3a4-5678-4bcd-9012-fedcba654321",
          "original_filename": "contract.pdf",
          "document_type": "contract"
        },
        "page_number": 5,
        "chunk_index": 22
      },
      {
        "chunk_id": "c1d2e3f4-0000-0000-0000-000000000032",
        "content": "The final deliverable is due no later than June 30, 2026. Milestone payments are structured as follows...",
        "similarity": 0.791,
        "document": {
          "id": "d1e2f3a4-5678-4bcd-9012-fedcba654321",
          "original_filename": "contract.pdf",
          "document_type": "contract"
        },
        "page_number": 7,
        "chunk_index": 31
      }
    ],
    "total_results": 2,
    "search_time_ms": 12
  },
  "error": null
}
```

**Errors**:
- `422 Unprocessable Entity` — Query is empty or too long (max 1000 characters)

---

## Q&A Endpoints

### POST /api/v1/qa/ask

**Authenticated**

Ask a natural language question about your documents. Uses the RAG pipeline.

**Request**:
```json
{
  "question": "What are the payment terms in the Acme contract?",
  "document_ids": ["d1e2f3a4-5678-4bcd-9012-fedcba654321"],
  "top_k": 5
}
```

**Field descriptions**:
- `question` (string, required): The question to answer
- `document_ids` (list[UUID], optional): Limit to specific documents. If null, searches all user's documents.
- `top_k` (int, default: 5): Number of chunks to retrieve as context

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "answer": "According to the Acme Corp service agreement, payment must be made within 30 calendar days of receiving an invoice. Late payments incur interest at 1.5% per month. The total contract value is $150,000, paid in three milestone installments.",
    "sources": [
      {
        "chunk_id": "c1d2e3f4-0000-0000-0000-000000000015",
        "document_id": "d1e2f3a4-5678-4bcd-9012-fedcba654321",
        "document_name": "contract.pdf",
        "page_number": 5,
        "content_preview": "Payment shall be made within 30 calendar days...",
        "relevance": 0.847
      },
      {
        "chunk_id": "c1d2e3f4-0000-0000-0000-000000000032",
        "document_id": "d1e2f3a4-5678-4bcd-9012-fedcba654321",
        "document_name": "contract.pdf",
        "page_number": 7,
        "content_preview": "The final deliverable is due no later than...",
        "relevance": 0.791
      }
    ],
    "confidence": 0.89,
    "model_used": "gpt-4o-mini",
    "latency_ms": 2340
  },
  "error": null
}
```

**When the answer is not in the documents**:
```json
{
  "success": true,
  "data": {
    "answer": "I could not find information about employee benefits in the provided documents. The uploaded contract covers service terms, payment, and deliverables but does not mention employee benefits.",
    "sources": [],
    "confidence": 0.15,
    "model_used": "gpt-4o-mini",
    "latency_ms": 1820
  },
  "error": null
}
```

**Errors**:
- `422 Unprocessable Entity` — Question is empty or too long (max 2000 characters)
- `404 Not Found` — One or more document_ids not found or not owned by user

---

### GET /api/v1/qa/history

**Authenticated**

Retrieve past Q&A interactions.

**Query Parameters**:
- `page` (int, default: 1)
- `limit` (int, default: 20, max: 100)

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "q1a2b3c4-5678-4def-9012-aaaaaaaaaaaa",
        "question": "What are the payment terms in the Acme contract?",
        "answer": "According to the Acme Corp service agreement...",
        "source_count": 2,
        "confidence": 0.89,
        "model_used": "gpt-4o-mini",
        "latency_ms": 2340,
        "created_at": "2026-06-24T11:00:00Z"
      }
    ],
    "total": 15,
    "page": 1,
    "limit": 20,
    "has_next": false
  },
  "error": null
}
```

---

## System Endpoints

### GET /health  *(liveness — implemented in Phase 1)*

**Public** — No authentication required.

A lightweight **liveness** probe: it answers "is the process up?" without
touching any dependency, so it is fast and never fails because of a slow
database. This is the unversioned endpoint container orchestrators and load
balancers poll. It is implemented now, in the Phase 1 foundation.

**Response** `200 OK`:
```json
{
  "status": "healthy",
  "service": "document-intelligence-api"
}
```

> Note: this liveness response is intentionally **not** wrapped in the standard
> data envelope — probes want the smallest, fastest possible payload.

---

### GET /api/v1/health  *(readiness — future)*

**Public** — No authentication required.

A richer **readiness** probe: "are my dependencies reachable so I can actually
serve work?" It checks the database, Redis, and Celery. This is added in a later
phase once those dependencies exist; it complements (does not replace) the
liveness probe above.

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "0.1.0",
    "checks": {
      "database": { "status": "up", "latency_ms": 2 },
      "redis": { "status": "up", "latency_ms": 1 },
      "celery": { "status": "up", "workers": 4 }
    }
  },
  "error": null
}
```

If a dependency is down:
```json
{
  "success": true,
  "data": {
    "status": "degraded",
    "version": "0.1.0",
    "checks": {
      "database": { "status": "up", "latency_ms": 2 },
      "redis": { "status": "down", "error": "Connection refused" },
      "celery": { "status": "down", "error": "No workers responding" }
    }
  },
  "error": null
}
```

Note: Returns `200` even when degraded (the health endpoint itself is working). Load balancers should check `data.status` field.

---

### GET /api/v1/me

**Authenticated**

Get the current user's profile.

**Response** `200 OK`:
```json
{
  "success": true,
  "data": {
    "id": "a3f2b1c4-5678-4def-9012-abcdef123456",
    "email": "jeevana@example.com",
    "full_name": "Nanepalli Jeevana",
    "document_count": 42,
    "total_queries": 156,
    "created_at": "2026-06-24T10:30:00Z"
  },
  "error": null
}
```

---

## Common Error Codes

| HTTP Status | Error Code | When |
|-------------|-----------|------|
| `400` | `BAD_REQUEST` | Malformed request body |
| `401` | `UNAUTHORIZED` | Missing or invalid token |
| `403` | `FORBIDDEN` | Valid token but insufficient permissions |
| `404` | `NOT_FOUND` | Resource doesn't exist or not owned by user |
| `409` | `CONFLICT` | Duplicate resource (e.g., email already registered) |
| `413` | `CONTENT_TOO_LARGE` | File exceeds size limit |
| `415` | `UNSUPPORTED_MEDIA_TYPE` | File type not supported |
| `422` | `VALIDATION_ERROR` | Request body validation failed |
| `429` | `RATE_LIMITED` | Too many requests |
| `500` | `INTERNAL_ERROR` | Server error (includes correlation ID for debugging) |

---

## Authentication Flow

All endpoints except `/auth/register`, `/auth/login`, `/auth/refresh`, and `/health` require a Bearer token.

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Token lifecycle**:
```
Register → Login → Access Token (15 min)
                 → Refresh Token (7 days, httpOnly cookie)

Access Token expires → POST /auth/refresh → New Access Token
Refresh Token expires → Must login again
Logout → Refresh token revoked in Redis
```

---

## Rate Limits

| Endpoint Group | Limit | Window |
|---------------|-------|--------|
| `/auth/login` | 5 requests | 5 minutes (per IP) |
| `/auth/register` | 3 requests | 10 minutes (per IP) |
| `/documents/upload` | 10 uploads | 1 minute (per user) |
| `/qa/ask` | 20 questions | 1 minute (per user) |
| `/search` | 30 searches | 1 minute (per user) |
| All other endpoints | 60 requests | 1 minute (per user) |

When rate limited, the response includes:
```
HTTP 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1719225600
```

---

## Versioning Strategy

The API is versioned via URL path (`/api/v1/`). When breaking changes are needed:
1. Create `/api/v2/` with new endpoints
2. Keep `/api/v1/` running for backward compatibility
3. Deprecate `/api/v1/` with a sunset header after migration period
