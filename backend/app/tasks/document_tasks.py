"""
Background document ingestion task.

Architecture:
  - Celery task registered in the 'document_processing' queue
  - Supabase is the SINGLE SOURCE OF TRUTH for processing_status and progress
  - Redis is NOT used for state — only as the broker transport
  - Progress is REAL (computed from actual work done, not hardcoded percentages)

Lifecycle:
  queued → processing → (parsing → chunking → embedding → vectorizing) → completed
  On failure:   failed (with error message + retry_count increment)
  On retry:     retrying → processing → ...

Idempotency:
  If document already has processing_status = 'completed', task exits immediately.
  This prevents duplicate vectors/chunks on accidental re-enqueue.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


# ─── DB helpers ───────────────────────────────────────────────────────────────

def _get_supabase():
    """Return Supabase admin client (bypasses RLS for internal writes)."""
    from app.db.supabase import get_supabase_admin_client
    return get_supabase_admin_client()


def _update_doc_status(
    document_id: str,
    *,
    status: str,
    progress: int = 0,
    stage: str = "",
    error: Optional[str] = None,
    job_id: Optional[str] = None,
    total_pages: Optional[int] = None,
    total_chunks: Optional[int] = None,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    increment_retry: bool = False,
) -> None:
    """Persist processing state into Supabase documents table."""
    sb = _get_supabase()
    if not sb:
        logger.warning("Supabase unavailable — cannot update document status.")
        return

    payload: dict = {
        "processing_status": status,
        "processing_progress": progress,
    }
    if stage:
        payload["processing_stage"] = stage
    if error is not None:
        payload["processing_error"] = error
    if job_id is not None:
        payload["job_id"] = job_id
    if total_pages is not None:
        payload["total_pages"] = total_pages
    if total_chunks is not None:
        payload["total_chunks"] = total_chunks
    if started_at is not None:
        payload["processing_started_at"] = started_at
    if completed_at is not None:
        payload["processing_completed_at"] = completed_at

    try:
        if increment_retry:
            # Fetch current retry_count then increment
            row = sb.table("documents").select("retry_count").eq("document_id", document_id).single().execute()
            current = (row.data or {}).get("retry_count", 0) or 0
            payload["retry_count"] = current + 1

        sb.table("documents").update(payload).eq("document_id", document_id).execute()
        logger.debug("Updated document status. document_id=%s status=%s progress=%s", document_id, status, progress)
    except Exception as exc:
        logger.error("Failed to update document status in DB: %s", exc)


def _get_doc_status(document_id: str) -> Optional[str]:
    """Fetch current processing_status from Supabase."""
    sb = _get_supabase()
    if not sb:
        return None
    try:
        row = sb.table("documents").select("processing_status").eq("document_id", document_id).single().execute()
        return (row.data or {}).get("processing_status")
    except Exception:
        return None


# ─── Main task ────────────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.tasks.document_tasks.process_document_task",
    max_retries=3,
    queue="document_processing",
    acks_late=True,
)
def process_document_task(
    self: Task,
    document_id: str,
    file_path: str,
    collection_id: str,
    user_id: Optional[str] = None,
) -> dict:
    """
    Full document ingestion pipeline running in a Celery worker.

    Steps:
      1. Idempotency check — abort if already completed
      2. Parse PDF into pages
      3. Chunk pages into embedding-ready segments
      4. Generate embeddings (progress per-chunk)
      5. Store vectors in ChromaDB/FAISS
      6. Persist final metadata to Supabase
      7. Mark completed

    Returns dict with summary for rpc:// result (not stored in Redis).
    """
    task_id = self.request.id or "unknown"
    started_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "process_document_task started. document_id=%s task_id=%s file_path=%s collection_id=%s",
        document_id, task_id, file_path, collection_id,
    )

    # ── 1. Idempotency guard ──────────────────────────────────────────────────
    current_status = _get_doc_status(document_id)
    if current_status == "completed":
        logger.info("Document already completed — skipping. document_id=%s", document_id)
        return {"document_id": document_id, "status": "already_completed"}

    # ── 2. Mark as processing ─────────────────────────────────────────────────
    _update_doc_status(
        document_id,
        status="processing",
        progress=5,
        stage="starting",
        job_id=task_id,
        error=None,
        started_at=started_at,
    )

    try:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Uploaded file not found: {file_path}")

        # ── 3. Parse PDF ──────────────────────────────────────────────────────
        _update_doc_status(document_id, status="processing", progress=10, stage="parsing")
        from app.rag.loaders import PDFLoader
        loader = PDFLoader(file_path=str(path))
        documents = loader.load()

        if not documents or not any(d.page_content.strip() for d in documents):
            raise ValueError("PDF contains no extractable text")

        total_pages = len(documents)
        _update_doc_status(
            document_id,
            status="processing",
            progress=20,
            stage="chunking",
            total_pages=total_pages,
        )
        logger.info("Parsed %d pages. document_id=%s", total_pages, document_id)

        # ── 4. Chunk ──────────────────────────────────────────────────────────
        from app.core.config import settings
        from app.rag.chunking import TextSplitter

        splitter = TextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        chunks = splitter.split_documents(documents)

        if not chunks:
            raise ValueError("Text splitter produced no chunks")

        total_chunks = len(chunks)
        _update_doc_status(
            document_id,
            status="processing",
            progress=35,
            stage="chunking",
            total_chunks=total_chunks,
        )
        logger.info("Generated %d chunks. document_id=%s", total_chunks, document_id)

        # Attach metadata to every chunk
        for idx, chunk in enumerate(chunks):
            chunk.metadata.update({
                "document_id": document_id,
                "collection_id": collection_id,
                "uploaded_filename": path.name,
                "chunk_id": f"{document_id}-{idx:04d}",
            })

        # ── 5. Embed (real per-chunk progress) ───────────────────────────────
        _update_doc_status(document_id, status="processing", progress=40, stage="embedding")
        from app.rag.embeddings import EmbeddingModel as EmbeddingManager

        embedding_manager = EmbeddingManager()
        texts = [chunk.page_content for chunk in chunks]
        embeddings: list = []

        # Embed in batches of 32 — update progress per batch
        batch_size = 32
        for batch_start in range(0, total_chunks, batch_size):
            batch_texts = texts[batch_start: batch_start + batch_size]
            batch_embeddings = embedding_manager.embed_documents(batch_texts)
            embeddings.extend(batch_embeddings)

            # Real progress: 40% + up to 40% during embedding phase
            embed_progress = int(40 + (len(embeddings) / total_chunks) * 40)
            _update_doc_status(
                document_id,
                status="processing",
                progress=embed_progress,
                stage="embedding",
            )
            logger.debug(
                "Embedded %d/%d chunks. progress=%d%% document_id=%s",
                len(embeddings), total_chunks, embed_progress, document_id,
            )

        if len(embeddings) != total_chunks:
            raise ValueError(f"Embedding mismatch: expected {total_chunks}, got {len(embeddings)}")

        # ── 6. Store vectors ──────────────────────────────────────────────────
        _update_doc_status(document_id, status="processing", progress=82, stage="vectorizing")
        from app.rag.vectorstore import ChromaManager, FAISSManager, ChromaDBError, FAISSError

        vector_db_type = settings.VECTOR_DB_TYPE.lower()
        stored_count = 0

        if vector_db_type == "faiss":
            manager = FAISSManager(
                index_dir=str(settings.FAISS_INDEX_DIR),
                collection_name=collection_id,
                embedding_function=embedding_manager.embeddings,
            )
            manager.add_documents(chunks)
            manager.persist()
            stats = manager.get_collection_stats()
            stored_count = int(stats.get("document_count", 0))
        else:
            # ChromaDB path
            from importlib.util import find_spec
            if find_spec("langchain_chroma") is not None:
                manager = ChromaManager(
                    persist_dir=str(settings.CHROMA_PERSIST_DIR),
                    collection_name=collection_id,
                    embedding_function=embedding_manager.embeddings,
                )
                manager.add_documents(chunks)
                manager.persist()
                stats = manager.get_collection_stats()
                stored_count = int(stats.get("document_count", 0))
            else:
                import chromadb
                client = chromadb.PersistentClient(path=str(settings.CHROMA_PERSIST_DIR))

                # Dimension guard
                new_dim = len(embeddings[0]) if embeddings else 0
                try:
                    existing = client.get_collection(name=collection_id)
                    probe = existing.get(limit=1, include=["embeddings"])
                    probe_emb = probe.get("embeddings") or []
                    if probe_emb and len(probe_emb[0]) != new_dim:
                        logger.warning(
                            "Dimension mismatch in collection '%s' (%d vs %d) — recreating.",
                            collection_id, len(probe_emb[0]), new_dim,
                        )
                        client.delete_collection(name=collection_id)
                except Exception:
                    pass  # Collection doesn't exist yet

                collection = client.get_or_create_collection(name=collection_id)
                ids = [str(chunk.metadata["chunk_id"]) for chunk in chunks]
                docs_text = [chunk.page_content for chunk in chunks]
                metas = [_sanitize_metadata(chunk.metadata) for chunk in chunks]

                # Delete existing IDs to prevent duplicates
                existing_result = collection.get(ids=ids)
                existing_ids = set(existing_result.get("ids", []))
                if existing_ids:
                    collection.delete(ids=list(existing_ids))

                collection.add(ids=ids, documents=docs_text, metadatas=metas, embeddings=embeddings)
                stored_count = collection.count()

        _update_doc_status(document_id, status="processing", progress=95, stage="saving")
        logger.info("Stored %d vectors. document_id=%s", stored_count, document_id)

        # ── 7. Mark completed ─────────────────────────────────────────────────
        completed_at = datetime.now(timezone.utc).isoformat()
        _update_doc_status(
            document_id,
            status="completed",
            progress=100,
            stage="completed",
            total_pages=total_pages,
            total_chunks=total_chunks,
            completed_at=completed_at,
        )

        logger.info(
            "Document ingestion complete. document_id=%s pages=%d chunks=%d vectors=%d",
            document_id, total_pages, total_chunks, stored_count,
        )

        return {
            "document_id": document_id,
            "status": "completed",
            "total_pages": total_pages,
            "total_chunks": total_chunks,
            "stored_vectors": stored_count,
        }

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.error(
            "Document ingestion failed. document_id=%s error=%s retries=%d/%d",
            document_id, error_msg, self.request.retries, self.max_retries,
        )

        if self.request.retries < self.max_retries:
            # Retry with exponential backoff: 10s, 20s, 40s
            retry_delay = 10 * (2 ** self.request.retries)
            _update_doc_status(
                document_id,
                status="retrying",
                progress=0,
                stage="retrying",
                error=error_msg,
                increment_retry=True,
            )
            logger.info(
                "Scheduling retry %d/%d in %ds. document_id=%s",
                self.request.retries + 1, self.max_retries, retry_delay, document_id,
            )
            raise self.retry(exc=exc, countdown=retry_delay)
        else:
            # All retries exhausted — mark as permanently failed
            _update_doc_status(
                document_id,
                status="failed",
                progress=0,
                stage="failed",
                error=error_msg,
                increment_retry=True,
            )
            logger.error(
                "All retries exhausted. document_id=%s marked failed.", document_id,
            )
            return {
                "document_id": document_id,
                "status": "failed",
                "error": error_msg,
            }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _sanitize_metadata(metadata: dict) -> dict:
    """Convert metadata to ChromaDB-compatible primitive values."""
    sanitized: dict = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[str(key)] = value
        else:
            sanitized[str(key)] = str(value)
    return sanitized
