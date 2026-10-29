# Policy Intelligence

**AI-based policy document Q&A using retrieval-augmented generation (RAG).** This repository includes a React/Vite/TypeScript frontend, a FastAPI backend, PostgreSQL persistence, PDF/DOCX ingestion, hybrid retrieval, and grounded Groq answers.

## Architecture

```text
React + Vite + TypeScript (Nginx container)
        | /api proxy
        v
FastAPI + SQLAlchemy (Python 3.12 container)
        | PostgreSQL driver: psycopg[binary]
        v
PostgreSQL (Docker Compose)

PDF/DOCX -> PostgreSQL chunks -> TF-IDF + BM25 -> RRF -> Groq -> citations
                                            (selected document only)
```

The backend extracts PDF/DOCX text, detects likely sections, and stores
page-aware chunks and document metadata in PostgreSQL. Questions are scoped to
the selected document, ranked with TF-IDF and BM25, fused with Reciprocal Rank
Fusion, and answered by Groq using only retrieved evidence. Citation metadata
and exact quotes are generated from stored chunks by the backend.
The RAG implementation uses `pypdf`, `python-docx`, scikit-learn TF-IDF,
`rank-bm25`, and Groq. It does not use OpenAI, Anthropic, sentence-transformers,
transformers, PyTorch, or GPU-dependent embeddings. The Groq API key belongs
only in the backend environment; never expose it through frontend variables.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer and npm
- Docker Desktop / Docker Engine with the Compose plugin (only needed for PostgreSQL)

## Environment setup

From the repository root, copy `.env.example` to `.env`, set a URL-safe
`POSTGRES_PASSWORD`, and set `GROQ_API_KEY`. The default model is
`openai/gpt-oss-20b`. Docker Compose builds `DATABASE_URL` with the internal
hostname `postgres`; for a backend run on the host, use `localhost` instead.
Keep `.env` private; it is ignored by Git. The Groq key is passed only to the
backend container.

## Run PostgreSQL

From the repository root:

```bash
docker compose up --build -d
docker compose ps
```

The frontend is available at <http://localhost:8080>, the backend at
<http://localhost:8000>, and PostgreSQL at `localhost:5432`. Compose waits for
PostgreSQL health before starting the backend. The FastAPI lifespan applies
Alembic migrations before serving requests, and the frontend waits for backend
health. Stop with `docker compose down`; add `-v` only if you intentionally
want to delete the persisted PostgreSQL volume.

## Run the backend

In a terminal:

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The Docker API is available at <http://localhost:8000>. Health check:
<http://localhost:8000/health>. Interactive API documentation:
<http://localhost:8000/docs>. Startup runs Alembic migrations; it does not seed
users or policy documents.

## Document API

Upload a PDF or DOCX with multipart form field `file` (maximum 25 MB):

```bash
curl -F "file=@./leave-policy.pdf" http://localhost:8000/api/documents
curl http://localhost:8000/api/documents
curl http://localhost:8000/api/documents/<document-id>
curl -X DELETE http://localhost:8000/api/documents/<document-id>
```

The upload response includes `id`, `status`, `page_count`, and `chunk_count`.
Document detail also returns each chunk's ID, text, page, section, token count,
and SHA-256 content hash. Re-uploading identical content returns HTTP 409.
Scanned PDFs return HTTP 422 with `Scanned PDF text extraction is not supported yet.`
PDF page numbers are 1-based; DOCX page values are `null` because the format
does not provide reliable page boundaries during text extraction.

## Ask a policy question

Upload a real policy document first, then use its returned ID. Omit
`conversation_id` to create a conversation; send the returned ID on follow-up
questions. The request is always scoped to the given document.

```bash
curl -F "file=@./employee-policy.pdf" http://localhost:8000/api/documents
curl -X POST http://localhost:8000/api/ask \
        -H "Content-Type: application/json" \
        -d '{"document_id":"<uploaded-document-id>","question":"What approval is required for remote work?"}'
```

The response includes `answer`, `grounded`, `needs_clarification`,
`document_id`, `conversation_id`, `latency_ms`, and backend-generated
`citations` containing chunk ID, page, section, an exact quote, and relevance
score. Include `conversation_id` in the next request to continue the same
document-bound conversation. Unsupported questions return
`grounded: false` with no citations. Missing Groq configuration returns 503;
provider failures return a sanitized 502.

The database defines `users`, `documents`, `chunks`, `conversations`,
`messages`, `citations`, and `feedback`. Document/chunk and conversation/message
deletions cascade to dependent records. No policy documents are bundled or
loaded automatically.

## Backend tests

Install test dependencies and run from `backend`:

```bash
pip install -r requirements-dev.txt
pytest
```

## Run the frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite development server proxies `/api` requests to the backend at `http://localhost:8000`.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Backend environment label; defaults to `development`. |
| `FRONTEND_ORIGIN` | Allowed browser origin for the API; defaults to `http://localhost:5173`. |
| `DATABASE_URL` | PostgreSQL SQLAlchemy connection URL used for schema creation and all document reads/writes. |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | PostgreSQL container initialization settings. |
| `GROQ_API_KEY` | Backend-only Groq credential, required for evidence-backed answers. |
| `GROQ_MODEL` | Backend Groq model; defaults to `openai/gpt-oss-20b`. |

Vite exposes only variables prefixed with `VITE_` to browser code. No secret should use that prefix.

## Current scope

- Health endpoint and minimal responsive React shell
- PostgreSQL persistence for seven application tables
- PDF/DOCX upload, extraction, page/section-aware chunking, and document CRUD
- Document-scoped TF-IDF/BM25/RRF retrieval and grounded Groq question answering
- No sample policy documents, synthetic dataset, or authentication
