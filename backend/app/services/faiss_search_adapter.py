"""
FAISS Search Adapter for SemanticRetriever compatibility.

This adapter wraps FAISSManager to provide a search interface compatible
with the SemanticRetriever class.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document

from app.rag.embeddings import EmbeddingModel as EmbeddingManager
from app.rag.vectorstore.faiss_manager import FAISSManager, FAISSError

logger = logging.getLogger(__name__)


class FAISSSearchAdapter:
    """Adapter exposing FAISSManager through SemanticRetriever's search interface."""

    def __init__(
        self,
        index_dir: Path,
        collection_name: str,
        embedding_manager: EmbeddingManager,
    ) -> None:
        """
        Initialize the FAISS search adapter.

        Args:
            index_dir: Directory containing FAISS indices.
            collection_name: Name of the FAISS collection.
            embedding_manager: EmbeddingManager instance for query embeddings.
        """
        self.index_dir = Path(index_dir)
        self.collection_name = collection_name
        self.embedding_manager = embedding_manager
        self.manager = FAISSManager(
            index_dir=str(self.index_dir),
            collection_name=collection_name,
            embedding_function=embedding_manager.embeddings,
        )

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
            metadata_filter: Optional metadata filter (unused for FAISS).

        Returns:
            List of (Document, score) tuples.
        """
        return self.manager.search(query=query, k=k, metadata_filter=metadata_filter)
