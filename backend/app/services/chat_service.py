"""
Chat service for grounded RAG question answering.

The service coordinates semantic retrieval, prompt construction, Ollama
generation, and source formatting for FastAPI chat endpoints.
"""

import logging
import math
import time
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from langchain_core.documents import Document

from app.core.config import settings
from app.rag.embeddings import EmbeddingError
from app.rag.embeddings import EmbeddingModel as EmbeddingManager
from app.rag.llm import (
    OllamaClient,
    OllamaConnectionError,
    OllamaError,
    OllamaGenerationError,
    OllamaTimeoutError,
)
from app.rag.pipelines import RetrievalPipeline
from app.rag.retrievers import RetrieverError, SemanticRetriever
from app.rag.vectorstore import ChromaDBError, ChromaManager, FAISSManager, FAISSError
from app.schemas.chat_schema import ChatResponse, RetrievalDebugItem, SourceResponse


logger = logging.getLogger(__name__)


class ChatServiceError(Exception):
    """Base exception for chat service failures."""


class ChatValidationError(ChatServiceError):
    """Raised when chat input or output validation fails."""


class ChatRetrievalError(ChatServiceError):
    """Raised when semantic retrieval fails."""


class ChatGenerationError(ChatServiceError):
    """Raised when LLM generation fails."""


@dataclass(frozen=True)
class RetrievedContext:
    """Retrieved documents and formatted context for generation."""

    query: str
    results: List[Tuple[Document, float]]
    context: str
    sources: List[SourceResponse]


class NativeChromaSearchAdapter:
    """Adapter exposing native chromadb through SemanticRetriever's search shape."""

    def __init__(
        self,
        persist_dir: Path,
        collection_name: str,
        embedding_manager: EmbeddingManager,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.embedding_manager = embedding_manager
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_collection(collection_name)

    def search(
        self,
        query: str,
        k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        """Return retrieved documents with relevance-like scores."""
        query_embedding = self.embedding_manager.embed_query(query)
        response = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=metadata_filter,
            include=["documents", "metadatas", "distances"],
        )

        documents = response.get("documents", [[]])[0]
        metadatas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]

        results: List[Tuple[Document, float]] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
            score = 1.0 / (1.0 + float(distance))
            results.append((Document(page_content=text, metadata=metadata or {}), score))

        return results


class ChatService:
    """
    Service responsible for RAG chat orchestration.

    The service is compatible with FastAPI async routes: call `ask_question`
    directly from a threadpool or wrap it in your route's async orchestration.
    """

    # RAG mode presets: top_k and temperature overrides
    RAG_MODE_PRESETS = {
        "precise":  {"top_k": 3,  "temperature": 0.1},
        "balanced": {"top_k": 3,  "temperature": 0.3},
        "creative": {"top_k": 8,  "temperature": 0.8},
    }

    # Response-style system prompt addendum
    STYLE_ADDENDUM = {
        "professional":       "Respond in a clear, professional tone suitable for enterprise use.",
        "concise":            "Be extremely concise. Prefer bullet points and short sentences.",
        "beginner_friendly":  "Explain concepts simply, avoid jargon, and use analogies where helpful.",
        "research":           "Provide detailed analysis, include caveats, and cite evidence thoroughly.",
        "technical":          "Use precise technical language and include implementation details when relevant.",
    }

    def __init__(
        self,
        chroma_persist_dir: Path = settings.CHROMA_PERSIST_DIR,
        faiss_index_dir: Path = settings.FAISS_INDEX_DIR,
        vector_db_type: str = settings.VECTOR_DB_TYPE,
        default_collection_name: str = settings.CHROMA_COLLECTION_NAME,
        default_top_k: int = settings.DEFAULT_TOP_K,
        ollama_base_url: str = settings.OLLAMA_BASE_URL,
        ollama_model: str = settings.OLLAMA_MODEL,
        request_timeout: int = settings.REQUEST_TIMEOUT,
    ) -> None:
        self.chroma_persist_dir = Path(chroma_persist_dir)
        self.faiss_index_dir = Path(faiss_index_dir)
        self.vector_db_type = vector_db_type.lower()
        self.default_collection_name = default_collection_name
        self.default_top_k = default_top_k
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model
        self.request_timeout = request_timeout
        self.logger = logger
        self._embedding_manager: Optional[EmbeddingManager] = None
        self._llm_client: Optional[OllamaClient] = None

        self.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self.faiss_index_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(
            "ChatService initialized. vector_db=%s default_collection=%s ollama_model=%s",
            self.vector_db_type,
            self.default_collection_name,
            self.ollama_model,
        )

    @property
    def embedding_manager(self) -> EmbeddingManager:
        """Lazily initialize the embedding manager."""
        if self._embedding_manager is None:
            self._embedding_manager = EmbeddingManager()
        return self._embedding_manager

    @property
    def llm_client(self) -> OllamaClient:
        """Lazily initialize the Ollama client (default temperature; overridden per-call)."""
        if self._llm_client is None:
            self._llm_client = OllamaClient(
                base_url=self.ollama_base_url,
                model_name=self.ollama_model,
                timeout=self.request_timeout,
                temperature=0.3,
                top_p=0.9,
                top_k=40,
            )
        return self._llm_client

    def retrieve_context(
        self,
        question: str,
        top_k: Optional[int] = None,
        collection_id: Optional[str] = None,
    ) -> RetrievedContext:
        """
        Retrieve relevant chunks and build citation-ready context.

        Args:
            question: User question.
            top_k: Optional retrieval count override.
            collection_id: Optional target vector collection.
        """
        try:
            normalized_question = self._validate_question(question)
            retrieve_k = self._resolve_top_k(top_k)
            target_collection = self._resolve_collection_id(collection_id)

            # Explicit query embedding validation; SemanticRetriever/vector store
            # will embed again for search depending on backend.
            query_embedding = self.embedding_manager.embed_query(normalized_question)
            self._validate_embedding(query_embedding)

            vector_store = self._create_vector_store(target_collection)
            retriever = SemanticRetriever(vector_store=vector_store, top_k=retrieve_k)
            results = retriever.retrieve(
                query=normalized_question,
                top_k=retrieve_k,
                metadata_filter=self._metadata_filter(collection_id),
            )

            self._validate_retrieval_results(results)
            context = self._format_context(results)
            sources = self._format_sources(results)

            self.logger.info(
                "Retrieved context. collection_id=%s top_k=%s results=%s",
                target_collection,
                retrieve_k,
                len(results),
            )
            return RetrievedContext(
                query=normalized_question,
                results=results,
                context=context,
                sources=sources,
            )

        except (ChatValidationError, ChatRetrievalError):
            raise
        except (EmbeddingError, RetrieverError, ChromaDBError) as exc:
            error_msg = f"Semantic retrieval failed: {exc}"
            self.logger.error(error_msg, exc_info=True)
            raise ChatRetrievalError(error_msg) from exc
        except Exception as exc:
            error_msg = f"Unexpected retrieval failure: {type(exc).__name__}: {exc}"
            self.logger.error(error_msg, exc_info=True)
            raise ChatRetrievalError(error_msg) from exc

    def build_prompt(self, question: str, retrieved_context: RetrievedContext) -> str:
        """
        Build a grounded RAG prompt with citation-friendly context sections.
        """
        normalized_question = self._validate_question(question)
        if not retrieved_context.context.strip():
            raise ChatValidationError("Retrieved context is empty")

        return f"""Answer the user question using ONLY the retrieved context below.

Rules:
- Do not use outside knowledge.
- If the context is insufficient, say: "The retrieved context does not contain enough information."
- Keep the answer concise and factual.
- When possible, mention source numbers like [1], [2].

Retrieved context:
{retrieved_context.context}

User question:
{normalized_question}

Grounded answer:
"""

    def generate_answer(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        response_style: Optional[str] = None,
    ) -> str:
        """
        Generate a grounded answer with Ollama.

        Args:
            prompt: The grounded RAG prompt.
            temperature: Per-request LLM temperature (from user settings).
            response_style: Style tag used to build the system prompt.
        """
        try:
            if not prompt or not prompt.strip():
                raise ChatValidationError("Prompt cannot be empty")

            # Build dynamic system prompt
            base_system = (
                "You are a grounded enterprise RAG assistant. Answer strictly from the "
                "retrieved context. If the context is insufficient, say that the context "
                "does not contain enough information. Do not invent facts. "
                "Cite source numbers like [1], [2] when useful."
            )
            style_addendum = self.STYLE_ADDENDUM.get(response_style or "professional", "")
            system_prompt = f"{base_system} {style_addendum}".strip()

            # Resolve temperature
            effective_temperature = temperature if temperature is not None else 0.3

            answer = self.llm_client.generate(
                prompt=prompt,
                system=system_prompt,
                temperature=effective_temperature,
            )

            if not answer or not answer.strip():
                raise ChatGenerationError("Ollama returned an empty answer")

            return answer.strip()

        except ChatValidationError:
            raise
        except OllamaTimeoutError as exc:
            error_msg = f"Ollama request timed out: {exc}"
            self.logger.error(error_msg)
            raise ChatGenerationError(error_msg) from exc
        except (OllamaConnectionError, OllamaGenerationError, OllamaError) as exc:
            error_msg = f"Ollama generation failed: {exc}"
            self.logger.error(error_msg, exc_info=True)
            raise ChatGenerationError(error_msg) from exc
        except Exception as exc:
            error_msg = f"Unexpected generation failure: {type(exc).__name__}: {exc}"
            self.logger.error(error_msg, exc_info=True)
            raise ChatGenerationError(error_msg) from exc

    def ask_question(
        self,
        question: str,
        top_k: Optional[int] = None,
        collection_id: Optional[str] = None,
        temperature: Optional[float] = None,
        rag_mode: Optional[str] = None,
        response_style: Optional[str] = None,
        show_sources: Optional[bool] = None,
        preferred_model: Optional[str] = None,
    ) -> ChatResponse:
        """
        Orchestrate retrieval, prompt building, generation, and source formatting.

        Phase 7: Checks Redis cache before expensive RAG pipeline.
        Cache key = chat:{collection}:{rag_mode}:{response_style}:{question_hash}
        Falls back silently if Redis is unavailable.
        """
        started_at = time.perf_counter()

        # ─── Apply RAG mode presets ────────────────────────────────────
        mode = (rag_mode or "balanced").lower()
        preset = self.RAG_MODE_PRESETS.get(mode, self.RAG_MODE_PRESETS["balanced"])

        # top_k: explicit > preset > default
        effective_top_k = top_k if top_k is not None else preset["top_k"]
        # temperature: explicit > preset
        effective_temperature = temperature if temperature is not None else preset["temperature"]

        effective_style = response_style or "professional"
        effective_collection = collection_id or self.default_collection_name

        self.logger.info(
            "ask_question: rag_mode=%s top_k=%s temperature=%.2f response_style=%s show_sources=%s",
            mode, effective_top_k, effective_temperature, effective_style, show_sources,
        )

        # ─── Phase 7: Redis cache check ───────────────────────────────
        try:
            from app.services.cache_service import chat_cache
            cached = chat_cache.get(
                effective_collection,
                question,
                mode,
                effective_style,
                temperature=effective_temperature,
                top_k=effective_top_k,
                show_sources=show_sources,
                preferred_model=preferred_model,
            )
            if cached:
                self.logger.info("Cache HIT — returning cached response. collection=%s", effective_collection)
                return ChatResponse(
                    answer=cached.get("answer", ""),
                    sources=cached.get("sources", []) if show_sources is not False else [],
                    retrieved_chunks=cached.get("retrieved_chunks", 0),
                    retrieval_debug=cached.get("retrieval_debug", []),
                    response_time=cached.get("response_time", 0.0),
                )
        except Exception as cache_exc:
            self.logger.debug("Cache check failed (non-critical): %s", cache_exc)

        try:
            retrieved_context = self.retrieve_context(
                question=question,
                top_k=effective_top_k,
                collection_id=collection_id,
            )

            # Short-circuit if no relevant chunks were retrieved
            if not retrieved_context.results:
                self.logger.info("No context retrieved. Short-circuiting with safe fallback.")
                return ChatResponse(
                    answer="The retrieved context does not contain enough information.",
                    sources=[],
                    retrieved_chunks=0,
                    retrieval_debug=[],
                    response_time=time.perf_counter() - started_at,
                )

            prompt = self.build_prompt(question, retrieved_context)

            # Instantiate RetrievalPipeline for compatibility and introspection
            RetrievalPipeline(
                retriever=SemanticRetriever(
                    vector_store=self._create_vector_store(
                        self._resolve_collection_id(collection_id)
                    ),
                    top_k=effective_top_k,
                ),
                llm_client=self.llm_client,
                top_k=effective_top_k,
                system_prompt=(
                    "You are a grounded enterprise RAG assistant. "
                    "Answer strictly from the retrieved context."
                ),
            )

            answer = self.generate_answer(
                prompt=prompt,
                temperature=effective_temperature,
                response_style=response_style,
            )
            elapsed = time.perf_counter() - started_at

            # Honour show_sources setting (default True)
            sources = retrieved_context.sources if (show_sources is not False) else []

            response = ChatResponse(
                answer=answer,
                sources=sources,
                retrieved_chunks=len(retrieved_context.results),
                retrieval_debug=self._format_retrieval_debug(retrieved_context.results),
                response_time=elapsed,
            )
            self._validate_chat_response_lenient(response, show_sources=show_sources)

            # ─── Phase 7: Store in Redis cache ────────────────────────
            try:
                from app.services.cache_service import chat_cache
                chat_cache.set(
                    effective_collection,
                    question,
                    mode,
                    effective_style,
                    {
                        "answer":           response.answer,
                        "sources":          [s.model_dump() for s in retrieved_context.sources],
                        "retrieved_chunks": response.retrieved_chunks,
                        "retrieval_debug":  [item.model_dump() for item in response.retrieval_debug],
                        "response_time":    elapsed,
                    },
                    temperature=effective_temperature,
                    top_k=effective_top_k,
                    show_sources=show_sources,
                    preferred_model=preferred_model,
                )
            except Exception as cache_set_exc:
                self.logger.debug("Cache SET failed (non-critical): %s", cache_set_exc)

            self.logger.info(
                "Chat request completed. collection_id=%s chunks=%s response_time=%.3fs",
                effective_collection,
                response.retrieved_chunks,
                elapsed,
            )
            return response

        except ChatServiceError:
            raise
        except Exception as exc:
            error_msg = f"Chat workflow failed: {type(exc).__name__}: {exc}"
            self.logger.error(error_msg, exc_info=True)
            raise ChatServiceError(error_msg) from exc

    def _create_vector_store(self, collection_id: str) -> Any:
        """Create a vector store compatible with SemanticRetriever."""
        if self.vector_db_type == "faiss":
            return self._create_faiss_vector_store(collection_id)
        else:
            return self._create_chromadb_vector_store(collection_id)

    def _create_chromadb_vector_store(self, collection_id: str) -> Any:
        """Create a ChromaDB vector store."""
        self.logger.debug(
            "Creating ChromaDB vector store. persist_dir=%s collection_id=%s",
            self.chroma_persist_dir,
            collection_id,
        )
        
        if find_spec("langchain_chroma") is not None:
            try:
                store = ChromaManager(
                    persist_dir=str(self.chroma_persist_dir),
                    collection_name=collection_id,
                    embedding_function=self.embedding_manager.embeddings,
                )
                self.logger.info(
                    "Using LangChain ChromaManager. collection=%s persist_dir=%s",
                    collection_id,
                    self.chroma_persist_dir,
                )
                return store
            except Exception as e:
                self.logger.error(
                    "Failed to create ChromaManager: %s. Attempting native adapter.",
                    e,
                    exc_info=True,
                )
                # Fall through to native adapter

        try:
            # List available collections for debugging
            debug_client = chromadb.PersistentClient(path=str(self.chroma_persist_dir))
            available_collections = [c.name for c in debug_client.list_collections()]
            self.logger.debug(
                "Available collections in %s: %s",
                self.chroma_persist_dir,
                available_collections,
            )

            # If the requested collection doesn't exist, auto-fallback to the
            # first available collection that actually has documents
            effective_collection_id = collection_id
            if collection_id not in available_collections and available_collections:
                effective_collection_id = available_collections[0]
                self.logger.warning(
                    "Collection '%s' not found. Auto-falling back to '%s'.",
                    collection_id,
                    effective_collection_id,
                )

            adapter = NativeChromaSearchAdapter(
                persist_dir=self.chroma_persist_dir,
                collection_name=effective_collection_id,
                embedding_manager=self.embedding_manager,
            )
            self.logger.info(
                "Using native ChromaDB adapter. collection=%s persist_dir=%s",
                effective_collection_id,
                self.chroma_persist_dir,
            )
            return adapter
        except chromadb.errors.NotFoundError as e:
            error_msg = (
                f"Collection '{collection_id}' not found at {self.chroma_persist_dir}. "
                f"Available collections: {available_collections}. "
                "Please upload documents to this collection first."
            )
            self.logger.error(error_msg)
            raise ChatRetrievalError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to create ChromaDB vector store: {type(e).__name__}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise ChatRetrievalError(error_msg) from e

    def _create_faiss_vector_store(self, collection_id: str) -> Any:
        """Create a FAISS vector store."""
        self.logger.debug(
            "Creating FAISS vector store. index_dir=%s collection_id=%s",
            self.faiss_index_dir,
            collection_id,
        )
        
        try:
            store = FAISSManager(
                index_dir=str(self.faiss_index_dir),
                collection_name=collection_id,
                embedding_function=self.embedding_manager.embeddings,
            )
            stats = store.get_collection_stats()
            self.logger.info(
                "Created FAISS vector store. collection=%s vectors=%s",
                collection_id,
                stats.get("vector_count", 0),
            )
            
            if stats.get("vector_count", 0) == 0:
                error_msg = (
                    f"Collection '{collection_id}' is empty at {self.faiss_index_dir}. "
                    "Please upload documents to this collection first."
                )
                self.logger.error(error_msg)
                raise ChatRetrievalError(error_msg)
            
            return store
        except FAISSError as e:
            error_msg = f"FAISS error: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise ChatRetrievalError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to create FAISS vector store: {type(e).__name__}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise ChatRetrievalError(error_msg) from e

    def _metadata_filter(self, collection_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Build an optional metadata filter for collection-scoped retrieval."""
        if not collection_id:
            return None
        return {"collection_id": self._resolve_collection_id(collection_id)}

    def _format_context(self, results: List[Tuple[Document, float]]) -> str:
        """Format retrieved chunks into citation-aware context blocks."""
        context_parts = []
        for index, (document, score) in enumerate(results, 1):
            metadata = document.metadata
            source_file = metadata.get("file_name") or metadata.get("source") or "unknown"
            page = metadata.get("page_number", metadata.get("page", "unknown"))
            chunk_id = metadata.get("chunk_id") or metadata.get("test_document_id")

            context_parts.append(
                "\n".join(
                    [
                        f"[{index}] Source: {source_file}",
                        f"Page: {page}",
                        f"Chunk ID: {chunk_id or 'unknown'}",
                        f"Relevance Score: {float(score):.4f}",
                        "Content:",
                        document.page_content.strip(),
                    ]
                )
            )

        return "\n\n".join(context_parts)

    def _format_sources(self, results: List[Tuple[Document, float]]) -> List[SourceResponse]:
        """Convert retrieved result metadata into API source citations."""
        sources: List[SourceResponse] = []
        for document, score in results:
            metadata = document.metadata
            sources.append(
                SourceResponse(
                    source_file=str(
                        metadata.get("file_name")
                        or metadata.get("source")
                        or "unknown"
                    ),
                    page_number=self._optional_int(
                        metadata.get("page_number", metadata.get("page"))
                    ),
                    chunk_id=self._optional_str(
                        metadata.get("chunk_id") or metadata.get("test_document_id")
                    ),
                    relevance_score=float(score),
                )
            )
        return sources

    def _format_retrieval_debug(
        self,
        results: List[Tuple[Document, float]],
    ) -> List[RetrievalDebugItem]:
        """Build compact retrieval diagnostics without affecting generation."""
        debug_items: List[RetrievalDebugItem] = []
        for index, (document, score) in enumerate(results):
            metadata = document.metadata or {}
            preview = " ".join(document.page_content.split())[:200]
            debug_items.append(
                RetrievalDebugItem(
                    score=float(score),
                    source=str(
                        metadata.get("file_name")
                        or metadata.get("source")
                        or metadata.get("uploaded_filename")
                        or "unknown"
                    ),
                    page=self._optional_int(
                        metadata.get("page_number", metadata.get("page"))
                    ),
                    chunk_id=self._optional_str(
                        metadata.get("chunk_id") or metadata.get("test_document_id")
                    ),
                    chunk_index=self._optional_int(
                        metadata.get("chunk_index", metadata.get("source_document_index", index))
                    ),
                    preview=preview,
                )
            )
        return debug_items

    @staticmethod
    def _validate_question(question: str) -> str:
        """Normalize and validate a question."""
        if not isinstance(question, str):
            raise ChatValidationError("question must be a string")

        normalized = question.strip()
        if len(normalized) < 3:
            raise ChatValidationError("question must be at least 3 characters long")
        return normalized

    def _resolve_top_k(self, top_k: Optional[int]) -> int:
        """Resolve and validate retrieval top_k."""
        resolved = top_k if top_k is not None else self.default_top_k
        if not isinstance(resolved, int) or resolved <= 0:
            raise ChatValidationError("top_k must be a positive integer")
        return resolved

    def _resolve_collection_id(self, collection_id: Optional[str]) -> str:
        """Resolve and validate collection ID."""
        resolved = (collection_id or self.default_collection_name).strip()
        if not resolved:
            raise ChatValidationError("collection_id cannot be empty")
        if not all(char.isalnum() or char in {"_", "-"} for char in resolved):
            raise ChatValidationError(
                "collection_id may only contain letters, numbers, underscores, and hyphens"
            )
        return resolved

    @staticmethod
    def _validate_embedding(embedding: List[float]) -> None:
        """Validate a query embedding."""
        if not embedding:
            raise ChatRetrievalError("Query embedding is empty")
        if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in embedding):
            raise ChatRetrievalError("Query embedding contains invalid values")

    @staticmethod
    def _validate_retrieval_results(results: List[Tuple[Document, float]]) -> None:
        """Validate retrieved chunks and metadata integrity."""
        if not results:
            return  # Empty results are now a valid state for graceful no-context handling


        required_metadata = {"source", "file_name"}
        for index, (document, score) in enumerate(results):
            if not document.page_content.strip():
                raise ChatRetrievalError(f"Retrieved chunk {index} is empty")
            if not isinstance(score, (int, float)) or not math.isfinite(float(score)):
                raise ChatRetrievalError(f"Retrieved chunk {index} has invalid score")
            if not required_metadata.intersection(document.metadata):
                raise ChatRetrievalError(f"Retrieved chunk {index} has no source metadata")

    @staticmethod
    def _validate_chat_response(response: ChatResponse) -> None:
        """Validate final API response (strict — sources required)."""
        if not response.answer.strip():
            raise ChatGenerationError("Generated answer is empty")
        if response.retrieved_chunks <= 0:
            raise ChatRetrievalError("No chunks were retrieved")
        if not response.sources:
            raise ChatRetrievalError("No source citations were produced")

    @staticmethod
    def _validate_chat_response_lenient(
        response: ChatResponse,
        show_sources: Optional[bool] = None,
    ) -> None:
        """Validate final API response allowing empty sources when show_sources is False."""
        if not response.answer.strip():
            raise ChatGenerationError("Generated answer is empty")
        if response.retrieved_chunks <= 0:
            raise ChatRetrievalError("No chunks were retrieved")
        # Only require sources when show_sources is not explicitly False
        if show_sources is not False and not response.sources:
            raise ChatRetrievalError("No source citations were produced")

    @staticmethod
    def _optional_int(value: Any) -> Optional[int]:
        """Convert a metadata value to optional int."""
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_str(value: Any) -> Optional[str]:
        """Convert a metadata value to optional string."""
        if value is None:
            return None
        text = str(value).strip()
        return text or None
