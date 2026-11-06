"""PDF text extraction for Zecpath AI Platform.

Extraction strategy (applied per page in order):

1. **PyMuPDF** (primary) — sorts text blocks by (y, x) so two-column
   layouts are read left-to-right, top-to-bottom correctly.
2. **pdfplumber** (table supplement) — extracts tabular content that
   PyMuPDF may miss.
3. **OCR fallback** (pytesseract + pdf2image) — triggered when a page
   yields fewer than :attr:`OCR_CHAR_THRESHOLD` characters after the
   primary pass.  The ``ocr_used`` flag is set in the returned result.
   If Tesseract is not installed the fallback is skipped with a warning.

The result conforms to the common :class:`~parsers.docx_reader.ExtractResult`
TypedDict shared across all readers.
"""

from __future__ import annotations

import importlib
import importlib.util
import shutil
from pathlib import Path
from typing import Any

from parsers.docx_reader import ExtractResult
from utils.logger import get_logger

logger = get_logger("zecpath.parsers.pdf")

# Characters per page below which OCR is attempted.
OCR_CHAR_THRESHOLD = 50

# ---------------------------------------------------------------------------
# Optional dependency checks (soft)
# ---------------------------------------------------------------------------

def _has_tesseract() -> bool:
    """Return True if the Tesseract binary is discoverable on PATH."""
    return shutil.which("tesseract") is not None


def _fitz_available() -> bool:
    """Return True if PyMuPDF (fitz) is importable."""
    return importlib.util.find_spec("fitz") is not None


def _pdfplumber_available() -> bool:
    """Return True if pdfplumber is importable."""
    return importlib.util.find_spec("pdfplumber") is not None


def _pdf2image_available() -> bool:
    """Return True if pdf2image is importable."""
    return importlib.util.find_spec("pdf2image") is not None


def _pytesseract_available() -> bool:
    """Return True if pytesseract is importable."""
    return importlib.util.find_spec("pytesseract") is not None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_page_pymupdf(page: Any) -> str:
    """Extract text from one PyMuPDF page, sorted by (y, x) position.

    Sorting ensures two-column text reads column-by-column rather than
    interleaving lines from both columns.

    Args:
        page: A ``fitz.Page`` object (typed as Any to avoid hard fitz import).

    Returns:
        Extracted page text with blocks sorted top-to-bottom, left-to-right.
    """
    blocks = page.get_text("blocks")  # type: ignore[attr-defined]
    # Each block: (x0, y0, x1, y1, text, block_no, block_type)
    # block_type 0 = text, 1 = image; skip images
    text_blocks = [b for b in blocks if b[6] == 0]
    # Sort by vertical position first, then horizontal
    text_blocks.sort(key=lambda b: (round(b[1] / 10) * 10, b[0]))
    return "\n".join(str(b[4]).strip() for b in text_blocks if str(b[4]).strip())


def _extract_tables_pdfplumber(pdf_path: Path, page_num: int) -> str:
    """Extract table text from a single page using pdfplumber.

    Args:
        pdf_path: Path to the PDF file.
        page_num: 0-indexed page number.

    Returns:
        Tab-separated table cells joined by newlines, or empty string.
    """
    import pdfplumber  # noqa: PLC0415

    lines: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        if page_num >= len(pdf.pages):
            return ""
        page = pdf.pages[page_num]
        tables = page.extract_tables()
        for table in tables:
            for row in table:
                cells = [cell or "" for cell in row]
                lines.append("\t".join(cells))
    return "\n".join(lines)


def _ocr_page(pdf_path: Path, page_num: int, dpi: int = 300) -> str:
    """Render one PDF page to an image and OCR it with Tesseract.

    Args:
        pdf_path: Path to the PDF.
        page_num: 0-indexed page number.
        dpi: Render resolution (300 is safe for most documents).

    Returns:
        OCR'd text string, or empty string if OCR unavailable/fails.
    """
    if not _has_tesseract():
        logger.warning(
            "OCR requested for page %d of '%s' but Tesseract not found on PATH — skipping",
            page_num + 1,
            pdf_path.name,
        )
        return ""
    if not _pdf2image_available() or not _pytesseract_available():
        logger.warning(
            "OCR skipped: pdf2image or pytesseract not installed",
        )
        return ""

    from pdf2image import convert_from_path  # noqa: PLC0415
    import pytesseract  # noqa: PLC0415

    images = convert_from_path(
        str(pdf_path),
        dpi=dpi,
        first_page=page_num + 1,
        last_page=page_num + 1,
    )
    if not images:
        return ""
    return pytesseract.image_to_string(images[0])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read(path: str | Path) -> ExtractResult:
    """Extract all text from a ``.pdf`` file.

    Args:
        path: Filesystem path to the ``.pdf`` file.

    Returns:
        An :class:`~parsers.docx_reader.ExtractResult` dict with
        ``type="pdf"``.  ``method_used`` is one of ``"pymupdf"``,
        ``"pymupdf+ocr"``, or ``"ocr"`` depending on which paths fired.
        ``ocr_used`` is ``True`` when OCR was triggered for at least one page.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If PyMuPDF is not installed or the file cannot be opened.

    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not _fitz_available():
        raise ValueError(
            "PyMuPDF (fitz) is required for PDF reading but is not installed. "
            "Run: pip install PyMuPDF"
        )

    import fitz  # noqa: PLC0415

    logger.info("PDF reader: opening %s", path.name)

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        raise ValueError(f"Cannot open '{path.name}' as a PDF: {exc}") from exc

    page_count = len(doc)
    page_texts: list[str] = []
    ocr_used = False
    methods_used: set[str] = set()

    for page_num in range(page_count):
        page = doc[page_num]

        # --- Primary: PyMuPDF sorted blocks ---
        primary_text = _extract_page_pymupdf(page)
        methods_used.add("pymupdf")

        # --- Supplement: pdfplumber tables ---
        table_text = ""
        if _pdfplumber_available():
            try:
                table_text = _extract_tables_pdfplumber(path, page_num)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "pdfplumber failed on page %d of '%s': %s",
                    page_num + 1, path.name, exc,
                )

        combined = "\n".join(t for t in [primary_text, table_text] if t).strip()

        # --- OCR fallback ---
        if len(combined) < OCR_CHAR_THRESHOLD:
            logger.warning(
                "PDF reader: page %d of '%s' has only %d chars — attempting OCR",
                page_num + 1, path.name, len(combined),
            )
            ocr_text = _ocr_page(path, page_num)
            if ocr_text.strip():
                combined = ocr_text.strip()
                ocr_used = True
                methods_used.add("ocr")
                logger.info(
                    "OCR produced %d chars for page %d of '%s'",
                    len(combined), page_num + 1, path.name,
                )

        if combined:
            page_texts.append(combined)

    doc.close()

    full_text = "\n\n".join(page_texts)
    char_count = len(full_text)

    method_label = "+".join(sorted(methods_used))

    logger.info(
        "PDF reader: '%s' → %d pages, %d chars, method=%s, ocr=%s",
        path.name, page_count, char_count, method_label, ocr_used,
    )

    return ExtractResult(
        file=str(path),
        type="pdf",
        pages=page_count,
        method_used=method_label,
        ocr_used=ocr_used,
        text=full_text,
    )
