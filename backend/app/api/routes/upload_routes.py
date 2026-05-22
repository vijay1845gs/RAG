"""
FastAPI upload routes — Phase 7 async ingestion.

Upload flow (new):
  1. Validate file metadata
  2. Save file to disk
  3. Create DB row (processing_status = 'queued')
  4. Enqueue Celery task
  5. Return immediately (<1 second)

Response: { document_id, job_id, status: "queued", filename, collection_id }

The legacy /collections and /documents/{id} sub-routes are preserved as-is.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.upload_schema import (
    AsyncUploadResponse,
    CollectionCreateRequest,
    CollectionResponse,
    DocumentMetadataResponse,
    UploadErrorResponse,
)
from app.services.upload_service import (
    FileValidationError,
    UploadService,
    UploadServiceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])

# Shared service instance (file save / validation only — embedding now in worker)
upload_service = UploadService()


@router.post(
    "",
    response_model=AsyncUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": UploadErrorResponse, "description": "Invalid file format or request"},
        413: {"model": UploadErrorResponse, "description": "File exceeds maximum upload size"},
        422: {"model": UploadErrorResponse, "description": "Validation error"},
        500: {"model": UploadErrorResponse, "description": "Internal server error"},
    },
    summary="Upload a PDF for async background ingestion",
    description=(
        "Upload a PDF file. Returns immediately (<1 second) with a document_id and job_id. "
        "Poll GET /documents/{document_id}/status to track ingestion progress."
    ),
)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to upload", media_type="application/pdf"),
    collection_id: Optional[str] = Form(
        default=None,
        description="Target collection ID (alphanumeric, underscores, hyphens)",
        min_length=1,
        max_length=128,
    ),
    user_id: Optional[str] = Form(default=None, description="User ID for document ownership"),
) -> AsyncUploadResponse:
    filename = file.filename or "unknown"
    document_id = uuid4().hex
    logger.info(
        "Async upload initiated. document_id=%s file=%s collection_id=%s user_id=%s",
        document_id, filename, collection_id, user_id,
    )

    try:
        # ── 1. Save file to disk ──────────────────────────────────────────────
        saved_path = await upload_service.save_uploaded_file(
            upload_file=file,
            document_id=document_id,
        )

        # ── 2. Resolve collection ─────────────────────────────────────────────
        from app.core.config import settings
        resolved_collection = (collection_id or settings.CHROMA_COLLECTION_NAME).strip()

        # ── 3. Create DB row with status = queued ─────────────────────────────
        job_id = "pending"  # will be updated by the task itself
        try:
            from app.db.supabase import get_supabase_admin_client
            sb = get_supabase_admin_client()
            if sb:
                sb.table("documents").insert({
                    "document_id": document_id,
                    "user_id": user_id,
                    "filename": str(saved_path.name),
                    "collection_id": collection_id or resolved_collection,
                    "upload_status": "queued",
                    "processing_status": "queued",
                    "processing_progress": 0,
                    "job_id": None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
        except Exception as db_err:
            logger.warning("Failed to create document DB row: %s", db_err)

        # ── 4. Enqueue Celery task ────────────────────────────────────────────
        try:
            from app.tasks.document_tasks import process_document_task
            result = process_document_task.apply_async(
                args=[document_id, str(saved_path), resolved_collection, user_id],
                queue="document_processing",
            )
            job_id = result.id
            logger.info("Document task enqueued. document_id=%s job_id=%s", document_id, job_id)

            # Update DB with the real job_id
            try:
                from app.db.supabase import get_supabase_admin_client
                sb = get_supabase_admin_client()
                if sb:
                    sb.table("documents").update({"job_id": job_id}).eq("document_id", document_id).execute()
            except Exception:
                pass  # Non-critical — task will update status anyway

        except Exception as queue_err:
            logger.error("Failed to enqueue document task: %s", queue_err, exc_info=True)
            # Update DB row to failed if we can't enqueue
            try:
                from app.db.supabase import get_supabase_admin_client
                sb = get_supabase_admin_client()
                if sb:
                    sb.table("documents").update({
                        "processing_status": "failed",
                        "processing_error": f"Failed to enqueue task: {queue_err}",
                    }).eq("document_id", document_id).execute()
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=UploadErrorResponse(
                    error="Queue error",
                    details="Failed to enqueue document processing task. Is the Celery worker running?",
                ).model_dump(),
            )

        # ── 5. Invalidate chat cache for this collection ──────────────────────
        try:
            from app.services.cache_service import chat_cache
            chat_cache.invalidate_collection(resolved_collection)
        except Exception:
            pass  # Non-critical

        # ── 6. Return immediately ─────────────────────────────────────────────
        return AsyncUploadResponse(
            document_id=document_id,
            job_id=job_id,
            status="queued",
            filename=str(saved_path.name),
            collection_id=collection_id or resolved_collection,
            message="Document queued for processing. Poll /documents/{}/status for progress.".format(document_id),
        )

    except FileValidationError as exc:
        error_msg = str(exc)
        logger.warning("File validation failed. file=%s error=%s", filename, error_msg)
        if "exceeds max size" in error_msg.lower():
            raise HTTPException(
                status_code=413,
                detail=UploadErrorResponse(error="File too large", details=error_msg).model_dump(),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=UploadErrorResponse(error="File validation failed", details=error_msg).model_dump(),
        )

    except HTTPException:
        raise

    except UploadServiceError as exc:
        logger.error("Upload service error. file=%s error=%s", filename, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=UploadErrorResponse(error="Upload service error", details=str(exc)).model_dump(),
        )

    except Exception as exc:
        logger.error("Unexpected upload error. file=%s error=%s", filename, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=UploadErrorResponse(
                error="Unexpected error",
                details="An unexpected error occurred. Please try again.",
            ).model_dump(),
        )


@router.post(
    "/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": UploadErrorResponse, "description": "Invalid collection name"},
        409: {"model": UploadErrorResponse, "description": "Collection already exists"},
        500: {"model": UploadErrorResponse, "description": "Failed to create collection"},
    },
    summary="Create a new document collection",
    description="Create a new collection in the vector store for organizing document embeddings.",
)
async def create_collection(request: CollectionCreateRequest) -> CollectionResponse:
    logger.info("Create collection initiated. collection_name=%s", request.collection_name)
    try:
        collection_name = request.collection_name.strip()
        if not collection_name or len(collection_name) < 2:
            raise ValueError("Collection name must be at least 2 characters")
        if len(collection_name) > 128:
            raise ValueError("Collection name must not exceed 128 characters")
        response = CollectionResponse(
            collection_id=collection_name,
            collection_name=collection_name,
            description=request.description,
            total_documents=0,
            created_at=datetime.now(timezone.utc),
        )
        logger.info("Collection created. collection_id=%s", response.collection_id)
        return response
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=UploadErrorResponse(error="Validation error", details=str(exc)).model_dump(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=UploadErrorResponse(error="Collection creation failed", details=str(exc)).model_dump(),
        )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentMetadataResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document metadata",
)
async def get_document_metadata(document_id: str) -> DocumentMetadataResponse:
    logger.info("Document metadata request. document_id=%s", document_id)
    if not document_id or not document_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=UploadErrorResponse(error="Invalid document ID", details="Document ID cannot be empty").model_dump(),
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=UploadErrorResponse(
            error="Document not found",
            details=f"No document found with ID {document_id!r}.",
        ).model_dump(),
    )
