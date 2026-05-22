"""
Full end-to-end RAG pipeline integration test.

Validates:
PDF -> Chunking -> Embeddings -> ChromaDB -> Semantic Retrieval -> Qwen3 Generation

Usage:
    python backend/test_pipeline.py
"""

import logging
import math
import os
import shutil
import sys
import time
import warnings
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from langchain_core.documents import Document


os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
warnings.filterwarnings("ignore", message=".*HuggingFaceEmbeddings.*")
warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
warnings.filterwarnings("ignore", message="Warning: You are sending unauthenticated requests.*")

try:
    from langchain_core._api.deprecation import LangChainDeprecationWarning

    warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub.utils._http").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


PDF_PATH = Path(__file__).parent / "test_data" / "cia_notes.pdf"
KNOWN_FALLBACK_PDF = Path(__file__).parent / "test_data" / "CIA - 2 COMPLETE NOTES.pdf"
COLLECTION_NAME = "rag_full_pipeline_integration_test"
TOP_K = 3
MODEL_NAME = "qwen3:8b"
OLLAMA_TIMEOUT_SECONDS = 240
TEST_QUERIES = [
    "What is NLP?",
    "Explain YOLO in computer vision",
    "What are intelligent systems in healthcare?",
]


class NativeChromaSearchAdapter:
    """Test adapter exposing native chromadb through the ChromaManager search shape."""

    def __init__(self, persist_dir: Path, collection_name: str, embedding_manager: Any) -> None:
        import chromadb

        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_manager = embedding_manager
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_collection(collection_name)

    def search(
        self,
        query: str,
        k: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Document, float]]:
        """Search native ChromaDB and return SemanticRetriever-compatible results."""
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
            relevance_score = 1.0 / (1.0 + float(distance))
            results.append((Document(page_content=text, metadata=metadata or {}), relevance_score))

        return results


def setup_paths() -> None:
    """Add backend directory to Python path for app.* imports."""
    backend_dir = Path(__file__).parent
    sys.path.insert(0, str(backend_dir))
    logger.debug("Added to sys.path: %s", backend_dir)


def print_separator(title: str = "", width: int = 80) -> None:
    """Print a formatted separator line."""
    if title:
        padding = max((width - len(title) - 2) // 2, 0)
        print("=" * padding + f" {title} " + "=" * (width - padding - len(title) - 2))
    else:
        print("=" * width)


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print()
    print_separator(title)


def safe_console_text(value: Any) -> str:
    """Return text that can be printed safely on the active Windows console."""
    text = str(value)
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


def preview_text(text: str, max_length: int = 360) -> str:
    """Return a compact Windows-safe text preview."""
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return safe_console_text(normalized)
    return safe_console_text(normalized[:max_length].rstrip() + "... (truncated)")


def resolve_pdf_path() -> Path:
    """Resolve the required PDF path, with a clear fallback for the current workspace."""
    if PDF_PATH.exists():
        return PDF_PATH

    if KNOWN_FALLBACK_PDF.exists():
        print(f"[WARN] Requested PDF not found: {PDF_PATH}")
        print(f"[WARN] Using available CIA notes PDF instead: {KNOWN_FALLBACK_PDF}")
        return KNOWN_FALLBACK_PDF

    raise FileNotFoundError(f"Required PDF file not found: {PDF_PATH}")


def reset_test_persist_dir(persist_dir: Path) -> None:
    """Clear only this script's test persistence directory."""
    backend_dir = Path(__file__).parent.resolve()
    resolved_dir = persist_dir.resolve()

    if not str(resolved_dir).startswith(str(backend_dir)):
        raise ValueError(f"Refusing to clear path outside backend: {resolved_dir}")

    if resolved_dir.exists():
        shutil.rmtree(resolved_dir)

    resolved_dir.mkdir(parents=True, exist_ok=True)


def validate_extractable_text(documents: List[Any]) -> None:
    """Ensure loaded documents contain text before chunking."""
    if not documents:
        raise ValueError("No documents were loaded from the PDF.")

    if not any(getattr(document, "page_content", "").strip() for document in documents):
        raise ValueError(
            "Loaded PDF contains no extractable text. Use a PDF with a text layer "
            "or add OCR before testing the full RAG pipeline."
        )


def validate_chunks(chunks: List[Any]) -> None:
    """Ensure chunks are suitable for embedding and retrieval."""
    if not chunks:
        raise ValueError("Chunking produced zero chunks.")

    empty_indexes = [
        index
        for index, chunk in enumerate(chunks)
        if not getattr(chunk, "page_content", "").strip()
    ]
    if empty_indexes:
        raise ValueError(
            "Chunks with empty content found at indexes: "
            + ", ".join(str(index) for index in empty_indexes[:10])
        )


def is_numeric_vector(vector: Any) -> bool:
    """Return True when value is a non-empty sequence of finite numeric values."""
    if hasattr(vector, "tolist"):
        vector = vector.tolist()

    if not isinstance(vector, (list, tuple)) or not vector:
        return False

    for value in vector:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return False

    return True


def validate_embeddings(embeddings: List[List[float]], expected_count: int) -> int:
    """Validate embedding count, dimensions, and numeric values."""
    if not embeddings:
        raise ValueError("No embeddings were generated.")

    if len(embeddings) != expected_count:
        raise ValueError(f"Expected {expected_count} embeddings, got {len(embeddings)}.")

    vector_lengths = {len(embedding) for embedding in embeddings}
    if len(vector_lengths) != 1:
        raise ValueError(
            "Embedding vector lengths are inconsistent: "
            + ", ".join(str(length) for length in sorted(vector_lengths))
        )

    invalid_indexes = [
        index
        for index, embedding in enumerate(embeddings)
        if not is_numeric_vector(embedding)
    ]
    if invalid_indexes:
        raise ValueError(
            "Empty or non-numeric embeddings found at indexes: "
            + ", ".join(str(index) for index in invalid_indexes[:10])
        )

    return vector_lengths.pop()


def chunk_texts(chunks: Iterable[Any]) -> List[str]:
    """Extract chunk text content for embedding and storage."""
    return [chunk.page_content for chunk in chunks]


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Keep metadata values compatible with ChromaDB primitive metadata types."""
    sanitized: Dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[str(key)] = value
        else:
            sanitized[str(key)] = str(value)
    return sanitized


def build_chroma_payload(
    chunks: List[Any],
    embeddings: List[List[float]],
) -> Tuple[List[str], List[str], List[Dict[str, Any]], List[List[float]]]:
    """Build ids, documents, metadata, and embeddings for ChromaDB insertion."""
    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for index, chunk in enumerate(chunks):
        metadata = sanitize_metadata(chunk.metadata)
        metadata["test_document_id"] = f"chunk-{index:04d}"
        metadata["embedding_dimension"] = len(embeddings[index])
        metadata["has_embedding"] = True

        ids.append(f"chunk-{index:04d}")
        documents.append(chunk.page_content)
        metadatas.append(metadata)

    return ids, documents, metadatas, embeddings


def store_with_chromadb_client(
    persist_dir: Path,
    collection_name: str,
    chunks: List[Any],
    embeddings: List[List[float]],
) -> int:
    """Store chunks using native chromadb PersistentClient."""
    import chromadb

    client = chromadb.PersistentClient(path=str(persist_dir))

    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = client.create_collection(
        name=collection_name,
        metadata={"purpose": "rag_full_pipeline_integration_test"},
    )

    ids, documents, metadatas, vectors = build_chroma_payload(chunks, embeddings)
    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=vectors)

    stored_count = collection.count()
    persisted_client = chromadb.PersistentClient(path=str(persist_dir))
    persisted_count = persisted_client.get_collection(collection_name).count()

    if persisted_count != stored_count:
        raise ValueError(
            f"Persisted count {persisted_count} does not match stored count {stored_count}."
        )

    return stored_count


def create_vector_store(
    chroma_manager_class: Any,
    persist_dir: Path,
    collection_name: str,
    chunks: List[Any],
    embeddings: List[List[float]],
    embedding_manager: Any,
) -> Tuple[Any, int, str]:
    """Create and populate a vector store compatible with SemanticRetriever."""
    if find_spec("langchain_chroma") is None:
        print("[WARN] langchain_chroma is not installed; using native chromadb adapter")
        stored_count = store_with_chromadb_client(
            persist_dir=persist_dir,
            collection_name=collection_name,
            chunks=chunks,
            embeddings=embeddings,
        )
        return (
            NativeChromaSearchAdapter(
                persist_dir=persist_dir,
                collection_name=collection_name,
                embedding_manager=embedding_manager,
            ),
            stored_count,
            "chromadb.PersistentClient",
        )

    manager = chroma_manager_class(
        persist_dir=str(persist_dir),
        collection_name=collection_name,
        embedding_function=embedding_manager.embeddings,
    )
    manager.add_documents(chunks)
    manager.persist()
    stats = manager.get_collection_stats()
    return manager, int(stats.get("document_count", 0)), "ChromaManager"


def validate_retrieved_results(results: List[Tuple[Document, float]], top_k: int) -> None:
    """Validate retrieval count, content, score ordering, and metadata."""
    if not results:
        raise ValueError("Semantic retrieval returned zero chunks.")

    if len(results) > top_k:
        raise ValueError(f"Retrieved {len(results)} chunks, expected at most {top_k}.")

    required_metadata = {"source", "file_name", "page", "page_number"}
    previous_score: Optional[float] = None

    for index, (document, score) in enumerate(results):
        if not document.page_content.strip():
            raise ValueError(f"Retrieved chunk {index} has empty content.")

        if not isinstance(score, (int, float)) or not math.isfinite(float(score)):
            raise ValueError(f"Retrieved chunk {index} has invalid score: {score}")

        if previous_score is not None and score > previous_score:
            raise ValueError("Retrieved scores are not sorted in descending order.")
        previous_score = float(score)

        missing = sorted(required_metadata - set(document.metadata))
        if missing:
            raise ValueError(
                f"Retrieved chunk {index} metadata missing keys: " + ", ".join(missing)
            )


def validate_rag_response(response: Any, retrieved_results: List[Tuple[Document, float]]) -> None:
    """Validate generated answer, citations, and grounding surface."""
    if not response.answer or not response.answer.strip():
        raise ValueError("Generated answer is empty.")

    if not response.sources:
        raise ValueError("RAG response did not include source citations.")

    if response.retrieval_count != len(retrieved_results):
        raise ValueError(
            f"Response retrieval count {response.retrieval_count} does not match "
            f"retrieved result count {len(retrieved_results)}."
        )

    for index, source in enumerate(response.sources):
        if not source.get("metadata"):
            raise ValueError(f"Source citation {index} is missing metadata.")
        if "file_name" not in source and "source" not in source:
            raise ValueError(f"Source citation {index} lacks source identity.")


def source_citation(source: Dict[str, Any]) -> str:
    """Build a compact source citation string."""
    file_name = source.get("file_name") or source.get("metadata", {}).get("file_name", "unknown")
    page = source.get("page") or source.get("metadata", {}).get("page", "unknown")
    score = source.get("similarity_score", "n/a")
    return f"{file_name}, page {page}, score {score}"


def print_retrieved_chunks(results: List[Tuple[Document, float]]) -> None:
    """Print retrieved chunk previews and metadata."""
    for index, (document, score) in enumerate(results, 1):
        print()
        print(f"Retrieved chunk {index}")
        print(f"  relevance_score: {float(score):.6f}")
        print(f"  preview: {preview_text(document.page_content)}")
        print("  metadata preview:")
        for key in sorted(document.metadata):
            print(f"    {safe_console_text(key)}: {safe_console_text(document.metadata[key])}")


def print_sources(sources: List[Dict[str, Any]]) -> None:
    """Print source citations."""
    for index, source in enumerate(sources, 1):
        print(f"  [{index}] {safe_console_text(source_citation(source))}")


def run_pipeline_test() -> bool:
    """
    Execute the full end-to-end RAG integration test.

    Returns:
        bool: True when the test passes, False otherwise.
    """
    try:
        print_section("IMPORTING MODULES")
        logger.info("Importing full RAG pipeline components...")

        from app.rag.loaders import PDFLoader
        from app.rag.chunking import ChunkingError, TextSplitter
        from app.rag.embeddings import EmbeddingError
        from app.rag.embeddings import EmbeddingModel as EmbeddingManager
        from app.rag.vectorstore import ChromaManager
        from app.rag.retrievers import RetrieverError, SemanticRetriever
        from app.rag.llm import OllamaClient, OllamaError
        from app.rag.pipelines import PipelineError, RetrievalPipeline

        print("[OK] Successfully imported all RAG pipeline components")
        logger.info("Imports completed successfully")

        persist_dir = Path(__file__).parent / "test_pipeline_chroma_db"
        reset_test_persist_dir(persist_dir)

        print_section("LOADING PDF")
        pdf_path = resolve_pdf_path()
        loader = PDFLoader(file_path=str(pdf_path))
        documents = loader.load()
        validate_extractable_text(documents)

        print(f"PDF path: {safe_console_text(pdf_path)}")
        print(f"Total documents loaded: {len(documents)}")

        print_section("CHUNKING")
        splitter = TextSplitter(chunk_size=500, chunk_overlap=100)
        chunks = splitter.split_documents(documents)
        validate_chunks(chunks)
        print(f"Total chunks created: {len(chunks)}")

        print_section("EMBEDDINGS")
        embedding_manager = EmbeddingManager()
        embeddings = embedding_manager.embed_documents(chunk_texts(chunks))
        vector_length = validate_embeddings(embeddings, expected_count=len(chunks))
        print(f"Embedding model: {embedding_manager.get_model_info().get('model_name')}")
        print(f"Embeddings generated: {len(embeddings)}")
        print(f"Embedding vector length: {vector_length}")

        print_section("CHROMADB STORAGE")
        vector_store, stored_count, storage_backend = create_vector_store(
            chroma_manager_class=ChromaManager,
            persist_dir=persist_dir,
            collection_name=COLLECTION_NAME,
            chunks=chunks,
            embeddings=embeddings,
            embedding_manager=embedding_manager,
        )

        if stored_count != len(chunks):
            raise ValueError(f"Expected {len(chunks)} stored chunks, got {stored_count}.")

        print(f"Storage backend: {storage_backend}")
        print(f"Total chunks stored: {stored_count}")
        print(f"Chroma persistence directory: {safe_console_text(persist_dir)}")
        print(f"Collection name: {COLLECTION_NAME}")

        print_section("PIPELINE SETUP")
        retriever = SemanticRetriever(vector_store=vector_store, top_k=TOP_K, similarity_threshold=settings.SIMILARITY_THRESHOLD)
        llm_client = OllamaClient(
            model_name=MODEL_NAME,
            timeout=OLLAMA_TIMEOUT_SECONDS,
            temperature=0.2,
            top_p=0.9,
            top_k=40,
        )

        if not llm_client.check_model_availability(MODEL_NAME):
            raise ValueError(f"Model '{MODEL_NAME}' is not available. Run: ollama pull {MODEL_NAME}")

        system_prompt = (
            "You are a grounded RAG assistant. Answer strictly using the provided context. "
            "If the context is insufficient, say that the context does not contain enough information. "
            "Keep the answer concise and do not invent facts."
        )
        pipeline = RetrievalPipeline(
            retriever=retriever,
            llm_client=llm_client,
            top_k=TOP_K,
            system_prompt=system_prompt,
        )

        print(f"LLM model: {MODEL_NAME}")
        print(f"Top-k retrieval: {TOP_K}")
        print("[OK] RetrievalPipeline initialized")

        for query_index, query in enumerate(TEST_QUERIES, 1):
            print_section(f"QUERY {query_index}")
            print(f"Query: {query}")

            started_at = time.time()
            retrieved_results = retriever.retrieve(query=query, top_k=TOP_K)
            validate_retrieved_results(retrieved_results, top_k=TOP_K)

            print(f"Retrieved chunk count: {len(retrieved_results)}")
            print_retrieved_chunks(retrieved_results)

            response = pipeline.generate(query=query, top_k=TOP_K)
            validate_rag_response(response, retrieved_results)

            elapsed_seconds = time.time() - started_at

            print()
            print("Generated answer:")
            print(safe_console_text(response.answer.strip()))
            print()
            print("Source citations:")
            print_sources(response.sources)
            print(f"Response length: {len(response.answer.strip())} characters")
            print(f"Processing time: {elapsed_seconds:.2f} seconds")
            print("[OK] Query processed successfully")

        print_section("FINAL VALIDATION")
        print("[OK] PDF parsing completed")
        print("[OK] Chunking completed")
        print("[OK] Embedding generation completed")
        print("[OK] ChromaDB storage and persistence completed")
        print("[OK] Semantic retrieval completed")
        print("[OK] Qwen3 generation completed")
        print("[OK] Citations and metadata preserved")

        print_section("TEST RESULT")
        print("[OK] FULL END-TO-END RAG PIPELINE TEST PASSED")
        logger.info("Full end-to-end RAG pipeline test passed")
        return True

    except ImportError as exc:
        print_section("ERROR - IMPORT FAILED")
        print(f"[ERROR] Failed to import required module: {exc}")
        logger.error("Import failed", exc_info=True)
        return False

    except FileNotFoundError as exc:
        print_section("ERROR - FILE NOT FOUND")
        print(f"[ERROR] {exc}")
        logger.error("Required file was not found: %s", exc)
        return False

    except ValueError as exc:
        print_section("ERROR - VALIDATION FAILED")
        print(f"[ERROR] {exc}")
        logger.error("Validation failed: %s", exc)
        return False

    except ChunkingError as exc:
        print_section("ERROR - CHUNKING FAILED")
        print(f"[ERROR] {exc}")
        logger.error("Chunking failed: %s", exc)
        return False

    except EmbeddingError as exc:
        print_section("ERROR - EMBEDDING FAILED")
        print(f"[ERROR] {exc}")
        logger.error("Embedding failed: %s", exc)
        return False

    except RetrieverError as exc:
        print_section("ERROR - RETRIEVAL FAILED")
        print(f"[ERROR] {exc}")
        logger.error("Retrieval failed: %s", exc)
        return False

    except OllamaError as exc:
        print_section("ERROR - OLLAMA FAILED")
        print(f"[ERROR] {exc}")
        logger.error("Ollama failed: %s", exc)
        return False

    except PipelineError as exc:
        print_section("ERROR - PIPELINE FAILED")
        print(f"[ERROR] {exc}")
        logger.error("Pipeline failed: %s", exc)
        return False

    except Exception as exc:
        print_section("ERROR - UNEXPECTED FAILURE")
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        logger.error("Unexpected pipeline test failure", exc_info=True)
        return False


def main() -> int:
    """
    Main entry point.

    Returns:
        int: 0 for success, 1 for failure, 130 when interrupted.
    """
    print()
    print_separator()
    print(" FULL END-TO-END RAG PIPELINE INTEGRATION TEST")
    print_separator()

    setup_paths()

    try:
        success = run_pipeline_test()

        print()
        print_separator()
        if success:
            print(" Test execution completed successfully")
            exit_code = 0
        else:
            print(" Test execution failed")
            exit_code = 1
        print_separator()
        print()

        return exit_code

    except KeyboardInterrupt:
        print()
        print_section("INTERRUPTED")
        print("[ERROR] Test interrupted by user")
        logger.warning("Test interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())
