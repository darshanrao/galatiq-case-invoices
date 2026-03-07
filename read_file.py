"""
Read invoice file from disk and detect format.

For PDF: extracts text via pdfplumber.
Returns raw_content and file_format for downstream parsers.
"""

import os
from pathlib import Path


def read_invoice_file(path: str | Path) -> tuple[str, str]:
    """Read the invoice file and detect its format.

    Args:
        path: Path to the invoice file.

    Returns:
        Tuple of (raw_content, file_format).
        file_format is one of: "json", "csv", "xml", "txt".
        PDFs are converted to text; format returned as "txt".

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Invoice file not found: {path}")

    ext = path.suffix.lower().lstrip(".")

    if ext == "pdf":
        raw_content, file_format = _read_pdf(path)
    else:
        with open(path, encoding="utf-8") as f:
            raw_content = f.read()
        file_format = ext if ext in ("txt", "json", "csv", "xml") else "txt"

    return (raw_content, file_format)


def _read_pdf(path: Path) -> tuple[str, str]:
    """Read PDF and extract text via pdfplumber."""
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return ("\n".join(pages), "txt")
    except Exception as exc:
        raise RuntimeError(f"PDF extraction failed: {exc}") from exc
