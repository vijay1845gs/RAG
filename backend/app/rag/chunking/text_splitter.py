"""
Text Chunking Module for RAG Systems

This module provides functionality to split long documents into manageable chunks
while preserving metadata and maintaining semantic coherence. It attempts to use
LangChain's SemanticChunker for meaning-based splitting, with fallback to a
MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter combination.

Author: RAG System
Version: 2.0.0
"""

import logging
from typing import List, Optional, Dict, Any

from langchain_core.documents import Document

try:
    from langchain_experimental.text_splitter import SemanticChunker

    _SEMANTIC_CHUNKER_AVAILABLE = True
except Exception:
    _SEMANTIC_CHUNKER_AVAILABLE = False

# Import RecursiveCharacterTextSplitter - this is required
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

try:
    from langchain_text_splitters import MarkdownHeaderTextSplitter

    _MARKDOWN_SPLITTER_AVAILABLE = True
except Exception:
    _MARKDOWN_SPLITTER_AVAILABLE = False

from app.rag.embeddings import EmbeddingModel as EmbeddingManager

logger = logging.getLogger(__name__)


class ChunkingError(Exception):
    """Base exception for chunking errors."""

    pass


class InvalidChunkConfigError(ChunkingError):
    """Raised when chunk configuration parameters are invalid."""

    pass


class EmptyDocumentError(ChunkingError):
    """Raised when attempting to chunk an empty document."""

    pass


class TextSplitter:
    """
    A production-grade text chunking class for RAG systems.

    This class attempts to use SemanticChunker for semantic-based splitting.
    If SemanticChunker is unavailable or fails, it falls back to splitting by
    markdown headers then recursive character splitting.

    Attributes:
        chunk_size (int): Maximum size of each chunk in characters (used in fallback).
        chunk_overlap (int): Number of characters to overlap between chunks (used in fallback).
        embedding_model (EmbeddingManager): Embedding model for semantic chunking.
        _splitter: The active splitter instance.
        _use_semantic (bool): Whether semantic chunking is active.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize the TextSplitter with configuration parameters.

        Args:
            chunk_size (int): Maximum size of each chunk in characters.
                Defaults to 500. Must be positive.
            chunk_overlap (int): Number of characters to overlap between chunks.
                Defaults to 100. Must be non-negative and less than chunk_size.
            separators (Optional[List[str]]): Custom separators for splitting.
                If None, uses default separators. Order matters - tried in order.
                Note: Only used in the fallback RecursiveCharacterTextSplitter.

        Raises:
            InvalidChunkConfigError: If parameters are invalid.
        """
        self.logger = logger
        self._validate_config(chunk_size, chunk_overlap)

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", " ", ""]

        # Initialize embedding model for semantic chunking
        self.embedding_model = EmbeddingManager()

        # Determine which splitter to use
        self._use_semantic = False
        self._splitter = None
        self._initialize_splitter()

        self.logger.info(
            f"TextSplitter initialized with chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap}, "
            f"semantic_chunking={self._use_semantic}"
        )

    def _initialize_splitter(self) -> None:
        """Initialize the appropriate splitter based on availability."""
        # Try SemanticChunker first
        if _SEMANTIC_CHUNKER_AVAILABLE:
            try:
                self._splitter = SemanticChunker(
                    embeddings=self.embedding_model.embeddings,
                    breakpoint_threshold_type="percentile",
                    breakpoint_threshold_amount=95,
                    add_start_index=True,
                    min_chunk_size=200,
                )
                self._use_semantic = True
                self.logger.info("SemanticChunker initialized successfully")
                return
            except Exception as e:
                self.logger.warning(
                    f"Failed to initialize SemanticChunker: {e}. Falling back."
                )

        # Fallback to MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter
        if _MARKDOWN_SPLITTER_AVAILABLE:
            self._markdown_splitter = MarkdownHeaderTextSplitter(
                headers_to_split_on=[
                    ("#", "Header 1"),
                    ("##", "Header 2"),
                    ("###", "Header 3"),
                    ("####", "Header 4"),
                    ("#####", "Header 5"),
                    ("######", "Header 6"),
                ],
                strip_headers=False,
            )
            self._recursive_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=self.separators,
                is_separator_regex=False,
            )
            self._use_semantic = False
            self.logger.info(
                "Using fallback: MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter"
            )
        else:
            # Last resort: just RecursiveCharacterTextSplitter
            self._splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=self.separators,
                is_separator_regex=False,
            )
            self._use_semantic = False
            self.logger.warning(
                "MarkdownHeaderTextSplitter not available; using only RecursiveCharacterTextSplitter"
            )

    @staticmethod
    def _validate_config(chunk_size: int, chunk_overlap: int) -> None:
        """
        Validate chunking configuration parameters.

        Args:
            chunk_size (int): Maximum chunk size.
            chunk_overlap (int): Chunk overlap.

        Raises:
            InvalidChunkConfigError: If parameters are invalid.
        """
        if not isinstance(chunk_size, int):
            raise InvalidChunkConfigError(
                f"chunk_size must be an integer, got {type(chunk_size).__name__}"
            )

        if chunk_size <= 0:
            raise InvalidChunkConfigError(
                f"chunk_size must be positive, got {chunk_size}"
            )

        if not isinstance(chunk_overlap, int):
            raise InvalidChunkConfigError(
                f"chunk_overlap must be an integer, got {type(chunk_overlap).__name__}"
            )

        if chunk_overlap < 0:
            raise InvalidChunkConfigError(
                f"chunk_overlap must be non-negative, got {chunk_overlap}"
            )

        if chunk_overlap >= chunk_size:
            raise InvalidChunkConfigError(
                f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size})"
            )

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        Split a list of documents into chunks while preserving metadata.

        Each input document is split into multiple chunks. Metadata from the
        original document is preserved in all chunks, with additional metadata
        tracking the chunk index within the original document.

        Args:
            documents (List[Document]): List of LangChain Document objects to split.

        Returns:
            List[Document]: List of chunked Document objects with preserved metadata.

        Raises:
            EmptyDocumentError: If the documents list is empty.
            ChunkingError: If an error occurs during chunking.
        """
        if not documents:
            error_msg = "Cannot chunk empty document list"
            self.logger.warning(error_msg)
            raise EmptyDocumentError(error_msg)

        try:
            self.logger.info(
                f"Starting chunking process for {len(documents)} documents"
            )

            all_chunks: List[Document] = []
            total_input_chars = 0
            total_output_chars = 0

            for doc_idx, document in enumerate(documents):
                if not document.page_content or not document.page_content.strip():
                    self.logger.warning(
                        f"Document {doc_idx} has empty content, skipping"
                    )
                    continue

                # Perform splitting based on active strategy
                if self._use_semantic:
                    # SemanticChunker splits on semantic sentence/topic boundaries
                    split_docs = self._splitter.split_documents(
                        [document]
                    )
                else:
                    # Fallback: first split by markdown headers, then recursively
                    markdown_docs = self._markdown_splitter.split_text(
                        document.page_content
                    )
                    # Each markdown doc is a Document with header metadata
                    # We need to merge with original document metadata
                    enriched_markdown_docs: List[Document] = []
                    for md_doc in markdown_docs:
                        # Combine original metadata with header metadata
                        combined_metadata = {**document.metadata, **md_doc.metadata}
                        enriched_markdown_docs.append(
                            Document(
                                page_content=md_doc.page_content,
                                metadata=combined_metadata,
                            )
                        )
                    # Now recursively split each markdown section
                    split_docs: List[Document] = []
                    for section_doc in enriched_markdown_docs:
                        section_chunks = self._recursive_splitter.split_documents(
                            [section_doc]
                        )
                        split_docs.extend(section_chunks)

                # Drop empty chunks (defensive guard against upstream splitter bugs
                # e.g. SemanticChunker final-group min_chunk_size bypass)
                non_empty = [
                    c for c in split_docs if c.page_content and c.page_content.strip()
                ]
                dropped = len(split_docs) - len(non_empty)
                if dropped:
                    self.logger.warning(
                        "Dropped %d empty chunk(s) from document %d",
                        dropped, doc_idx,
                    )
                split_docs = non_empty

                # Enhance metadata for each chunk
                for chunk_idx, chunk in enumerate(split_docs):
                    # Preserve original metadata (already done in fallback)
                    chunk.metadata["source_document_index"] = doc_idx
                    chunk.metadata["chunk_index"] = chunk_idx
                    chunk.metadata["chunk_total"] = len(split_docs)
                    chunk.metadata["chunk_size"] = len(chunk.page_content)

                    total_output_chars += len(chunk.page_content)

                all_chunks.extend(split_docs)
                total_input_chars += len(document.page_content)

            self.logger.info(
                f"Chunking complete: {len(documents)} documents → {len(all_chunks)} chunks. "
                f"Input: {total_input_chars} chars, Output: {total_output_chars} chars"
            )

            return all_chunks

        except EmptyDocumentError:
            raise
        except Exception as e:
            error_msg = f"Error during document chunking: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            raise ChunkingError(error_msg) from e

    # The following methods are kept for compatibility but may not be used in the current pipeline.
    # They delegate to the appropriate underlying splitter.

    def split_text(self, text: str) -> List[str]:
        """
        Split a raw text string into chunks.

        This method works directly on text content without Document objects.
        Useful for chunking text retrieved from various sources.

        Args:
            text (str): Raw text content to split.

        Returns:
            List[str]: List of text chunks.

        Raises:
            EmptyDocumentError: If the text is empty or whitespace-only.
            ChunkingError: If an error occurs during chunking.
        """
        if not text or not text.strip():
            error_msg = "Cannot chunk empty text"
            self.logger.warning(error_msg)
            raise EmptyDocumentError(error_msg)

        try:
            self.logger.debug(f"Splitting raw text: {len(text)} characters")

            if self._use_semantic:
                # SemanticChunker returns List[str] via split_text
                chunks = self._splitter.split_text(text)
                # Defensive filter: drop empty strings (e.g. SemanticChunker
                # final-group min_chunk_size bypass bug in langchain_experimental)
                return [c for c in chunks if c and c.strip()]
            else:
                if _MARKDOWN_SPLITTER_AVAILABLE:
                    # Apply markdown split then recursive split on each section
                    markdown_docs = self._markdown_splitter.split_text(text)
                    all_splits: List[str] = []
                    for md_doc in markdown_docs:
                        section_chunks = self._recursive_splitter.split_text(
                            md_doc.page_content
                        )
                        all_splits.extend(section_chunks)
                    return all_splits
                else:
                    return self._splitter.split_text(text)

        except Exception as e:
            error_msg = f"Error splitting text: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            raise ChunkingError(error_msg) from e

    def split_text_to_documents(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Split raw text into chunks and return as Document objects.

        Converts text chunks into LangChain Document objects with optional
        metadata attachment. Useful for unified processing pipelines.

        Args:
            text (str): Raw text content to split.
            metadata (Optional[Dict[str, Any]]): Metadata to attach to all chunks.
                Defaults to None.

        Returns:
            List[Document]: List of Document objects with chunks as content.

        Raises:
            EmptyDocumentError: If the text is empty.
            ChunkingError: If an error occurs during chunking.
        """
        try:
            chunks = self.split_text(text)

            documents: List[Document] = []
            for idx, chunk in enumerate(chunks):
                doc_metadata = {**(metadata or {})}
                documents.append(
                    Document(
                        page_content=chunk,
                        metadata=doc_metadata,
                    )
                )

            self.logger.info(
                f"Created {len(documents)} Document objects from text chunks"
            )
            return documents

        except EmptyDocumentError:
            raise
        except Exception as e:
            error_msg = f"Error converting text chunks to documents: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            raise ChunkingError(error_msg) from e

    def reconfigure(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        separators: Optional[List[str]] = None,
    ) -> None:
        """
        Reconfigure the splitter with new parameters.

        Allows changing chunking parameters without creating a new instance.
        Useful when processing different document types with different requirements.

        Args:
            chunk_size (Optional[int]): New chunk size. If None, uses current value.
            chunk_overlap (Optional[int]): New chunk overlap. If None, uses current value.
            separators (Optional[List[str]]): New separators. If None, uses current value.

        Raises:
            InvalidChunkConfigError: If new parameters are invalid.
        """
        new_chunk_size = chunk_size if chunk_size is not None else self.chunk_size
        new_chunk_overlap = (
            chunk_overlap if chunk_overlap is not None else self.chunk_overlap
        )
        new_separators = separators if separators is not None else self.separators

        self._validate_config(new_chunk_size, new_chunk_overlap)

        self.chunk_size = new_chunk_size
        self.chunk_overlap = new_chunk_overlap
        self.separators = new_separators

        # Reinitialize splitter with new config
        self._initialize_splitter()

        self.logger.info(
            f"TextSplitter reconfigured: chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap}"
        )

    def get_statistics(self, chunks: List[Document]) -> Dict[str, Any]:
        """
        Calculate statistics about a set of chunks.

        Provides insights into chunk distribution, sizes, and characteristics.
        Useful for validating chunking behavior and debugging.

        Args:
            chunks (List[Document]): List of chunked documents.

        Returns:
            Dict[str, Any]: Dictionary containing chunk statistics:
                - total_chunks: Total number of chunks
                - total_characters: Total characters across all chunks
                - avg_chunk_size: Average chunk size
                - min_chunk_size: Smallest chunk
                - max_chunk_size: Largest chunk
                - total_overhead: Character overhead from overlaps
        """
        if not chunks:
            return {
                "total_chunks": 0,
                "total_characters": 0,
                "avg_chunk_size": 0,
                "min_chunk_size": 0,
                "max_chunk_size": 0,
                "total_overhead": 0,
            }

        chunk_sizes = [len(chunk.page_content) for chunk in chunks]
        total_chars = sum(chunk_sizes)

        # Calculate overlap overhead (approximation)
        total_overhead = (len(chunks) - 1) * self.chunk_overlap

        return {
            "total_chunks": len(chunks),
            "total_characters": total_chars,
            "avg_chunk_size": total_chars / len(chunks),
            "min_chunk_size": min(chunk_sizes),
            "max_chunk_size": max(chunk_sizes),
            "total_overhead": total_overhead,
        }

    def __repr__(self) -> str:
        """Return string representation of the TextSplitter instance."""
        return f"TextSplitter(chunk_size={self.chunk_size}, chunk_overlap={self.chunk_overlap})"

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return (
            f"TextSplitter configured with {self.chunk_size}B chunks "
            f"and {self.chunk_overlap}B overlap"
        )


# Convenience functions for backward compatibility
def split_documents(
    documents: List[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Document]:
    """
    Convenience function to split documents with a single call.

    This is a functional interface to the TextSplitter class for simple use cases
    where a one-off document split is needed without maintaining splitter state.

    Args:
        documents (List[Document]): List of documents to split.
        chunk_size (int): Size of each chunk. Defaults to 1000.
        chunk_overlap (int): Overlap between chunks. Defaults to 200.

    Returns:
        List[Document]: List of chunked documents.

    Raises:
        InvalidChunkConfigError: If chunk parameters are invalid.
        EmptyDocumentError: If documents list is empty.
        ChunkingError: If an error occurs during chunking.
    """
    splitter = TextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_documents(documents)


def split_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[str]:
    """
    Convenience function to split raw text with a single call.

    Args:
        text (str): Raw text to split.
        chunk_size (int): Size of each chunk. Defaults to 1000.
        chunk_overlap (int): Overlap between chunks. Defaults to 200.

    Returns:
        List[str]: List of text chunks.

    Raises:
        InvalidChunkConfigError: If chunk parameters are invalid.
        EmptyDocumentError: If text is empty.
        ChunkingError: If an error occurs during chunking.
    """
    splitter = TextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text(text)


def split_text_to_documents(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Document]:
    """
    Split raw text into Documents with a single call.

    Args:
        text (str): Raw text to split.
        chunk_size (int): Size of each chunk. Defaults to 1000.
        chunk_overlap (int): Overlap between chunks. Defaults to 200.
        metadata (Optional[Dict[str, Any]]): Metadata to attach to all chunks.
            Defaults to None.

    Returns:
        List[Document]: List of Document objects with chunks as content.

    Raises:
        InvalidChunkConfigError: If chunk parameters are invalid.
        EmptyDocumentError: If text is empty.
        ChunkingError: If an error occurs during chunking.
    """
    splitter = TextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_text_to_documents(text, metadata)


__all__ = [
    "ChunkingError",
    "InvalidChunkConfigError",
    "EmptyDocumentError",
    "TextSplitter",
    "split_documents",
    "split_text",
    "split_text_to_documents",
]
