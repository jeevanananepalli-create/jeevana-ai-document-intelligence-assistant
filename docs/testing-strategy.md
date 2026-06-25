# Testing Strategy

This document defines what gets tested, how, and why. Testing is not a checkbox — it's a design tool. Writing tests first (TDD) forces you to think about interfaces before implementations.

**Coverage target: 80% minimum, enforced in CI.**

---

## The Testing Pyramid

```
         ╱╲
        ╱  ╲         E2E Tests (few)
       ╱    ╲        Complete user journeys
      ╱──────╲       through the HTTP API
     ╱        ╲
    ╱          ╲      Integration Tests (some)
   ╱            ╲     Real database, real Redis,
  ╱──────────────╲    real file system
 ╱                ╲
╱                  ╲   Unit Tests (many)
╱────────────────────╲  Pure functions, no I/O
```

| Layer | What It Tests | Speed | Dependencies | Count |
|-------|--------------|-------|-------------|-------|
| Unit | Pure logic: chunking, validation, domain models | ~1ms each | None | ~60% of tests |
| Integration | Database repos, Celery tasks, file storage | ~100ms each | PostgreSQL, Redis | ~30% of tests |
| E2E | Full HTTP request/response cycles | ~500ms each | Entire stack | ~10% of tests |

**Why this ratio matters**: If most tests are E2E, your test suite is slow (minutes instead of seconds), flaky (network issues, timing), and hard to debug (which layer failed?). If most tests are unit tests, they run in seconds, never flake, and point to exact failures.

---

## Unit Testing

### What Gets Unit Tested

Unit tests cover **pure logic** — functions with no I/O (no database, no network, no filesystem). These functions take inputs and return outputs. No mocks needed.

### Domain Layer Tests

The domain layer is 100% pure logic. Every function here is unit testable without any setup.

#### Text Chunker

```
File: backend/tests/unit/domain/test_text_chunker.py

Tests:
├── test_empty_text_returns_empty_list
│     Input:  ""
│     Expect: []
│
├── test_short_text_returns_single_chunk
│     Input:  "Hello world" (< chunk_size)
│     Expect: ["Hello world"]
│
├── test_text_split_at_paragraph_boundary
│     Input:  Two paragraphs, total > chunk_size
│     Expect: Two chunks, split at "\n\n"
│
├── test_text_split_at_sentence_boundary_when_no_paragraph
│     Input:  Long text without paragraph breaks
│     Expect: Chunks split at ". " boundaries
│
├── test_chunk_overlap_present
│     Input:  Long text, overlap=64
│     Expect: Last 64 tokens of chunk N appear at start of chunk N+1
│
├── test_chunk_size_respected
│     Input:  Very long text
│     Expect: No chunk exceeds chunk_size tokens (allow ±10% tolerance for boundary alignment)
│
├── test_single_long_word_not_infinite_loop
│     Input:  "a" * 10000 (no spaces)
│     Expect: Chunks of max size, no hang
│
├── test_unicode_text_handled
│     Input:  Japanese/Arabic/emoji text
│     Expect: Valid chunks, no encoding errors
│
├── test_custom_chunk_size
│     Input:  text, chunk_size=128, overlap=16
│     Expect: Smaller chunks with correct overlap
│
└── test_preserves_whitespace_within_chunks
      Input:  Text with intentional formatting
      Expect: Internal whitespace preserved
```

**Why these specific tests**: Each test targets a specific behavior, not a specific implementation. The chunker could be rewritten completely, and these tests should still pass if the behavior is correct.

#### Domain Models

```
File: backend/tests/unit/domain/test_models.py

Tests:
├── test_document_creation_with_valid_data
├── test_document_is_immutable (frozen dataclass)
├── test_document_status_transitions
│     uploaded → processing ✓
│     processing → completed ✓
│     processing → failed ✓
│     completed → uploaded ✗ (invalid)
│     failed → uploaded ✗ (invalid)
│
├── test_document_chunk_ordering
│     Chunks with index 0, 1, 2 sort correctly
│
└── test_query_result_with_source_citations
```

### Application Layer Tests

Application layer tests mock the **ports** (interfaces), not the implementations. This verifies that use cases orchestrate correctly without testing database or LLM behavior.

#### Upload Document Use Case

```
File: backend/tests/unit/application/test_document_upload.py

Tests:
├── test_upload_stores_file_and_creates_record
│     Mock: StoragePort, DocumentRepository
│     Verify: storage.save() called with file content
│     Verify: repo.create() called with status="uploaded"
│     Verify: Returns document with correct metadata
│
├── test_upload_rejects_unsupported_file_type
│     Input:  file.exe
│     Expect: ValidationError raised
│
├── test_upload_rejects_oversized_file
│     Input:  file > MAX_FILE_SIZE
│     Expect: FileTooLargeError raised
│
├── test_upload_generates_uuid_filename
│     Input:  "my report.pdf"
│     Verify: Storage receives UUID-based filename, not original
│
└── test_upload_enqueues_processing_task
      Mock: TaskQueue
      Verify: task_queue.enqueue("process_document", document_id) called
```

#### Semantic Search Use Case

```
File: backend/tests/unit/application/test_semantic_search.py

Tests:
├── test_search_embeds_query_and_retrieves_chunks
│     Mock: EmbeddingPort returns [0.1, 0.2, ...], DocumentRepository returns chunks
│     Verify: embedding.embed() called with query text
│     Verify: repo.search_similar() called with query vector and top_k
│
├── test_search_filters_by_document_type
│     Verify: repo.search_similar() receives document_type filter
│
├── test_search_returns_results_with_similarity_scores
│     Verify: Each result has chunk content, similarity score, source document
│
├── test_search_empty_query_raises_validation_error
│
└── test_search_respects_top_k_limit
```

#### Document Q&A Use Case

```
File: backend/tests/unit/application/test_document_qa.py

Tests:
├── test_qa_retrieves_chunks_and_generates_answer
│     Mock: EmbeddingPort, DocumentRepository, LLMPort
│     Verify: Full pipeline: embed → retrieve → prompt → generate
│
├── test_qa_includes_source_citations_in_response
│     Verify: Response sources reference actual retrieved chunks
│
├── test_qa_prompt_includes_retrieved_context
│     Capture: The prompt sent to LLMPort
│     Verify: Contains retrieved chunk content
│     Verify: Contains the user's question
│     Verify: Contains system instructions about citing sources
│
├── test_qa_handles_no_relevant_chunks
│     Mock: repo.search_similar() returns empty
│     Verify: LLM prompted to say "information not found"
│
├── test_qa_limits_context_to_top_k_chunks
│     Verify: Only top_k chunks included in prompt, even if more exist
│
└── test_qa_records_latency
      Verify: Response includes latency_ms field
```

### How to Write a Unit Test (Step by Step)

For Jeevana — here's the exact pattern for every unit test:

```python
# 1. Name the test with test_ prefix and describe the behavior
def test_chunker_splits_at_paragraph_boundary():

    # 2. ARRANGE — Set up inputs
    text = "First paragraph content here.\n\nSecond paragraph starts here."
    chunker = TextChunker(chunk_size=20, chunk_overlap=0)

    # 3. ACT — Call the function
    chunks = chunker.chunk(text)

    # 4. ASSERT — Check the output
    assert len(chunks) == 2
    assert chunks[0].content == "First paragraph content here."
    assert chunks[1].content == "Second paragraph starts here."
```

The pattern is always: **Arrange → Act → Assert**. One behavior per test. No test should test two things.

---

## Integration Testing

### What Gets Integration Tested

Integration tests verify that your code works correctly **with real external systems** — a real PostgreSQL database, real Redis, real filesystem. They test the infrastructure layer implementations.

### Test Database Setup: testcontainers

`testcontainers-python` spins up a real PostgreSQL container for each test session. No shared test database, no data leaking between tests.

```python
# backend/tests/integration/conftest.py

import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16") as pg:
        # Run Alembic migrations against this container
        yield pg

@pytest.fixture
def db_session(postgres_container):
    # Create a new session per test, rollback after
    session = create_session(postgres_container.get_connection_url())
    yield session
    session.rollback()
```

**Why testcontainers, not SQLite**: SQLite behaves differently from PostgreSQL (no pgvector, different SQL dialect, no concurrent writes). Testing against SQLite gives false confidence. Testing against real PostgreSQL catches real bugs.

### Repository Tests

```
File: backend/tests/integration/test_document_repository.py

Tests:
├── test_create_document_persists_to_database
│     Insert a document, query it back, verify all fields
│
├── test_find_by_id_returns_document
├── test_find_by_id_returns_none_for_nonexistent
│
├── test_list_by_user_returns_only_user_documents
│     Insert docs for user A and user B
│     Query for user A → only user A's docs
│
├── test_list_with_pagination
│     Insert 25 documents
│     Query page=1, limit=10 → 10 items, has_next=True
│     Query page=3, limit=10 → 5 items, has_next=False
│
├── test_list_filtered_by_status
├── test_list_filtered_by_document_type
│
├── test_update_status
│     Create with status=uploaded
│     Update to status=processing
│     Verify updated_at changed
│
├── test_delete_removes_document_and_chunks
│     Insert document with chunks
│     Delete document
│     Verify chunks are also deleted (CASCADE)
│
└── test_search_similar_returns_ranked_results
      Insert chunks with known embeddings
      Search with a query vector
      Verify results are ordered by similarity
      Verify similarity scores are correct
```

### Celery Task Tests

```
File: backend/tests/integration/test_document_processing.py

Tests:
├── test_process_document_extracts_text_from_pdf
│     Upload a real test PDF
│     Run the Celery task synchronously (CELERY_ALWAYS_EAGER=True)
│     Verify extracted text is not empty
│     Verify chunks were created in database
│     Verify embeddings have correct dimension (384)
│     Verify document status is "completed"
│
├── test_process_document_handles_scanned_pdf
│     Upload a scanned PDF (image-only)
│     Verify OCR extraction ran
│     Verify text was extracted (may have lower quality)
│
├── test_process_document_handles_docx
├── test_process_document_handles_image
│
├── test_process_document_sets_failed_on_error
│     Upload a corrupted file
│     Verify status is "failed"
│     Verify processing_error contains error message
│
└── test_process_document_retries_on_transient_error
      Mock embedding API to fail once, succeed on retry
      Verify task completes after retry
```

### Test Fixtures: Sample Documents

Store small test documents in `backend/tests/fixtures/`:

```
backend/tests/fixtures/
├── sample.pdf          # 2-page digital PDF with embedded text
├── scanned.pdf         # 1-page scanned PDF (image of text)
├── sample.docx         # Simple Word document
├── sample.png          # Image with clear text
├── corrupted.pdf       # Invalid PDF file (for error handling tests)
└── empty.pdf           # Valid PDF with no text content
```

These are committed to git. They're small (< 100KB each) and never change.

---

## End-to-End Testing

### What Gets E2E Tested

E2E tests send real HTTP requests to the FastAPI `TestClient` (which starts the full application stack) and verify complete user journeys.

### Complete User Journeys

```
File: backend/tests/e2e/test_document_journey.py

Journey 1: Upload and process a document
├── POST /auth/register → 201
├── POST /auth/login → 200, get access_token
├── POST /documents/upload (sample.pdf) → 202
├── GET /documents/{id}/status → poll until "completed"
├── GET /documents/{id} → 200, has extracted_text, summary, entities
└── Verify: document appears in GET /documents list

Journey 2: Search across documents
├── Login
├── Upload 3 different documents, wait for processing
├── POST /search { query: "payment terms" }
│     → results reference the correct document
│     → similarity scores are > 0.5
│     → results are ordered by similarity (descending)
└── POST /search with document_type filter
      → only matching documents in results

Journey 3: Ask a question (RAG Q&A)
├── Login
├── Upload a contract PDF, wait for processing
├── POST /qa/ask { question: "What is the contract duration?" }
│     → answer references information from the contract
│     → sources array is not empty
│     → source chunk_ids exist in the document's chunks
└── Verify: query appears in GET /qa/history

Journey 4: Authentication flow
├── POST /auth/register → 201
├── POST /auth/login → 200
├── GET /documents (with token) → 200
├── GET /documents (without token) → 401
├── GET /documents (with expired token) → 401
├── POST /auth/refresh → 200, new access_token
├── GET /documents (with new token) → 200
├── POST /auth/logout → 200
└── POST /auth/refresh → 401 (refresh token revoked)

Journey 5: Authorization boundaries
├── User A uploads a document
├── User B tries GET /documents/{user_a_doc_id} → 404
├── User B tries DELETE /documents/{user_a_doc_id} → 404
└── User B tries POST /qa/ask with user_a's document_id → 404
```

### E2E Test Setup

```python
# backend/tests/e2e/conftest.py

import pytest
from fastapi.testclient import TestClient
from app.main import create_app

@pytest.fixture(scope="session")
def app(postgres_container, redis_container):
    """Create the full FastAPI app with real dependencies."""
    app = create_app(
        database_url=postgres_container.get_connection_url(),
        redis_url=redis_container.get_connection_url(),
        celery_always_eager=True,  # Run tasks synchronously in tests
    )
    return app

@pytest.fixture
def client(app):
    return TestClient(app)

@pytest.fixture
def authenticated_client(client):
    """Register a user and return an authenticated client."""
    client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "TestPass123!",
        "full_name": "Test User"
    })
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "TestPass123!"
    })
    token = response.json()["data"]["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

---

## Test-Driven Development (TDD) Workflow

For every feature, follow this cycle:

### Step 1: RED — Write a failing test

```python
def test_chunker_splits_at_paragraph_boundary():
    chunker = TextChunker(chunk_size=100, chunk_overlap=10)
    text = "Paragraph one.\n\nParagraph two."
    chunks = chunker.chunk(text)
    assert len(chunks) == 2
```

Run it: `uv run pytest tests/unit/domain/test_text_chunker.py -x`

It fails because `TextChunker` doesn't exist yet. **This is correct.**

### Step 2: GREEN — Write the minimal code to pass

```python
class TextChunker:
    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str) -> list[Chunk]:
        if not text:
            return []
        paragraphs = text.split("\n\n")
        return [Chunk(content=p, index=i) for i, p in enumerate(paragraphs)]
```

Run the test again: it passes. **Don't optimize yet.**

### Step 3: REFACTOR — Improve without changing behavior

Now handle edge cases, add the overlap logic, handle long paragraphs. After each change, run the tests. They should still pass.

### Step 4: REPEAT

Write the next test (e.g., `test_chunk_overlap_present`), watch it fail, implement the overlap, watch it pass.

---

## What NOT to Test

- **Third-party libraries**: Don't test that SQLAlchemy inserts correctly or that Pydantic validates. They have their own tests.
- **Framework behavior**: Don't test that FastAPI returns 422 for invalid request bodies. That's FastAPI's responsibility.
- **Trivial code**: Don't test getters, simple data classes with no logic, or config loading.
- **Implementation details**: Don't test private methods. Test the public interface. If you refactor internals, tests shouldn't break.

## When to Mock vs. When to Use Real Dependencies

| Situation | Approach | Why |
|-----------|---------|-----|
| Testing domain logic | No mocks, no dependencies | Domain is pure — no I/O |
| Testing use cases | Mock the ports (interfaces) | Verify orchestration, not infrastructure |
| Testing repositories | Real database (testcontainers) | SQLite ≠ PostgreSQL behavior |
| Testing Celery tasks | `CELERY_ALWAYS_EAGER=True` | Run synchronously, same logic |
| Testing LLM calls | Mock the LLMPort | LLM calls are expensive, slow, non-deterministic |
| Testing embedding generation | Mock in unit tests, real in integration | Real embeddings verify dimension and format |

---

## CI Pipeline Integration

```yaml
# .github/workflows/ci.yml (test job)
test:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: pgvector/pgvector:pg16
      env:
        POSTGRES_PASSWORD: test
      ports:
        - 5432:5432
    redis:
      image: redis:7
      ports:
        - 6379:6379

  steps:
    - uses: actions/checkout@v4
    - name: Install uv
      uses: astral-sh/setup-uv@v4
    - name: Install dependencies
      run: cd backend && uv sync
    - name: Run tests with coverage
      run: |
        cd backend
        uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
    - name: Upload coverage report
      uses: actions/upload-artifact@v4
      with:
        name: coverage-report
        path: backend/htmlcov/
```

**The CI pipeline fails if coverage drops below 80%.** This is enforced by `--cov-fail-under=80`. No exceptions.

---

## Running Tests Locally

```bash
cd backend

# Run all tests
uv run pytest

# Run only unit tests (fast — no database needed)
uv run pytest tests/unit/

# Run a specific test file
uv run pytest tests/unit/domain/test_text_chunker.py

# Run a specific test by name
uv run pytest -k "test_chunker_splits_at_paragraph"

# Run with verbose output (see each test name)
uv run pytest -v

# Run with coverage report
uv run pytest --cov=app --cov-report=term-missing

# Stop at first failure (useful during development)
uv run pytest -x

# Run with print output visible
uv run pytest -s
```
