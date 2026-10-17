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
   +-- TF-IDF vectorization + cosine similarity (CPU work in a thread)
              |
              v
       Extractive grounded answer + source metadata
              |
              v
          React answer/source view
```

## Data model

- `documents`: title, full content, creation timestamp.
- `chunks`: document foreign key, chunk order, text content. The local version computes TF-IDF vectors at question time from saved chunks rather than persisting dense vectors.
- `question_history`: submitted questions and timestamp. A production system should add user identity and a retention policy if history is needed.

## Service boundaries

- **API layer:** request validation, HTTP status codes, rate limiting and response serialization.
- **Persistence:** SQLAlchemy async sessions and relational metadata/content storage.
- **Chunking/retrieval:** deterministic chunk splitting and TF-IDF cosine similarity. This is a lightweight offline substitute, not a neural semantic embedding service.
- **Answer generation:** local extractive answer from the highest-ranked chunk. A provider-backed LLM adapter can be added behind this boundary and must receive only retrieved context plus the question.
- **UI:** consumes public endpoints and handles loading, error, answer, source and article-list states.

## Async behavior and failures

Database operations use SQLAlchemy's async API. Retrieval uses `asyncio.to_thread` because scikit-learn vectorization is CPU work and should not run directly on the event loop. The offline implementation makes no upstream model calls. If an embedding or LLM provider is introduced, use a shared async HTTP client, explicit timeouts, bounded retries with exponential backoff for transient failures, and special handling for upstream 429 responses. Do not retry invalid requests or repeat non-idempotent operations without an idempotency strategy. Return stable client errors and log diagnostic details server-side without logging secrets.

## Rate limiting

`POST /ask` permits 20 requests per client IP per 60-second window by default. It returns 429 and `Retry-After` when full. The in-memory implementation is intentionally local-only: counters reset on restart and are not shared across workers. Production should use Redis or a gateway rate limiter and key by authenticated user or tenant, with IP as a secondary abuse-control signal.

## Operational concerns

- Read configuration from environment variables; keep secrets out of Git.
- Add structured request logs, request IDs, latency/error metrics, database pool metrics and upstream model latency/cost metrics.
- Configure connection pooling based on load and database limits.
- Add authentication, authorization, document ownership, retention and audit rules before exposing the service to real users.
- Use bounded request sizes, timeouts, bounded retries, and graceful failure responses.
- The current local database is suitable for a small demo, not concurrent multi-instance production use.

## Scaling discussion

### 10K concurrent requests

First measure the mix of waiting on the database versus CPU retrieval and (in a provider-backed version) LLM latency. Keep network/database operations async, use connection pooling, set request and upstream timeouts, and tune worker count based on CPU and memory. The LLM call path is likely to dominate latency and cost, so enforce concurrency limits and timeouts around it. SQLite and the process-local limiter are not suitable for this load.

### 100K concurrent requests

Run stateless API replicas behind a load balancer; move to PostgreSQL and use Redis for shared rate limits and short-lived caches. Put expensive ingestion/embedding jobs on a queue and apply backpressure when the provider or vector store is saturated. Add tracing, dashboards, alerting, and per-tenant quotas. Use a dedicated vector store or PostgreSQL with pgvector after measuring recall and latency against the expected corpus.

### 1M concurrent requests

Separate synchronous question traffic from ingestion and other background work. Scale API, retrieval, embedding, and generation services independently; use queue-based admission control, provider concurrency budgets, caching for repeated questions, and capacity planning informed by load tests. Consider partitioning/sharding by tenant or corpus and multi-region deployment only if latency, availability, residency, and data consistency requirements justify it. Add graceful degradation (for example, return retrieved passages without generated prose if generation is unavailable) and circuit breakers to avoid cascading failures.

## Assumptions to validate

Before choosing infrastructure, measure corpus size, average chunk count, query rate, p95/p99 latency, answer quality, embedding/generation cost, tenant isolation needs, provider rate limits, and acceptable stale-cache behavior. Exact instance counts should follow load tests rather than guesses.
