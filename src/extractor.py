"""
PDF text extractor using pdfplumber.

This module handles the mechanical work of pulling raw text out of PDF pages.
The actual transaction extraction is done by Claude Code (the AI assistant)
which reads the PDF directly and writes structured output via save.py.
"""

from pathlib import Path

import pdfplumber


def extract_text(pdf_path: Path) -> str:
    """Extract all text from a PDF, one page at a time, preserving layout."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=True) or ""
            if text.strip():
                pages.append(f"--- Page {i} ---\n{text}")
    return "\n\n".join(pages)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.extractor <path/to/statement.pdf>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    print(extract_text(pdf_path))
