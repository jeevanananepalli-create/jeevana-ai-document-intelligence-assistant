# Database Design

## Overview

PostgreSQL 16 with the `pgvector` extension serves as the single data store for both relational data and vector embeddings. This design eliminates the need for a separate vector database while maintaining full SQL query capabilities.

## Entity-Relationship Diagram

```
┌───────────────┐       ┌───────────────────┐       ┌──────────────────┐
│    users      │       │    documents       │       │ document_chunks  │
├───────────────┤       ├───────────────────┤       ├──────────────────┤
│ id (PK)       │──────<│ id (PK)           │──────<│ id (PK)          │
│ email         │       │ user_id (FK)      │       │ document_id (FK) │
│ password_hash │       │ filename          │       │ chunk_index      │
│ full_name     │       │ original_filename │       │ content          │
│ is_active     │       │ file_type         │       │ embedding (vec)  │
│ created_at    │       │ file_size_bytes   │       │ page_number      │
│ updated_at    │       │ mime_type         │       │ token_count      │
└───────────────┘       │ status            │       │ metadata (jsonb) │
                        │ extracted_text    │       │ created_at       │
                        │ summary           │       └──────────────────┘
                        │ document_type     │
                        │ entities (jsonb)  │
                        │ page_count        │
                        │ processing_error  │
                        │ storage_path      │
                        │ created_at        │
                        │ updated_at        │
                        └───────────────────┘

┌───────────────────┐
│  query_history    │
├───────────────────┤
│ id (PK)           │
│ user_id (FK)      │
│ query_text        │
│ query_embedding   │
│ response_text     │
│ source_chunks     │
│ model_used        │
│ latency_ms        │
│ created_at        │
└───────────────────┘
```

## Table Definitions

### users

Stores authenticated user accounts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Unique user identifier |
| `email` | `VARCHAR(255)` | UNIQUE, NOT NULL | Login email |
| `password_hash` | `VARCHAR(255)` | NOT NULL | bcrypt hash of password |
| `full_name` | `VARCHAR(255)` | NOT NULL | Display name |
| `is_active` | `BOOLEAN` | DEFAULT TRUE | Soft-delete flag |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Account creation time |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Last modification time |

**Indexes:**
- `idx_users_email` — UNIQUE on `email` (login lookup)

**Design decisions:**
- UUIDs instead of auto-increment integers: prevents enumeration attacks and is better for distributed systems
- `password_hash` never stores plaintext — bcrypt with cost factor 12
- `is_active` for soft-delete: users can be deactivated without losing their document history

---

### documents

Core table representing uploaded documents and their AI-generated analysis.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK | Unique document identifier |
| `user_id` | `UUID` | FK → users.id, NOT NULL | Owner |
| `filename` | `VARCHAR(255)` | NOT NULL | Storage filename (UUID-based) |
| `original_filename` | `VARCHAR(500)` | NOT NULL | User-provided filename |
| `file_type` | `VARCHAR(10)` | NOT NULL | `pdf`, `png`, `jpg`, `docx` |
| `file_size_bytes` | `BIGINT` | NOT NULL | Raw file size |
| `mime_type` | `VARCHAR(100)` | NOT NULL | Validated MIME type |
| `status` | `VARCHAR(20)` | NOT NULL, DEFAULT 'uploaded' | Processing status |
| `extracted_text` | `TEXT` | NULLABLE | Full extracted text |
| `summary` | `TEXT` | NULLABLE | AI-generated summary |
| `document_type` | `VARCHAR(50)` | NULLABLE | AI-classified type |
| `entities` | `JSONB` | NULLABLE | Extracted entities |
| `page_count` | `INTEGER` | NULLABLE | Number of pages |
| `processing_error` | `TEXT` | NULLABLE | Error message if failed |
| `storage_path` | `VARCHAR(500)` | NOT NULL | Path to stored file |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Upload time |
| `updated_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Last modification |

**Indexes:**
- `idx_documents_user_id` — on `user_id` (user's document list)
- `idx_documents_status` — on `status` (processing queue queries)
- `idx_documents_user_status` — composite on `(user_id, status)` (filtered document lists)
- `idx_documents_created_at` — on `created_at DESC` (chronological listing)
- `idx_documents_document_type` — on `document_type` (type-based filtering)

**Status values (enum):**

```
uploaded → processing → completed
                     → failed
```

| Status | Meaning |
|--------|---------|
| `uploaded` | File received and stored, queued for processing |
| `processing` | Celery worker is actively processing |
| `completed` | Processing complete, chunks and analysis available |
| `failed` | Processing failed, see `processing_error` |

These four values are the single source of truth for document state across the system. The API contract ([api-contract.md](api-contract.md)) exposes the same values, and the processing pipeline transitions a document through them in order. See [api-contract.md → Document Processing States](api-contract.md) for the API-facing description and the live-update options.

**Design decisions:**
- `filename` is UUID-based (e.g., `a3f2b1c4.pdf`), not the user's original filename, to prevent path traversal attacks
- `entities` is JSONB rather than a separate table — the entity schema varies by document type, and JSONB provides flexible, queryable storage
- `extracted_text` stores the full text for full-text search and display, even though chunks store portions of it

---

### document_chunks

Stores text chunks with their vector embeddings for semantic search.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK | Unique chunk identifier |
| `document_id` | `UUID` | FK → documents.id, NOT NULL | Parent document |
| `chunk_index` | `INTEGER` | NOT NULL | Order within document (0-based) |
| `content` | `TEXT` | NOT NULL | Chunk text content |
| `embedding` | `VECTOR(384)` | NOT NULL | Vector embedding |
| `page_number` | `INTEGER` | NULLABLE | Source page (if applicable) |
| `token_count` | `INTEGER` | NOT NULL | Token count of chunk |
| `metadata` | `JSONB` | DEFAULT '{}' | Additional chunk metadata |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Creation time |

**Indexes:**
- `idx_chunks_document_id` — on `document_id` (get all chunks for a document)
- `idx_chunks_embedding_ivfflat` — IVFFlat index on `embedding` using cosine distance
- `idx_chunks_document_chunk` — UNIQUE on `(document_id, chunk_index)` (ordering)

**Vector index configuration:**

```sql
CREATE INDEX idx_chunks_embedding_ivfflat
ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

The `lists` parameter should be tuned based on dataset size:
- Rule of thumb: `lists = sqrt(num_vectors)`
- For 10K chunks: `lists = 100`
- For 100K chunks: `lists = 316`

**Trade-off: IVFFlat vs HNSW**

| Index Type | Build Time | Query Time | Recall | Memory |
|------------|-----------|------------|--------|--------|
| IVFFlat | Fast | Fast | Good (~95%) | Low |
| HNSW | Slow | Fastest | Best (~99%) | High |

IVFFlat is chosen for simplicity and lower resource usage. HNSW can be swapped in by changing the index type if recall quality is insufficient.

**Design decisions:**
- `VECTOR(384)` matches `all-MiniLM-L6-v2` output dimension. If switching to OpenAI embeddings (1536 dims), this column must be altered. The embedding dimension is defined as a constant in application config.
- `chunk_index` preserves document order for display and context window construction
- `page_number` is nullable because some document types (plain images) don't have page numbers
- `metadata` JSONB stores arbitrary chunk-level data (e.g., section headers, font information) without schema changes

---

### query_history

Tracks user queries for analytics and debugging retrieval quality.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK | Unique query identifier |
| `user_id` | `UUID` | FK → users.id, NOT NULL | Who asked |
| `query_text` | `TEXT` | NOT NULL | The question asked |
| `query_embedding` | `VECTOR(384)` | NULLABLE | Embedded query vector |
| `response_text` | `TEXT` | NOT NULL | LLM response |
| `source_chunks` | `JSONB` | NOT NULL | Array of chunk IDs used as context |
| `model_used` | `VARCHAR(100)` | NOT NULL | LLM model identifier |
| `latency_ms` | `INTEGER` | NOT NULL | Total query-to-response time |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Query time |

**Indexes:**
- `idx_query_history_user_id` — on `user_id` (user's query history)
- `idx_query_history_created_at` — on `created_at DESC` (recent queries)

**Design decisions:**
- `source_chunks` as JSONB array stores the chunk IDs that were retrieved for this query. This enables evaluation of retrieval quality: "were the right chunks retrieved for this question?"
- `latency_ms` tracks end-to-end performance. If the query pipeline is slow, this data identifies whether the bottleneck is embedding, retrieval, or LLM generation.
- `query_embedding` is stored for potential offline analysis of query clustering — understanding what users ask about.

---

## Migration Strategy

Use **Alembic** for schema migrations, not `Base.metadata.create_all()`.

### Why Alembic

- **Version control**: Each migration is a Python file tracked in git
- **Reversible**: Every migration has an `upgrade()` and `downgrade()` function
- **Production mindset**: Real databases evolve. Using Alembic shows awareness that schema changes must be managed, not just applied once

### Migration Workflow

```bash
# Generate migration from model changes
alembic revision --autogenerate -m "add document_type column"

# Apply migration
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

### Initial Migration

The first migration creates:
1. pgvector extension: `CREATE EXTENSION IF NOT EXISTS vector`
2. All tables with constraints
3. All indexes including the IVFFlat vector index

---

## Query Patterns

### Get user's documents (paginated)

```sql
SELECT id, original_filename, file_type, status, document_type, 
       summary, page_count, created_at
FROM documents
WHERE user_id = :user_id
ORDER BY created_at DESC
LIMIT :limit OFFSET :offset;
```

Uses: `idx_documents_user_id`, `idx_documents_created_at`

### Semantic search (vector similarity)

```sql
SELECT dc.id, dc.content, dc.page_number, dc.document_id,
       d.original_filename,
       1 - (dc.embedding <=> :query_embedding) AS similarity
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id
WHERE d.user_id = :user_id
ORDER BY dc.embedding <=> :query_embedding
LIMIT :top_k;
```

Uses: `idx_chunks_embedding_ivfflat`

The `<=>` operator computes cosine distance. `1 - distance = similarity`.

### Filter search by document type

```sql
SELECT dc.id, dc.content, dc.page_number,
       1 - (dc.embedding <=> :query_embedding) AS similarity
FROM document_chunks dc
JOIN documents d ON dc.document_id = d.id
WHERE d.user_id = :user_id
  AND d.document_type = :doc_type
ORDER BY dc.embedding <=> :query_embedding
LIMIT :top_k;
```

This is where pgvector shines over dedicated vector databases — the `JOIN` and `WHERE` filter on relational data is native SQL.

---

## Data Volume Estimates

| Entity | Expected Volume | Storage Estimate |
|--------|----------------|-----------------|
| Users | 10-100 (demo) | Negligible |
| Documents | 100-1,000 | ~1-10 GB (files on disk) |
| Chunks per document | 20-200 (avg ~50) | ~500 bytes text + 1.5 KB vector per chunk |
| Total chunks | 5,000-50,000 | ~100 MB (text + vectors) |
| Query history | 1,000-10,000 | ~50 MB |

At these volumes, PostgreSQL with pgvector handles everything comfortably on a single instance. No sharding, no read replicas, no partitioning needed.

---

## Security Considerations

1. **Row-level access**: Every query includes `WHERE user_id = :user_id` to enforce document ownership. Consider adding PostgreSQL Row-Level Security (RLS) policies as an additional defense layer.
2. **Password storage**: bcrypt with cost factor 12. Never store, log, or return password hashes in API responses.
3. **SQL injection**: All queries use parameterized statements via SQLAlchemy ORM. Raw SQL is never constructed from user input.
4. **File storage**: Document files are stored outside the database (local disk or S3). Only the `storage_path` reference is in the database.
5. **Soft delete**: Users are soft-deleted (`is_active = FALSE`) to preserve referential integrity with documents and query history.
