"""
Vector Store Module

This package provides vector store functionality for RAG systems, including
ChromaDB-based persistent storage and FAISS CPU-optimized search for document 
embeddings and semantic search.
"""

from app.rag.vectorstore.chroma_manager import (
    ChromaManager,
    ChromaDBError,
    VectorStoreInitError,
    CollectionNotFoundError,
    DocumentAddError,
    SearchError,
    InvalidInputError,
    create_chroma_manager,
)

from app.rag.vectorstore.faiss_manager import (
    FAISSManager,
    FAISSError,
    FAISSInitError,
    FAISSSearchError,
    create_faiss_manager,
)

__all__ = [
    # ChromaDB
    "ChromaManager",
    "ChromaDBError",
    "VectorStoreInitError",
    "CollectionNotFoundError",
    "DocumentAddError",
    "SearchError",
    "InvalidInputError",
    "create_chroma_manager",
    # FAISS
    "FAISSManager",
    "FAISSError",
    "FAISSInitError",
    "FAISSSearchError",
    "create_faiss_manager",
]
