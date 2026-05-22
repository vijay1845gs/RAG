"""
Standalone integration test for semantic retrieval.

This script verifies PDF loading, chunking, embedding generation, ChromaDB vector
storage, and SemanticRetriever retrieval without running Ollama, LLM generation,
or FastAPI.

Usage:
    python backend/test_retriever.py
"""

import logging
import math
import os
import shutil
import sys
import warnings
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.config import settings


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

from langchain_core.documents import Document


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


QUERY = "What are glioma symptoms?"
TOP_K = 3
COLLECTION_NAME = "rag_retriever_integration_test"


class NativeChromaSearchAdapter:
    """Test adapter that gives native chromadb the ChromaManager search interface."""

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
            score = 1.0 / (1.0 + float(distance))
            results.append(
                (
                    Document(page_content=text, metadata=metadata or {}),
                    score,
                )
            )

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
    """Format retrieved chunk content for a compact terminal preview."""
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return safe_console_text(normalized)
    return safe_console_text(normalized[:max_length].rstrip() + "... (truncated)")


def resolve_test_pdf() -> Path:
    """Return article-1.pdf when present, otherwise the first available test PDF."""
    test_data_dir = Path(__file__).parent / "test_data"
    preferred_pdf = test_data_dir / "article-1.pdf"

    if preferred_pdf.exists():
        return preferred_pdf

    available_pdfs = sorted(test_data_dir.glob("*.pdf"))
    if available_pdfs:
        print(f"[WARN] Preferred PDF not found: {preferred_pdf}")
        print(f"[WARN] Using available PDF instead: {available_pdfs[0]}")
        return available_pdfs[0]

    raise FileNotFoundError(
        f"No PDF files found in test data directory: {test_data_dir}"
    )


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
            "or add OCR before testing retrieval."
        )


def validate_chunks(chunks: List[Any]) -> None:
    """Ensure chunks are suitable for retrieval indexing."""
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
        if not isinstance(value, (int, float)):
            return False
        if not math.isfinite(float(value)):
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
        metadata={"purpose": "rag_retriever_integration_test"},
    )

    ids, documents, metadatas, vectors = build_chroma_payload(chunks, embeddings)
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=vectors,
    )

    stored_count = collection.count()

    persisted_client = chromadb.PersistentClient(path=str(persist_dir))
    persisted_collection = persisted_client.get_collection(collection_name)
    persisted_count = persisted_collection.count()

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


def validate_retrieval(
    results: List[Tuple[Document, float]],
    expected_max: int,
) -> None:
    """Validate retrieved chunks, scores, and metadata integrity."""
    if not results:
        raise ValueError("Semantic retrieval returned zero chunks.")

    if len(results) > expected_max:
        raise ValueError(f"Retrieved {len(results)} chunks, expected at most {expected_max}.")

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


def print_result_preview(index: int, document: Document, score: float) -> None:
    """Print a retrieved result in a readable, Windows-safe format."""
    print()
    print(f"Result {index + 1}")
    print(f"  relevance_score: {float(score):.6f}")
    print(f"  preview: {preview_text(document.page_content)}")
    print("  metadata:")
    for key in sorted(document.metadata):
        print(f"    {safe_console_text(key)}: {safe_console_text(document.metadata[key])}")


def run_retriever_test() -> bool:
    """
    Execute the semantic retrieval integration test.

    Returns:
        bool: True when the test passes, False otherwise.
    """
    try:
        print_section("IMPORTING MODULES")
        logger.info("Importing PDFLoader, TextSplitter, EmbeddingManager, ChromaManager, and SemanticRetriever...")

        from app.rag.loaders import PDFLoader
        from app.rag.chunking import ChunkingError, TextSplitter
        from app.rag.embeddings import EmbeddingError
        from app.rag.embeddings import EmbeddingModel as EmbeddingManager
        from app.rag.vectorstore import ChromaManager
        from app.rag.retrievers import RetrieverError, SemanticRetriever

        print("[OK] Successfully imported retrieval pipeline components")
        logger.info("Imports completed successfully")

        persist_dir = Path(__file__).parent / "test_retriever_chroma_db"
        reset_test_persist_dir(persist_dir)

        print_section("LOADING PDF")
        pdf_path = resolve_test_pdf()
        logger.info("Using PDF path: %s", pdf_path)

        loader = PDFLoader(file_path=str(pdf_path))
        documents = loader.load()
        validate_extractable_text(documents)

        print(f"PDF path: {safe_console_text(pdf_path)}")
        print(f"Total documents loaded: {len(documents)}")

        print_section("SPLITTING DOCUMENTS")
        splitter = TextSplitter(chunk_size=500, chunk_overlap=100)
        chunks = splitter.split_documents(documents)
        validate_chunks(chunks)
        print(f"Total chunks prepared: {len(chunks)}")

        print_section("GENERATING EMBEDDINGS")
        embedding_manager = EmbeddingManager()
        embeddings = embedding_manager.embed_documents(chunk_texts(chunks))
        vector_length = validate_embeddings(embeddings, expected_count=len(chunks))
        print(f"Embedding model: {embedding_manager.get_model_info().get('model_name')}")
        print(f"Embeddings generated: {len(embeddings)}")
        print(f"Embedding vector length: {vector_length}")

        print_section("STORING IN CHROMADB")
        vector_store, stored_count, storage_backend = create_vector_store(
            chroma_manager_class=ChromaManager,
            persist_dir=persist_dir,
            collection_name=COLLECTION_NAME,
            chunks=chunks,
            embeddings=embeddings,
            embedding_manager=embedding_manager,
        )

        if stored_count <= 0:
            raise ValueError("Vector store contains no data after indexing.")

        print(f"Storage backend: {storage_backend}")
        print(f"Total chunks stored: {stored_count}")
        print(f"Chroma persistence directory: {safe_console_text(persist_dir)}")
        print(f"Collection name: {COLLECTION_NAME}")

        print_section("SEMANTIC RETRIEVAL")
        retriever = SemanticRetriever(vector_store=vector_store, top_k=TOP_K, similarity_threshold=settings.SIMILARITY_THRESHOLD)
        results = retriever.retrieve(query=QUERY, top_k=TOP_K)
        validate_retrieval(results, expected_max=TOP_K)

        print(f"Query used: {QUERY}")
        print(f"Number of retrieved chunks: {len(results)}")

        for index, (document, score) in enumerate(results):
            print_result_preview(index, document, score)

        print_section("VALIDATION")
        print("[OK] Retrieval count is greater than zero")
        print("[OK] Retrieved content is non-empty")
        print("[OK] Relevance scores are present and sorted")
        print("[OK] Retrieved metadata integrity maintained")

        print_section("TEST RESULT")
        print("[OK] SEMANTIC RETRIEVAL TEST PASSED")
        logger.info("Semantic retrieval integration test passed")
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

    except Exception as exc:
        print_section("ERROR - UNEXPECTED FAILURE")
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        logger.error("Unexpected retriever test failure", exc_info=True)
        return False


def main() -> int:
    """
    Main entry point.

    Returns:
        int: 0 for success, 1 for failure, 130 when interrupted.
    """
    print()
    print_separator()
    print(" SEMANTIC RETRIEVAL INTEGRATION TEST")
    print_separator()

    setup_paths()

    try:
        success = run_retriever_test()

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
