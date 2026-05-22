"""
Standalone integration test for embedding generation.

This script verifies that PDF loading, text chunking, and embedding generation
work together without involving ChromaDB, retrieval, or LLM generation.

Usage:
    python backend/test_embeddings.py
"""

import logging
import math
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Iterable, List, Sequence


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


SAMPLE_QUERY = "What are glioma symptoms?"


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


def preview_vector(vector: Sequence[float], limit: int = 10) -> str:
    """Format the first few embedding values for readable terminal output."""
    values = [f"{float(value):.6f}" for value in vector[:limit]]
    return "[" + ", ".join(values) + "]"


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


def validate_extractable_text(documents: List[Any]) -> None:
    """Ensure loaded documents contain text before chunking."""
    if not documents:
        raise ValueError("No documents were loaded from the PDF.")

    if not any(getattr(document, "page_content", "").strip() for document in documents):
        raise ValueError(
            "Loaded PDF contains no extractable text. Use a PDF with a text layer "
            "or add OCR before testing embeddings."
        )


def validate_chunks(chunks: List[Any]) -> None:
    """Ensure chunking produced content suitable for embedding."""
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
    if not isinstance(vector, (list, tuple)) or not vector:
        return False

    for value in vector:
        if not isinstance(value, (int, float)):
            return False
        if not math.isfinite(float(value)):
            return False

    return True


def validate_embeddings(
    document_embeddings: List[List[float]],
    query_embedding: List[float],
    expected_count: int,
) -> int:
    """Validate embedding count, numeric values, and consistent dimensions."""
    if not document_embeddings:
        raise ValueError("No document embeddings were generated.")

    if len(document_embeddings) != expected_count:
        raise ValueError(
            f"Expected {expected_count} document embeddings, "
            f"got {len(document_embeddings)}."
        )

    if not is_numeric_vector(query_embedding):
        raise ValueError("Query embedding is empty, invalid, or non-numeric.")

    vector_lengths = {len(vector) for vector in document_embeddings}
    if len(vector_lengths) != 1:
        raise ValueError(
            "Document embedding vector lengths are inconsistent: "
            + ", ".join(str(length) for length in sorted(vector_lengths))
        )

    vector_length = vector_lengths.pop()
    if len(query_embedding) != vector_length:
        raise ValueError(
            f"Query embedding length {len(query_embedding)} does not match "
            f"document embedding length {vector_length}."
        )

    invalid_indexes = [
        index
        for index, embedding in enumerate(document_embeddings)
        if not is_numeric_vector(embedding)
    ]
    if invalid_indexes:
        raise ValueError(
            "Non-numeric document embeddings found at indexes: "
            + ", ".join(str(index) for index in invalid_indexes[:10])
        )

    return vector_length


def chunk_texts(chunks: Iterable[Any]) -> List[str]:
    """Extract chunk text content for the embedding manager."""
    return [chunk.page_content for chunk in chunks]


def run_embeddings_test() -> bool:
    """
    Execute the embedding integration test.

    Returns:
        bool: True when the test passes, False otherwise.
    """
    try:
        print_section("IMPORTING MODULES")
        logger.info("Importing PDFLoader, TextSplitter, and EmbeddingManager...")

        from app.rag.loaders import PDFLoader
        from app.rag.chunking import ChunkingError, TextSplitter
        from app.rag.embeddings import EmbeddingError
        from app.rag.embeddings import EmbeddingModel as EmbeddingManager

        print("[OK] Successfully imported PDFLoader, TextSplitter, and EmbeddingManager")
        logger.info("Imports completed successfully")

        print_section("LOADING PDF")
        pdf_path = resolve_test_pdf()
        logger.info("Using PDF path: %s", pdf_path)

        loader = PDFLoader(file_path=str(pdf_path))
        documents = loader.load()
        validate_extractable_text(documents)

        total_text_characters = sum(len(document.page_content.strip()) for document in documents)
        print(f"PDF path: {safe_console_text(pdf_path)}")
        print(f"Total documents loaded: {len(documents)}")
        print(f"Total extractable text characters: {total_text_characters}")
        logger.info("Loaded %s document(s)", len(documents))

        print_section("SPLITTING DOCUMENTS")
        splitter = TextSplitter(chunk_size=500, chunk_overlap=100)
        chunks = splitter.split_documents(documents)
        validate_chunks(chunks)

        print(f"Total chunks processed: {len(chunks)}")
        logger.info("Prepared %s chunk(s) for embedding", len(chunks))

        print_section("GENERATING EMBEDDINGS")
        embedding_manager = EmbeddingManager()
        model_info = embedding_manager.get_model_info()
        logger.info("Embedding model loaded: %s", model_info)

        document_texts = chunk_texts(chunks)
        document_embeddings = embedding_manager.embed_documents(document_texts)
        query_embedding = embedding_manager.embed_query(SAMPLE_QUERY)

        vector_length = validate_embeddings(
            document_embeddings=document_embeddings,
            query_embedding=query_embedding,
            expected_count=len(chunks),
        )

        print(f"Embedding model: {model_info.get('model_name')}")
        print(f"Total embeddings generated: {len(document_embeddings)}")
        print(f"Embedding vector length: {vector_length}")
        print(f"First 10 embedding values: {preview_vector(document_embeddings[0])}")

        print_section("QUERY EMBEDDING")
        print(f"Sample query: {SAMPLE_QUERY}")
        print(f"Query embedding length: {len(query_embedding)}")
        print(f"Query embedding preview: {preview_vector(query_embedding)}")

        print_section("VALIDATION")
        print("[OK] Document embeddings generated successfully")
        print("[OK] Query embedding generated successfully")
        print("[OK] Vector lengths are consistent")
        print("[OK] Embeddings contain finite numeric values")

        print_section("TEST RESULT")
        print("[OK] EMBEDDING GENERATION TEST PASSED")
        logger.info("Embedding integration test passed")
        return True

    except ImportError as exc:
        print_section("ERROR - IMPORT FAILED")
        print(f"[ERROR] Failed to import required module: {exc}")
        logger.error("Import failed", exc_info=True)
        return False

    except FileNotFoundError as exc:
        print_section("ERROR - FILE NOT FOUND")
        print(f"[ERROR] {exc}")
        logger.error("Required PDF file was not found: %s", exc)
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

    except Exception as exc:
        print_section("ERROR - UNEXPECTED FAILURE")
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        logger.error("Unexpected embedding test failure", exc_info=True)
        return False


def main() -> int:
    """
    Main entry point.

    Returns:
        int: 0 for success, 1 for failure, 130 when interrupted.
    """
    print()
    print_separator()
    print(" EMBEDDING GENERATION INTEGRATION TEST")
    print_separator()

    setup_paths()

    try:
        success = run_embeddings_test()

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
