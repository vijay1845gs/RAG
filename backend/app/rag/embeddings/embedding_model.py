"""
Embedding Model Module for RAG Systems

This module provides functionality to generate embeddings for documents and queries
using LangChain's HuggingFaceEmbeddings with the sentence-transformers/all-MiniLM-L6-v2
model. It implements a singleton pattern to optimize model loading and memory usage
across the application.

Author: RAG System
Version: 1.0.0
"""

import logging
import threading
from typing import List, Optional, Union

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingError(Exception):
    """Base exception for embedding errors."""

    pass


class ModelLoadError(EmbeddingError):
    """Raised when the embedding model fails to load."""

    pass


class EmbeddingGenerationError(EmbeddingError):
    """Raised when embedding generation fails."""

    pass


class InvalidInputError(EmbeddingError):
    """Raised when input is invalid for embedding."""

    pass


class EmbeddingModel:
    """
    A production-grade embedding model manager for RAG systems.

    This class encapsulates embedding functionality, handling model initialization,
    caching, and providing clean interfaces for generating embeddings from documents
    and queries. Implements a singleton pattern for efficient resource management.

    Attributes:
        model_name (str): Ollama model identifier.
        model_kwargs (dict): Keyword arguments for model initialization.
        encode_kwargs (dict): Keyword arguments for encoding.
        embeddings (OllamaEmbeddings): Underlying LangChain embeddings instance.
        logger (logging.Logger): Logger instance for this class.

    Class Attributes:
        _instance (EmbeddingModel): Singleton instance.
        _lock (threading.Lock): Thread lock for singleton initialization.

    Example:
        >>> # First call initializes the model
        >>> embedding_model = EmbeddingModel.get_instance()
        >>> embeddings = embedding_model.embed_query("What is AI?")
        >>> print(f"Query embedding dimension: {len(embeddings)}")
    """

    _instance: Optional["EmbeddingModel"] = None
    _lock = threading.Lock()

    # Default model configuration
    DEFAULT_MODEL_NAME = settings.EMBEDDING_MODEL
    DEFAULT_MODEL_KWARGS = {}
    DEFAULT_ENCODE_KWARGS = {}

    def __new__(cls) -> "EmbeddingModel":
        """
        Implement singleton pattern with thread safety.

        Returns:
            EmbeddingModel: Singleton instance of EmbeddingModel.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        model_kwargs: Optional[dict] = None,
        encode_kwargs: Optional[dict] = None,
    ) -> None:
        """
        Initialize the EmbeddingModel.

        Due to singleton pattern, this is only called once. Subsequent instantiations
        return the same instance without re-running initialization.

        Args:
            model_name (str): Ollama model identifier. Defaults to settings.EMBEDDING_MODEL.
            model_kwargs (Optional[dict]): Keyword arguments for model initialization.
                Defaults to DEFAULT_MODEL_KWARGS.
            encode_kwargs (Optional[dict]): Keyword arguments for encoding.
                Defaults to DEFAULT_ENCODE_KWARGS.

        Raises:
            ModelLoadError: If the embedding model fails to load.

        Example:
            >>> model = EmbeddingModel()
            >>> # Or with custom configuration
            >>> model = EmbeddingModel(
            ...     model_name="sentence-transformers/all-mpnet-base-v2",
            ...     model_kwargs={"device": "cuda"}
            ... )
        """
        # Skip initialization if already initialized (singleton)
        if hasattr(self, "_initialized"):
            return

        self.logger = logger
        self.model_name = model_name
        self.model_kwargs = model_kwargs or self.DEFAULT_MODEL_KWARGS.copy()
        self.encode_kwargs = encode_kwargs or self.DEFAULT_ENCODE_KWARGS.copy()

        try:
            self.logger.info(f"Loading embedding model: {self.model_name}")

            self.embeddings = OllamaEmbeddings(
                base_url=settings.OLLAMA_BASE_URL,
                model=self.model_name,
                **self.model_kwargs,
            )

            # Get embedding dimension for validation
            test_embedding = self.embeddings.embed_query("test")
            self.embedding_dimension = len(test_embedding)

            self._initialized = True

            self.logger.info(
                f"Embedding model loaded successfully. "
                f"Model: {self.model_name}, Dimension: {self.embedding_dimension}"
            )

        except Exception as e:
            error_msg = (
                f"Failed to load embedding model {self.model_name}: "
                f"{type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise ModelLoadError(error_msg) from e

    @classmethod
    def get_instance(
        cls,
        model_name: str = DEFAULT_MODEL_NAME,
        model_kwargs: Optional[dict] = None,
        encode_kwargs: Optional[dict] = None,
    ) -> "EmbeddingModel":
        """
        Get the singleton instance of EmbeddingModel.

        This is the recommended way to access the embedding model throughout
        the application to ensure only one model is loaded.

        Args:
            model_name (str): Ollama model identifier.
            model_kwargs (Optional[dict]): Keyword arguments for model initialization.
            encode_kwargs (Optional[dict]): Keyword arguments for encoding.

        Returns:
            EmbeddingModel: Singleton instance.

        Example:
            >>> model = EmbeddingModel.get_instance()
            >>> embeddings = model.embed_query("test query")
        """
        instance = cls(
            model_name=model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs,
        )
        return instance

    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a query string.

        Generates a single embedding vector for a query. Optimized for single
        query processing with consistent behavior.

        Args:
            query (str): The query text to embed.

        Returns:
            List[float]: The embedding vector as a list of floats.

        Raises:
            InvalidInputError: If the query is empty or invalid.
            EmbeddingGenerationError: If embedding generation fails.

        Example:
            >>> model = EmbeddingModel.get_instance()
            >>> embedding = model.embed_query("What is artificial intelligence?")
            >>> print(f"Embedding dimension: {len(embedding)}")
        """
        try:
            if not query or not isinstance(query, str):
                raise InvalidInputError(
                    f"Query must be a non-empty string, got {type(query).__name__}"
                )

            if not query.strip():
                raise InvalidInputError("Query cannot be empty or whitespace-only")

            self.logger.debug(f"Generating embedding for query: {query[:100]}...")

            embedding = self.embeddings.embed_query(query)

            if not isinstance(embedding, list) or len(embedding) == 0:
                raise EmbeddingGenerationError(
                    "Generated embedding is empty or invalid"
                )

            self.logger.debug(
                f"Query embedding generated successfully. Dimension: {len(embedding)}"
            )
            return embedding

        except InvalidInputError:
            raise

        except Exception as e:
            error_msg = (
                f"Error generating query embedding: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise EmbeddingGenerationError(error_msg) from e

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of document texts.

        Generates embedding vectors for multiple documents. Optimized for batch
        processing with vectorized operations.

        Args:
            documents (List[str]): List of document texts to embed.

        Returns:
            List[List[float]]: List of embedding vectors, one per document.

        Raises:
            InvalidInputError: If documents list is empty or contains invalid items.
            EmbeddingGenerationError: If embedding generation fails.

        Example:
            >>> model = EmbeddingModel.get_instance()
            >>> texts = ["Document 1 content...", "Document 2 content..."]
            >>> embeddings = model.embed_documents(texts)
            >>> print(f"Generated {len(embeddings)} embeddings")
        """
        try:
            if not documents or not isinstance(documents, list):
                raise InvalidInputError(
                    f"Documents must be a non-empty list, got {type(documents).__name__}"
                )

            # Validate all items are strings
            for i, doc in enumerate(documents):
                if not isinstance(doc, str):
                    raise InvalidInputError(
                        f"Document {i} is not a string, got {type(doc).__name__}"
                    )

                if not doc.strip():
                    raise InvalidInputError(
                        f"Document {i} is empty or whitespace-only"
                    )

            self.logger.info(
                f"Generating embeddings for {len(documents)} documents"
            )

            embeddings = self.embeddings.embed_documents(documents)

            if not embeddings or len(embeddings) != len(documents):
                raise EmbeddingGenerationError(
                    f"Generated {len(embeddings)} embeddings for {len(documents)} documents"
                )

            self.logger.info(
                f"Successfully generated {len(embeddings)} document embeddings. "
                f"Dimension: {len(embeddings[0]) if embeddings else 0}"
            )
            return embeddings

        except InvalidInputError:
            raise

        except Exception as e:
            error_msg = (
                f"Error generating document embeddings: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise EmbeddingGenerationError(error_msg) from e

    def embed_langchain_documents(
        self, documents: List[Document]
    ) -> List[Document]:
        """
        Embed LangChain Document objects and attach embeddings as metadata.

        Generates embeddings for LangChain Document objects and stores the
        embedding vectors in the document metadata under the 'embedding' key.

        Args:
            documents (List[Document]): List of LangChain Document objects.

        Returns:
            List[Document]: Same documents with embeddings attached to metadata.

        Raises:
            InvalidInputError: If documents list is empty or invalid.
            EmbeddingGenerationError: If embedding generation fails.

        Example:
            >>> model = EmbeddingModel.get_instance()
            >>> docs = loader.load()  # Load documents
            >>> embedded_docs = model.embed_langchain_documents(docs)
            >>> # Each doc now has doc.metadata['embedding']
        """
        try:
            if not documents or not isinstance(documents, list):
                raise InvalidInputError(
                    "Documents must be a non-empty list of LangChain Document objects"
                )

            # Extract text content from documents
            texts = [doc.page_content for doc in documents]

            # Validate all texts are valid
            for i, text in enumerate(texts):
                if not isinstance(text, str) or not text.strip():
                    raise InvalidInputError(
                        f"Document {i} has invalid or empty content"
                    )

            self.logger.info(
                f"Generating embeddings for {len(documents)} LangChain documents"
            )

            # Generate embeddings
            embeddings = self.embed_documents(texts)

            # Attach embeddings to document metadata
            for doc, embedding in zip(documents, embeddings):
                doc.metadata["embedding"] = embedding
                doc.metadata["embedding_model"] = self.model_name
                doc.metadata["embedding_dimension"] = self.embedding_dimension

            self.logger.info(
                f"Successfully embedded {len(documents)} LangChain documents"
            )
            return documents

        except InvalidInputError:
            raise

        except Exception as e:
            error_msg = (
                f"Error embedding LangChain documents: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise EmbeddingGenerationError(error_msg) from e

    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of generated embeddings.

        Returns the size of embedding vectors produced by this model.
        Useful for validation and vector database configuration.

        Returns:
            int: The embedding dimension.

        Example:
            >>> model = EmbeddingModel.get_instance()
            >>> dim = model.get_embedding_dimension()
            >>> print(f"Embedding dimension: {dim}")
        """
        return self.embedding_dimension

    def get_model_info(self) -> dict:
        """
        Get information about the current embedding model.

        Returns a dictionary containing model configuration and metadata.

        Returns:
            dict: Dictionary with keys:
                - model_name: Ollama model identifier
                - embedding_dimension: Size of embedding vectors
                - model_kwargs: Model initialization parameters
                - encode_kwargs: Encoding parameters

        Example:
            >>> model = EmbeddingModel.get_instance()
            >>> info = model.get_model_info()
            >>> print(f"Using model: {info['model_name']}")
        """
        return {
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dimension,
            "model_kwargs": self.model_kwargs,
            "encode_kwargs": self.encode_kwargs,
        }

    @classmethod
    def reset_singleton(cls) -> None:
        """
        Reset the singleton instance (for testing purposes).

        Clears the singleton instance to allow creating a new one with
        different configuration. Use with caution in production.

        Example:
            >>> EmbeddingModel.reset_singleton()
            >>> model = EmbeddingModel(model_name="different-model")
        """
        with cls._lock:
            cls._instance = None
        logger.info("EmbeddingModel singleton reset")

    def __repr__(self) -> str:
        """Return string representation of the EmbeddingModel instance."""
        return (
            f"EmbeddingModel(model_name='{self.model_name}', "
            f"dimension={self.embedding_dimension})"
        )

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return (
            f"EmbeddingModel using {self.model_name} "
            f"({self.embedding_dimension}-dimensional embeddings)"
        )


def get_embedding_model() -> EmbeddingModel:
    """
    Convenience function to get the embedding model singleton.

    Simplifies access to the embedding model throughout the application.

    Returns:
        EmbeddingModel: The singleton embedding model instance.

    Example:
        >>> model = get_embedding_model()
        >>> embeddings = model.embed_query("test query")
    """
    return EmbeddingModel.get_instance()


def embed_text(text: str) -> List[float]:
    """
    Convenience function to embed a single text string.

    Args:
        text (str): Text to embed.

    Returns:
        List[float]: Embedding vector.

    Raises:
        InvalidInputError: If text is empty.
        EmbeddingGenerationError: If embedding fails.

    Example:
        >>> embedding = embed_text("Hello, world!")
        >>> print(f"Embedding dimension: {len(embedding)}")
    """
    model = EmbeddingModel.get_instance()
    return model.embed_query(text)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Convenience function to embed multiple text strings.

    Args:
        texts (List[str]): List of texts to embed.

    Returns:
        List[List[float]]: List of embedding vectors.

    Raises:
        InvalidInputError: If texts list is empty.
        EmbeddingGenerationError: If embedding fails.

    Example:
        >>> texts = ["Hello", "World"]
        >>> embeddings = embed_texts(texts)
        >>> print(f"Generated {len(embeddings)} embeddings")
    """
    model = EmbeddingModel.get_instance()
    return model.embed_documents(texts)
