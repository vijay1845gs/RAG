"""
ChromaDB Vector Store Manager Module

This module provides functionality to manage vector embeddings using ChromaDB,
including persistent storage, document indexing, and semantic retrieval operations.
It handles collection management, metadata preservation, and efficient top-k search.

Author: RAG System
Version: 1.0.0
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

from app.core.config import settings

try:
    from langchain_chroma import Chroma
except ModuleNotFoundError:
    Chroma = None

logger = logging.getLogger(__name__)


class ChromaDBError(Exception):
    """Base exception for ChromaDB errors."""

    pass


class VectorStoreInitError(ChromaDBError):
    """Raised when vector store initialization fails."""

    pass


class CollectionNotFoundError(ChromaDBError):
    """Raised when a collection does not exist."""

    pass


class DocumentAddError(ChromaDBError):
    """Raised when adding documents to the vector store fails."""

    pass


class SearchError(ChromaDBError):
    """Raised when search operations fail."""

    pass


class InvalidInputError(ChromaDBError):
    """Raised when input parameters are invalid."""

    pass


class ChromaManager:
    """
    A production-grade ChromaDB vector store manager for RAG systems.

    This class encapsulates ChromaDB functionality, handling persistent storage,
    document embedding, semantic search, and collection management. It provides
    clean interfaces for adding documents, retrieving similar chunks, and managing
    vector store lifecycle.

    Attributes:
        persist_dir (Path): Directory for persistent ChromaDB storage.
        embedding_function (OllamaEmbeddings): Embedding function for vectorization.
        chroma_client (Chroma): LangChain Chroma vector store instance.
        collection_name (str): Current active collection name.
        logger (logging.Logger): Logger instance for this class.

    Example:
        >>> manager = ChromaManager(collection_name="my_documents")
        >>> chunks = splitter.split_documents(documents)
        >>> manager.add_documents(chunks)
        >>> results = manager.search("What is AI?", k=5)
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: str = "default",
        embedding_function: Optional[OllamaEmbeddings] = None,
    ) -> None:
        """
        Initialize the ChromaDB manager.

        Args:
            persist_dir (str): Directory for persistent storage.
                Defaults to settings.CHROMA_PERSIST_DIR (resolved at call time).
            collection_name (str): Name of the collection to use or create.
                Defaults to "default".
            embedding_function (Optional[OllamaEmbeddings]): Custom embedding function.
                If None, uses default OllamaEmbeddings with settings.EMBEDDING_MODEL.

        Raises:
            VectorStoreInitError: If initialization fails.

        Example:
            >>> manager = ChromaManager(collection_name="research_papers")
            >>> # Or with custom embeddings
            >>> from langchain_community.embeddings import OllamaEmbeddings
            >>> embeddings = OllamaEmbeddings(base_url=settings.OLLAMA_BASE_URL, model="nomic-embed-text:latest")
            >>> manager = ChromaManager(embedding_function=embeddings)
        """
        self.logger = logger
        self._validate_collection_name(collection_name)

        try:
            # Resolve persist directory - always use settings as source of truth
            # to prevent CWD-dependent path mismatches between upload and chat
            effective_persist_dir = settings.CHROMA_PERSIST_DIR if persist_dir is None else Path(persist_dir)
            self.persist_dir = effective_persist_dir
            self.collection_name = collection_name

            # Create persist directory if it doesn't exist
            self.persist_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"ChromaDB persist directory: {self.persist_dir}")

            if Chroma is None:
                raise VectorStoreInitError(
                    "langchain_chroma is not installed. Install it before using ChromaManager."
                )

            # Initialize embedding function
            if embedding_function is None:
                self.logger.info(f"Loading default embedding model ({settings.EMBEDDING_MODEL})")
                embedding_function = OllamaEmbeddings(
                    base_url=settings.OLLAMA_BASE_URL,
                    model=settings.EMBEDDING_MODEL,
                )

            self.embedding_function = embedding_function

            # Initialize ChromaDB client
            self.chroma_client = Chroma(
                collection_name=collection_name,
                persist_directory=str(self.persist_dir),
                embedding_function=embedding_function,
            )

            self.logger.info(
                f"ChromaDB manager initialized. Collection: {collection_name}"
            )

        except Exception as e:
            error_msg = (
                f"Failed to initialize ChromaDB manager: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise VectorStoreInitError(error_msg) from e

    @staticmethod
    def _validate_collection_name(collection_name: str) -> None:
        """
        Validate collection name format.

        Args:
            collection_name (str): Collection name to validate.

        Raises:
            InvalidInputError: If collection name is invalid.
        """
        if not collection_name or not isinstance(collection_name, str):
            raise InvalidInputError(
                f"Collection name must be a non-empty string, got {type(collection_name).__name__}"
            )

        if not collection_name.strip():
            raise InvalidInputError("Collection name cannot be empty or whitespace-only")

        # ChromaDB allows alphanumeric, underscore, hyphen
        if not all(c.isalnum() or c in ("_", "-") for c in collection_name):
            raise InvalidInputError(
                f"Collection name contains invalid characters: {collection_name}"
            )

    def add_documents(
        self,
        documents: List[Document],
        batch_size: int = 100,
    ) -> List[str]:
        """
        Add documents to the vector store.

        Adds document chunks with their embeddings and metadata to the ChromaDB
        collection. Supports batch processing for efficient ingestion of large
        document sets.

        Args:
            documents (List[Document]): List of LangChain Document objects to add.
            batch_size (int): Number of documents to process per batch.
                Defaults to 100. Larger batches are faster but use more memory.

        Returns:
            List[str]: List of document IDs assigned by ChromaDB.

        Raises:
            InvalidInputError: If documents list is empty.
            DocumentAddError: If adding documents fails.

        Example:
            >>> manager = ChromaManager()
            >>> chunks = splitter.split_documents(documents)
            >>> doc_ids = manager.add_documents(chunks)
            >>> print(f"Added {len(doc_ids)} documents to vector store")
        """
        try:
            if not documents or not isinstance(documents, list):
                raise InvalidInputError(
                    f"Documents must be a non-empty list, got {type(documents).__name__}"
                )

            self.logger.info(
                f"Adding {len(documents)} documents to collection: {self.collection_name}"
            )

            doc_ids = []
            total_processed = 0

            # Process documents in batches
            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]

                try:
                    # Add batch to ChromaDB
                    batch_ids = self.chroma_client.add_documents(batch)
                    doc_ids.extend(batch_ids)
                    total_processed += len(batch)

                    self.logger.debug(
                        f"Batch {i // batch_size + 1}: Added {len(batch)} documents"
                    )

                except Exception as batch_error:
                    error_msg = f"Error adding document batch: {str(batch_error)}"
                    self.logger.error(error_msg)
                    raise DocumentAddError(error_msg) from batch_error

            # Newer langchain_chroma persists automatically when a persist
            # directory is configured; older versions still expose persist().
            self._persist_if_supported()

            self.logger.info(
                f"Successfully added {len(doc_ids)} documents. "
                f"Document IDs: {len(set(doc_ids))} unique"
            )

            return doc_ids

        except InvalidInputError:
            raise

        except DocumentAddError:
            raise

        except Exception as e:
            error_msg = (
                f"Error adding documents to vector store: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise DocumentAddError(error_msg) from e

    def search(
        self,
        query: str,
        k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        """
        Search for similar documents using semantic similarity.

        Performs semantic search on the vector store and returns top-k results
        with their similarity scores. Supports optional metadata filtering.

        Args:
            query (str): Query text to search for.
            k (int): Number of top results to return. Defaults to 5.
            metadata_filter (Optional[Dict[str, Any]]): Metadata filter criteria.
                Example: {"collection_id": "col_123", "file_type": "pdf"}
                Defaults to None (no filtering).

        Returns:
            List[Tuple[Document, float]]: List of (document, similarity_score) tuples.
                Higher scores indicate better matches.

        Raises:
            InvalidInputError: If query is empty or k is invalid.
            SearchError: If search operation fails.

        Example:
            >>> manager = ChromaManager()
            >>> results = manager.search("What is machine learning?", k=5)
            >>> for doc, score in results:
            ...     print(f"Score: {score:.4f}")
            ...     print(f"Content: {doc.page_content[:100]}...")
        """
        try:
            if not query or not isinstance(query, str):
                raise InvalidInputError(
                    f"Query must be a non-empty string, got {type(query).__name__}"
                )

            if not query.strip():
                raise InvalidInputError("Query cannot be empty or whitespace-only")

            if not isinstance(k, int) or k <= 0:
                raise InvalidInputError(f"k must be a positive integer, got {k}")

            self.logger.info(f"Searching for: {query[:100]}... (k={k})")

            # Perform similarity search with scores
            results = self.chroma_client.similarity_search_with_score(
                query=query,
                k=k,
                filter=metadata_filter,
            )

            if not results:
                self.logger.warning(f"No results found for query: {query[:50]}...")
                return []

            self.logger.info(f"Found {len(results)} results")

            return results

        except InvalidInputError:
            raise

        except Exception as e:
            error_msg = (
                f"Error searching vector store: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise SearchError(error_msg) from e

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Perform similarity search returning only documents.

        Performs semantic search and returns only the document objects without
        similarity scores. Useful when scores are not needed.

        Args:
            query (str): Query text to search for.
            k (int): Number of top results to return. Defaults to 5.
            metadata_filter (Optional[Dict[str, Any]]): Metadata filter criteria.

        Returns:
            List[Document]: List of matching documents.

        Raises:
            InvalidInputError: If query is empty or k is invalid.
            SearchError: If search operation fails.

        Example:
            >>> results = manager.similarity_search("AI technologies", k=3)
            >>> for doc in results:
            ...     print(doc.page_content)
        """
        try:
            results_with_scores = self.search(query, k, metadata_filter)
            return [doc for doc, _ in results_with_scores]

        except Exception as e:
            error_msg = (
                f"Error performing similarity search: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise SearchError(error_msg) from e

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current collection.

        Returns information about the collection including document count and
        collection metadata.

        Returns:
            Dict[str, Any]: Dictionary with keys:
                - collection_name: Name of the collection
                - document_count: Number of documents in collection
                - persist_dir: Persistence directory path

        Example:
            >>> stats = manager.get_collection_stats()
            >>> print(f"Documents in collection: {stats['document_count']}")
        """
        try:
            # Get collection from ChromaDB
            collection = self.chroma_client._collection

            stats = {
                "collection_name": self.collection_name,
                "document_count": collection.count() if hasattr(collection, "count") else 0,
                "persist_dir": str(self.persist_dir),
            }

            self.logger.debug(f"Collection stats: {stats}")
            return stats

        except Exception as e:
            self.logger.error(f"Error getting collection stats: {str(e)}")
            return {
                "collection_name": self.collection_name,
                "document_count": 0,
                "persist_dir": str(self.persist_dir),
            }

    def delete_collection(self) -> None:
        """
        Delete the current collection from the vector store.

        Removes all documents and metadata from the collection. This operation
        is irreversible.

        Example:
            >>> manager = ChromaManager(collection_name="old_collection")
            >>> manager.delete_collection()
            >>> # Collection is now removed
        """
        try:
            self.logger.warning(f"Deleting collection: {self.collection_name}")

            self.chroma_client.delete_collection()

            self.logger.info(f"Collection deleted: {self.collection_name}")

        except Exception as e:
            error_msg = (
                f"Error deleting collection: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise ChromaDBError(error_msg) from e

    def persist(self) -> None:
        """
        Persist the vector store to disk.

        Ensures all changes are written to persistent storage when the installed
        Chroma wrapper exposes an explicit persist method. Newer
        langchain_chroma versions persist automatically when a persist directory
        is configured, so this method is a compatibility no-op there.

        Example:
            >>> manager = ChromaManager()
            >>> manager.add_documents(chunks)
            >>> manager.persist()  # Ensure persistence
        """
        try:
            self.logger.debug("Persisting vector store to disk")
            self._persist_if_supported()
            self.logger.info("Vector store persisted successfully")

        except Exception as e:
            error_msg = f"Error persisting vector store: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            raise ChromaDBError(error_msg) from e

    def _persist_if_supported(self) -> None:
        """Persist explicitly for older Chroma wrappers; no-op for newer ones."""
        persist = getattr(self.chroma_client, "persist", None)
        if callable(persist):
            persist()
        else:
            self.logger.debug(
                "Chroma client has no persist() method; relying on automatic persistence"
            )

    def delete_documents_by_metadata(
        self,
        metadata_filter: Dict[str, Any],
    ) -> int:
        """
        Delete all documents matching metadata filter.

        Removes all documents from the collection that match the provided
        metadata criteria. Useful for cleanup when deleting documents.

        Args:
            metadata_filter (Dict[str, Any]): Metadata filter criteria.
                Example: {"document_id": "doc_123"}

        Returns:
            int: Number of documents deleted.

        Raises:
            InvalidInputError: If metadata_filter is invalid.
            ChromaDBError: If deletion fails.

        Example:
            >>> count = manager.delete_documents_by_metadata({"document_id": "doc_123"})
            >>> print(f"Deleted {count} documents")
        """
        try:
            if not metadata_filter or not isinstance(metadata_filter, dict):
                raise InvalidInputError(
                    f"metadata_filter must be a non-empty dict, got {type(metadata_filter).__name__}"
                )

            self.logger.info(f"Deleting documents with filter: {metadata_filter}")

            # Get the underlying Chroma collection to perform the delete
            collection = self.chroma_client._collection

            # Use ChromaDB's native delete with where clause
            result = collection.delete(where=metadata_filter)

            # Persist after deletion when required by the installed wrapper.
            self._persist_if_supported()

            deleted_count = len(result) if result else 0
            self.logger.info(f"Deleted {deleted_count} documents matching filter")

            return deleted_count

        except InvalidInputError:
            raise
        except Exception as e:
            error_msg = (
                f"Error deleting documents by metadata: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise ChromaDBError(error_msg) from e

    def list_collections(self) -> List[str]:
        """
        List all available collections in the vector store.

        Returns names of all collections stored in the persistence directory.

        Returns:
            List[str]: List of collection names.

        Example:
            >>> manager = ChromaManager()
            >>> collections = manager.list_collections()
            >>> print(f"Available collections: {collections}")
        """
        try:
            # Access the client to list collections
            if hasattr(self.chroma_client, "_client"):
                collections = self.chroma_client._client.list_collections()
                collection_names = [c.name for c in collections]
            else:
                collection_names = [self.collection_name]

            self.logger.debug(f"Found {len(collection_names)} collections")
            return collection_names

        except Exception as e:
            self.logger.warning(f"Error listing collections: {str(e)}")
            return [self.collection_name]

    def switch_collection(self, collection_name: str) -> None:
        """
        Switch to a different collection.

        Changes the active collection. Creates the collection if it doesn't exist.

        Args:
            collection_name (str): Name of the collection to switch to.

        Raises:
            InvalidInputError: If collection name is invalid.
            ChromaDBError: If switching fails.

        Example:
            >>> manager = ChromaManager(collection_name="collection_1")
            >>> manager.switch_collection("collection_2")
            >>> # Now operating on collection_2
        """
        try:
            self._validate_collection_name(collection_name)

            self.logger.info(
                f"Switching from collection '{self.collection_name}' to '{collection_name}'"
            )

            self.collection_name = collection_name

            if Chroma is None:
                raise ChromaDBError(
                    "langchain_chroma is not installed. Install it before switching collections."
                )

            # Reinitialize with new collection
            self.chroma_client = Chroma(
                collection_name=collection_name,
                persist_directory=str(self.persist_dir),
                embedding_function=self.embedding_function,
            )

            self.logger.info(f"Switched to collection: {collection_name}")

        except InvalidInputError:
            raise

        except Exception as e:
            error_msg = (
                f"Error switching collection: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise ChromaDBError(error_msg) from e

    def clear_all(self) -> None:
        """
        Clear all data from persistence directory.

        WARNING: This removes all collections and embeddings permanently.
        Use with caution.

        Example:
            >>> manager = ChromaManager()
            >>> manager.clear_all()  # Clears entire vector store
        """
        try:
            self.logger.warning(f"Clearing all data in {self.persist_dir}")

            # Delete all files in the persist directory
            if self.persist_dir.exists():
                for item in self.persist_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        import shutil
                        shutil.rmtree(item)

            self.logger.info("Vector store completely cleared")

        except Exception as e:
            error_msg = f"Error clearing vector store: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg)
            raise ChromaDBError(error_msg) from e

    def __repr__(self) -> str:
        """Return string representation of the ChromaManager instance."""
        return (
            f"ChromaManager(collection_name='{self.collection_name}', "
            f"persist_dir='{self.persist_dir}')"
        )

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return (
            f"ChromaDB Manager for collection '{self.collection_name}' "
            f"at {self.persist_dir}"
        )


def create_chroma_manager(
    persist_dir: Optional[str] = None,
    collection_name: str = "default",
) -> ChromaManager:
    """
    Convenience function to create a ChromaDB manager instance.

    Args:
        persist_dir (str | None): Persistence directory path.
            Defaults to settings.CHROMA_PERSIST_DIR (resolved at call time).
        collection_name (str): Collection name.

    Returns:
        ChromaManager: Initialized ChromaDB manager.

    Example:
        >>> manager = create_chroma_manager(collection_name="my_docs")
        >>> manager.add_documents(chunks)
    """
    return ChromaManager(persist_dir=persist_dir, collection_name=collection_name)
