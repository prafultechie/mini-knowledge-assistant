# Architecture and trade-offs

## Current request flow

```text
React UI
   | HTTP/JSON
   v
FastAPI routes + Pydantic validation
   | async SQLAlchemy
   v
SQLite: documents, chunks, question_history
   ^
   | retrieved chunk records
   |
Local Ollama embedding model (nomic-embed-text)
   |
   v
Embedding similarity search over document chunks
   |
   v
Relevant chunks + user question
   |
   v
Local Ollama language model (llama3.2:3b)
   |
   v
Grounded answer + source metadata
   |
   v
React answer/source view
```

## Data model

- `documents`: title, full content, creation timestamp.
- `chunks`: document foreign key, chunk order, text content, and stored embedding data.
- `question_history`: submitted questions and timestamp. A production system should add user identity and a retention policy if history is needed.

## Service boundaries

- **API layer:** request validation, HTTP status codes, rate limiting, and response serialization.
- **Persistence:** SQLAlchemy async sessions and relational metadata/content storage.
- **Chunking:** splits document content into smaller chunks with configurable chunk size and overlap.
- **Embeddings and retrieval:** uses the local Ollama embedding model `nomic-embed-text` to represent text numerically and retrieve relevant document chunks using embedding similarity.
- **Answer generation:** uses the local Ollama language model `llama3.2:3b` with the question and retrieved context to generate an answer. Source metadata is returned so users can inspect the supporting documents.
- **UI:** consumes public endpoints and handles loading, error, answer, source, and document-list states.

## Async behavior and failures

Database operations use SQLAlchemy's async API. Embedding generation and model inference may involve local HTTP calls to the Ollama service. Keep blocking work off the FastAPI event loop, configure timeouts, and handle Ollama being unavailable or a model missing. Return stable client errors and log diagnostic details server-side without exposing secrets or internal stack traces.

## Rate limiting

`POST /ask` permits 20 requests per client IP per 60-second window by default. It returns HTTP `429` and a `Retry-After` header when the limit is reached.

The in-memory implementation is local-only: counters reset on restart and are not shared across workers. Production should use Redis or a gateway rate limiter and key by authenticated user or tenant, with IP as a secondary abuse-control signal.

## Operational concerns

- Read configuration from environment variables; keep secrets out of Git.
- Add structured request logs, request IDs, latency/error metrics, database pool metrics, and model latency metrics.
- Configure connection pooling based on load and database limits.
- Add authentication, authorization, document ownership, retention, and audit rules before exposing the service to real users.
- Use bounded request sizes, timeouts, and graceful failure responses.
- The current SQLite database is suitable for a small demo, not concurrent multi-instance production use.
- Local model inference depends on available system memory, CPU/GPU resources, and Ollama availability.

## Scaling discussion

### 10K concurrent requests

First measure database wait time, embedding latency, retrieval latency, and generation latency. Keep network and database operations async, use connection pooling, configure request and model-service timeouts, and tune worker count based on CPU and memory. Local model inference may become the main bottleneck. SQLite and the process-local limiter are not suitable for this load.

### 100K concurrent requests

Run stateless API replicas behind a load balancer; move to PostgreSQL and use Redis for shared rate limits and short-lived caches. Put expensive ingestion and embedding jobs on a queue and apply backpressure when model workers or the vector store are saturated. Add tracing, dashboards, alerting, and per-tenant quotas. Evaluate a dedicated vector store or PostgreSQL with pgvector after measuring retrieval quality and latency.

### 1M concurrent requests

Separate synchronous question traffic from ingestion and other background work. Scale API, retrieval, embedding, and generation services independently. Use queue-based admission control, model concurrency limits, caching for repeated questions, and capacity planning informed by load tests. Consider partitioning or sharding by tenant or corpus and multi-region deployment only if latency, availability, residency, and consistency requirements justify it. Add graceful degradation and circuit breakers to avoid cascading failures.

## Assumptions to validate

Before choosing infrastructure, measure corpus size, average chunk count, query rate, p95/p99 latency, answer quality, embedding and generation throughput, tenant isolation needs, and acceptable stale-cache behavior. Exact instance counts should follow load tests rather than guesses.
