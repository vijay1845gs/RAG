"""
Pydantic schemas for document upload and collection APIs.

These models are designed for FastAPI request validation, OpenAPI generation,
and JSON-safe serialization in document ingestion workflows.

Phase 7 additions:
  AsyncUploadResponse    — immediate response after async enqueue (<1 s)
  DocumentStatusResponse — polling response with real progress + stage
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UploadResponse(BaseModel):
    """Successful document upload and ingestion response."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "document_id": "doc_01HX7Q9K7Z8M4C2A1B3D5E6F7G",
                    "filename": "cia_notes.pdf",
                    "collection_id": "cia_notes",
                    "total_pages": 19,
                    "total_chunks": 38,
                    "upload_status": "completed",
                    "uploaded_at": "2026-05-18T14:30:00Z",
                }
            ]
        }
    )

    document_id: str = Field(
        ...,
        min_length=1,
        description="Unique document identifier assigned by the backend.",
        examples=["doc_01HX7Q9K7Z8M4C2A1B3D5E6F7G"],
    )
    filename: str = Field(
        ...,
        min_length=1,
        description="Original uploaded filename.",
        examples=["cia_notes.pdf"],
    )
    collection_id: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Collection identifier where the document was indexed.",
        examples=["cia_notes"],
    )
    total_pages: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of pages parsed from the document.",
        examples=[19],
    )
    total_chunks: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of chunks created during ingestion.",
        examples=[38],
    )
    upload_status: str = Field(
        ...,
        min_length=1,
        description="Current upload or ingestion status.",
        examples=["completed"],
    )
    uploaded_at: datetime = Field(
        ...,
        description="UTC timestamp when the upload was accepted or completed.",
    )


class UploadErrorResponse(BaseModel):
    """Error response for upload or ingestion failures."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error": "Upload failed",
                    "details": "Only PDF files are supported.",
                }
            ]
        }
    )

    error: str = Field(
        ...,
        min_length=1,
        description="Short, client-safe error message.",
        examples=["Upload failed"],
    )
    details: Optional[str] = Field(
        default=None,
        description="Optional diagnostic details suitable for API clients.",
        examples=["Only PDF files are supported."],
    )


class CollectionCreateRequest(BaseModel):
    """Request body for creating a vector collection."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "collection_name": "cia_notes",
                    "description": "Course notes indexed for RAG queries.",
                }
            ]
        },
    )

    collection_name: str = Field(
        ...,
        min_length=2,
        max_length=128,
        description="Human-readable collection name.",
        examples=["cia_notes"],
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional collection description.",
        examples=["Course notes indexed for RAG queries."],
    )

    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, value: str) -> str:
        """Normalize and validate collection names for API use."""
        collection_name = value.strip()
        if not collection_name:
            raise ValueError("collection_name must not be empty")
        if len(collection_name) < 2:
            raise ValueError("collection_name must be at least 2 characters long")
        return collection_name

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        """Trim optional descriptions and collapse blank values to None."""
        if value is None:
            return None

        description = value.strip()
        return description or None


class CollectionResponse(BaseModel):
    """Collection metadata response."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "collection_id": "cia_notes",
                    "collection_name": "cia_notes",
                    "description": "Course notes indexed for RAG queries.",
                    "total_documents": 4,
                    "created_at": "2026-05-18T14:30:00Z",
                }
            ]
        }
    )

    collection_id: str = Field(
        ...,
        min_length=1,
        description="Unique collection identifier.",
        examples=["cia_notes"],
    )
    collection_name: str = Field(
        ...,
        min_length=1,
        description="Display name for the collection.",
        examples=["cia_notes"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional collection description.",
        examples=["Course notes indexed for RAG queries."],
    )
    total_documents: int = Field(
        ...,
        ge=0,
        description="Number of documents in the collection.",
        examples=[4],
    )
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the collection was created.",
    )


class DocumentMetadataResponse(BaseModel):
    """Document metadata response for uploaded/indexed files."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "document_id": "doc_01HX7Q9K7Z8M4C2A1B3D5E6F7G",
                    "filename": "cia_notes.pdf",
                    "file_size": 2422299,
                    "total_pages": 19,
                    "total_chunks": 38,
                    "uploaded_at": "2026-05-18T14:30:00Z",
                }
            ]
        }
    )

    document_id: str = Field(
        ...,
        min_length=1,
        description="Unique document identifier.",
        examples=["doc_01HX7Q9K7Z8M4C2A1B3D5E6F7G"],
    )
    filename: str = Field(
        ...,
        min_length=1,
        description="Original uploaded filename.",
        examples=["cia_notes.pdf"],
    )
    file_size: Optional[int] = Field(
        default=None,
        ge=0,
        description="Uploaded file size in bytes.",
        examples=[2422299],
    )
    total_pages: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of parsed pages.",
        examples=[19],
    )
    total_chunks: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of chunks created from the document.",
        examples=[38],
    )
    uploaded_at: datetime = Field(
        ...,
        description="UTC timestamp when the document was uploaded.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Phase 7 — Async Ingestion Schemas
# ──────────────────────────────────────────────────────────────────────────────

ProcessingStatus = Literal["queued", "processing", "retrying", "completed", "failed"]

ProcessingStage = Literal[
    "queued", "starting", "parsing", "chunking", "embedding",
    "vectorizing", "saving", "completed", "retrying", "failed",
]


class AsyncUploadResponse(BaseModel):
    """
    Immediate response returned after async document enqueue (<1 second).

    The document is NOT yet processed — use DocumentStatusResponse polling
    endpoint to track progress.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "document_id": "doc_abc123",
                    "job_id": "celery-task-uuid-here",
                    "status": "queued",
                    "filename": "annual_report.pdf",
                    "collection_id": "my-collection",
                    "message": "Document queued for processing. Poll /documents/{id}/status for progress.",
                }
            ]
        }
    )

    document_id: str = Field(..., description="Unique document identifier.")
    job_id: str = Field(..., description="Celery task ID for this ingestion job.")
    status: ProcessingStatus = Field(default="queued", description="Initial processing status.")
    filename: str = Field(..., description="Original uploaded filename.")
    collection_id: Optional[str] = Field(default=None, description="Target collection identifier.")
    message: str = Field(
        default="Document queued for processing.",
        description="Human-readable status message.",
    )


class DocumentStatusResponse(BaseModel):
    """
    Real-time document processing status for polling.

    Progress is REAL (computed from actual work done):
      0–10%:  starting / initializing
      10–20%: parsing PDF pages
      20–40%: chunking
      40–80%: generating embeddings (per-chunk updates)
      80–95%: storing vectors
      95–99%: saving metadata
      100%:   completed
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "document_id": "doc_abc123",
                    "status": "processing",
                    "progress": 67,
                    "stage": "embedding",
                    "job_id": "celery-task-uuid-here",
                    "error": None,
                    "retry_count": 0,
                    "processing_started_at": "2026-05-21T10:00:00Z",
                    "processing_completed_at": None,
                }
            ]
        }
    )

    document_id: str = Field(..., description="Unique document identifier.")
    status: ProcessingStatus = Field(..., description="Current processing status.")
    progress: int = Field(default=0, ge=0, le=100, description="Processing progress 0–100.")
    stage: Optional[str] = Field(default=None, description="Current processing stage label.")
    job_id: Optional[str] = Field(default=None, description="Celery task ID.")
    error: Optional[str] = Field(default=None, description="Error message if status is failed.")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts so far.")
    processing_started_at: Optional[datetime] = Field(default=None)
    processing_completed_at: Optional[datetime] = Field(default=None)
