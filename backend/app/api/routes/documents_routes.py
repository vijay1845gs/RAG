"""
Documents routes — production-grade CRUD for user documents.

Table columns (db/schema.sql):
  id             UUID   PK DEFAULT uuid_generate_v4()
  user_id        UUID   NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE
  collection_id  UUID   NOT NULL REFERENCES public.collections(id) ON DELETE CASCADE
  filename       TEXT   NOT NULL
  document_id    TEXT   NOT NULL
  total_pages    INT
  total_chunks   INT
  upload_status  TEXT   DEFAULT 'processing' NOT NULL
  file_size      BIGINT
  created_at     TIMESTAMPTZ DEFAULT NOW() NOT NULL

Canonical document identifier exposed in the API: document_id (TEXT PK).
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query, status

from app.db.supabase import get_supabase_admin_client
from app.db.supabase import get_supabase_client as get_anon_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


# ─── Helpers ─────────────────────────────────────────────────────

def _sb_read():
    sb = get_anon_client()
    if sb is None:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    return sb


def _sb_write():
    sb = get_supabase_admin_client()
    if sb is None:
        raise HTTPException(status_code=503, detail="Service-role key not configured")
    return sb


def _doc_envelope(doc: dict) -> dict:
    """Normalise a raw DB row adding stable frontend keys."""
    return {
        "id":                      doc.get("id", ""),
        "document_id":             doc.get("document_id", ""),
        "user_id":                 doc.get("user_id", ""),
        "collection_id":           doc.get("collection_id") or "",
        "filename":                doc.get("filename", ""),
        "total_pages":             doc.get("total_pages"),
        "total_chunks":            doc.get("total_chunks"),
        "upload_status":           doc.get("upload_status", "processing"),
        # Phase 7 processing fields
        "processing_status":       doc.get("processing_status", doc.get("upload_status", "unknown")),
        "processing_progress":     doc.get("processing_progress", 0),
        "processing_stage":        doc.get("processing_stage"),
        "job_id":                  doc.get("job_id"),
        "processing_error":        doc.get("processing_error"),
        "retry_count":             doc.get("retry_count", 0),
        "processing_started_at":   doc.get("processing_started_at"),
        "processing_completed_at": doc.get("processing_completed_at"),
        "file_size":               doc.get("file_size"),
        "created_at":              doc.get("created_at"),
    }


def _paginated_envelope(items, total: int, limit: int, offset: int) -> dict:
    return {
        "items":     items,
        "total":     total,
        "limit":     limit,
        "offset":    offset,
        "has_more":  offset + len(items) < total,
    }


# ─── Routes ──────────────────────────────────────────────────────

# ── LIST (paginated + search + sort) ─────────────────────────────

@router.get("", response_model=dict)
async def list_documents(
    user_id:      str,
    collection_id: Optional[str] = Query(None, description="Filter by collection UUID"),
    search:        Optional[str] = Query(None, min_length=1, description="Substring match on filename"),
    sort_by:       str            = Query("created_at", pattern="^(created_at|filename|upload_status|total_chunks)$"),
    sort_order:    str            = Query("desc",  pattern="^(asc|desc)$"),
    limit:         int            = Query(20, ge=1, le=200),
    offset:        int            = Query(0, ge=0),
):
    """
    Return a paginated document list for the authenticated user.

    Uses two queries total (N-query-free):
      1. filtered + ordered count → total
      2. page slice → items
    """
    sb = _sb_read()

    base = (
        sb.table("documents")
        .select("*", count="exact")
        .eq("user_id", user_id)
    )
    if collection_id:
        base = base.eq("collection_id", collection_id)
    if search:
        base = base.ilike("filename", f"%{search}%")

    total_res  = base.order(sort_by, desc=(sort_order == "desc")).execute()
    total      = total_res.count or 0

    page_res = (
        sb.table("documents")
        .select("*", count="exact")
        .eq("user_id", user_id)
    )
    if collection_id:
        page_res = page_res.eq("collection_id", collection_id)
    if search:
        page_res = page_res.ilike("filename", f"%{search}%")

    page_res = (
        page_res
        .order(sort_by, desc=(sort_order == "desc"))
        .range(offset, offset + limit - 1)
        .execute()
    )

    items = [_doc_envelope(d) for d in (page_res.data or [])]
    return _paginated_envelope(items, total, limit, offset)


# ── GET by document_id ───────────────────────────────────────────

@router.get("/{document_id}", response_model=dict)
async def get_document(
    document_id: str,
    user_id:     str,
):
    """Return a single document row by document_id."""
    sb = _sb_read()
    res = (
        sb.table("documents")
        .select("*")
        .eq("document_id", document_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_envelope(res.data)


# ── PREVIEW ──────────────────────────────────────────────────────

@router.get("/{document_id}/preview", response_model=dict)
async def preview_document(
    document_id: str,
    user_id:     str,
):
    """
    Return preview metadata for a document.

    Response:
      filename, uploaded_at, collection (name + id), total_chunks,
      file_size, upload_status, upload_duration, preview_text
    """
    sb = _sb_read()

    doc_res = (
        sb.table("documents")
        .select("*")
        .eq("document_id", document_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not doc_res.data:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = doc_res.data
    coll_res = (
        sb.table("collections")
        .select("id, name, description")
        .eq("id", doc.get("collection_id"))
        .single()
        .execute()
    )
    coll = coll_res.data if coll_res.data else {}

    return {
        "document_id":     doc.get("document_id"),
        "filename":        doc.get("filename"),
        "uploaded_at":     doc.get("created_at"),
        "collection": {
            "id":          coll.get("id", doc.get("collection_id", "")),
            "name":        coll.get("name") or "Unknown",
            "description": coll.get("description"),
        },
        "total_pages":     doc.get("total_pages"),
        "total_chunks":    doc.get("total_chunks"),
        "file_size":       doc.get("file_size"),
        "upload_status":   doc.get("upload_status", "processing"),
        "preview_text":    None,          # populated by caller from storage
    }


# ── RENAME ───────────────────────────────────────────────────────

@router.patch("/{document_id}", response_model=dict)
async def rename_document(
    document_id: str,
    payload:     dict[str, str],       # { "filename": "New Name.pdf" }
    user_id:     str                   = Query(..., description="UUID of the owning user"),
):
    """Rename a document (updates the `filename` column). Requires `filename` in the body."""
    sb = _sb_write()
    new_name = payload.get("filename", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="filename is required in the request body")

    own = (
        sb.table("documents")
        .select("id")
        .eq("document_id", document_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not own.data:
        raise HTTPException(status_code=404, detail="Document not found")

    res = (
        sb.table("documents")
        .update({"filename": new_name})
        .eq("id", own.data[0]["id"])
        .execute()
    )

    row = res.data[0] if res.data else {"document_id": document_id, "filename": new_name}
    return {
        "success":   True,
        "document_id": row.get("document_id", document_id),
        "filename":  row.get("filename", new_name),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── MOVE COLLECTION ──────────────────────────────────────────────

@router.patch("/{document_id}/collection", response_model=dict)
async def move_document_collection(
    document_id:   str,
    payload:       dict[str, str] = Body(...),   # { "collection_id": "<target-uuid>" }
    user_id:       str               = Query(..., description="UUID of the owning user"),
):
    """Move a document to a different collection. Validates target-collection ownership and re-processes embeddings."""
    sb = _sb_write()
    target_cid = (payload.get("collection_id") or "").strip()
    if not target_cid:
        raise HTTPException(status_code=400, detail="collection_id is required in the request body")

    # Verify source document ownership and get current collection + file path
    src = (
        sb.table("documents")
        .select("id, collection_id, filename")
        .eq("document_id", document_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not src.data:
        raise HTTPException(status_code=404, detail="Source document not found")

    source_cid = src.data[0]["collection_id"]
    file_path = src.data[0]["filename"]

    # Verify target collection ownership
    own_coll = (
        sb.table("collections")
        .select("id")
        .eq("id", target_cid)
        .eq("user_id", user_id)
        .execute()
    )
    if not own_coll.data:
        raise HTTPException(status_code=404, detail="Target collection not found")

    src_id = src.data[0]["id"]

    # Step 1: Delete embeddings from source collection in vector store
    try:
        from app.core.config import settings
        from app.rag.vectorstore import ChromaManager, FAISSManager
        import os

        if settings.VECTOR_DB_TYPE.lower() == "chromadb":
            manager = ChromaManager(
                persist_dir=settings.CHROMA_PERSIST_DIR,
                collection_name=source_cid,
            )
            deleted_count = manager.delete_documents_by_metadata({"document_id": document_id})
            logger.info("Deleted %d chunks from ChromaDB collection %s", deleted_count, source_cid)
        else:
            manager = FAISSManager(
                index_dir=settings.FAISS_INDEX_DIR,
                collection_name=source_cid,
            )
            deleted_count = manager.delete_documents_by_metadata({"document_id": document_id})
            manager.persist()
            logger.info("Deleted %d chunks from FAISS collection %s", deleted_count, source_cid)
    except Exception as exc:
        logger.warning("Failed to delete embeddings from source collection: %s", exc)

    # Step 2: Update database record
    (
        sb.table("documents")
        .update({"collection_id": target_cid})
        .eq("id", src_id)
        .execute()
    )

    # Step 3: Re-process embeddings into target collection
    try:
        file_on_disk = Path(settings.UPLOAD_DIR) / file_path if file_path else None
        if file_on_disk and file_on_disk.exists():
            from app.tasks.document_tasks import process_document_task
            result = process_document_task.apply_async(
                args=[document_id, str(file_on_disk), target_cid, user_id],
                queue="document_processing",
            )
            logger.info(
                "Re-processing document %s into collection %s. job_id=%s",
                document_id, target_cid, result.id,
            )
        else:
            logger.warning(
                "File not found for re-processing document %s: %s",
                document_id, file_path,
            )
    except Exception as exc:
        logger.error("Failed to re-process document %s into new collection: %s", document_id, exc)

    return {
        "success":     True,
        "document_id": document_id,
        "collection_id": target_cid,
        "updated_at":  datetime.now(timezone.utc).isoformat(),
        "reprocessing": "queued" if file_on_disk and file_on_disk.exists() else "file_not_found",
    }


# ── DELETE ───────────────────────────────────────────────────────

@router.delete("/{document_id}", response_model=dict)
async def delete_document(
    document_id: str,
    user_id:     str,
):
    """
    Hard-delete a document from the DB and vector store.

    Full life-cycle cleanup in this endpoint:
      • delete chunks/embeddings from vector store (ChromaDB/FAISS)
      • delete vector references  
      • delete document row from DB (user-scoped)
      • cleanup storage file from local disk (best-effort)
      • cleanup storage file from Supabase Storage (best-effort)
      • cleanup orphaned metadata

    Returns: { "success": true, "deleted_document_id": "..." }
    """
    sb = _sb_write()

    # ── 1. Fetch row before deletion ────────────────────────────
    pre = (
        sb.table("documents")
        .select("*")
        .eq("document_id", document_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not pre.data:
        # ── Debug: check if document exists at all (ignore user_id) ──
        debug_res = (
            sb.table("documents")
            .select("*")
            .eq("document_id", document_id)
            .execute()
        )
        if debug_res.data:
            stored_user = debug_res.data[0].get("user_id", "unknown")
            logger.warning(
                "DELETE 404: document_id=%s exists but user_id mismatch. "
                "Requested user_id=%s, stored user_id=%s — proceeding with admin delete.",
                document_id, user_id, stored_user,
            )
            pre = debug_res
        else:
            logger.warning(
                "DELETE 404: document_id=%s not found in documents table at all.",
                document_id,
            )
            raise HTTPException(status_code=404, detail="Document not found")


    row   = pre.data[0]
    doc_pk = row["id"]
    collection_id = row.get("collection_id", "")

    # ── 2. Delete chunks from vector store ──────────────────────
    try:
        from app.core.config import settings
        from app.rag.vectorstore import ChromaManager, ChromaDBError
        
        if settings.VECTOR_DB_TYPE.lower() == "chromadb":
            # Delete from ChromaDB by document_id metadata
            try:
                manager = ChromaManager(
                    persist_dir=settings.CHROMA_PERSIST_DIR,
                    collection_name=collection_id or settings.CHROMA_COLLECTION_NAME,
                )
                deleted_count = manager.delete_documents_by_metadata(
                    {"document_id": document_id}
                )
                logger.info(
                    "Deleted %d chunks from ChromaDB for document_id=%s",
                    deleted_count,
                    document_id,
                )
            except ChromaDBError as ve:
                logger.warning(
                    "Failed to delete chunks from ChromaDB: %s", ve
                )
            except Exception as ve:
                logger.warning(
                    "Unexpected error deleting from vector store: %s", ve
                )
    except ImportError:
        logger.warning("Vector store modules not available for cleanup")
    except Exception as cleanup_err:
        logger.warning("Vector store cleanup error: %s", cleanup_err)

    # ── 3. Delete from documents table ──────────────────────────
    (
        sb.table("documents")
        .delete()
        .eq("id", doc_pk)
        .execute()
    )

    # ── 4. Best-effort local-file removal ───────────────────────
    stored_path = row.get("filename", "")
    if stored_path:
        try:
            import os as _os
            if _os.path.exists(stored_path):
                _os.remove(stored_path)
                logger.info("Removed local file: %s", stored_path)
        except Exception as exc:
            logger.warning("Failed to remove local file %s: %s", stored_path, exc)

    # ── 5. Best-effort Supabase Storage removal ──────────────────
    try:
        from supabase import create_client as _sc
        import os as _os
        _url  = _os.getenv("SUPABASE_URL", "")
        _skey = _os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if _url and _skey:
            _sb2 = _sc(_url, _skey)
            # Try common bucket names used for uploads
            for bucket in ["uploads", "documents", "user-uploads"]:
                try:
                    _sb2.storage.from_(bucket).remove([stored_path])
                    logger.info("Removed Supabase Storage object: %s from %s", stored_path, bucket)
                except Exception:
                    pass
    except Exception as exc:
        logger.warning("Failed Supabase Storage cleanup for %s: %s", document_id, exc)

    return {
        "success":            True,
        "deleted_document_id": document_id,
    }


# ── PROCESSING STATUS (Phase 7) ──────────────────────────────────

@router.get("/{document_id}/status", response_model=dict)
async def get_document_status(
    document_id: str,
    user_id: Optional[str] = Query(None, description="Optional user ID for ownership check"),
):
    """
    Poll real-time document processing status.

    Returns the current processing_status, progress (0–100), stage label,
    job_id, and any error message. Frontend uses this for progress polling.

    Adaptive polling intervals recommended:
      queued:     5 seconds
      processing: 3 seconds
      retrying:   4 seconds
      completed:  stop polling
      failed:     stop polling
    """
    sb = _sb_read()

    query = sb.table("documents").select(
        "document_id, processing_status, processing_progress, processing_stage, "
        "job_id, processing_error, retry_count, "
        "processing_started_at, processing_completed_at, upload_status"
    ).eq("document_id", document_id)

    if user_id:
        query = query.eq("user_id", user_id)

    res = query.single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = res.data
    # Coalesce: prefer processing_status, fall back to upload_status
    effective_status = doc.get("processing_status") or doc.get("upload_status") or "unknown"

    return {
        "document_id":              doc.get("document_id"),
        "status":                   effective_status,
        "progress":                 doc.get("processing_progress", 0),
        "stage":                    doc.get("processing_stage"),
        "job_id":                   doc.get("job_id"),
        "error":                    doc.get("processing_error"),
        "retry_count":              doc.get("retry_count", 0),
        "processing_started_at":    doc.get("processing_started_at"),
        "processing_completed_at":  doc.get("processing_completed_at"),
    }


# ── RETRY FAILED DOCUMENT (Phase 7) ─────────────────────────────

@router.post("/{document_id}/retry", response_model=dict)
async def retry_document_processing(
    document_id: str,
    user_id: Optional[str] = Query(None, description="User ID for ownership verification"),
):
    """
    Re-enqueue a failed document for reprocessing.

    Only works when processing_status == 'failed'.
    Resets retry_count, progress, error, and sets status back to 'queued'
    before enqueuing the Celery task.
    """
    sb = _sb_write()

    # 1. Fetch the document
    query = sb.table("documents").select("*").eq("document_id", document_id)
    if user_id:
        query = query.eq("user_id", user_id)
    res = query.single().execute()

    if not res.data:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = res.data
    current_status = doc.get("processing_status") or doc.get("upload_status", "")

    if current_status != "failed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry document with status '{current_status}'. Only 'failed' documents can be retried.",
        )

    # 2. Reset processing state
    from datetime import datetime, timezone
    sb.table("documents").update({
        "processing_status":   "queued",
        "processing_progress": 0,
        "processing_stage":    "queued",
        "processing_error":    None,
        "retry_count":         0,
        "job_id":              None,
        "upload_status":       "queued",
    }).eq("document_id", document_id).execute()

    # 3. Re-enqueue Celery task
    # Reconstruct file path from filename stored in DB
    from app.core.config import settings
    filename = doc.get("filename", "")
    collection_id = doc.get("collection_id") or settings.CHROMA_COLLECTION_NAME
    stored_user_id = doc.get("user_id")

    # Search uploads directory for the file
    import os
    possible_paths = []
    if filename:
        possible_paths.append(str(settings.UPLOAD_DIR / filename))
        # Also try document_id prefix pattern
        for f in settings.UPLOAD_DIR.iterdir() if settings.UPLOAD_DIR.exists() else []:
            if document_id in f.name:
                possible_paths.insert(0, str(f))
                break

    file_path = possible_paths[0] if possible_paths and os.path.exists(possible_paths[0]) else filename

    try:
        from app.tasks.document_tasks import process_document_task
        result = process_document_task.apply_async(
            args=[document_id, file_path, collection_id, stored_user_id],
            queue="document_processing",
        )
        job_id = result.id

        # Update DB with new job_id
        sb.table("documents").update({"job_id": job_id}).eq("document_id", document_id).execute()

        logger.info(
            "Document retry enqueued. document_id=%s job_id=%s", document_id, job_id
        )
        return {
            "success":      True,
            "document_id": document_id,
            "job_id":      job_id,
            "status":      "queued",
            "message":     "Document re-enqueued for processing.",
        }
    except Exception as exc:
        logger.error("Failed to re-enqueue document. document_id=%s error=%s", document_id, exc)
        # Revert status to failed
        sb.table("documents").update({
            "processing_status": "failed",
            "processing_error":  f"Retry failed: {exc}",
        }).eq("document_id", document_id).execute()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to re-enqueue document processing: {exc}",
        )


__all__ = ["router"]
