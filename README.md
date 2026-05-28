# RAG Platform

A full-stack Retrieval-Augmented Generation platform for uploading PDFs, indexing their content, and chatting with grounded answers from your own documents. The project combines a FastAPI backend, a React/Vite frontend, Supabase for user data and metadata, Ollama for local LLM and embedding calls, ChromaDB or FAISS for vector search, and Redis/Celery for background document processing.

This README was generated from the current project structure and implementation, not from a template.

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [Current Architecture](#current-architecture)
- [Main Data Flows](#main-data-flows)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Backend Details](#backend-details)
- [Frontend Details](#frontend-details)
- [Configuration](#configuration)
- [Setup](#setup)
- [Running Locally](#running-locally)
- [API Reference](#api-reference)
- [Database and Persistence](#database-and-persistence)
- [RAG Pipeline Details](#rag-pipeline-details)
- [Async Processing](#async-processing)
- [Testing](#testing)
- [Known Caveats](#known-caveats)
- [Troubleshooting](#troubleshooting)

## What This Project Does

The app lets authenticated users:

- Sign up and log in with Supabase Auth.
- Create collections to organize document workspaces.
- Upload PDF files into a selected collection.
- Process PDFs asynchronously in a Celery worker.
- Extract PDF text page by page with `pypdf`.
- Split pages into chunks using semantic chunking when available, with recursive chunking fallback.
- Generate embeddings with Ollama via LangChain's `OllamaEmbeddings`.
- Store vectors in ChromaDB by default, or FAISS when configured.
- Ask questions against indexed documents.
- Receive grounded answers from an Ollama chat/generation model.
- View source citations, relevance scores, and retrieved chunk counts.
- Save chat sessions and messages in Supabase.
- Persist per-user settings such as retrieval depth, temperature, theme, source visibility, response style, and RAG mode.
- Monitor queue/cache/worker stats from the dashboard.

## Current Architecture

```text
Browser
  |
  | React 19 + Vite SPA
  | routes: login, signup, dashboard, upload, chat, documents, history, settings
  v
FastAPI backend
  |
  | /api/v1 routes
  |
  +-- Supabase
  |     auth, profiles, collections, documents, chat_sessions,
  |     chat_messages, settings, processing status
  |
  +-- Redis
  |     Celery broker and chat response cache
  |
  +-- Celery worker
  |     async PDF ingestion and processing progress updates
  |
  +-- Ollama
  |     embeddings: mxbai-embed-large:latest by default
  |     generation: qwen2.5:3b by default
  |
  +-- Vector store
        ChromaDB persistent store by default
        FAISS supported by configuration
```

The backend source of truth is `backend/app`. Some older top-level backend folders still exist (`backend/api`, `backend/rag`, `backend/services`, etc.), but the running application imports from `backend/app/...`.

## Main Data Flows

### Upload and Ingestion

1. The frontend sends a multipart PDF upload to `POST /api/v1/upload`.
2. `UploadService.save_uploaded_file()` validates the file and stores it under `backend/app/uploads` by default.
3. A row is inserted into Supabase `documents` with `processing_status = queued`.
4. `process_document_task` is enqueued on the Celery `document_processing` queue.
5. The worker loads the PDF with `PDFLoader`.
6. `TextSplitter` chunks the extracted pages.
7. `EmbeddingModel` generates Ollama embeddings in batches.
8. Chunks, metadata, and embeddings are stored in ChromaDB or FAISS.
9. Supabase `documents` is updated with progress, page count, chunk count, job id, completion time, or failure details.
10. The frontend polls `GET /api/v1/documents/{document_id}/status`.

### Chat

1. The frontend sends `POST /api/v1/chat`.
2. `ChatService` applies the requested RAG mode, top-k, temperature, style, and source visibility settings.
3. Redis cache is checked using collection, question, RAG mode, and response style.
4. The user question is embedded with Ollama.
5. `SemanticRetriever` searches the selected vector collection.
6. Results are filtered by `SIMILARITY_THRESHOLD`.
7. A grounded prompt is built with numbered context blocks.
8. Ollama generates the answer.
9. The response returns answer text, sources, retrieved chunk count, and response time.
10. When enabled, the frontend saves the conversation through `/api/v1/chat/messages`.

### Authentication and User State

1. The frontend uses `@supabase/supabase-js` for auth session management.
2. Protected routes require a Supabase session.
3. Backend profile routes read/write the `profiles` table.
4. Collections, documents, settings, and chat history are user-scoped through explicit `user_id` parameters and Supabase RLS policies.

## Technology Stack

| Layer | Current Implementation |
| --- | --- |
| Frontend | React 19, Vite 8, React Router 7, Axios, Framer Motion, Lucide React, Tailwind CSS 4 |
| Backend API | Python, FastAPI, Uvicorn, Pydantic v2, pydantic-settings |
| Auth and metadata DB | Supabase Auth and Supabase Postgres |
| PDF loading | `pypdf` wrapped in `PDFLoader` |
| Chunking | LangChain `SemanticChunker` when available; Markdown/recursive fallback |
| Embeddings | Ollama embeddings through `langchain_ollama.OllamaEmbeddings` |
| LLM | Ollama HTTP API through `OllamaClient` |
| Vector DB | ChromaDB default; FAISS optional |
| Queue | Celery with Redis broker and `rpc://` result backend |
| Cache | Redis chat response cache |
| Scripts | Windows `.bat` launchers for backend, frontend, Redis, worker, and Flower |

## Project Structure

```text
RAG/
  README.md
  start_rag_project.bat        # launches Redis, backend, frontend, Celery worker
  stop_rag_project.bat         # stops local project services
  test_supabase.py             # Supabase connectivity probe
  infrastructure/
    phase6_settings_migration.sql
    phase6_settings_fix_migration.sql
  docs/
    rls-policies.sql
  backend/
    requirements.txt
    .env.example
    start_backend.bat
    start_worker.bat
    start_flower.bat
    fix_settings_table.py
    app/
      main.py                  # FastAPI entrypoint
      core/
        config.py              # central runtime settings
        celery_app.py          # Celery app factory
      db/
        supabase.py            # Supabase client factories
      api/routes/
        upload_routes.py
        chat_routes.py
        documents_routes.py
        collections_routes.py
        chat_history_routes.py
        auth_routes.py
        settings_routes.py
        queue_routes.py
      services/
        upload_service.py
        chat_service.py
        cache_service.py
        faiss_search_adapter.py
      tasks/
        document_tasks.py
      rag/
        loaders/pdf_loader.py
        chunking/text_splitter.py
        embeddings/embedding_model.py
        retrievers/semantic_retriever.py
        pipelines/retrieval_pipeline.py
        vectorstore/chroma_manager.py
        vectorstore/faiss_manager.py
        llm/ollama_client.py
      schemas/
        upload_schema.py
        chat_schema.py
    db/
      schema.sql
      rls_policies.sql
    migrations/
      phase7_async_processing.sql
    tests and root test_*.py files
  frontend/
    package.json
    vite.config.js
    start_frontend.bat
    src/
      main.jsx
      App.jsx
      index.css
      lib/supabase.js
      services/api.js
      router/index.jsx
      contexts/AuthContext.jsx
      contexts/SettingsContext.jsx
      components/AppLayout.jsx
      components/ProtectedRoute.jsx
      pages/
        Login.jsx
        Signup.jsx
        Dashboard.jsx
        Upload.jsx
        Chat.jsx
        Documents.jsx
        History.jsx
        Settings.jsx
```

## Backend Details

The FastAPI app is defined in `backend/app/main.py`.

Mounted routers:

- `/api/v1/upload`
- `/api/v1/chat`
- `/api/v1/auth`
- `/api/v1/documents`
- `/api/v1/collections`
- `/api/v1/settings`
- `/api/v1/queue`

Base utility routes:

- `GET /` returns app status and version.
- `GET /health` returns health information.
- `GET /docs` exposes Swagger UI.
- `GET /redoc` exposes ReDoc.

Important backend components:

- `Settings` in `app/core/config.py`: loads `.env`, creates runtime directories, validates Ollama URL, validates chunk size/overlap, and exposes all defaults.
- `UploadService`: validates PDFs, saves uploads, and can run synchronous ingestion.
- `process_document_task`: the active async ingestion path used by upload routes.
- `ChatService`: orchestrates retrieval, prompt construction, Ollama generation, source formatting, and Redis caching.
- `EmbeddingModel`: singleton wrapper around Ollama embeddings.
- `SemanticRetriever`: retrieves and filters vector results by similarity threshold.
- `ChromaManager` and `FAISSManager`: vector store implementations.
- `cache_service`: Redis cache wrapper used for chat response caching and dashboard stats.
- `supabase.py`: anon and service-role client factories.

## Frontend Details

The frontend is a protected React SPA.

Routes:

- `/login`: public login screen.
- `/signup`: public signup screen.
- `/dashboard`: overview and queue intelligence.
- `/upload`: PDF upload workflow.
- `/chat`: new chat.
- `/chat/:sessionId`: existing chat session.
- `/documents`: document list and document operations.
- `/history`: saved chat sessions.
- `/settings`: per-user AI/workspace preferences.

Key frontend modules:

- `src/lib/supabase.js`: creates the Supabase browser client from `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
- `src/contexts/AuthContext.jsx`: manages Supabase session, current user, profile fetch, login, signup, and logout.
- `src/contexts/SettingsContext.jsx`: loads backend settings, performs optimistic updates, debounces saves, and applies theme.
- `src/services/api.js`: central Axios wrapper for backend API calls.
- `src/router/index.jsx`: route definitions and protected layout.

## Configuration

Backend configuration is read from `backend/.env` through `app/core/config.py`.

Important backend environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `RAG Backend` | FastAPI app title |
| `API_VERSION` | `v1` | API route prefix |
| `DEBUG` | `False` | Enables debug error detail |
| `HOST` | `0.0.0.0` | Backend host setting |
| `PORT` | `8000` | Backend port setting |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Generation model |
| `EMBEDDING_MODEL` | `mxbai-embed-large:latest` | Ollama embedding model |
| `REQUEST_TIMEOUT` | `120` | Ollama request timeout seconds |
| `VECTOR_DB_TYPE` | `chromadb` | `chromadb` or `faiss` |
| `CHROMA_DB_PATH` | unset | Optional override for Chroma persistence |
| `CHROMA_COLLECTION_NAME` | `default_ollama` | Default vector collection |
| `FAISS_INDEX_PATH` | unset | Optional override for FAISS persistence |
| `CHUNK_SIZE` | `1000` | Fallback chunk size |
| `CHUNK_OVERLAP` | `200` | Fallback chunk overlap |
| `SIMILARITY_THRESHOLD` | `0.10` | Minimum score retained by retriever |
| `UPLOAD_DIR` | `backend/app/uploads` | PDF storage directory |
| `MAX_UPLOAD_SIZE` | `26214400` | 25 MB upload limit |
| `DEFAULT_TOP_K` | `3` | Backend default retrieval count |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis cache URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker |
| `CELERY_RESULT_BACKEND` | `rpc://` | Celery result backend |
| `REDIS_CACHE_TTL` | `300` | Chat cache TTL seconds |
| `CELERY_TASK_MAX_RETRIES` | `3` | Document processing retries |
| `SUPABASE_URL` | empty | Supabase project URL |
| `SUPABASE_ANON_KEY` | empty | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | empty | Supabase service-role key for backend writes |

Frontend configuration should live in `frontend/.env`.

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
VITE_SUPABASE_ANON_KEY=YOUR_ANON_KEY_HERE
```

Note: most API calls in `frontend/src/services/api.js` currently use `http://localhost:8000` directly. `AuthContext` uses `VITE_API_BASE_URL`.

## Setup

### Prerequisites

- Windows PowerShell or CMD, based on the provided scripts.
- Python 3.11+ recommended.
- Node.js 18+ recommended.
- Redis running locally or available through Docker/WSL.
- Ollama installed and running.
- A Supabase project with the required tables and RLS policies.

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Update `backend/.env` with your Supabase, Ollama, Redis, vector DB, and path settings.

The current code imports packages that may not be present in `requirements.txt` in some environments, including `langchain-ollama`, `langchain-text-splitters`, `langchain-experimental`, `langchain-chroma`, and FAISS support if you use `VECTOR_DB_TYPE=faiss`. Install them if imports fail.

### Ollama

```bash
ollama serve
ollama pull qwen2.5:3b
ollama pull mxbai-embed-large:latest
```

The generation model and embedding model are independent. Keep vector collections consistent with the embedding model dimension. The ingestion code can recreate Chroma collections when it detects an embedding dimension mismatch.

### Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env` with Supabase browser credentials and, if needed, API base URL.

### Supabase

Apply the SQL files in the project before relying on auth, collections, documents, settings, and chat history:

- `backend/db/schema.sql`
- `backend/db/rls_policies.sql`
- `docs/rls-policies.sql`
- `infrastructure/phase6_settings_migration.sql`
- `infrastructure/phase6_settings_fix_migration.sql`
- `backend/migrations/phase7_async_processing.sql`

The exact order depends on your current Supabase state. For a new project, start with the schema, then RLS, then phase migrations.

## Running Locally

### One-command Windows launcher

From the repository root:

```bat
start_rag_project.bat
```

This attempts to start:

- Redis on `localhost:6379`
- FastAPI on `http://localhost:8000`
- React/Vite on `http://localhost:5173`
- Celery worker on the `document_processing` queue

Then open:

- App: `http://localhost:5173`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Stop services with:

```bat
stop_rag_project.bat
```

### Manual startup

Terminal 1:

```bash
redis-server
```

Terminal 2:

```bash
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --reload
```

Terminal 3:

```bash
cd backend
venv\Scripts\activate
python -m celery -A app.core.celery_app worker --loglevel=info --pool=solo -Q document_processing
```

Terminal 4:

```bash
cd frontend
npm run dev
```

Optional Flower:

```bash
cd backend
start_flower.bat
```

## API Reference

All application API routes are under `/api/v1`.

### Upload

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/upload` | Upload a PDF and enqueue async ingestion. Returns `document_id`, `job_id`, status, filename, and collection. |
| `POST` | `/api/v1/upload/collections` | Legacy-style collection creation response without Supabase persistence. |
| `GET` | `/api/v1/upload/documents/{document_id}` | Legacy metadata endpoint currently returns 404 placeholder. |

### Chat

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/chat` | Ask a RAG question. Supports `question`, `collection_id`, `top_k`, `temperature`, `rag_mode`, `response_style`, and `show_sources`. |

### Chat History

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/chat/sessions?user_id=...` | List chat sessions for a user. |
| `POST` | `/api/v1/chat/sessions?user_id=...&title=...` | Create a new chat session. |
| `GET` | `/api/v1/chat/sessions/{session_id}?user_id=...` | Fetch a session and its messages. |
| `POST` | `/api/v1/chat/messages` | Save a chat message. |
| `DELETE` | `/api/v1/chat/sessions/{session_id}?user_id=...` | Delete a chat session and messages. |

### Documents

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/documents?user_id=...` | Paginated list with optional `collection_id`, `search`, `sort_by`, `sort_order`, `limit`, and `offset`. |
| `GET` | `/api/v1/documents/{document_id}?user_id=...` | Fetch one document row. |
| `GET` | `/api/v1/documents/{document_id}/preview?user_id=...` | Fetch preview metadata. |
| `PATCH` | `/api/v1/documents/{document_id}?user_id=...` | Rename a document with body `{ "filename": "..." }`. |
| `PATCH` | `/api/v1/documents/{document_id}/collection?user_id=...` | Move a document to another collection and enqueue reprocessing. |
| `DELETE` | `/api/v1/documents/{document_id}?user_id=...` | Delete document row and best-effort vector/file/storage cleanup. |
| `GET` | `/api/v1/documents/{document_id}/status` | Poll async processing status. |
| `POST` | `/api/v1/documents/{document_id}/retry` | Re-enqueue a failed document. |

### Collections

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/collections?user_id=...&name=...` | Create a Supabase-backed collection. |
| `GET` | `/api/v1/collections?user_id=...` | List user collections with best-effort document counts. |
| `PATCH` | `/api/v1/collections/{collection_id}?user_id=...` | Rename collection. |
| `DELETE` | `/api/v1/collections/{collection_id}?user_id=...` | Delete collection and its document rows. |

### Auth/Profile

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/auth/profile/{user_id}` | Fetch profile row. |
| `POST` | `/api/v1/auth/profile` | Upsert profile after signup. |
| `PATCH` | `/api/v1/auth/profile/{user_id}` | Update profile fields. |

### Settings

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/settings/{user_id}` | Fetch settings; creates defaults if missing. |
| `PATCH` | `/api/v1/settings/{user_id}` | Partially update settings. |
| `POST` | `/api/v1/settings/{user_id}/reset` | Reset settings to factory defaults. |

### Queue

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/queue/stats` | Return queued/active/completed/failed counts, Redis cache stats, and Celery worker status. |

## Database and Persistence

Supabase is used for:

- Auth users through Supabase Auth.
- `profiles` for app profile data.
- `collections` for user document groups.
- `documents` for upload metadata and processing status.
- `chat_sessions` and `chat_messages` for conversation history.
- `settings` for user preferences.

Vector data is stored separately:

- ChromaDB persists under `CHROMA_PERSIST_DIR`.
- FAISS persists under `FAISS_INDEX_DIR`.

Uploaded PDFs are stored locally under `UPLOAD_DIR`. Supabase Storage cleanup is attempted during document deletion for common bucket names, but local disk is the primary upload path used by the current ingestion task.

## RAG Pipeline Details

### PDF Loading

`PDFLoader` uses `pypdf.PdfReader`, creates one LangChain `Document` per PDF page, and attaches:

- `source`
- `file_name`
- `page`
- `page_number`

Scanned PDFs without extractable text will fail processing unless OCR is added.

### Chunking

`TextSplitter` tries semantic chunking first:

- `SemanticChunker`
- percentile breakpoint threshold
- threshold amount `95`
- minimum chunk size `200`

Fallback behavior:

- split by markdown headers when available
- then use `RecursiveCharacterTextSplitter`
- default `chunk_size = 1000`
- default `chunk_overlap = 200`
- separators: blank line, newline, space, character

Every chunk receives metadata such as:

- `source_document_index`
- `chunk_index`
- `chunk_total`
- `chunk_size`
- `document_id`
- `collection_id`
- `uploaded_filename`
- `chunk_id`

### Embeddings

Embeddings are generated by Ollama through `langchain_ollama.OllamaEmbeddings`.

Default:

```text
mxbai-embed-large:latest
```

The embedding model is a singleton, so the first load is reused across requests and tasks in the same process.

### Vector Storage

Default backend:

```text
VECTOR_DB_TYPE=chromadb
```

ChromaDB stores document text, metadata, ids, and embeddings in a persistent client directory.

Optional backend:

```text
VECTOR_DB_TYPE=faiss
```

FAISS manager support exists in the codebase, including persistence and document metadata operations.

### Retrieval

`SemanticRetriever`:

- validates the query
- calls vector store `search()`
- filters results using `SIMILARITY_THRESHOLD`
- sorts by score descending
- returns `(Document, score)` tuples

Default threshold:

```text
SIMILARITY_THRESHOLD=0.10
```

This is intentionally permissive. Raise it for stricter matching; lower it only if relevant chunks are being filtered out.

### Generation

`ChatService` builds a prompt that tells the model:

- answer only from retrieved context
- say the context is insufficient when needed
- keep answers concise and factual
- cite source numbers when useful

RAG modes:

| Mode | Top K | Temperature |
| --- | ---: | ---: |
| `precise` | 3 | 0.1 |
| `balanced` | 5 | 0.3 |
| `creative` | 8 | 0.8 |

Response styles:

- `professional`
- `concise`
- `beginner_friendly`
- `research`
- `technical`

## Async Processing

Document ingestion is queue-based.

Celery settings:

- app name: `rag_worker`
- queue: `document_processing`
- broker: Redis
- result backend: `rpc://`
- Windows worker pool: `solo`
- max retries: 3
- retry backoff: 10s, 20s, 40s

Processing lifecycle:

```text
queued -> processing -> parsing -> chunking -> embedding -> vectorizing -> saving -> completed
```

Failure lifecycle:

```text
queued -> processing -> retrying -> processing -> failed
```

Supabase `documents` is the source of truth for:

- `processing_status`
- `processing_progress`
- `processing_stage`
- `job_id`
- `processing_error`
- `retry_count`
- `processing_started_at`
- `processing_completed_at`

## Testing

Backend test files currently live mostly at the backend root:

- `backend/test_pdf_loader.py`
- `backend/test_chunking.py`
- `backend/test_embeddings.py`
- `backend/test_chromadb.py`
- `backend/test_retriever.py`
- `backend/test_pipeline.py`
- `backend/test_ollama.py`

Run:

```bash
cd backend
pytest -v
```

Frontend scripts:

```bash
cd frontend
npm run lint
npm run build
```

There is no frontend test script currently defined in `frontend/package.json`.

## Known Caveats

- The root README that existed before this update was stale and contained encoding artifacts; this version is ASCII-clean.
- `backend/requirements.txt` lists `sentence-transformers`, but the current embedding implementation uses `langchain_ollama.OllamaEmbeddings`. Install `langchain-ollama` if it is missing.
- `TextSplitter` imports newer LangChain packages such as `langchain-text-splitters` and optionally `langchain-experimental`; install them if chunking imports fail.
- `ChromaManager` prefers `langchain_chroma` when available, then the code has native Chroma fallbacks in service paths. Install `langchain-chroma` for the manager path.
- `frontend/src/services/api.js` hardcodes `http://localhost:8000` while `AuthContext` uses `VITE_API_BASE_URL`.
- `start_rag_project.bat` contains a visible `ssREM` typo before the frontend section. The launcher may still proceed depending on CMD behavior, but it should be cleaned up.
- Supabase service-role key is required for backend writes in collections, settings, chat history, and document status updates.
- Uploaded file deletion currently checks the stored `filename` directly and may miss files stored under `UPLOAD_DIR` if only a basename is saved.

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| Frontend cannot log in | Missing `VITE_SUPABASE_URL` or `VITE_SUPABASE_ANON_KEY` | Add `frontend/.env` and restart Vite. |
| Backend returns 503 for auth, documents, settings, or history | Supabase credentials missing | Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and for writes `SUPABASE_SERVICE_ROLE_KEY`. |
| Upload returns queue error | Celery worker or Redis not running | Start Redis and `backend/start_worker.bat`. |
| Document stays queued | Worker is not consuming `document_processing` | Check Celery window and Redis connection. |
| PDF fails with no extractable text | Scanned/image-only PDF | Add OCR preprocessing or upload text-based PDFs. |
| Chat says no chunks were retrieved | Empty vector collection, wrong collection id, high threshold, or embedding mismatch | Upload documents, verify collection, lower `SIMILARITY_THRESHOLD`, or recreate collection after embedding model changes. |
| Ollama embedding model fails | Model not pulled or Ollama not running | Run `ollama serve` and `ollama pull mxbai-embed-large:latest`. |
| Ollama generation fails | Chat model not pulled | Run `ollama pull qwen2.5:3b` or update `OLLAMA_MODEL`. |
| Chroma dimension mismatch | Changed embedding model after indexing | Re-ingest documents or let the ingestion guard recreate affected collections. |
| Frontend API calls hit the wrong backend | Hardcoded API base in `api.js` | Update `BASE_URL` or refactor to use `VITE_API_BASE_URL`. |

## License

No license file is currently present in the repository. Add one before publishing or distributing this project.
