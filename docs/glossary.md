# Glossary

Every technical term used in this project, explained for someone learning these concepts for the first time. Terms are grouped by topic, not alphabetical, so related concepts appear together.

---

## AI & Machine Learning

### Embedding
A list of numbers (a vector) that represents the *meaning* of a piece of text. Similar texts produce similar embeddings.

**Example**: The sentence "The cat sat on the mat" might be represented as `[0.23, -0.45, 0.12, ...]` — a list of 384 numbers. The sentence "A kitten was on the rug" would produce a very similar list of numbers, because the meaning is similar. "Stock prices rose sharply" would produce a very different list.

**Why it matters here**: We convert every document chunk into an embedding and store it in the database. When a user searches, we convert their query into an embedding and find the chunks with the most similar embeddings.

### Large Language Model (LLM)
A neural network trained on massive amounts of text that can generate human-like text responses. Examples: GPT-4, Claude, Gemini.

**How it works (simplified)**: The model predicts the next word (token) based on all the previous words. It does this billions of times during training, learning patterns in language. It doesn't "understand" text — it's very good at predicting what text should come next.

**Why it matters here**: We use an LLM to summarize documents, extract entities, classify document types, and answer questions about documents.

### RAG (Retrieval-Augmented Generation)
A technique where you first *retrieve* relevant information from a database, then *augment* the LLM's prompt with that information, so the LLM *generates* an answer based on your specific data — not just its training data.

**Without RAG**: "What are the payment terms?" → LLM guesses based on general knowledge → often wrong or made up.

**With RAG**: "What are the payment terms?" → System finds the relevant contract paragraph → gives it to the LLM → LLM answers based on the actual contract → accurate and cited.

**Analogy**: An open-book exam. The LLM is the student. RAG gives them the right textbook pages before they answer.

### Token
The basic unit of text that an LLM processes. A token is roughly ¾ of a word. Common words are single tokens ("the", "hello"). Uncommon words are split into multiple tokens ("unbelievable" → "un" + "believ" + "able").

**Why it matters here**: LLMs have a maximum context window measured in tokens (e.g., 128K tokens). Our chunks are 512 tokens. Knowing token counts helps us stay within limits.

### Context Window
The maximum amount of text (measured in tokens) that an LLM can process in a single request. Includes both the input (prompt + context) and the output (response).

**Example**: GPT-4o has a 128K token context window. If your prompt is 10K tokens, the model can generate up to 118K tokens of response (though in practice, you'd set a lower limit).

**Why it matters here**: When answering questions, we include retrieved document chunks in the prompt. We must ensure the total (system prompt + chunks + question + response) fits within the context window.

### Structured Output
A way to force an LLM to return data in a specific format (like JSON matching a defined schema) instead of free-form text.

**Without structured output**: LLM returns "The document is a contract between Acme and Beta..." — you have to parse this unreliably.

**With structured output**: LLM returns `{"document_type": "contract", "entities": [{"name": "Acme", "type": "organization"}]}` — guaranteed valid, directly usable in code.

### Hallucination
When an LLM generates information that sounds plausible but is factually incorrect or completely made up. LLMs don't "know" things — they predict likely text.

**Why it matters here**: RAG reduces hallucination by providing source documents. We also instruct the LLM to say "I don't know" when the answer isn't in the provided context. The `confidence` field in our responses helps users gauge reliability.

### Fine-Tuning
Modifying an LLM's internal parameters (weights) by training it on additional data. This is different from RAG.

**RAG vs Fine-Tuning**:
- RAG: Same model, better input (like giving a student reference books)
- Fine-Tuning: Changed model, same input (like training a student for months)

**We use RAG, not fine-tuning**, because our users' documents change constantly. Fine-tuning is for stable knowledge that doesn't change often.

---

## Vector Search & Similarity

### Vector
A list of numbers representing a point in multi-dimensional space. In our project, each text embedding is a vector with 384 dimensions (384 numbers).

**Analogy**: A 2D vector like `[3, 4]` is a point on a flat map. A 384-dimensional vector is a point in a space with 384 axes — impossible to visualize, but the math works the same way.

### Vector Database
A database optimized for storing and searching vectors based on similarity. Examples: Pinecone, Qdrant, Milvus.

**We use pgvector** — a PostgreSQL extension that adds vector capabilities to a regular database. This gives us vector search AND traditional SQL in one system.

### Cosine Similarity
A mathematical measure of how similar two vectors are, based on the angle between them. Range: -1 (opposite) to 1 (identical). In our project, similar texts have cosine similarity close to 1.

**Analogy**: Imagine two arrows pointing from the center of a clock. If both point to 12, the similarity is 1.0. If one points to 12 and the other to 6, the similarity is -1.0. If one points to 12 and the other to 3, the similarity is 0.

### Cosine Distance
`1 - cosine_similarity`. Range: 0 (identical) to 2 (opposite). pgvector uses the `<=>` operator for cosine distance. Lower distance = more similar.

### Approximate Nearest Neighbor (ANN)
A search algorithm that finds *approximately* the most similar vectors, trading a small amount of accuracy for a large speed improvement.

**Exact search**: Compare the query vector against every vector in the database. Accurate but slow (O(n)).

**ANN search**: Use an index (like IVFFlat or HNSW) to skip most vectors. 95-99% as accurate, 100-1000x faster.

### IVFFlat (Inverted File with Flat compression)
An indexing method for vector search. It divides all vectors into clusters (like sorting books onto labeled shelves). When searching, it only checks the few nearest clusters instead of every vector.

**The approach, step by step**:
1. **Build time**: group all vectors into `lists` clusters, each with a representative center (this is k-means clustering).
2. **Query time**: find the cluster center(s) closest to the query, then compare the query only against the vectors in those clusters — not the whole database.

**`lists` parameter**: how many clusters to create. More clusters = each cluster is smaller = faster search, but a higher chance of missing a true neighbor that landed in an adjacent cluster (lower recall). A common starting heuristic is `lists = sqrt(number_of_vectors)`.

**`probes` parameter**: how many clusters to actually search at query time. More probes = higher recall but slower. This is the dial you turn to trade speed for accuracy without rebuilding the index.

**When it's useful**: a great default when you have a moderate number of vectors (thousands to ~1 million), want low memory usage, and can tolerate ~95% recall. It builds quickly and is light on RAM. Its weakness is recall at cluster boundaries and slower performance than HNSW at large scale. **This project uses IVFFlat** because at our scale its simplicity and low resource cost outweigh HNSW's advantages.

### HNSW (Hierarchical Navigable Small World)
A more advanced, graph-based indexing method for vector search. Instead of clusters, it builds a **multi-layer graph** where each vector is a node connected to its nearest neighbors.

**How the graph works (intuition)**: think of it like a transport network. The top layer has a few "long-distance" links that let a search jump across the vector space quickly (like flights between cities). Each lower layer adds more local, short-distance links (like roads within a city). A search starts at the top, greedily hops toward the query through progressively finer layers, and arrives at the nearest neighbors — without ever examining most of the vectors.

**Accuracy vs. performance trade-off**:
- 👍 **Higher recall (~99%) and faster queries** than IVFFlat, especially at large scale — roughly `O(log n)` search.
- 👎 **Uses more memory** (it stores the graph's edges, not just the vectors) and **builds more slowly**.
- **Tuning dials**: `m` (edges per node — higher = better recall, more memory) and `ef_search` (how widely to explore at query time — higher = better recall, slower).

**When to choose it over IVFFlat**: when recall and query latency matter more than memory and build time, or once the vector count grows past roughly a million. In this project, switching from IVFFlat to HNSW is a one-line index change (pgvector supports both), which is why it's the documented next step in the scaling path.

---

## Document Processing

### OCR (Optical Character Recognition)
Technology that converts images of text into machine-readable text. Takes a photo of a page and outputs the text on that page.

**Why it matters here**: Scanned PDFs and images don't have "real" text — they're just pictures. OCR extracts the text so we can process it.

### Tesseract
An open-source OCR engine, originally developed by HP and now maintained by Google. We use it via the `pytesseract` Python library.

### Chunking
The process of splitting a long document into smaller pieces (chunks) for storage and retrieval. Our chunks are ~512 tokens with 64 tokens of overlap.

**Why not store the whole document as one piece?** Two reasons:
1. The embedding of a long document is a blurry average of all its topics. A chunk embedding is specific to one topic — better for precise search.
2. LLMs have limited context windows. We can only include a few chunks in the prompt, not entire documents.

### Chunk Overlap
The intentional repetition of text between consecutive chunks. If chunk 1 ends with "...payment is due within" and chunk 2 starts with "payment is due within 30 days...", the overlap ensures the complete sentence appears in at least one chunk.

**Without overlap**: Important information at chunk boundaries gets split and lost.

---

## Architecture & Design

### Clean Architecture
A software design philosophy where code is organized in layers, with the innermost layer (domain/business logic) having no dependencies on the outer layers (database, web framework, etc.).

**Key rule**: Dependencies point inward. The domain layer never imports from the infrastructure layer.

**Why it matters**: You can change your database, web framework, or LLM provider without touching your business logic. Each layer is independently testable.

### Domain Layer
The innermost layer of Clean Architecture. Contains pure business logic — no database calls, no HTTP, no external services. Just data models and rules.

**Example**: `TextChunker` is domain logic. It takes text and returns chunks. It doesn't know or care where the text came from or where the chunks will be stored.

### Port
An interface (Python `Protocol` class) that defines what the domain needs without specifying how it's implemented. Named after the "ports and adapters" pattern.

**Example**: `EmbeddingPort` says "I need a method that converts text to vectors." It doesn't say "use OpenAI" or "use sentence-transformers." The infrastructure layer provides the concrete implementation.

### Use Case
A single unit of application logic that orchestrates domain objects and ports to fulfill one user-facing operation.

**Example**: `UploadDocumentUseCase` coordinates: validate file → store file → create database record → enqueue processing task. It calls ports but doesn't know the database or storage implementation.

### Strategy Pattern
A design pattern where you define a family of algorithms (strategies), encapsulate each one, and make them interchangeable.

**In our project**: Different document types need different extraction methods. `PDFTextExtractionStrategy`, `PDFOCRExtractionStrategy`, `DocxExtractionStrategy` all implement the same interface. The processing pipeline picks the right strategy based on file type.

### Repository Pattern
A design pattern that encapsulates data access logic behind a clean interface. The application code calls `repo.find_by_id(doc_id)` without knowing if the data comes from PostgreSQL, MongoDB, or an API.

### Dependency Injection (DI)
A technique where a component receives its dependencies from the outside instead of creating them internally.

**Without DI**: `class UserService: def __init__(self): self.db = PostgresDatabase()` — hardcoded dependency, can't test without a database.

**With DI**: `class UserService: def __init__(self, db: Database): self.db = db` — pass in any database implementation, easy to test with a fake.

### Monolith
A software application deployed as a single unit. All code runs in one process.

**Not a bad word**: A well-structured monolith with clean internal boundaries is often better than a poorly structured set of microservices. We chose a monolith because it's simpler to develop, deploy, and debug for a single-developer project.

### Microservices
A software architecture where the application is split into small, independently deployable services that communicate over the network.

**We don't use this** because the operational complexity (service discovery, distributed tracing, inter-service auth) outweighs the benefits at our scale.

---

## Web & API

### REST (Representational State Transfer)
An architectural style for web APIs where resources (documents, users) are accessed via URLs using HTTP methods (GET, POST, PUT, DELETE).

**Example**: `GET /api/v1/documents/123` retrieves document 123. `DELETE /api/v1/documents/123` deletes it. The URL is the resource, the HTTP method is the action.

### JWT (JSON Web Token)
A compact, self-contained token used for authentication. Contains encoded JSON with user information and is cryptographically signed to prevent tampering.

**Structure**: `header.payload.signature` (three Base64-encoded parts separated by dots)

**How we use it**: After login, the server issues a JWT. The client includes it in every request's `Authorization` header. The server verifies the signature without checking a database.

### API Versioning
Including a version number in the API URL (`/api/v1/`, `/api/v2/`) so that old clients continue working when the API changes.

### Rate Limiting
Restricting how many requests a client can make in a given time period. Prevents abuse and protects server resources.

**Example**: 5 login attempts per 5 minutes per IP address. After the 5th attempt, the server returns `429 Too Many Requests`.

### CORS (Cross-Origin Resource Sharing)
A browser security mechanism that restricts which websites can call your API. Prevents malicious websites from making requests to your API using a user's credentials.

**Example**: Your frontend runs on `localhost:3000` and your API on `localhost:8000`. Without CORS configuration, the browser blocks the frontend from calling the API.

### Idempotency
An operation is **idempotent** if performing it many times has the same effect as performing it once. The result doesn't change no matter how many times you repeat the call.

**Everyday analogy**: pressing a floor button in an elevator is idempotent — pressing it five times still gets you to the same floor once. Adding an item to a shopping cart is *not* idempotent — press it five times and you have five items.

**Which HTTP methods are idempotent**:
- `GET`, `PUT`, `DELETE` are expected to be idempotent. `DELETE /documents/123` twice leaves the document deleted either way (the second call just returns "already gone").
- `POST` is generally *not* idempotent — `POST /documents/upload` twice creates two documents.

**Why APIs need it**: networks are unreliable. A client sends a request, the server processes it, but the response is lost on the way back. The client doesn't know if it succeeded, so it **retries**. Without idempotency, that retry causes a duplicate — a second charge, a second upload, a duplicate record. With idempotency, the retry is safe: the system recognizes it as the same operation and doesn't double-act. This is essential for any system with automatic retries — and a Celery-based pipeline retries failed tasks by design.

**Example in document processing**: the `process_document` Celery task is designed to be idempotent. If a worker crashes after embedding chunks but before marking the document `completed`, Celery re-runs the task. Without care, the re-run would insert a *second* set of chunks for the same document. We prevent this by making the operation safe to repeat — for example, deleting any existing chunks for that document before inserting (or using the unique constraint on `(document_id, chunk_index)` so duplicate inserts are rejected). Either way, running the task once or three times leaves exactly one correct set of chunks. The `reanalyze` endpoint follows the same principle: re-running analysis overwrites the previous summary/entities rather than appending.

### OpenAPI (Swagger)
A specification for describing REST APIs. FastAPI automatically generates an OpenAPI document from your route definitions, which powers the interactive API documentation at `/docs`.

---

## Infrastructure & DevOps

### Docker
A platform for running applications in isolated containers. A container packages your application with all its dependencies (Python, libraries, system tools) so it runs identically on any machine.

**Analogy**: A container is like a shipping container — it holds everything the application needs, and it works the same way regardless of what ship (computer) it's on.

### Docker Compose
A tool for defining and running multi-container applications. Our `docker-compose.yml` starts PostgreSQL, Redis, FastAPI, Celery, and Next.js with a single command.

### Celery
A distributed task queue for Python. We use it to process documents asynchronously — the API server enqueues a task, and a separate Celery worker process picks it up and runs it.

**The problem it solves**: OCR and embedding generation take 5–30 seconds. If you did that work inside the API request handler, the user's browser would hang for 30 seconds waiting for a response, and a server restart mid-request would lose the work entirely. Celery decouples *accepting* the work from *doing* the work: the API stores the task and responds immediately with `202 Accepted`, while the heavy lifting happens in the background. If a worker crashes, the task is still in the queue and another worker picks it up — durability you don't get from a plain background thread.

**Worker** — *the thing that does the work*. A worker is a separate, long-running process (often several of them, often in their own container) that sits in a loop: pull the next task off the queue, run the Python function it names, record the result, repeat. Workers scale **horizontally** — to process more documents at once, you run more worker processes (`docker compose up --scale worker=8`). Each worker handles one task at a time, so 8 workers process 8 documents in parallel.

**Message broker** — *the queue in the middle*. The broker is the shared inbox that sits between the API (which **produces** tasks) and the workers (which **consume** them). The API doesn't call workers directly; it drops a message describing the task into the broker, and any available worker takes it. We use **Redis** as the broker. This indirection is what makes the system durable and scalable: producers and consumers don't need to know about each other, tasks survive if no worker is currently free, and you can add or remove workers without touching the API. (A *result backend* — also Redis here — separately stores the outcome of each task so the status can be reported back.)

```
  API server                Redis (broker)              Celery workers
  ──────────                ──────────────              ──────────────
  enqueue task  ──────────▶  [ task | task | task ]  ──────────▶  worker 1 ─┐
  return 202                  (durable queue)                     worker 2 ─┤ run in
                                                                  worker 3 ─┘ parallel
```

### Redis
An in-memory data store used for caching and message queuing. In our project, Redis serves two purposes:
1. **Celery broker**: Stores the task queue that Celery workers read from
2. **Rate limiting**: Counts requests per IP/user for rate limiting

### CI/CD (Continuous Integration / Continuous Deployment)
- **CI**: Automatically running tests, linting, and type checking on every code push. If anything fails, the push is blocked.
- **CD**: Automatically deploying code to production after CI passes. We implement CI (GitHub Actions) but not CD (manual deployment for this project).

### Alembic
A database migration tool for SQLAlchemy. Creates version-controlled scripts that evolve the database schema over time.

**Without Alembic**: You manually run `CREATE TABLE` and hope you remember all the changes you made.

**With Alembic**: Each schema change is a Python file. `alembic upgrade head` applies all pending migrations. `alembic downgrade -1` rolls back the last change.

### pgvector
A PostgreSQL extension that adds vector data types and similarity search operators. Allows storing embeddings as a native column type and searching by cosine/Euclidean distance.

---

## Database

### Primary Key (PK)
A column (or set of columns) that uniquely identifies each row in a table. Every table has one. In our project, we use UUIDs as primary keys.

### Foreign Key (FK)
A column that references the primary key of another table, creating a relationship. `documents.user_id` is a foreign key referencing `users.id` — it means "this document belongs to this user."

### Index
A data structure that speeds up database lookups, like the index at the back of a book. Without an index, the database must scan every row to find a match.

**Trade-off**: Indexes speed up reads but slow down writes (the index must be updated on every insert/update). Only create indexes for columns you frequently query.

### JSONB
A PostgreSQL data type for storing JSON data in a binary, queryable format. Unlike a regular text column with JSON, JSONB can be indexed and queried efficiently.

**We use it for**: Storing extracted entities (which have variable structure depending on document type) and chunk metadata.

### Migration
A version-controlled change to the database schema. Like a git commit for your database structure.

### Transaction
A group of database operations that either all succeed or all fail. If inserting chunks fails halfway, the transaction rolls back and no partial data is left behind.

---

## Testing

### Unit Test
A test that verifies a single function or class in isolation, with no external dependencies (no database, no network, no filesystem). Runs in milliseconds.

### Integration Test
A test that verifies how multiple components work together with real dependencies (real database, real Redis). Runs in hundreds of milliseconds.

### E2E (End-to-End) Test
A test that verifies a complete user journey through the entire system, from HTTP request to database and back. Runs in seconds.

### Test Coverage
The percentage of code lines that are executed during tests. 80% coverage means 80% of your code is tested. We enforce 80% minimum in CI.

### TDD (Test-Driven Development)
A development methodology: write the test first (it fails), write the code to make it pass, then refactor. Red → Green → Refactor.

### Mock
A fake object that replaces a real dependency in tests. In unit tests, we mock the database port so we can test business logic without a real database.

### testcontainers
A library that spins up real Docker containers (PostgreSQL, Redis) for integration tests. Each test gets a clean, isolated database.

---

## Security

### Hashing (Password)
A one-way mathematical function that converts a password into a fixed-length string. You can verify a password against the hash, but you can't reverse the hash back to the password.

**bcrypt**: A deliberately slow hashing algorithm designed for passwords. The slowness (configurable via "cost factor") makes brute-force attacks impractical.

### Salt
Random data added to a password before hashing. Two users with the same password get different hashes because each has a different salt. Prevents attackers from using precomputed hash tables (rainbow tables).

### Access Token
A short-lived credential (15 minutes in our system) that proves the user is authenticated. Sent in the `Authorization` header of every API request.

### Refresh Token
A longer-lived credential (7 days in our system) used only to obtain new access tokens. Stored as an `httpOnly` cookie so JavaScript can't access it (XSS protection).

### CSRF (Cross-Site Request Forgery)
An attack where a malicious website tricks a user's browser into making requests to your API using the user's cookies. Mitigated by using JWT in headers (not cookies) for API calls.

### XSS (Cross-Site Scripting)
An attack where malicious JavaScript is injected into a web page. Mitigated by sanitizing user input and using `httpOnly` cookies for sensitive tokens.

---

## Frontend

### React
A JavaScript library for building user interfaces using reusable components.

### Next.js
A React framework that adds server-side rendering, file-based routing, and other production features on top of React.

### TypeScript
A programming language that adds type annotations to JavaScript. Catches bugs at compile time instead of runtime. All our frontend code is TypeScript.

### shadcn/ui
A collection of accessible, customizable UI components built on Radix UI. Unlike traditional UI libraries, components are copied into your project (not installed as a dependency), giving you full control.

### Component
A reusable piece of UI (a button, a card, a form). In React, components are functions that return JSX (HTML-like syntax in JavaScript).

### SSR (Server-Side Rendering)
Generating HTML on the server instead of in the browser. Improves initial page load speed and SEO. Next.js supports SSR by default.
