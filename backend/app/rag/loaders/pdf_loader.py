"""
PDF Document Loader Module

This module provides functionality to load and parse PDF files using LangChain's
PyPDFLoader. It handles various error scenarios gracefully and returns standardized
LangChain Document objects suitable for downstream RAG pipeline processing.

Author: RAG System
Version: 1.0.0
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class PDFLoaderError(Exception):
    """Base exception for PDF loader errors."""

    pass


class InvalidFilePathError(PDFLoaderError):
    """Raised when the provided file path is invalid."""

    pass


class PDFFileNotFoundError(PDFLoaderError):
    """Raised when the PDF file does not exist."""

    pass


class CorruptedPDFError(PDFLoaderError):
    """Raised when the PDF file is corrupted or cannot be parsed."""

    pass


class EmptyPDFError(PDFLoaderError):
    """Raised when the PDF file is empty or contains no readable pages."""

    pass


class PDFLoader:
    """
    A production-grade PDF document loader for RAG systems.

    This class encapsulates PDF loading functionality, handling various error
    scenarios and providing clean, reusable interfaces for loading PDF documents
    into standardized LangChain Document objects.

    Attributes:
        file_path (Path): Path to the PDF file to be loaded.
        logger (logging.Logger): Logger instance for this class.

    Example:
        >>> loader = PDFLoader("path/to/document.pdf")
        >>> documents = loader.load()
        >>> print(f"Loaded {len(documents)} pages")
    """

    def __init__(self, file_path: str) -> None:
        """
        Initialize the PDFLoader with a file path.

        Args:
            file_path (str): Path to the PDF file to load.

        Raises:
            InvalidFilePathError: If the file path is None or empty.
            PDFFileNotFoundError: If the file does not exist.
        """
        self.logger = logger
        self._validate_file_path(file_path)
        self.file_path = Path(file_path)
        self.logger.info(f"PDFLoader initialized for file: {self.file_path}")

    def _validate_file_path(self, file_path: str) -> None:
        """
        Validate that the file path is valid and the file exists.

        Args:
            file_path (str): Path to validate.

        Raises:
            InvalidFilePathError: If file_path is None or empty.
            PDFFileNotFoundError: If the file does not exist.
        """
        if not file_path or not isinstance(file_path, str):
            error_msg = f"Invalid file path: {file_path}. Path must be a non-empty string."
            self.logger.error(error_msg)
            raise InvalidFilePathError(error_msg)

        path = Path(file_path)

        if not path.exists():
            error_msg = f"PDF file not found: {file_path}"
            self.logger.error(error_msg)
            raise PDFFileNotFoundError(error_msg)

        if not path.is_file():
            error_msg = f"Path is not a file: {file_path}"
            self.logger.error(error_msg)
            raise InvalidFilePathError(error_msg)

        if path.suffix.lower() != ".pdf":
            self.logger.warning(
                f"File extension is not .pdf: {file_path}. Proceeding anyway."
            )

    def _validate_file_readability(self) -> None:
        """
        Validate that the file is readable and not empty.

        Raises:
            InvalidFilePathError: If the file is not readable.
            EmptyPDFError: If the file is empty.
        """
        try:
            if not os.access(self.file_path, os.R_OK):
                error_msg = f"PDF file is not readable: {self.file_path}"
                self.logger.error(error_msg)
                raise InvalidFilePathError(error_msg)

            file_size = self.file_path.stat().st_size
            if file_size == 0:
                error_msg = f"PDF file is empty: {self.file_path}"
                self.logger.error(error_msg)
                raise EmptyPDFError(error_msg)

            self.logger.debug(
                f"File validation successful. Size: {file_size} bytes"
            )

        except (OSError, IOError) as e:
            error_msg = f"Error accessing PDF file {self.file_path}: {str(e)}"
            self.logger.error(error_msg)
            raise InvalidFilePathError(error_msg) from e

    def load(self) -> List[Document]:
        """
        Load and parse the PDF file into LangChain Document objects.

        Each page of the PDF becomes a separate Document object with the page
        content as the page_content and metadata including page number and source.

        Returns:
            List[Document]: List of LangChain Document objects, one per PDF page.

        Raises:
            CorruptedPDFError: If the PDF cannot be parsed due to corruption.
            EmptyPDFError: If the PDF contains no readable pages.

        Example:
            >>> loader = PDFLoader("document.pdf")
            >>> docs = loader.load()
            >>> for doc in docs:
            ...     print(f"Page {doc.metadata['page']}: {doc.page_content[:100]}")
        """
        try:
            self._validate_file_readability()

            self.logger.info(f"Starting PDF parsing: {self.file_path}")

            documents = self._load_with_pypdf()

            if not documents:
                error_msg = f"No pages could be extracted from PDF: {self.file_path}"
                self.logger.warning(error_msg)
                raise EmptyPDFError(error_msg)

            # Enhance metadata with source file information
            for i, doc in enumerate(documents):
                doc.metadata["source"] = str(self.file_path)
                doc.metadata["file_name"] = self.file_path.name
                doc.metadata["page_number"] = i
                if "page" not in doc.metadata:
                    doc.metadata["page"] = i

            self.logger.info(
                f"Successfully loaded {len(documents)} pages from: {self.file_path}"
            )
            return documents

        except EmptyPDFError:
            raise

        except Exception as e:
            error_msg = (
                f"Error parsing PDF file {self.file_path}: {type(e).__name__}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise CorruptedPDFError(error_msg) from e

    def load_with_metadata(
        self, additional_metadata: Optional[dict] = None
    ) -> List[Document]:
        """
        Load PDF and add additional metadata to each document.

        This method extends the standard load() functionality by allowing
        custom metadata to be attached to each document. Useful for tracking
        collection IDs, upload timestamps, or user information.

        Args:
            additional_metadata (Optional[dict]): Additional metadata to add
                to each document. Defaults to None.

        Returns:
            List[Document]: List of Document objects with enhanced metadata.

        Raises:
            CorruptedPDFError: If the PDF cannot be parsed.
            EmptyPDFError: If the PDF contains no readable pages.

        Example:
            >>> loader = PDFLoader("document.pdf")
            >>> metadata = {"collection_id": "col_123", "user_id": "user_456"}
            >>> docs = loader.load_with_metadata(metadata)
        """
        documents = self.load()

        if additional_metadata:
            for doc in documents:
                doc.metadata.update(additional_metadata)
            self.logger.debug(
                f"Added additional metadata to {len(documents)} documents"
            )

        return documents

    def get_page_count(self) -> int:
        """
        Get the total number of pages in the PDF without loading content.

        This is a lightweight operation useful for validation and logging
        before performing full document loading.

        Returns:
            int: The number of pages in the PDF.

        Raises:
            CorruptedPDFError: If the PDF cannot be read.
            InvalidFilePathError: If the file is not readable.

        Example:
            >>> loader = PDFLoader("document.pdf")
            >>> pages = loader.get_page_count()
            >>> print(f"PDF has {pages} pages")
        """
        try:
            self._validate_file_readability()
            page_count = self._get_page_count_with_pypdf()

            self.logger.debug(f"PDF page count: {page_count}")
            return page_count

        except EmptyPDFError:
            return 0

        except Exception as e:
            error_msg = (
                f"Error reading PDF page count for {self.file_path}: {str(e)}"
            )
            self.logger.error(error_msg)
            raise CorruptedPDFError(error_msg) from e

    def __repr__(self) -> str:
        """Return string representation of the PDFLoader instance."""
        return f"PDFLoader(file_path='{self.file_path}')"

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"PDFLoader for '{self.file_path.name}'"

    def _load_with_pypdf(self) -> List[Document]:
        """Load PDF pages without importing heavyweight LangChain loader modules."""
        from pypdf import PdfReader
        import re

        reader = PdfReader(str(self.file_path))
        documents: List[Document] = []
        
        # Cleaning Stats
        pages_removed = 0
        references_removed = False
        original_chars = 0
        cleaned_chars = 0
        
        # 1. Extract raw pages to allow cross-page header/footer detection
        raw_pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            original_chars += len(text)
            raw_pages.append(text)
            
        # 2. Identify common headers and footers across the document
        start_lines = {}
        end_lines = {}
        for text in raw_pages:
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            if lines:
                start_lines[lines[0]] = start_lines.get(lines[0], 0) + 1
                end_lines[lines[-1]] = end_lines.get(lines[-1], 0) + 1
                
        # If a line appears at the start/end of >3 pages, it's likely a header/footer
        common_headers = {line for line, count in start_lines.items() if count > 3 and len(line) < 100}
        common_footers = {line for line, count in end_lines.items() if count > 3 and len(line) < 100}

        # Regex for identifying References/Bibliography sections
        ref_pattern = re.compile(r'^\s*(?:References|Bibliography|Works Cited)\s*$', re.IGNORECASE | re.MULTILINE)

        # 3. Process and clean pages
        for page_index, text in enumerate(raw_pages):
            # A. Remove everything after References are detected
            if references_removed:
                pages_removed += 1
                continue
                
            # B. Remove obvious title/cover pages
            if page_index == 0:
                text_len = len(text.strip())
                if text_len < 800:
                    upper_count = sum(1 for c in text if c.isupper())
                    alpha_count = sum(1 for c in text if c.isalpha())
                    # Skip if high uppercase ratio (title) or just very short
                    if (alpha_count > 0 and (upper_count / alpha_count) > 0.3) or text_len < 300:
                        pages_removed += 1
                        self.logger.debug(f"[CLEANING] Removed likely title/cover page (Page {page_index})")
                        continue
                        
            # A. Detect References/Bibliography section
            ref_match = ref_pattern.search(text)
            if ref_match:
                text = text[:ref_match.start()]
                references_removed = True
                self.logger.debug(f"[CLEANING] Removed references section starting at Page {page_index}")
                
            # C. Remove noisy headers/footers and page numbers
            lines = text.split('\n')
            cleaned_lines = []
            for i, line in enumerate(lines):
                stripped = line.strip()
                # Remove isolated page numbers
                if re.match(r'^\d+$', stripped):
                    continue
                # Remove repeated headers (top of page)
                if i < 3 and stripped in common_headers:
                    continue
                # Remove repeated footers (bottom of page)
                if i > len(lines) - 4 and stripped in common_footers:
                    continue
                cleaned_lines.append(line)
                
            text = '\n'.join(cleaned_lines)
            
            # D. Normalize whitespace
            # Remove excessive line breaks (3 or more -> 2)
            text = re.sub(r'\n{3,}', '\n\n', text)
            # Remove trailing spaces before newlines
            text = re.sub(r'[ \t]+\n', '\n', text)
            text = text.strip()
            
            if not text:
                pages_removed += 1
                continue
                
            cleaned_chars += len(text)
            
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": str(self.file_path),
                        "file_name": self.file_path.name,
                        "page": page_index,
                        "page_number": page_index,
                    },
                )
            )

        reduction = 100 * (1 - cleaned_chars / max(original_chars, 1)) if original_chars else 0
        self.logger.info(
            f"[CLEANING STATS] {self.file_path.name}: "
            f"Pages removed: {pages_removed}, "
            f"References removed: {references_removed}, "
            f"Text reduction: {reduction:.1f}% ({original_chars} -> {cleaned_chars} chars)"
        )

        return documents

    def _get_page_count_with_pypdf(self) -> int:
        """Return page count using the same lightweight backend as load()."""
        from pypdf import PdfReader

        reader = PdfReader(str(self.file_path))
        return len(reader.pages)


def load_pdf(file_path: str) -> List[Document]:
    """
    Convenience function to load a PDF file with a single call.

    This is a functional interface to the PDFLoader class for simple use cases
    where a one-off PDF load is needed without maintaining loader state.

    Args:
        file_path (str): Path to the PDF file to load.

    Returns:
        List[Document]: List of LangChain Document objects.

    Raises:
        InvalidFilePathError: If the file path is invalid.
        PDFFileNotFoundError: If the file does not exist.
        CorruptedPDFError: If the PDF cannot be parsed.
        EmptyPDFError: If the PDF contains no readable pages.

    Example:
        >>> documents = load_pdf("path/to/document.pdf")
        >>> print(f"Loaded {len(documents)} pages")
    """
    loader = PDFLoader(file_path)
    return loader.load()


def load_pdfs_from_directory(
    directory_path: str, recursive: bool = False
) -> dict[str, List[Document]]:
    """
    Load all PDF files from a directory.

    Loads all PDF files found in the specified directory and returns a dictionary
    mapping file paths to their loaded documents. Useful for batch processing
    multiple PDFs.

    Args:
        directory_path (str): Path to the directory containing PDF files.
        recursive (bool): If True, recursively search subdirectories.
            Defaults to False.

    Returns:
        dict[str, List[Document]]: Dictionary mapping file paths to loaded documents.
            Empty dict if no PDFs are found.

    Raises:
        InvalidFilePathError: If the directory path is invalid or not a directory.

    Example:
        >>> pdf_docs = load_pdfs_from_directory("./documents", recursive=True)
        >>> for file_path, documents in pdf_docs.items():
        ...     print(f"{file_path}: {len(documents)} pages")
    """
    dir_path = Path(directory_path)

    if not dir_path.exists():
        error_msg = f"Directory not found: {directory_path}"
        logger.error(error_msg)
        raise InvalidFilePathError(error_msg)

    if not dir_path.is_dir():
        error_msg = f"Path is not a directory: {directory_path}"
        logger.error(error_msg)
        raise InvalidFilePathError(error_msg)

    logger.info(f"Scanning directory for PDFs: {directory_path}")

    # Find all PDF files
    if recursive:
        pdf_files = list(dir_path.rglob("*.pdf"))
    else:
        pdf_files = list(dir_path.glob("*.pdf"))

    logger.info(f"Found {len(pdf_files)} PDF files in {directory_path}")

    # Load each PDF
    results = {}
    for pdf_file in pdf_files:
        try:
            loader = PDFLoader(str(pdf_file))
            documents = loader.load()
            results[str(pdf_file)] = documents
            logger.info(f"Successfully loaded: {pdf_file}")

        except PDFLoaderError as e:
            logger.error(f"Failed to load {pdf_file}: {str(e)}")
            results[str(pdf_file)] = []

        except Exception as e:
            logger.error(f"Unexpected error loading {pdf_file}: {str(e)}")
            results[str(pdf_file)] = []

    return results
