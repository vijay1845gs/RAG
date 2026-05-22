"""
Upload service for PDF ingestion into the RAG vector database.

The service owns the upload workflow:
1. validate and save an uploaded PDF
2. load and chunk the document
3. generate embeddings
4. store chunks in ChromaDB or FAISS
5. return structured upload metadata
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import chromadb
from fastapi import UploadFile
from langchain_core.documents import Document

from app.core.config import settings
from app.rag.chunking import TextSplitter
from app.rag.embeddings import EmbeddingModel as EmbeddingManager
from app.rag.loaders import PDFLoader
from app.rag.vectorstore import ChromaDBError, ChromaManager, FAISSManager, FAISSError
from app.schemas.upload_schema import UploadResponse


logger = logging.getLogger(__name__)


class UploadServiceError(Exception):
    """Base exception for upload service failures."""


class FileValidationError(UploadServiceError):
    """Raised when an uploaded file is invalid."""


class DocumentProcessingError(UploadServiceError):
    """Raised when PDF loading, chunking, or embedding generation fails."""


class VectorStorageError(UploadServiceError):
    """Raised when vector storage fails."""


@dataclass(frozen=True)
class DocumentIngestionResult:
    """Internal summary of a processed document."""

    document_id: str
    filename: str
    collection_id: str
    total_pages: int
    total_chunks: int
    stored_vectors: int
    uploaded_at: datetime


class UploadService:
    """
    Service responsible for PDF upload and RAG ingestion.

    The class is intentionally framework-light: it accepts FastAPI `UploadFile`
    objects at the boundary, then delegates document processing to the existing
    RAG components.
    """

    PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
    READ_CHUNK_SIZE = 1024 * 1024

    def __init__(
        self,
        upload_dir: Path = settings.UPLOAD_DIR,
        max_upload_size: int = settings.MAX_UPLOAD_SIZE,
        chroma_persist_dir: Path = settings.CHROMA_PERSIST_DIR,
        faiss_index_dir: Path = settings.FAISS_INDEX_DIR,
        vector_db_type: str = settings.VECTOR_DB_TYPE,
        default_collection_name: str = settings.CHROMA_COLLECTION_NAME,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP,
    ) -> None:
        self.upload_dir = Path(upload_dir)
        self.max_upload_size = max_upload_size
        self.chroma_persist_dir = Path(chroma_persist_dir)
        self.faiss_index_dir = Path(faiss_index_dir)
        self.vector_db_type = vector_db_type.lower()
        self.default_collection_name = default_collection_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.logger = logger

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.faiss_index_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(
            "UploadService initialized. upload_dir=%s persist_dir=%s vector_db=%s default_collection=%s",
            self.upload_dir,
            self.chroma_persist_dir if self.vector_db_type == "chromadb" else self.faiss_index_dir,
            self.vector_db_type,
            self.default_collection_name,
        )

    async def save_uploaded_file(
        self,
        upload_file: UploadFile,
        document_id: Optional[str] = None,
    ) -> Path:
        """
        Validate and persist an uploaded PDF.

        Args:
            upload_file: FastAPI uploaded file object.
            document_id: Optional document ID to use in the generated filename.

        Returns:
            Path: Saved PDF path.

        Raises:
            FileValidationError: If the file is not a PDF or exceeds size limits.
        """
        try:
            self._validate_upload_metadata(upload_file)
            self.upload_dir.mkdir(parents=True, exist_ok=True)

            safe_name = self._safe_filename(upload_file.filename or "document.pdf")
            suffix = Path(safe_name).suffix.lower() or ".pdf"
            stem = Path(safe_name).stem or "document"
            unique_id = document_id or uuid4().hex
            saved_path = self.upload_dir / f"{unique_id}_{stem}{suffix}"

            bytes_written = 0
            await upload_file.seek(0)

            with saved_path.open("wb") as output_file:
                while True:
                    chunk = await upload_file.read(self.READ_CHUNK_SIZE)
                    if not chunk:
                        break

                    bytes_written += len(chunk)
                    if bytes_written > self.max_upload_size:
                        output_file.close()
                        saved_path.unlink(missing_ok=True)
                        raise FileValidationError(
                            f"Uploaded file exceeds max size of {self.max_upload_size} bytes"
                        )

                    output_file.write(chunk)

            await upload_file.seek(0)

            if bytes_written == 0:
                saved_path.unlink(missing_ok=True)
                raise FileValidationError("Uploaded file is empty")

            self.logger.info(
                "Saved uploaded PDF. filename=%s path=%s bytes=%s",
                upload_file.filename,
                saved_path,
                bytes_written,
            )
            return saved_path

        except FileValidationError:
            raise
        except Exception as exc:
            error_msg = f"Failed to save uploaded file: {type(exc).__name__}: {exc}"
            self.logger.error(error_msg, exc_info=True)
            raise FileValidationError(error_msg) from exc

    def process_document(
        self,
        file_path: Path,
        document_id: str,
        collection_id: Optional[str] = None,
    ) -> DocumentIngestionResult:
        """
        Load, chunk, embed, and store a saved PDF document.

        Args:
            file_path: Path to the saved PDF.
            document_id: Stable document identifier.
            collection_id: Optional target Chroma collection.

        Returns:
            DocumentIngestionResult: Processing metadata summary.
        """
        try:
            target_collection = self._resolve_collection_id(collection_id)

            loader = PDFLoader(file_path=str(file_path))
            documents = loader.load()
            self._validate_loaded_documents(documents)

            splitter = TextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
            chunks = splitter.split_documents(documents)
            self._validate_chunks(chunks)
            self._attach_ingestion_metadata(
                chunks=chunks,
                document_id=document_id,
                collection_id=target_collection,
                filename=file_path.name,
            )

            embedding_manager = EmbeddingManager()
            embeddings = embedding_manager.embed_documents(
                [chunk.page_content for chunk in chunks]
            )
            self._validate_embeddings(embeddings, expected_count=len(chunks))

            stored_vectors = self._store_chunks(
                chunks=chunks,
                embeddings=embeddings,
                collection_id=target_collection,
                embedding_manager=embedding_manager,
            )

            if stored_vectors < len(chunks):
                raise VectorStorageError(
                    f"Stored {stored_vectors} vectors for {len(chunks)} chunks"
                )

            result = DocumentIngestionResult(
                document_id=document_id,
                filename=file_path.name,
                collection_id=target_collection,
                total_pages=len(documents),
                total_chunks=len(chunks),
                stored_vectors=stored_vectors,
                uploaded_at=datetime.now(timezone.utc),
            )

            self.logger.info(
                "Processed document. document_id=%s collection_id=%s pages=%s chunks=%s",
                result.document_id,
                result.collection_id,
                result.total_pages,
                result.total_chunks,
            )
            return result

        except (FileValidationError, DocumentProcessingError, VectorStorageError):
            raise
        except Exception as exc:
            error_msg = f"Failed to process document: {type(exc).__name__}: {exc}"
            self.logger.error(error_msg, exc_info=True)
            raise DocumentProcessingError(error_msg) from exc

    async def upload_document(
        self,
        upload_file: UploadFile,
        collection_id: Optional[str] = None,
    ) -> UploadResponse:
        """
        Orchestrate the complete upload and ingestion workflow.

        Args:
            upload_file: FastAPI uploaded PDF.
            collection_id: Optional target collection ID.

        Returns:
            UploadResponse: API-safe upload metadata.
        """
        document_id = uuid4().hex

        try:
            saved_path = await self.save_uploaded_file(
                upload_file=upload_file,
                document_id=document_id,
            )
            result = self.process_document(
                file_path=saved_path,
                document_id=document_id,
                collection_id=collection_id,
            )

            return UploadResponse(
                document_id=result.document_id,
                filename=result.filename,
                collection_id=result.collection_id,
                total_pages=result.total_pages,
                total_chunks=result.total_chunks,
                upload_status="completed",
                uploaded_at=result.uploaded_at,
            )

        except UploadServiceError:
            self.logger.exception(
                "Upload workflow failed. document_id=%s filename=%s",
                document_id,
                getattr(upload_file, "filename", None),
            )
            raise
        except Exception as exc:
            error_msg = f"Unexpected upload workflow failure: {type(exc).__name__}: {exc}"
            self.logger.error(error_msg, exc_info=True)
            raise UploadServiceError(error_msg) from exc

    def _validate_upload_metadata(self, upload_file: UploadFile) -> None:
        """Validate filename and content type before saving."""
        filename = upload_file.filename or ""
        suffix = Path(filename).suffix.lower()
        content_type = (upload_file.content_type or "").lower()

        if suffix != ".pdf":
            raise FileValidationError("Only PDF files are supported")

        if content_type and content_type not in self.PDF_CONTENT_TYPES:
            raise FileValidationError(
                f"Invalid content type '{content_type}'. Expected application/pdf"
            )

    @staticmethod
    def _safe_filename(filename: str) -> str:
        """Return a Windows-safe filename while preserving the extension."""
        candidate = Path(filename).name.strip()
        candidate = re.sub(r"[^A-Za-z0-9._ -]+", "_", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip(" .")
        return candidate or "document.pdf"

    def _resolve_collection_id(self, collection_id: Optional[str]) -> str:
        """Normalize and validate the target collection ID."""
        resolved = (collection_id or self.default_collection_name).strip()
        if not resolved:
            raise FileValidationError("collection_id cannot be empty")

        if not all(char.isalnum() or char in {"_", "-"} for char in resolved):
            raise FileValidationError(
                "collection_id may only contain letters, numbers, underscores, and hyphens"
            )

        return resolved

    @staticmethod
    def _validate_loaded_documents(documents: List[Document]) -> None:
        """Validate loaded PDF documents."""
        if not documents:
            raise DocumentProcessingError("PDF loader returned no documents")

        if not any(document.page_content.strip() for document in documents):
            raise DocumentProcessingError(
                "PDF contains no extractable text. OCR is required for scanned PDFs"
            )

    @staticmethod
    def _validate_chunks(chunks: List[Document]) -> None:
        """Validate generated chunks."""
        if not chunks:
            raise DocumentProcessingError("Text splitter generated no chunks")

        empty_indexes = [
            index
            for index, chunk in enumerate(chunks)
            if not chunk.page_content.strip()
        ]
        if empty_indexes:
            raise DocumentProcessingError(
                "Empty chunks generated at indexes: "
                + ", ".join(str(index) for index in empty_indexes[:10])
            )

    @staticmethod
    def _attach_ingestion_metadata(
        chunks: List[Document],
        document_id: str,
        collection_id: str,
        filename: str,
    ) -> None:
        """Attach upload metadata to every chunk before vector storage."""
        for index, chunk in enumerate(chunks):
            chunk.metadata.update(
                {
                    "document_id": document_id,
                    "collection_id": collection_id,
                    "uploaded_filename": filename,
                    "chunk_id": f"{document_id}-{index:04d}",
                }
            )

    @staticmethod
    def _validate_embeddings(
        embeddings: List[List[float]],
        expected_count: int,
    ) -> None:
        """Validate embedding generation output."""
        if not embeddings:
            raise DocumentProcessingError("Embedding generation returned no vectors")

        if len(embeddings) != expected_count:
            raise DocumentProcessingError(
                f"Expected {expected_count} embeddings, got {len(embeddings)}"
            )

        vector_lengths = {len(vector) for vector in embeddings}
        if len(vector_lengths) != 1:
            raise DocumentProcessingError(
                "Embedding vector lengths are inconsistent: "
                + ", ".join(str(length) for length in sorted(vector_lengths))
            )

        invalid_indexes = [
            index
            for index, vector in enumerate(embeddings)
            if not vector or not all(isinstance(value, (int, float)) for value in vector)
        ]
        if invalid_indexes:
            raise DocumentProcessingError(
                "Invalid embeddings at indexes: "
                + ", ".join(str(index) for index in invalid_indexes[:10])
            )

    def _store_chunks(
        self,
        chunks: List[Document],
        embeddings: List[List[float]],
        collection_id: str,
        embedding_manager: EmbeddingManager,
    ) -> int:
        """Store chunks using configured vector DB backend (ChromaDB or FAISS)."""
        try:
            if self.vector_db_type == "faiss":
                return self._store_chunks_faiss(chunks, embedding_manager, collection_id)
            else:
                return self._store_chunks_chromadb(
                    chunks, embeddings, embedding_manager, collection_id
                )

        except (ChromaDBError, FAISSError) as exc:
            error_msg = f"Vector storage failed: {exc}"
            self.logger.error(error_msg, exc_info=True)
            raise VectorStorageError(error_msg) from exc
        except Exception as exc:
            error_msg = f"Unexpected vector storage error: {type(exc).__name__}: {exc}"
            self.logger.error(error_msg, exc_info=True)
            raise VectorStorageError(error_msg) from exc

    def _store_chunks_chromadb(
        self,
        chunks: List[Document],
        embeddings: List[List[float]],
        embedding_manager: EmbeddingManager,
        collection_id: str,
    ) -> int:
        """Store chunks in ChromaDB."""
        self.logger.info(
            "Storing chunks in ChromaDB. collection_id=%s persist_dir=%s chunks=%s vectors=%s",
            collection_id,
            self.chroma_persist_dir,
            len(chunks),
            len(embeddings),
        )
        
        if find_spec("langchain_chroma") is not None:
            self.logger.debug("Using LangChain ChromaManager for storage")
            manager = ChromaManager(
                persist_dir=str(self.chroma_persist_dir),
                collection_name=collection_id,
                embedding_function=embedding_manager.embeddings,
            )
            manager.add_documents(chunks)
            manager.persist()
            stats = manager.get_collection_stats()
            stored_count = int(stats.get("document_count", 0))
            self.logger.info(
                "Successfully stored vectors in ChromaDB. collection_id=%s stored_count=%s",
                collection_id,
                stored_count,
            )
            return stored_count

        self.logger.debug("Using native ChromaDB for storage")
        return self._store_chunks_native_chromadb(
            chunks=chunks,
            embeddings=embeddings,
            collection_id=collection_id,
        )

    def _store_chunks_faiss(
        self,
        chunks: List[Document],
        embedding_manager: EmbeddingManager,
        collection_id: str,
    ) -> int:
        """Store chunks in FAISS."""
        self.logger.info(
            "Storing chunks in FAISS. collection_id=%s index_dir=%s chunks=%s",
            collection_id,
            self.faiss_index_dir,
            len(chunks),
        )
        
        manager = FAISSManager(
            index_dir=str(self.faiss_index_dir),
            collection_name=collection_id,
            embedding_function=embedding_manager.embeddings,
        )
        manager.add_documents(chunks)
        manager.persist()
        stats = manager.get_collection_stats()
        stored_count = int(stats.get("document_count", 0))
        self.logger.info(
            "Successfully stored vectors in FAISS. collection_id=%s stored_count=%s",
            collection_id,
            stored_count,
        )
        return stored_count

    def _store_chunks_native_chromadb(
        self,
        chunks: List[Document],
        embeddings: List[List[float]],
        collection_id: str,
    ) -> int:
        """Store precomputed embeddings with native chromadb.PersistentClient."""
        client = chromadb.PersistentClient(path=str(self.chroma_persist_dir))

        ids = [str(chunk.metadata["chunk_id"]) for chunk in chunks]
        documents = [chunk.page_content for chunk in chunks]
        metadatas = [self._sanitize_metadata(chunk.metadata) for chunk in chunks]

        # Check if the existing collection has the wrong embedding dimension
        # and delete it if so (e.g., migrating from HuggingFace 384-dim to Ollama 1024-dim)
        new_dim = len(embeddings[0]) if embeddings else 0
        try:
            existing_col = client.get_collection(name=collection_id)
            # Probe the existing dimension by fetching one record
            probe = existing_col.get(limit=1, include=["embeddings"])
            existing_embeddings = probe.get("embeddings") or []
            if existing_embeddings and len(existing_embeddings[0]) != new_dim:
                self.logger.warning(
                    "Collection '%s' has wrong embedding dimension (%s vs %s). "
                    "Deleting and recreating collection.",
                    collection_id,
                    len(existing_embeddings[0]),
                    new_dim,
                )
                client.delete_collection(name=collection_id)
        except Exception:
            # Collection doesn't exist yet — that's fine
            pass

        collection = client.get_or_create_collection(
            name=collection_id,
            metadata={"managed_by": "UploadService"},
        )

        existing = collection.get(ids=ids)
        existing_ids = set(existing.get("ids", []))
        if existing_ids:
            collection.delete(ids=list(existing_ids))

        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

        return collection.count()

    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Convert metadata to ChromaDB-compatible primitive values."""
        sanitized: Dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                sanitized[str(key)] = value
            else:
                sanitized[str(key)] = str(value)
        return sanitized
