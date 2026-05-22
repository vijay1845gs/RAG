"""
FAISS Vector Store Manager Module

This module provides functionality to manage vector embeddings using FAISS,
a library for efficient similarity search. It handles index creation, document
storage, and semantic retrieval operations optimized for CPU inference.

Author: RAG System
Version: 1.0.0
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from app.core.config import settings

try:
    import faiss
    import numpy as np
except ImportError:
    faiss = None
    np = None

logger = logging.getLogger(__name__)


class FAISSError(Exception):
    """Base exception for FAISS errors."""
    pass


class FAISSInitError(FAISSError):
    """Raised when FAISS initialization fails."""
    pass


class FAISSSearchError(FAISSError):
    """Raised when FAISS search operations fail."""
    pass


class FAISSManager:
    """
    A CPU-optimized FAISS vector store manager for RAG systems.

    This class wraps FAISS functionality for efficient similarity search
    with CPU inference. It handles index management, document storage,
    and metadata preservation.

    Attributes:
        index_dir (Path): Directory for persistent FAISS index storage.
        embedding_function (OllamaEmbeddings): Embedding function for vectorization.
        index (faiss.IndexFlatL2): FAISS index instance.
        collection_name (str): Current active collection name.
        documents_path (Path): Path to stored document metadata.
        logger (logging.Logger): Logger instance for this class.
    """

    def __init__(
        self,
        index_dir: Optional[str] = None,
        collection_name: str = "default",
        embedding_function: Optional[OllamaEmbeddings] = None,
    ) -> None:
        """
        Initialize the FAISS manager.

        Args:
            index_dir (str): Directory for persistent index storage.
            collection_name (str): Name of the collection (used for metadata).
            embedding_function (Optional[OllamaEmbeddings]): Custom embedding function.
                If None, uses default OllamaEmbeddings with settings.EMBEDDING_MODEL.

        Raises:
            FAISSInitError: If initialization fails.
        """
        self.logger = logger
        
        if faiss is None:
            raise FAISSInitError(
                "faiss is not installed. Install it with: pip install faiss-cpu"
            )

        try:
            self.index_dir = Path(index_dir) if index_dir else Path("./faiss_index")
            self.index_dir.mkdir(parents=True, exist_ok=True)
            self.collection_name = collection_name

            # Initialize embedding function
            if embedding_function is None:
                self.logger.info(f"Loading default embedding model ({settings.EMBEDDING_MODEL})")
                embedding_function = OllamaEmbeddings(
                    base_url=settings.OLLAMA_BASE_URL,
                    model=settings.EMBEDDING_MODEL,
                )

            self.embedding_function = embedding_function
            self.embedding_dim = len(embedding_function.embed_query("test"))

            # Initialize FAISS index
            self.index = faiss.IndexFlatL2(self.embedding_dim)
            
            # Paths for persistence
            self.index_path = self.index_dir / f"{collection_name}.faiss"
            self.documents_path = self.index_dir / f"{collection_name}_documents.json"
            self.documents: List[Document] = []

            # Load existing index if available
            self._load_index()

            self.logger.info(
                f"FAISS manager initialized. Collection: {collection_name}, Index dir: {self.index_dir}"
            )

        except Exception as e:
            error_msg = f"Failed to initialize FAISS manager: {type(e).__name__}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise FAISSInitError(error_msg) from e

    def add_documents(self, documents: List[Document]) -> None:
        """
        Add documents to the FAISS index.

        Args:
            documents: List of Document objects to add.

        Raises:
            FAISSError: If adding documents fails.
        """
        try:
            if not documents:
                self.logger.warning("No documents provided to add_documents")
                return

            # Generate embeddings
            texts = [doc.page_content for doc in documents]
            embeddings = self.embedding_function.embed_documents(texts)
            embeddings_array = np.array(embeddings, dtype=np.float32)

            # Add to FAISS index
            self.index.add(embeddings_array)

            # Store documents with metadata
            self.documents.extend(documents)

            self.logger.info(
                f"Added {len(documents)} documents to FAISS index. Total: {self.index.ntotal}"
            )

        except Exception as e:
            error_msg = f"Failed to add documents: {type(e).__name__}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise FAISSError(error_msg) from e

    def search(
        self,
        query: str,
        k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        """
        Search for similar documents.

        Args:
            query: Search query text.
            k: Number of results to return.
            metadata_filter: Optional metadata filter (currently unused).

        Returns:
            List of (Document, score) tuples.

        Raises:
            FAISSSearchError: If search fails.
        """
        try:
            if self.index.ntotal == 0:
                self.logger.warning("FAISS index is empty")
                return []

            # Embed the query
            query_embedding = self.embedding_function.embed_query(query)
            query_array = np.array([query_embedding], dtype=np.float32)

            # Search
            distances, indices = self.index.search(query_array, min(k, self.index.ntotal))

            # Convert distances to similarity scores
            results: List[Tuple[Document, float]] = []
            for idx, distance in zip(indices[0], distances[0]):
                if idx < len(self.documents):
                    score = 1.0 / (1.0 + float(distance))
                    results.append((self.documents[int(idx)], score))

            self.logger.debug(f"Search returned {len(results)} results")
            return results

        except Exception as e:
            error_msg = f"Search failed: {type(e).__name__}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise FAISSSearchError(error_msg) from e

    def persist(self) -> None:
        """Save the index and documents to disk."""
        try:
            faiss.write_index(self.index, str(self.index_path))
            
            # Save documents as JSON
            docs_data = []
            for doc in self.documents:
                docs_data.append({
                    "page_content": doc.page_content,
                    "metadata": doc.metadata,
                })
            
            with open(self.documents_path, "w") as f:
                json.dump(docs_data, f, indent=2)

            self.logger.info(
                f"Persisted FAISS index to {self.index_path} and documents to {self.documents_path}"
            )

        except Exception as e:
            error_msg = f"Failed to persist index: {type(e).__name__}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise FAISSError(error_msg) from e

    def _load_index(self) -> None:
        """Load existing index and documents from disk."""
        try:
            if self.index_path.exists():
                self.index = faiss.read_index(str(self.index_path))
                self.logger.info(f"Loaded existing FAISS index with {self.index.ntotal} vectors")

            if self.documents_path.exists():
                with open(self.documents_path, "r") as f:
                    docs_data = json.load(f)
                
                self.documents = [
                    Document(page_content=d["page_content"], metadata=d["metadata"])
                    for d in docs_data
                ]
                self.logger.info(f"Loaded {len(self.documents)} documents from disk")

        except Exception as e:
            self.logger.warning(f"Could not load existing index: {e}")

    def get_collection_stats(self) -> Dict[str, Any]:
        """Return collection statistics."""
        return {
            "document_count": len(self.documents),
            "vector_count": self.index.ntotal,
            "embedding_dim": self.embedding_dim,
        }


def create_faiss_manager(
    index_dir: Optional[str] = None,
    collection_name: str = "default",
) -> FAISSManager:
    """
    Convenience function to create a FAISSManager instance.

    Args:
        index_dir: Directory for index storage.
        collection_name: Collection name.

    Returns:
        Initialized FAISSManager instance.
    """
    return FAISSManager(index_dir=index_dir, collection_name=collection_name)
