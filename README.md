# RAG (Retrieval-Augmented Generation) System

A modular, production-ready Retrieval-Augmented Generation (RAG) platform built with Python/FastAPI backend and React/Vite frontend. Enables users to upload documents, chat with their content using LLMs, and get accurate, citation-backed answers.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Configuration](#configuration)
- [Core Components & Values](#core-components--values)
  - [Embedding Model](#embedding-model)
  - [LLM & Generation Settings](#llm--generation-settings)
  - [Chunking Strategy](#chunking-strategy)
  - [Retrieval Settings](#retrieval-settings)
  - [Threshold & Top‑K](#threshold--top-k)
- [Setup & Installation](#setup--installation)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Frontend Usage](#frontend-usage)
- [Testing](#testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview
The RAG system allows users to:
- Upload PDF/DOCX documents
- Automatically extract text, chunk it, generate embeddings, and store them in a vector database (ChromaDB)
- Chat with the uploaded documents using an LLM (Ollama) with retrieval‑augmented generation
- View citations and source documents for each answer
- Manage multiple collections (workspaces) to isolate different document sets
- Persist chat history and uploaded file metadata across sessions (via localStorage on the frontend and optional Supabase backend)

---

## Features
- **Document Ingestion**: PDF & DOCX loaders, recursive character‑based chunking, metadata preservation
- **Vector Storage**: ChromaDB (persistent) with pluggable interface for other stores (FAISS, etc.)
- **Embeddings**: Sentence‑Transformers / HuggingFace models (configurable)
- **LLM Backend**: Ollama (supports Llama 2, Mistral, etc.) with adjustable temperature, top‑p, top‑k
- **Retrieval**: Semantic search with configurable top‑K and similarity threshold
- **Citation Generation**: Inline citations linking to source chunks
- **Multi‑tenant Collections**: Separate vector stores per collection
- **Chat History**: Persisted per‑session (localStorage) with optional Supabase backup
- **RESTful API**: Fully typed OpenAPI docs (Swagger/ReDoc)
- **React/Vite Frontend**: Modern UI with TailwindCSS, modal uploads, chat windows, collection manager
- **Docker & Kubernetes Ready**: Production‑grade deployment files
- **Comprehensive Test Suite**: Unit & integration tests for backend and frontend

---

## Architecture
```
RAG/
├── backend/                     # Python/FastAPI service
│   ├── api/                     # REST route handlers
│   ├── rag/                     # Core RAG pipeline (loaders, chunking, embeddings, vectorstore, retrievers, pipelines, LLM)
│   ├── services/                # Business logic wrappers
│   ├── db/                      # SQLAlchemy models & migrations
│   ├── schemas/                 # Pydantic request/response models
│   ├── config/                  # Settings, database, logging
│   └── uploads/                 # Temporary file storage
├── frontend/                    # React/Vite SPA
│   ├── src/
│   │   ├── pages/               # Route‑based pages (Chat, Documents, etc.)
│   │   ├── components/          # Reusable UI pieces
│   │   ├── hooks/               # Custom React hooks (useChat, useAuth, …)
│   │   ├── services/            # API service layer
│   │   ├── context/             # React Context for global state
│   │   └── types/               # TypeScript definitions
└── infrastructure/              # Docker, K8s, scripts
```

Data Flow (Upload → Query):
1. User uploads file → `upload_service` saves file → `PDFLoader`/`DocxLoader` extracts text
2. `TextSplitter` creates chunks (500 ch, 100 overlap) → metadata enriched
3. `EmbeddingService` generates vectors (sentence‑transformer model)
4. `VectorStore` (ChromaDB) stores `{id, chunk_text, embedding, metadata}`
5. On chat request: query embedded → similarity search → top‑K chunks filtered by threshold τ
6. Retrieved chunks + system prompt → LLM (Ollama) generates answer
7. Response parsed, citations attached, stored in chat history

---

## Technology Stack
| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **Database** | SQLAlchemy (PostgreSQL via Supabase optional), ChromaDB |
| **Embedding** | Sentence‑Transformers (`sentence-transformers/all-MiniLM-L6-v2` default) |
| **LLM** | Ollama (supports Llama2, Mistral, Nemotron, etc.) |
| **Frontend** | React 18, Vite, TypeScript, TailwindCSS |
| **State Management** | React Context + localStorage |
| **HTTP Client** | Axios |
| **Dev** | ESLint, Prettier, Jest/Test‑Runner (frontend), Pytest (backend) |
| **CI/CD** | Docker, Docker‑Compose, Kubernetes manifests |

---

## Configuration
Configuration lives in `backend/config/settings.py` (loaded from environment variables or `.env`). Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_NAME` | Application name | `RAG Backend` |
| `API_VERSION` | API version string | `v1` |
| `DEBUG` | Enable debug mode | `True` |
| `HOST` | Bind host | `0.0.0.0` |
| `PORT` | Bind port | `8000` |
| `CHUNK_SIZE` | Max characters per chunk | `500` |
| `CHUNK_OVERLAP` | Overlap between chunks | `100` |
| `EMBEDDING_MODEL_NAME` | HuggingFace sentence‑transformer model | `sentence-transformers/all-MiniLM-L6-v2` |
| `EMBEDDING_DEVICE` | `cpu` or `cuda` | `cpu` |
| `VECTOR_DB_TYPE` | `chromadb` or `faiss` | `chromadb` |
| `CHROMA_PERSIST_DIR` | Persistence path for ChromaDB | `./chroma_db` |
| `FAISS_INDEX_DIR` | Persistence path for FAISS | `./faiss_index` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Default LLM model | `llama2` |
| `LLM_TEMPERATURE` | Sampling temperature | `0.7` |
| `LLM_TOP_P` | Nucleus sampling top‑p | `0.9` |
| `LLM_TOP_K` | Top‑k sampling | `40` |
| `RETRIEVAL_TOP_K` | Number of chunks to retrieve before threshold | `5` |
| `RETRIEVAL_THRESHOLD` | Similarity threshold (cosine) for keeping chunks | `0.75` |
| `SUPABASE_URL` | Supabase project URL (optional) | *(empty)* |
| `SUPABASE_ANON_KEY` | Supabase anon key (optional) | *(empty)* |
| `LOG_LEVEL` | Logging level | `INFO` |
| `CORS_ORIGINS` | Allowed CORS origins (comma‑separated) | `*` |
| `MAX_UPLOAD_SIZE` | Max upload size in bytes | `10485760` (10 MB) |
| `UPLOAD_DIR` | Temporary upload folder | `./uploads` |

> **Note**: Leaving `SUPABASE_URL` and `SUPABASE_ANON_KEY` empty disables Supabase persistence; the system works fully with local ChromaDB and localStorage.

Create a `.env` file in the `backend/` folder based on `.env.example`.

---

## Core Components & Values

### Embedding Model
- **Provider**: HuggingFace Sentence‑Transformers
- **Default Model**: `all-MiniLM-L6-v2` (384‑dimension, fast & accurate)
- **Device**: Configurable via `EMBEDDING_DEVICE` (`cpu`/`cuda`)
- **Batch Size**: Internally handled by the model; can be tuned in `embedding_service.py` if needed

### LLM & Generation Settings
- **Backend**: Ollama HTTP API
- **Default Model**: `llama2` (change via `OLLAMA_MODEL`)
- **Temperature**: `LLM_TEMPERATURE` (default `0.7`) – controls randomness
- **Top‑p**: `LLM_TOP_P` (default `0.9`) – nucleus sampling
- **Top‑k**: `LLM_TOP_K` (default `40`) – limits sampling pool
- **Max Tokens**: Determined by model; can be overridden in prompt templates if needed
- **System Prompt**: Defined in `backend/rag/prompts/system_prompts.py` – instructs model to answer based on provided context and to cite sources

### Chunking Strategy
- **Algorithm**: `RecursiveCharacterTextSplitter` (LangChain)
- **Separators** (in order): `"\n\n"`, `"\n"`, `" "`, `""`
- **Chunk Size**: `CHUNK_SIZE` = **500** characters
- **Chunk Overlap**: `CHUNK_OVERLAP` = **100** characters
- **Metadata Enrichment**:
  - Original document metadata preserved
  - Added fields: `source_document_index`, `chunk_index`, `chunk_total`, `chunk_size`
- **Chunk Validation**: Ensures no empty chunks, logs statistics

### Retrieval Settings
- **Vector Store**: ChromaDB (persistent) – pluggable interface defined in `base_vectorstore.py`
- **Similarity Metric**: Cosine similarity (default for ChromaDB)
- **Top‑K**: `RETRIEVAL_TOP_K` = **5** (number of nearest neighbours fetched before thresholding)
- **Similarity Threshold**: `RETRIEVAL_THRESHOLD` = **0.75** (chunks with cosine similarity ≥ 0.75 are kept)
- **Fallback**: If fewer than 1 chunk passes threshold, the system falls back to the top‑1 chunk (to avoid empty context) – configurable in `semantic_retriever.py`

### Threshold & Top‑K
- **Top‑K (`RETRIEVAL_TOP_K`)**: Controls how many candidates are fetched from the vector store before applying the threshold. Higher values increase recall but add latency.
- **Threshold (`RETRIEVAL_THRESHOLD`)**: Minimum similarity score required for a chunk to be considered relevant.  
  - **Low τ (e.g., 0.5)** → more chunks, higher recall, potential noise.  
  - **High τ (e.g., 0.85)** → fewer, highly relevant chunks, higher precision.
- **Recommendation**: Start with the defaults (`top_k=5`, `τ=0.75`) and adjust using the validation procedure described in the[Tuning Threshold](#threshold--top-k) section of this README.

---

## Setup & Installation

### Prerequisites
- **Git**
- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **Ollama** installed & running (download from https://ollama.com)
- **(Optional)** Docker & Docker‑Compose for containerized deployment
- **(Optional)** Supabase account if you want cloud persistence

### Backend
```bash
# Clone repo (if not already)
git clone <repo-url>
cd RAG/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt   # or pip install -r pyproject.toml
# Ensure sentence-transformers, chromadb, fastapi, uvicorn, python-dotenv are installed

# Copy environment template
cp .env.example .env
# Edit .env as needed (see Configuration section)

# Initialize DB (if using PostgreSQL via Supabase)
# For local ChromaDB, no further DB setup needed
```

### Frontend
```bash
cd ../frontend
npm install
# Create .env from example (optional)
cp .env.example .env
# Adjust VITE_API_BASE_URL if backend runs on different host/port
```

### Ollama (LLM)
```bash
# Install Ollama (https://ollama.com/download)
# Pull a model, e.g.:
ollama pull llama2
# Ensure Ollama server is running (default localhost:11434)
ollama serve   # runs in background
```

---

## Running the Application

### Development Mode (Separate Terminals)

#### Backend
```bash
cd backend
# Activate venv if not already
source venv/bin/activate
python -m app.main   # or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

#### Frontend
```bash
cd frontend
npm run dev   # Vite dev server, defaults to http://localhost:5173
```
The frontend will proxy API calls to `http://localhost:8000` (adjust `VITE_API_BASE_URL` in `.env` if needed).

### Production (Docker‑Compose)
```bash
cd infrastructure/docker
docker-compose -f docker-compose.prod.yml up -d
```
This spins up:
- backend (FastAPI + Uvicorn)
- frontend (Nginx serving built React app)
- ChromaDB (persistent volume)
- Ollama (separate service; ensure model is pulled inside container or mount model store)

---

## API Endpoints
All routes are prefixed with `/api/v1`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| **POST** | `/upload` | Upload a PDF/DOCX, returns `UploadResponse` with `document_id`, `total_chunks`, etc. |
| **GET** | `/documents` | List documents for a user (supports `collection_id` filter) |
| **GET** | `/documents/{document_id}` | Get metadata for a specific document |
| **DELETE** | `/documents/{document_id}` | Delete a document (and its vectors) |
| **POST** | `/chat` | Send a chat request (`question`, optional `collection_id`, `top_k`). Returns answer, sources, response time. |
| **POST** | `/chat/sessions` | Create a new chat session |
| **GET** | `/chat/sessions` | List chat sessions for a user |
| **GET** | `/chat/sessions/{session_id}` | Get a session with its messages |
| **DELETE** | `/chat/sessions/{session_id}` | Delete a session and its messages |
| **POST** | `/chat/messages` | Save a chat message (used internally by frontend) |
| **GET** | `/auth/profile/{user_id}` | Get user profile |
| **POST** | `/auth/profile` | Create/update profile (called after Supabase sign‑up) |
| **GET** | `/health` | Health check |
| **GET** | `/search` | Advanced semantic search (returns chunks with scores) |

Full OpenAPI spec accessible at `/docs`.

---

## Frontend Usage
- **Dashboard**: Overview of document count, chat sessions, uploads, collections.
- **Documents**: Upload new files, view list, delete files, see chunk counts.
- **Chat**: Select a collection, type questions, view answers with inline citations, copy or regenerate.
- **Chat History** (`/history`): Browse past conversations; clicking a entry loads that chat for continuation.
- **Collections**: Create, edit, delete collections; each collection has its own isolated vector store.
- **Search**: Advanced search page to explore raw retrieved chunks and scores.

State (uploaded file list, chat history) is persisted in `localStorage`; clearing browser storage resets it unless Supabase is configured.

---

## Testing
### Backend
```bash
cd backend
pytest -v
```
Tests cover:
- Loaders, chunking, embeddings
- Vector store operations
- Retrieval pipelines
- API route handlers
- Service layer logic

### Frontend
```bash
cd frontend
npm run test   # Uses Jest + React Testing Library
```
Tests for UI components, hooks, and API service mocks.

---

## Deployment
### Docker (single‑host)
```bash
cd infrastructure/docker
docker-compose up -d   # uses docker-compose.yml (dev) or docker-compose.prod.yml (prod)
```

### Kubernetes
```bash
cd infrastructure/kubernetes
kubectl apply -f .
```
Includes Deployments, Services, Ingress, PersistentVolumes for ChromaDB and Ollama.

### Environment Variables for Prod
Set the following in your CI/CD or K8s secrets:
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `LLM_TEMPERATURE`, `LLM_TOP_P`, `LLM_TOP_K`
- `RETRIEVAL_TOP_K`, `RETRIEVAL_THRESHOLD`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY` (if using)
- `VECTOR_DB_TYPE` (chromadb/faiss)
- `LOG_LEVEL=warning`

---

## Troubleshooting
| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| **422 Unprocessable Entity** on `/chat/messages` | Payload fails Pydantic validation (missing/empty `question` or `answer`, wrong `sources_json` type) | Inspect request payload in DevTools Network tab; ensure non‑empty strings and proper JSON object for `sources_json` |
| **503 Service Unavailable** on auth/profile routes | Supabase client not configured (empty credentials) but routes still raise 503 | Verify `backend/app/api/routes/auth_routes.py` `_sb()` returns `None` instead of raising; update as per fix |
| **No chunks returned / empty answer** | Similarity threshold too high or embedding mismatch | Lower `RETRIEVAL_THRESHOLD` (e.g., to 0.60) or verify embedding model is loaded; check ChromaDB collection count |
| **Backend fails to start** | Missing environment variable or port conflict | Check `.env` values; ensure ports 8000 (backend) and 5173 (frontend) are free |
| **Frontend shows “Failed to load documents” but documents appear** | Backend documents route returns empty list (Supabase not configured) while frontend falls back to localStorage | Expected behavior when Supabase empty; ignore message or adjust backend to return empty list without error |
| **Chat history not persisting after reload** | `localStorage` cleared or `useApp` context not initialized | Ensure `frontend/src/AppContext.jsx` reads/writes localStorage correctly; no ad‑blocker clearing storage |
| **Ollama model not found** | Model not pulled or server not reachable | Run `ollama pull <model>` and verify `ollama serve` is running; check `OLLAMA_BASE_URL` |

---

## License
This project is licensed under the MIT License – see the `LICENSE` file for details.

---

**Happy Retrieval‑Augmented Generating!**  
For any questions, open an issue or reach out to the maintainers. 🚀