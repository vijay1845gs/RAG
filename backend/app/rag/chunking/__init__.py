"""
Text Chunking Module

This package provides text chunking functionality for RAG systems, including
splitting documents into semantically coherent chunks while preserving metadata.
"""

from app.rag.chunking.text_splitter import (
    TextSplitter,
    ChunkingError,
    InvalidChunkConfigError,
    EmptyDocumentError,
    split_documents,
    split_text,
)

__all__ = [
    "TextSplitter",
    "ChunkingError",
    "InvalidChunkConfigError",
    "EmptyDocumentError",
    "split_documents",
    "split_text",
]
