# Test Data Directory

This directory contains test data files for the RAG system tests.

## Sample PDF for PDF Loader Tests

To run the `test_pdf_loader.py` script, you need to place a sample PDF file here:

```
backend/test_data/sample.pdf
```

### Getting a Sample PDF

You can use any PDF file. Here are some options:

1. **Create a simple PDF**: Use any PDF creation tool or online service to create a test document
2. **Download a sample**: Find a public domain PDF online (e.g., from Project Gutenberg)
3. **Convert from text**: Convert a text file to PDF using tools like LibreOffice or Python libraries

### Python-based solution (one-time setup)

If you have `reportlab` installed, you can create a simple sample PDF:

```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("backend/test_data/sample.pdf", pagesize=letter)
c.drawString(100, 750, "Sample PDF Document")
c.drawString(100, 720, "This is a test document for the PDF loader module.")
c.showPage()
c.save()
```

Or if you have `fpdf`, you can use that instead.

### Expected Output

Once you have placed `sample.pdf` in this directory, running the test script should output:

```
================================================================================
                         PDF LOADER TEST SCRIPT
================================================================================

[... logging output ...]

================================================================================
                      IMPORTING PDF LOADER MODULE
================================================================================

✓ Successfully imported PDFLoader

================================================================================
                        CHECKING FOR SAMPLE PDF
================================================================================

✓ Sample PDF found at: backend/test_data/sample.pdf

================================================================================
                            LOADING PDF
================================================================================

✓ PDF loaded successfully

================================================================================
                        PDF LOADING RESULTS
================================================================================

Number of documents loaded: X

[... document metadata and text preview ...]

================================================================================
                           TEST RESULT
================================================================================

✓ PDF LOADER TEST PASSED
```

## Running the Test

From the `backend` directory:

```bash
python test_pdf_loader.py
```

Or from the project root:

```bash
python backend/test_pdf_loader.py
```

## What the Test Checks

- ✓ PDFLoader module import
- ✓ Sample PDF file existence
- ✓ PDF loading and document extraction
- ✓ Document count
- ✓ Document metadata
- ✓ Text content extraction

## Troubleshooting

- **"Sample PDF not found"**: Place a PDF file at `backend/test_data/sample.pdf`
- **Import errors**: Ensure the backend directory is properly set up with all RAG modules
- **Permission errors**: Check that the file has read permissions
- **Corrupted PDF**: Try with a different PDF file

---

**Note**: The test script handles errors gracefully and provides detailed logging output for debugging.
