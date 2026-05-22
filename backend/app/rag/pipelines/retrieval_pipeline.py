"""
Retrieval-Augmented Generation (RAG) Pipeline Module

This module provides a complete orchestration layer for RAG systems, coordinating
document retrieval, prompt engineering, LLM inference, and response generation.
It handles the entire flow from user query to final response with citations.

Author: RAG System
Version: 1.0.0
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Base exception for pipeline errors."""

    pass


class ComponentError(PipelineError):
    """Raised when a pipeline component fails."""

    pass


class QueryProcessingError(PipelineError):
    """Raised when query processing fails."""

    pass


class RetrievalError(PipelineError):
    """Raised when document retrieval fails."""

    pass


class GenerationError(PipelineError):
    """Raised when LLM generation fails."""

    pass


class InvalidInputError(PipelineError):
    """Raised when input parameters are invalid."""

    pass


class RAGResponse:
    """
    Data class for RAG pipeline responses.

    Encapsulates the response data including answer, sources, and metadata.

    Attributes:
        answer (str): The generated answer.
        sources (List[Dict[str, Any]]): List of source documents with metadata.
        query (str): Original user query.
        retrieval_count (int): Number of documents retrieved.
        generation_time_ms (float): Time taken to generate response.
        metadata (Dict[str, Any]): Additional metadata.
    """

    def __init__(
        self,
        answer: str,
        sources: List[Dict[str, Any]],
        query: str,
        retrieval_count: int,
        generation_time_ms: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize RAG response."""
        self.answer = answer
        self.sources = sources
        self.query = query
        self.retrieval_count = retrieval_count
        self.generation_time_ms = generation_time_ms
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary format."""
        return {
            "answer": self.answer,
            "sources": self.sources,
            "query": self.query,
            "retrieval_count": self.retrieval_count,
            "generation_time_ms": self.generation_time_ms,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"RAGResponse(query='{self.query[:50]}...', sources={len(self.sources)}, "
            f"generation_time={self.generation_time_ms:.2f}ms)"
        )


class RetrievalPipeline:
    """
    Production-grade Retrieval-Augmented Generation (RAG) pipeline.

    This class orchestrates the complete RAG workflow, coordinating document
    retrieval, prompt engineering, LLM inference, and response formatting.
    It implements a modular architecture for easy component substitution.

    Attributes:
        retriever: Document retriever (semantic or hybrid).
        llm_client: LLM client for text generation.
        logger (logging.Logger): Logger instance.

    Example:
        >>> from app.rag.retrievers import SemanticRetriever
        >>> from app.rag.llm import OllamaClient
        >>> from app.rag.vectorstore import ChromaManager
        >>>
        >>> vector_store = ChromaManager()
        >>> retriever = SemanticRetriever(vector_store=vector_store)
        >>> llm = OllamaClient()
        >>>
        >>> pipeline = RetrievalPipeline(retriever=retriever, llm_client=llm)
        >>> response = pipeline.generate("What is machine learning?")
        >>> print(response.answer)
    """

    def __init__(
        self,
        retriever: Any,
        llm_client: Any,
        top_k: int = 3,
        system_prompt: Optional[str] = None,
    ) -> None:
        """
        Initialize the RAG pipeline.

        Args:
            retriever: Document retriever component.
            llm_client: LLM client for generation.
            top_k (int): Number of documents to retrieve. Defaults to 3.
            system_prompt (Optional[str]): Custom system prompt. If None, uses default.

        Raises:
            ComponentError: If components are invalid.
            InvalidInputError: If configuration is invalid.

        Example:
            >>> pipeline = RetrievalPipeline(
            ...     retriever=retriever,
            ...     llm_client=llm,
            ...     top_k=5
            ... )
        """
        self.logger = logger

        try:
            if not retriever:
                raise ComponentError("Retriever component cannot be None")

            if not llm_client:
                raise ComponentError("LLM client component cannot be None")

            if not isinstance(top_k, int) or top_k <= 0:
                raise InvalidInputError(f"top_k must be a positive integer, got {top_k}")

            self.retriever = retriever
            self.llm_client = llm_client
            self.top_k = top_k

            # Set system prompt
            self.system_prompt = (
                system_prompt
                or self._get_default_system_prompt()
            )

            self.logger.info(
                f"RAG pipeline initialized with top_k={self.top_k}"
            )

        except (ComponentError, InvalidInputError):
            raise

        except Exception as e:
            error_msg = (
                f"Error initializing RAG pipeline: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise ComponentError(error_msg) from e

    @staticmethod
    def _get_default_system_prompt() -> str:
        """Get default system prompt for RAG."""
        return (
            "You are a helpful AI assistant that answers questions based on provided context. "
            "Answer ONLY using the information provided in the context. "
            "If the context does not contain information to answer the question, say 'I don't have information about that.' "
            "Do not make up or hallucinate information. "
            "Be concise and clear in your responses."
        )

    @staticmethod
    def _validate_query(query: str) -> None:
        """
        Validate query input.

        Args:
            query (str): Query to validate.

        Raises:
            InvalidInputError: If query is invalid.
        """
        if not query or not isinstance(query, str):
            raise InvalidInputError(
                f"Query must be a non-empty string, got {type(query).__name__}"
            )

        if not query.strip():
            raise InvalidInputError("Query cannot be empty or whitespace-only")

    def _retrieve_documents(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[Tuple[Document, float]]:
        """
        Retrieve relevant documents for a query.

        Args:
            query (str): User query.
            top_k (Optional[int]): Number of documents to retrieve.

        Returns:
            List[Tuple[Document, float]]: Retrieved documents with scores.

        Raises:
            RetrievalError: If retrieval fails.
        """
        try:
            retrieve_k = top_k if top_k is not None else self.top_k

            self.logger.debug(f"Retrieving {retrieve_k} documents for query")

            results = self.retriever.retrieve(query, top_k=retrieve_k)

            if not results:
                self.logger.warning("No documents retrieved")
                return []

            self.logger.info(f"Retrieved {len(results)} documents")
            return results

        except Exception as e:
            error_msg = (
                f"Error retrieving documents: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise RetrievalError(error_msg) from e

    def _build_context(
        self,
        documents: List[Tuple[Document, float]],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Build context string from retrieved documents.

        Formats retrieved documents into a context block and extracts source
        metadata for citation purposes.

        Args:
            documents (List[Tuple[Document, float]]): Retrieved documents with scores.

        Returns:
            Tuple[str, List[Dict[str, Any]]]: Context string and source metadata.

        Example:
            >>> context, sources = pipeline._build_context(documents)
            >>> # context: "Document 1: ...\nDocument 2: ..."
            >>> # sources: [{"source": "...", "page": ...}, ...]
        """
        context_parts = []
        sources = []

        for idx, (doc, score) in enumerate(documents, 1):
            # Add document to context
            context_parts.append(f"Document {idx}:\n{doc.page_content}")

            # Extract source metadata
            source_info = {
                "document_index": idx,
                "similarity_score": round(score, 4),
                "metadata": doc.metadata,
            }

            # Extract standard metadata fields if available
            if "source" in doc.metadata:
                source_info["source"] = doc.metadata["source"]
            if "page" in doc.metadata:
                source_info["page"] = doc.metadata["page"]
            if "file_name" in doc.metadata:
                source_info["file_name"] = doc.metadata["file_name"]

            sources.append(source_info)

        context = "\n\n".join(context_parts)
        return context, sources

    def _build_prompt(
        self,
        query: str,
        context: str,
    ) -> str:
        """
        Build the complete prompt for LLM.

        Combines context, question, and instructions into a structured prompt
        designed to minimize hallucinations.

        Args:
            query (str): User query.
            context (str): Retrieved context.

        Returns:
            str: Complete prompt for LLM.
        """
        prompt = f"""Based on the provided context, answer the following question.

CONTEXT:
{context}

QUESTION:
{query}

ANSWER:
Please provide a direct answer based ONLY on the information in the context above.
If the context does not contain relevant information, respond with "I don't have information about that."
"""
        return prompt

    def _generate_response(
        self,
        prompt: str,
    ) -> str:
        """
        Generate response using LLM.

        Args:
            prompt (str): Complete prompt for LLM.

        Returns:
            str: Generated response.

        Raises:
            GenerationError: If generation fails.
        """
        try:
            self.logger.debug("Sending prompt to LLM for generation")

            response = self.llm_client.generate(
                prompt=prompt,
                system=self.system_prompt,
            )

            if not response or not isinstance(response, str):
                raise GenerationError("Invalid response from LLM")

            self.logger.debug(f"Generated response: {len(response)} characters")
            return response

        except GenerationError:
            raise

        except Exception as e:
            error_msg = (
                f"Error generating response: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise GenerationError(error_msg) from e

    def generate(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> RAGResponse:
        """
        Generate RAG response for a user query.

        Orchestrates the complete RAG pipeline: retrieves relevant documents,
        builds context, generates response from LLM, and formats output with
        citations.

        Args:
            query (str): User query.
            top_k (Optional[int]): Override default number of documents.

        Returns:
            RAGResponse: Structured response with answer and sources.

        Raises:
            QueryProcessingError: If query processing fails.
            RetrievalError: If retrieval fails.
            GenerationError: If generation fails.

        Example:
            >>> response = pipeline.generate("What is machine learning?")
            >>> print(f"Answer: {response.answer}")
            >>> print(f"Sources: {len(response.sources)}")
            >>> print(response.to_dict())
        """
        import time

        start_time = time.time()

        try:
            self._validate_query(query)

            self.logger.info(f"Processing query: {query[:100]}...")

            # Step 1: Retrieve relevant documents
            retrieved_docs = self._retrieve_documents(query, top_k)

            if not retrieved_docs:
                self.logger.warning("No documents retrieved for query")
                # Generate response without context
                prompt = f"Question: {query}\n\nNote: No relevant context found. Provide a general answer if possible."
                answer = self._generate_response(prompt)

                elapsed_time = (time.time() - start_time) * 1000
                return RAGResponse(
                    answer=answer,
                    sources=[],
                    query=query,
                    retrieval_count=0,
                    generation_time_ms=elapsed_time,
                    metadata={"no_context": True},
                )

            # Step 2: Build context from retrieved documents
            context, sources = self._build_context(retrieved_docs)

            # Step 3: Build complete prompt
            prompt = self._build_prompt(query, context)

            # Step 4: Generate response using LLM
            answer = self._generate_response(prompt)

            # Step 5: Format and return response
            elapsed_time = (time.time() - start_time) * 1000

            response = RAGResponse(
                answer=answer,
                sources=sources,
                query=query,
                retrieval_count=len(retrieved_docs),
                generation_time_ms=elapsed_time,
            )

            self.logger.info(
                f"Query processed successfully. "
                f"Time: {elapsed_time:.2f}ms, Sources: {len(sources)}"
            )

            return response

        except QueryProcessingError:
            raise

        except RetrievalError:
            raise

        except GenerationError:
            raise

        except Exception as e:
            error_msg = (
                f"Error processing query: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise QueryProcessingError(error_msg) from e

    def batch_generate(
        self,
        queries: List[str],
        top_k: Optional[int] = None,
    ) -> List[RAGResponse]:
        """
        Generate responses for multiple queries in batch.

        Processes multiple queries sequentially and returns all responses.
        Useful for bulk query processing.

        Args:
            queries (List[str]): List of queries.
            top_k (Optional[int]): Override default number of documents.

        Returns:
            List[RAGResponse]: List of responses.

        Example:
            >>> queries = ["What is AI?", "Define machine learning"]
            >>> responses = pipeline.batch_generate(queries)
            >>> for response in responses:
            ...     print(f"Q: {response.query}")
            ...     print(f"A: {response.answer}\n")
        """
        try:
            if not queries or not isinstance(queries, list):
                raise InvalidInputError("Queries must be a non-empty list")

            self.logger.info(f"Batch processing {len(queries)} queries")

            responses = []
            for query in queries:
                try:
                    response = self.generate(query, top_k)
                    responses.append(response)

                except Exception as e:
                    self.logger.error(f"Error processing query '{query}': {str(e)}")
                    # Continue with next query
                    continue

            self.logger.info(f"Batch processing complete. Processed {len(responses)} queries")
            return responses

        except InvalidInputError:
            raise

        except Exception as e:
            error_msg = (
                f"Error in batch generation: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise PipelineError(error_msg) from e

    def set_system_prompt(self, prompt: str) -> None:
        """
        Update the system prompt used for generation.

        Args:
            prompt (str): New system prompt.

        Raises:
            InvalidInputError: If prompt is invalid.

        Example:
            >>> pipeline.set_system_prompt("You are a technical expert...")
        """
        if not prompt or not isinstance(prompt, str):
            raise InvalidInputError("System prompt must be a non-empty string")

        self.system_prompt = prompt
        self.logger.info("System prompt updated")

    def set_top_k(self, top_k: int) -> None:
        """
        Update the default number of documents to retrieve.

        Args:
            top_k (int): New top_k value.

        Raises:
            InvalidInputError: If top_k is invalid.

        Example:
            >>> pipeline.set_top_k(5)
        """
        if not isinstance(top_k, int) or top_k <= 0:
            raise InvalidInputError(f"top_k must be a positive integer, got {top_k}")

        self.top_k = top_k
        self.logger.info(f"Default top_k updated to {top_k}")

    def get_pipeline_info(self) -> Dict[str, Any]:
        """
        Get information about the current pipeline configuration.

        Returns:
            Dict[str, Any]: Pipeline configuration and component info.

        Example:
            >>> info = pipeline.get_pipeline_info()
            >>> print(f"Default top_k: {info['top_k']}")
        """
        info = {
            "top_k": self.top_k,
            "system_prompt_length": len(self.system_prompt),
        }

        # Add component info if available
        if hasattr(self.retriever, "get_retriever_info"):
            info["retriever"] = self.retriever.get_retriever_info()

        if hasattr(self.llm_client, "get_client_info"):
            info["llm_client"] = self.llm_client.get_client_info()

        return info

    def __repr__(self) -> str:
        """Return string representation."""
        return f"RetrievalPipeline(top_k={self.top_k})"

    def __str__(self) -> str:
        """Return human-readable representation."""
        return f"RAG Pipeline with top_k={self.top_k}"


def create_rag_pipeline(
    retriever: Any,
    llm_client: Any,
    top_k: int = 3,
    system_prompt: Optional[str] = None,
) -> RetrievalPipeline:
    """
    Convenience function to create a RAG pipeline instance.

    Args:
        retriever: Document retriever component.
        llm_client: LLM client for generation.
        top_k (int): Number of documents to retrieve. Defaults to 3.
        system_prompt (Optional[str]): Custom system prompt.

    Returns:
        RetrievalPipeline: Initialized pipeline.

    Raises:
        ComponentError: If components are invalid.

    Example:
        >>> from app.rag.retrievers import SemanticRetriever
        >>> from app.rag.llm import OllamaClient
        >>> from app.rag.vectorstore import ChromaManager
        >>>
        >>> vector_store = ChromaManager()
        >>> retriever = SemanticRetriever(vector_store=vector_store)
        >>> llm = OllamaClient()
        >>>
        >>> pipeline = create_rag_pipeline(retriever, llm, top_k=5)
        >>> response = pipeline.generate("What is AI?")
    """
    return RetrievalPipeline(
        retriever=retriever,
        llm_client=llm_client,
        top_k=top_k,
        system_prompt=system_prompt,
    )
