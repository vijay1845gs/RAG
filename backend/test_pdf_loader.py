"""
Standalone Test Script for PDF Loader Module

This script verifies that the PDF loader module works correctly by:
1. Loading a sample PDF from backend/test_data/sample.pdf
2. Printing the number of documents loaded
3. Displaying the first 500 characters of extracted text
4. Handling errors gracefully with logging

Usage:
    python backend/test_pdf_loader.py

Author: RAG System
Version: 1.0.0
"""

import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def setup_paths() -> None:
    """Add backend directory to Python path for imports."""
    backend_dir = Path(__file__).parent
    sys.path.insert(0, str(backend_dir))
    logger.debug(f"Added to sys.path: {backend_dir}")


def print_separator(title: str = "", width: int = 80) -> None:
    """Print a formatted separator line."""
    if title:
        padding = (width - len(title) - 2) // 2
        print("=" * padding + f" {title} " + "=" * (width - padding - len(title) - 2))
    else:
        print("=" * width)


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print()
    print_separator(title)


def test_pdf_loader() -> bool:
    """
    Test the PDF loader module.

    Returns:
        bool: True if test passed, False otherwise.
    """
    try:
        # Import PDFLoader
        print_section("IMPORTING PDF LOADER MODULE")
        logger.info("Importing PDFLoader from app.rag.loaders.pdf_loader...")

        from app.rag.loaders.pdf_loader import PDFLoader

        print("[OK] Successfully imported PDFLoader")
        logger.info("PDFLoader imported successfully")

        # Check if sample PDF exists
        print_section("CHECKING FOR SAMPLE PDF")
        test_data_dir = Path(__file__).parent / "test_data"
        sample_pdf_path = test_data_dir / "sample.pdf"
        if not sample_pdf_path.exists():
            available_pdfs = sorted(test_data_dir.glob("*.pdf"))
            if available_pdfs:
                sample_pdf_path = available_pdfs[0]

        logger.info(f"Looking for sample PDF at: {sample_pdf_path}")

        if not sample_pdf_path.exists():
            print(f"[WARN] Sample PDF not found at: {sample_pdf_path}")
            logger.warning(f"Sample PDF not found at {sample_pdf_path}")
            print("\nTo run this test, please place a PDF file at:")
            print(f"  {sample_pdf_path}")
            print("\nCreating a note for test data setup...")
            return False

        print(f"[OK] Sample PDF found at: {sample_pdf_path}")
        logger.info(f"Sample PDF found: {sample_pdf_path}")

        # Load PDF
        print_section("LOADING PDF")
        logger.info(f"Loading PDF from: {sample_pdf_path}")

        loader = PDFLoader(file_path=str(sample_pdf_path))
        logger.info("PDFLoader instance created")

        documents = loader.load()
        logger.info(f"PDF loaded successfully with {len(documents)} documents")

        print("[OK] PDF loaded successfully")

        # Display results
        print_section("PDF LOADING RESULTS")

        # Number of documents
        print(f"\nNumber of documents loaded: {len(documents)}")
        logger.info(f"Total documents: {len(documents)}")

        # Document metadata
        if documents:
            first_doc = documents[0]
            print(f"\nFirst document metadata:")
            if hasattr(first_doc, "metadata"):
                for key, value in first_doc.metadata.items():
                    print(f"  {key}: {value}")
                logger.info(f"First document metadata: {first_doc.metadata}")

        # Text preview
        print_section("TEXT CONTENT PREVIEW")

        if documents and len(documents) > 0:
            full_text = " ".join([doc.page_content for doc in documents])
            text_preview = full_text[:500]

            print(f"\nFirst 500 characters of extracted text:")
            print("-" * 80)
            print(text_preview)
            if len(full_text) > 500:
                print("... (truncated)")
            print("-" * 80)

            logger.info(f"Text preview (first 500 chars): {text_preview[:100]}...")

            # Additional statistics
            print()
            print(f"Total text length: {len(full_text)} characters")
            print(f"Number of pages/documents: {len(documents)}")

            if hasattr(documents[0], "metadata") and "page" in documents[0].metadata:
                print(f"Total pages: {documents[-1].metadata.get('page', '?')}")

        # Success
        print_section("TEST RESULT")
        print("\n[OK] PDF LOADER TEST PASSED")
        logger.info("PDF loader test completed successfully")
        print()

        return True

    except ImportError as e:
        print_section("ERROR - IMPORT FAILED")
        error_msg = f"Failed to import PDFLoader: {str(e)}"
        print(f"\n[ERROR] {error_msg}")
        logger.error(error_msg, exc_info=True)
        return False

    except FileNotFoundError as e:
        print_section("ERROR - FILE NOT FOUND")
        error_msg = f"PDF file not found: {str(e)}"
        print(f"\n[ERROR] {error_msg}")
        logger.error(error_msg, exc_info=True)
        return False

    except ValueError as e:
        print_section("ERROR - INVALID VALUE")
        error_msg = f"Invalid value error: {str(e)}"
        print(f"\n[ERROR] {error_msg}")
        logger.error(error_msg, exc_info=True)
        return False

    except Exception as e:
        print_section("ERROR - UNEXPECTED FAILURE")
        error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
        print(f"\n[ERROR] {error_msg}")
        logger.error(error_msg, exc_info=True)
        return False


def main() -> int:
    """
    Main entry point for the test script.

    Returns:
        int: Exit code (0 for success, 1 for failure).
    """
    print()
    print_separator()
    print(" PDF LOADER TEST SCRIPT")
    print_separator()

    setup_paths()

    try:
        success = test_pdf_loader()

        if success:
            print_separator()
            print(" Test execution completed successfully")
            print_separator()
            print()
            return 0
        else:
            print_separator()
            print(" Test execution failed")
            print_separator()
            print()
            return 1

    except KeyboardInterrupt:
        print()
        print_section("INTERRUPTED")
        print("\n[ERROR] Test interrupted by user")
        logger.warning("Test interrupted by user")
        print()
        return 130

    except Exception as e:
        print()
        print_section("FATAL ERROR")
        error_msg = f"Fatal error: {type(e).__name__}: {str(e)}"
        print(f"\n[ERROR] {error_msg}")
        logger.critical(error_msg, exc_info=True)
        print()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
