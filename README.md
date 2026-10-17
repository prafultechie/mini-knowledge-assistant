# Mini Knowledge Assistant

A small full-stack knowledge assistant for an internal support team. It supports article ingestion, chunking, local vector-style retrieval, grounded extractive answers, source references, and a React UI.

## Stack

- **Backend:** Python, FastAPI, SQLAlchemy async sessions, SQLite (easy local setup)
- **Retrieval:** scikit-learn TF-IDF vectors with cosine similarity as a deterministic, offline-friendly embedding/vector-search substitute
- **Frontend:** React and Vite
- **Tests:** pytest, pytest-asyncio, HTTPX

> **Demo vs production:** This version deliberately uses TF-IDF and extractive answer selection so it works without paid API credentials or a network model. It demonstrates the RAG stages, but it is not a neural embedding model or an LLM. For production semantic retrieval, replace the retrieval adapter with a real embedding model and vector database; replace `make_local_answer` with a provider-backed LLM call using retrieved context only. The `OPENAI_*` variables are reserved for that extension and are not used by the offline demo.

## Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer and npm

## Run locally

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
copy .env.example .env  # Windows; on macOS/Linux use: cp .env.example .env
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs
Health check: http://localhost:8000/health

### 2. Frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The frontend uses `http://localhost:8000` by default. To change it, create `frontend/.env` with `VITE_API_URL=http://localhost:8000` and restart Vite.

## API examples

Add a document:

```bash
curl -X POST http://localhost:8000/documents \
  -H 'Content-Type: application/json' \
  -d '{"title":"Refund Policy","content":"Customers can request a refund within 30 days of purchase. Refunds are processed within five business days."}'
```

List articles (pagination is supported):

```bash
curl 'http://localhost:8000/documents?page=1&page_size=10'
```

Ask a question:

```bash
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"How long do customers have to request a refund?"}'
```

`POST /ask` is limited to 20 requests per client IP per 60 seconds by default. A rejected request returns HTTP 429 and `Retry-After`. The demo limiter is process-local; use Redis for consistent limits across multiple workers or replicas.

## Tests

From `backend/` with its virtual environment activated:

```bash
pytest -q
```

The RAG unit tests should run without an API key. The API tests also require all packages in `requirements.txt` to be installed, including `aiosqlite`.

## Data and configuration

The default SQLite file is `backend/knowledge.db` and is created automatically. Set `DATABASE_URL` to use another SQLAlchemy async-compatible database URL. Do not commit `.env`, API keys, database files, virtual environments, `node_modules`, or build output.

## Implementation notes

- Request bodies use Pydantic validation and enforce size limits.
- Article content is stored once, with chunks stored separately and linked by foreign key.
- Retrieval runs in a worker thread so CPU-bound vectorization does not block the FastAPI event loop.
- External LLM calls are not made by the offline version. If introduced, use explicit connect/read timeouts, bounded retries with backoff for transient failures, handle provider 429 responses separately, and never return provider stack traces or secrets to clients.
- The app stores question history for a minimal audit trail. A production version should define retention, access controls, and privacy rules.
