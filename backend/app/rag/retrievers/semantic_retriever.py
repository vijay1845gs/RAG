"""
Semantic Retriever Module for RAG Systems

This module provides functionality to retrieve semantically similar document chunks
from a vector store based on user queries. It handles ranking, filtering, and
metadata preservation for downstream processing.

Author: RAG System
Version: 1.0.0
"""

import logging
from typing import List, Optional, Dict, Any, Tuple

from langchain_core.documents import Document

from app.core.config import settings

logger = logging.getLogger(__name__)


class RetrieverError(Exception):
    """Base exception for retriever errors."""

    pass


class QueryError(RetrieverError):
    """Raised when query validation fails."""

    pass


class RetrievalError(RetrieverError):
    """Raised when retrieval operation fails."""

    pass


class VectorStoreError(RetrieverError):
    """Raised when vector store operations fail."""

    pass


class InvalidConfigError(RetrieverError):
    """Raised when retriever configuration is invalid."""

    pass


class SemanticRetriever:
    """
    A production-grade semantic retriever for RAG systems.

    This class encapsulates semantic retrieval functionality, handling query
    processing, vector store searches, and result ranking. It provides clean
    interfaces for retrieving contextually relevant document chunks.

    Attributes:
        vector_store (ChromaManager): The underlying vector store for searches.
        top_k (int): Default number of top results to retrieve.
        logger (logging.Logger): Logger instance for this class.

    Example:
        >>> from app.rag.vectorstore import ChromaManager
        >>> from app.core.config import settings
        >>> vector_store = ChromaManager(collection_name="documents")
        >>> retriever = SemanticRetriever(
        ...     vector_store=vector_store,
        ...     top_k=5,
        ...     similarity_threshold=settings.SIMILARITY_THRESHOLD
        ... )
        >>> query = "What is machine learning?"
        >>> results = retriever.retrieve(query)
        >>> for doc, score in results:
        ...     print(f"Score: {score:.4f}")
        ...     print(f"Content: {doc.page_content[:100]}...")
    """

    def __init__(
        self,
        vector_store: Any,
        top_k: int = 3,
        similarity_threshold: Optional[float] = None,
    ) -> None:
        """
        Initialize the SemanticRetriever.

        Args:
            vector_store (ChromaManager): The vector store instance for searching.
            top_k (int): Default number of top results to retrieve. Defaults to 3.

        Raises:
            InvalidConfigError: If configuration is invalid.
            VectorStoreError: If vector store is invalid.

        Example:
            >>> from app.rag.vectorstore import ChromaManager
            >>> manager = ChromaManager()
            >>> retriever = SemanticRetriever(vector_store=manager, top_k=5)
        """
        self.logger = logger
        self._validate_config(top_k)
        # Validate similarity_threshold if provided
        if similarity_threshold is not None:
            self._validate_similarity_threshold(similarity_threshold)
        else:
            similarity_threshold = settings.SIMILARITY_THRESHOLD

        try:
            if not vector_store:
                raise VectorStoreError("Vector store cannot be None")

            self.vector_store = vector_store
            self.top_k = top_k
            self.similarity_threshold = similarity_threshold

            self.logger.info(
                f"SemanticRetriever initialized with top_k={self.top_k}, "
                f"similarity_threshold={self.similarity_threshold}"
            )

        except VectorStoreError:
            raise

        except Exception as e:
            error_msg = (
                f"Error initializing SemanticRetriever: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise VectorStoreError(error_msg) from e

    @staticmethod
    def _validate_config(top_k: int) -> None:
        """
        Validate retriever configuration parameters.

        Args:
            top_k (int): Number of top results to retrieve.

        Raises:
            InvalidConfigError: If parameters are invalid.
        """
        if not isinstance(top_k, int):
            raise InvalidConfigError(
                f"top_k must be an integer, got {type(top_k).__name__}"
            )

        if top_k <= 0:
            raise InvalidConfigError(f"top_k must be positive, got {top_k}")

    @staticmethod
    def _validate_similarity_threshold(threshold: float) -> None:
        """
        Validate similarity threshold parameter.

        Args:
            threshold (float): Similarity threshold value between 0.0 and 1.0.

        Raises:
            InvalidConfigError: If threshold is invalid.
        """
        if not isinstance(threshold, (float, int)):
            raise InvalidConfigError(
                f"similarity_threshold must be a float or int, got {type(threshold).__name__}"
            )

        if threshold < 0.0 or threshold > 1.0:
            raise InvalidConfigError(
                f"similarity_threshold must be between 0.0 and 1.0, got {threshold}"
            )

    @staticmethod
    def _validate_query(query: str) -> None:
        """
        Validate query input.

        Args:
            query (str): Query string to validate.

        Raises:
            QueryError: If query is invalid.
        """
        if not query or not isinstance(query, str):
            raise QueryError(
                f"Query must be a non-empty string, got {type(query).__name__}"
            )

        if not query.strip():
            raise QueryError("Query cannot be empty or whitespace-only")

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        """
        Retrieve semantically similar documents for a query.

        Performs semantic search in the vector store and returns top-k results
        with similarity scores. Supports optional metadata filtering.

        Args:
            query (str): The user query to retrieve documents for.
            top_k (Optional[int]): Number of results to retrieve. If None, uses default.
            metadata_filter (Optional[Dict[str, Any]]): Metadata filter criteria.
                Example: {"collection_id": "col_123", "file_type": "pdf"}

        Returns:
            List[Tuple[Document, float]]: List of (document, similarity_score) tuples.
                Sorted by relevance score in descending order.

        Raises:
            QueryError: If query is invalid.
            RetrievalError: If retrieval operation fails.

        Example:
            >>> retriever = SemanticRetriever(vector_store=manager, top_k=5)
            >>> results = retriever.retrieve("What is AI?", top_k=3)
            >>> for doc, score in results:
            ...     print(f"Score: {score:.4f}, Content: {doc.page_content[:50]}...")
        """
        try:
            self._validate_query(query)

            retrieve_k = top_k if top_k is not None else self.top_k

            if not isinstance(retrieve_k, int) or retrieve_k <= 0:
                raise QueryError(f"top_k must be a positive integer, got {retrieve_k}")

            self.logger.info(
                f"Retrieving {retrieve_k} documents for query: {query[:100]}..."
            )

            # Perform semantic search
            results = self.vector_store.search(
                query=query,
                k=retrieve_k,
                metadata_filter=metadata_filter,
            )

            if not results:
                self.logger.warning(f"No results found for query: {query[:50]}...")
                return []

            # Filter by similarity threshold
            filtered_results = [
                (doc, score) for doc, score in results 
                if score >= self.similarity_threshold
            ]

            if not filtered_results:
                self.logger.warning(
                    f"No results met similarity threshold {self.similarity_threshold} "
                    f"for query: {query[:50]}..."
                )
                return []

            # Sort by score in descending order (higher is better)
            sorted_results = sorted(filtered_results, key=lambda x: x[1], reverse=True)

            self.logger.info(
                f"Retrieved {len(sorted_results)} documents "
                f"(filtered from {len(results)} results using threshold {self.similarity_threshold})"
            )

            return sorted_results

        except QueryError:
            raise

        except Exception as e:
            error_msg = (
                f"Error retrieving documents: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise RetrievalError(error_msg) from e

    def retrieve_documents(
        self,
        query: str,
        top_k: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Retrieve documents without similarity scores.

        Performs semantic search and returns only the document objects without
        scores. Useful when scores are not needed for downstream processing.

        Args:
            query (str): The user query.
            top_k (Optional[int]): Number of results to retrieve.
            metadata_filter (Optional[Dict[str, Any]]): Metadata filter criteria.

        Returns:
            List[Document]: List of matching documents.

        Raises:
            QueryError: If query is invalid.
            RetrievalError: If retrieval operation fails.

        Example:
            >>> retriever = SemanticRetriever(vector_store=manager)
            >>> docs = retriever.retrieve_documents("Tell me about Python")
            >>> for doc in docs:
            ...     print(doc.page_content)
        """
        try:
            results = self.retrieve(query, top_k, metadata_filter)
            return [doc for doc, _ in results]

        except QueryError:
            raise

        except Exception as e:
            error_msg = (
                f"Error retrieving documents: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise RetrievalError(error_msg) from e

    def retrieve_with_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve documents and return comprehensive context information.

        Performs semantic search and returns detailed metadata about the
        retrieval operation, including scores, document count, and query info.

        Args:
            query (str): The user query.
            top_k (Optional[int]): Number of results to retrieve.
            metadata_filter (Optional[Dict[str, Any]]): Metadata filter criteria.

        Returns:
            Dict[str, Any]: Dictionary containing:
                - query: Original query string
                - top_k: Number of results retrieved
                - total_results: Actual count of results
                - documents: List of retrieved documents
                - scores: Corresponding similarity scores
                - avg_score: Average similarity score
                - max_score: Highest similarity score
                - min_score: Lowest similarity score
                - metadata_filter: Applied metadata filter

        Raises:
            QueryError: If query is invalid.
            RetrievalError: If retrieval operation fails.

        Example:
            >>> retriever = SemanticRetriever(vector_store=manager)
            >>> context = retriever.retrieve_with_context("machine learning", top_k=5)
            >>> print(f"Found {context['total_results']} results")
            >>> print(f"Average score: {context['avg_score']:.4f}")
        """
        try:
            self._validate_query(query)

            results = self.retrieve(query, top_k, metadata_filter)

            if not results:
                return {
                    "query": query,
                    "top_k": top_k or self.top_k,
                    "total_results": 0,
                    "documents": [],
                    "scores": [],
                    "avg_score": 0.0,
                    "max_score": 0.0,
                    "min_score": 0.0,
                    "metadata_filter": metadata_filter,
                }

            documents = [doc for doc, _ in results]
            scores = [score for _, score in results]

            return {
                "query": query,
                "top_k": top_k or self.top_k,
                "total_results": len(results),
                "documents": documents,
                "scores": scores,
                "avg_score": sum(scores) / len(scores) if scores else 0.0,
                "max_score": max(scores) if scores else 0.0,
                "min_score": min(scores) if scores else 0.0,
                "metadata_filter": metadata_filter,
            }

        except QueryError:
            raise

        except Exception as e:
            error_msg = (
                f"Error retrieving context: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise RetrievalError(error_msg) from e

    def batch_retrieve(
        self,
        queries: List[str],
        top_k: Optional[int] = None,
    ) -> Dict[str, List[Tuple[Document, float]]]:
        """
        Retrieve documents for multiple queries in batch.

        Performs semantic search for each query and returns results as a
        dictionary mapping queries to their retrieved documents.

        Args:
            queries (List[str]): List of query strings.
            top_k (Optional[int]): Number of results per query.

        Returns:
            Dict[str, List[Tuple[Document, float]]]: Mapping from query to results.

        Raises:
            QueryError: If any query is invalid.
            RetrievalError: If retrieval operation fails.

        Example:
            >>> retriever = SemanticRetriever(vector_store=manager)
            >>> queries = ["What is AI?", "Define machine learning"]
            >>> results = retriever.batch_retrieve(queries, top_k=3)
            >>> for query, docs in results.items():
            ...     print(f"Query: {query}")
            ...     print(f"Results: {len(docs)}")
        """
        try:
            if not queries or not isinstance(queries, list):
                raise QueryError("Queries must be a non-empty list")

            self.logger.info(f"Batch retrieving for {len(queries)} queries")

            results = {}
            for query in queries:
                try:
                    self._validate_query(query)
                    docs = self.retrieve(query, top_k)
                    results[query] = docs

                except QueryError as e:
                    self.logger.error(f"Error processing query '{query}': {str(e)}")
                    results[query] = []

            self.logger.info(
                f"Batch retrieval complete. Processed {len(results)} queries"
            )
            return results

        except QueryError:
            raise

        except Exception as e:
            error_msg = (
                f"Error in batch retrieval: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise RetrievalError(error_msg) from e

    def set_top_k(self, top_k: int) -> None:
        """
        Update the default top_k retrieval count.

        Allows changing the default number of results to retrieve without
        creating a new instance.

        Args:
            top_k (int): New default retrieval count.

        Raises:
            InvalidConfigError: If top_k is invalid.

        Example:
            >>> retriever = SemanticRetriever(vector_store=manager, top_k=3)
            >>> retriever.set_top_k(10)  # Change to retrieve 10 results by default
        """
        try:
            self._validate_config(top_k)
            self.top_k = top_k
            self.logger.info(f"Default top_k updated to {top_k}")

        except InvalidConfigError:
            raise

    def get_retriever_info(self) -> Dict[str, Any]:
        """
        Get information about the current retriever configuration.

        Returns configuration details and metadata about the retriever instance.

        Returns:
            Dict[str, Any]: Dictionary with keys:
                - default_top_k: Default number of results to retrieve
                - vector_store_collection: Current collection name (if available)

        Example:
            >>> retriever = SemanticRetriever(vector_store=manager, top_k=5)
            >>> info = retriever.get_retriever_info()
            >>> print(f"Default top_k: {info['default_top_k']}")
        """
        info = {
            "default_top_k": self.top_k,
        }

        # Add vector store collection name if available
        if hasattr(self.vector_store, "collection_name"):
            info["vector_store_collection"] = self.vector_store.collection_name

        return info

    def __repr__(self) -> str:
        """Return string representation of the SemanticRetriever instance."""
        collection = (
            self.vector_store.collection_name
            if hasattr(self.vector_store, "collection_name")
            else "unknown"
        )
        return f"SemanticRetriever(collection='{collection}', top_k={self.top_k})"

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"SemanticRetriever with default top_k={self.top_k}"


def create_semantic_retriever(
    vector_store: Any,
    top_k: int = 3,
) -> SemanticRetriever:
    """
    Convenience function to create a SemanticRetriever instance.

    Args:
        vector_store: The vector store for semantic search.
        top_k (int): Default number of results. Defaults to 3.

    Returns:
        SemanticRetriever: Initialized semantic retriever.

    Raises:
        InvalidConfigError: If configuration is invalid.
        VectorStoreError: If vector store is invalid.

    Example:
        >>> from app.rag.vectorstore import ChromaManager
        >>> manager = ChromaManager()
        >>> retriever = create_semantic_retriever(vector_store=manager, top_k=5)
        >>> results = retriever.retrieve("What is AI?")
    """
    return SemanticRetriever(vector_store=vector_store, top_k=top_k)
