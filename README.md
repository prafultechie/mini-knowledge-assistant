# Mini Knowledge Assistant

A full-stack knowledge assistant for an internal support team. It supports document ingestion, text chunking, local embeddings, similarity-based retrieval, grounded answers, source references, and a React UI.

## Stack

- **Backend:** Python, FastAPI, SQLAlchemy async sessions, SQLite
- **Embeddings and answer generation:** Local Ollama models
- **Embedding model:** `nomic-embed-text`
- **Language model:** `llama3.2:3b`
- **Frontend:** React and Vite
- **Tests:** pytest, pytest-asyncio, HTTPX

> **Local AI setup:** The application uses Ollama locally for embeddings and answer generation, so a paid API key is not required. Answers are generated using retrieved document context, with source references returned by the API. Answer quality depends on the available documents and the local model.

## Prerequisites

- Python 3.11 or newer
- Node.js and npm
- [Ollama](https://ollama.com/) installed and running locally

## Run locally

### 1. Set up Ollama

Install Ollama and pull the required models:

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

Ensure Ollama is running before starting the backend.

### 2. Backend

Open a terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

If your virtual environment already exists, activate it rather than creating it again.

API documentation: http://localhost:8000/docs

Health check: http://localhost:8000/health

### 3. Frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

The frontend uses `http://localhost:8000` by default. To change it, create `frontend/.env` with:

```env
VITE_API_URL=http://localhost:8000
```

Restart Vite after changing the environment variable.

## API examples

### Add a document

```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Refund Policy\",\"content\":\"Customers can request a refund within 30 days of purchase. Refunds are processed within five business days.\"}"
```

### List documents

```bash
curl "http://localhost:8000/documents?page=1&page_size=10"
```

### Ask a question

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"How long do customers have to request a refund?\"}"
```

The answer includes source references to help users verify the information against the uploaded documents.

## Rate limiting

`POST /ask` allows 20 requests per client IP per 60 seconds by default. Further requests return HTTP `429 Too Many Requests` with a `Retry-After` header.

The in-memory limiter is process-local. Use Redis or an API gateway for shared rate limits across multiple workers or replicas.

## Tests

From `backend/`, with the virtual environment activated:

```bash
pytest -q
```

Install all packages in `requirements.txt`, including `aiosqlite`, before running the API tests. Ollama must be available for tests that exercise the local model integration; unit tests that do not need model calls should be kept independent of Ollama.

## Data and configuration

The default SQLite database is `backend/knowledge.db` and is created automatically.

The backend configuration is read from environment variables in `backend/.env`. The local model settings use:

```env
OPENAI_API_KEY=
OPENAI_MODEL=llama3.2:3b
OPENAI_EMBEDDING_MODEL=nomic-embed-text
```

The `OPENAI_*` names are legacy configuration names in this project; the configured models are served locally by Ollama. No paid OpenAI API key is needed for the local setup.

Do not commit `.env` files, API keys, database files, virtual environments, `node_modules`, or unnecessary build output.

## Implementation notes

- Request bodies use Pydantic validation and enforce size limits.
- Document content is stored once, with chunks stored separately and linked by a foreign key.
- Embeddings are generated locally using the configured Ollama embedding model.
- Retrieved chunks provide context for grounded answer generation.
- Ollama/model-service failures should be handled gracefully without exposing internal stack traces or secrets to clients.
- The app stores question history for a minimal audit trail. A production version should define retention, access controls, and privacy rules.

## Production considerations

Before production deployment, consider authentication and authorization, a shared rate limiter, monitoring, request timeouts, database capacity, model-service reliability, and evaluation of retrieval and answer quality. For larger workloads, evaluate a dedicated vector database and separate background ingestion/embedding jobs from question-answering requests.
