"""
Standalone integration test for the text chunking module.

This script verifies that the PDF loader and text chunker work together by:
1. Loading backend/test_data/article-1.pdf
2. Splitting loaded documents into chunks
3. Printing chunking statistics and a preview
4. Validating chunk content and metadata preservation

Usage:
    python backend/test_chunking.py
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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


def truncate_text(text: str, max_length: int = 500) -> str:
    """Return a single-line-safe preview while preserving readability."""
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return safe_console_text(normalized)
    return safe_console_text(normalized[:max_length].rstrip() + "... (truncated)")


def safe_console_text(value: Any) -> str:
    """Return text that can be printed safely on the active Windows console."""
    text = str(value)
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


def validate_chunks(documents: List[Any], chunks: List[Any]) -> None:
    """Validate that chunking produced usable chunks with preserved metadata."""
    if not documents:
        raise ValueError("No documents were loaded from the PDF.")

    if not chunks:
        raise ValueError(
            "Chunking produced zero chunks. The PDF may contain no extractable text."
        )

    first_chunk = chunks[0]
    if not getattr(first_chunk, "page_content", "").strip():
        raise ValueError("First chunk has no text content.")

    first_metadata = getattr(first_chunk, "metadata", {})
    if not isinstance(first_metadata, dict) or not first_metadata:
        raise ValueError("First chunk metadata is missing or invalid.")

    required_metadata = {"source", "file_name", "page", "page_number"}
    missing_metadata = sorted(required_metadata - set(first_metadata))
    if missing_metadata:
        raise ValueError(
            "Chunk metadata did not preserve required keys: "
            + ", ".join(missing_metadata)
        )

    chunk_metadata = {"source_document_index", "chunk_index", "chunk_total", "chunk_size"}
    missing_chunk_metadata = sorted(chunk_metadata - set(first_metadata))
    if missing_chunk_metadata:
        raise ValueError(
            "Chunk metadata is missing chunking keys: "
            + ", ".join(missing_chunk_metadata)
        )


def validate_extractable_text(documents: List[Any]) -> None:
    """Validate that loaded PDF documents contain text before chunking."""
    if not documents:
        raise ValueError("No documents were loaded from the PDF.")

    non_empty_documents = [
        document
        for document in documents
        if getattr(document, "page_content", "").strip()
    ]

    if not non_empty_documents:
        raise ValueError(
            "Loaded PDF contains no extractable text. "
            "article-1.pdf appears to be image-only/scanned, so text chunking "
            "cannot run until OCR is added or a PDF with a text layer is used."
        )


def print_metadata(metadata: Dict[str, Any]) -> None:
    """Print metadata in a stable, readable order."""
    for key in sorted(metadata):
        print(f"  {safe_console_text(key)}: {safe_console_text(metadata[key])}")


def resolve_test_pdf() -> Path:
    """Return the preferred test PDF, falling back to any PDF in test_data."""
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


def run_chunking_test() -> bool:
    """
    Execute the chunking integration test.

    Returns:
        bool: True when the test passes, False otherwise.
    """
    try:
        print_section("IMPORTING MODULES")
        logger.info("Importing PDFLoader and TextSplitter...")

        from app.rag.loaders import PDFLoader
        from app.rag.chunking import ChunkingError, TextSplitter

        print("[OK] Successfully imported PDFLoader and TextSplitter")
        logger.info("Imports completed successfully")

        print_section("LOADING PDF")
        pdf_path = resolve_test_pdf()
        logger.info("Using PDF path: %s", pdf_path)

        loader = PDFLoader(file_path=str(pdf_path))
        documents = loader.load()
        total_documents = len(documents)
        total_text_characters = sum(len(doc.page_content.strip()) for doc in documents)
        non_empty_documents = sum(1 for doc in documents if doc.page_content.strip())

        print(f"PDF path: {pdf_path}")
        print(f"Total documents loaded: {total_documents}")
        print(f"Documents with extractable text: {non_empty_documents}")
        print(f"Total extractable text characters: {total_text_characters}")
        logger.info("Loaded %s document(s)", total_documents)

        validate_extractable_text(documents)

        print_section("SPLITTING DOCUMENTS")
        splitter = TextSplitter(chunk_size=500, chunk_overlap=100)
        chunks = splitter.split_documents(documents)
        stats = splitter.get_statistics(chunks)

        total_chunks = len(chunks)
        average_chunk_size = stats.get("avg_chunk_size", 0)

        print(f"Total chunks created: {total_chunks}")
        print(f"Average chunk size: {average_chunk_size:.2f} characters")
        logger.info(
            "Chunking complete: %s document(s), %s chunk(s), %.2f avg chars",
            total_documents,
            total_chunks,
            average_chunk_size,
        )

        validate_chunks(documents, chunks)

        first_chunk = chunks[0]
        first_metadata = first_chunk.metadata

        print_section("FIRST CHUNK PREVIEW")
        print(truncate_text(first_chunk.page_content))

        print_section("FIRST CHUNK METADATA")
        print_metadata(first_metadata)

        print_section("VALIDATION")
        print("[OK] Chunk count is greater than zero")
        print("[OK] Chunk content exists")
        print("[OK] Source document metadata was preserved")
        print("[OK] Chunk-specific metadata was added")

        print_section("TEST RESULT")
        print("[OK] TEXT CHUNKING TEST PASSED")
        logger.info("Text chunking integration test passed")
        return True

    except ImportError as exc:
        print_section("ERROR - IMPORT FAILED")
        print(f"[ERROR] Failed to import required module: {exc}")
        logger.error("Import failed", exc_info=True)
        return False

    except FileNotFoundError as exc:
        print_section("ERROR - FILE NOT FOUND")
        print(f"[ERROR] {exc}")
        logger.error("Required PDF file was not found", exc_info=True)
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

    except Exception as exc:
        print_section("ERROR - UNEXPECTED FAILURE")
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        logger.error("Unexpected chunking test failure", exc_info=True)
        return False


def main() -> int:
    """
    Main entry point.

    Returns:
        int: 0 for success, 1 for failure, 130 when interrupted.
    """
    print()
    print_separator()
    print(" TEXT CHUNKING INTEGRATION TEST")
    print_separator()

    setup_paths()

    try:
        success = run_chunking_test()

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
