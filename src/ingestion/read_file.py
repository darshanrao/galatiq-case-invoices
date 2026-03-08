"""
Read invoice file from disk and detect format.

For PDF: extracts text via pdfplumber. If text is empty or very short (scanned PDF),
returns format "scanned_pdf" so ingestion can use vision extraction.
For images (JPEG, PNG, etc.): returns format "image" for vision extraction.
"""

from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
SCANNED_PDF_TEXT_THRESHOLD = 50


def read_invoice_file(path: str | Path) -> tuple[str, str]:
    """Read the invoice file and detect its format.

    Returns:
        Tuple of (raw_content, file_format).
        file_format is one of: "json", "csv", "xml", "txt", "image", "scanned_pdf".
        For "image" and "scanned_pdf", raw_content is the file path for vision extraction.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Invoice file not found: {path}")

    ext = path.suffix.lower()

    if ext in IMAGE_EXTENSIONS:
        return (str(path.resolve()), "image")

    if ext == ".pdf":
        return _read_pdf(path)

    with open(path, encoding="utf-8", errors="replace") as f:
        raw_content = f.read()
    fmt = ext.lstrip(".") if ext.lstrip(".") in ("txt", "json", "csv", "xml") else "txt"
    return (raw_content, fmt)


def _read_pdf(path: Path) -> tuple[str, str]:
    """Read PDF via pdfplumber. If text is empty/short, treat as scanned PDF."""
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        raw = "\n".join(pages)
        text_stripped = raw.strip()
        if len(text_stripped) < SCANNED_PDF_TEXT_THRESHOLD:
            return (str(path.resolve()), "scanned_pdf")
        return (raw, "txt")
    except Exception as exc:
        raise RuntimeError(f"PDF extraction failed: {exc}") from exc
