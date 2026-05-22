"""
Embedding Module

This package provides embedding functionality for RAG systems, including
model management and vector generation for documents and queries.
"""

from app.rag.embeddings.embedding_model import (
    EmbeddingModel,
    EmbeddingError,
    ModelLoadError,
    EmbeddingGenerationError,
    InvalidInputError,
    get_embedding_model,
    embed_text,
    embed_texts,
)

__all__ = [
    "EmbeddingModel",
    "EmbeddingError",
    "ModelLoadError",
    "EmbeddingGenerationError",
    "InvalidInputError",
    "get_embedding_model",
    "embed_text",
    "embed_texts",
]
