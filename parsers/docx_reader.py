"""DOCX text extraction for Zecpath AI Platform.

Reads every text-bearing element of a ``.docx`` file in document order:

- Body paragraphs
- Table cells (row → column order)
- Section headers and footers
- Drawing / text-box shapes embedded in the document body

Returns a common :class:`ExtractResult` dict shared by all readers.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, TypedDict

from docx import Document as _DocxDocument
from docx.document import Document as DocxDoc
from docx.oxml.ns import qn

from utils.logger import get_logger

logger = get_logger("zecpath.parsers.docx")


# ---------------------------------------------------------------------------
# Shared result type (also imported by pdf_reader and reader_factory)
# ---------------------------------------------------------------------------


class ExtractResult(TypedDict):
    """Uniform output produced by every file reader."""

    file: str           # Original file path as string
    type: str           # MIME-ish label: "docx" | "pdf" | "doc"
    pages: int          # Page / section count (best estimate)
    method_used: str    # e.g. "python-docx", "pymupdf", "ocr"
    ocr_used: bool      # True when OCR was needed
    text: str           # Full extracted text (pre-clean)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iter_paragraph_texts(doc: DocxDoc) -> list[str]:
    """Yield text from every body paragraph in order."""
    return [para.text for para in doc.paragraphs]


def _iter_table_texts(doc: DocxDoc) -> list[str]:
    """Yield text from every table cell in row-major order."""
    lines: list[str] = []
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell_text = cell.text.strip()
                if cell_text:
                    lines.append(cell_text)
    return lines


def _iter_header_footer_texts(doc: DocxDoc) -> list[str]:
    """Yield text from section headers and footers."""
    lines: list[str] = []
    for section in doc.sections:
        for hf in (section.header, section.footer):
            if hf is not None:
                for para in hf.paragraphs:
                    if para.text.strip():
                        lines.append(para.text)
    return lines


def _iter_textbox_texts(doc: DocxDoc) -> list[str]:
    """Yield text from drawing/text-box shapes in the document body.

    Text boxes are stored inside ``<w:drawing>`` or ``<mc:AlternateContent>``
    elements using the ``<w:txbxContent>`` XML tag.
    """
    lines: list[str] = []
    txbx_tag = qn("w:txbxContent")
    p_tag = qn("w:p")
    t_tag = qn("w:t")

    for element in doc.element.body.iter():
        if element.tag == txbx_tag:
            for para_el in element.iter(p_tag):
                text = "".join(t.text or "" for t in para_el.iter(t_tag))
                if text.strip():
                    lines.append(text)
    return lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read(path: str | Path) -> ExtractResult:
    """Extract all text from a ``.docx`` file.

    Args:
        path: Filesystem path to the ``.docx`` file.

    Returns:
        An :class:`ExtractResult` dict with ``type="docx"``,
        ``method_used="python-docx"``, and ``ocr_used=False``.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If the file cannot be opened as a valid DOCX document.

    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    logger.info("DOCX reader: opening %s", path.name)

    try:
        # python-docx throws various exceptions on corrupt files; catch broadly.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # suppress lxml namespace warnings
            doc: DocxDoc = _DocxDocument(str(path))
    except Exception as exc:
        raise ValueError(f"Cannot open '{path.name}' as a DOCX document: {exc}") from exc

    # Collect text from every source in logical document order
    parts: list[str] = []
    parts.extend(_iter_paragraph_texts(doc))

    table_lines = _iter_table_texts(doc)
    if table_lines:
        parts.append("\n".join(table_lines))

    hf_lines = _iter_header_footer_texts(doc)
    if hf_lines:
        parts.append("\n".join(hf_lines))

    textbox_lines = _iter_textbox_texts(doc)
    if textbox_lines:
        parts.append("\n".join(textbox_lines))

    full_text = "\n".join(line for line in parts if line)
    char_count = len(full_text)

    # Estimate page count via section count (a rough but dependency-free proxy)
    page_estimate = len(doc.sections) or 1

    if char_count == 0:
        logger.warning(
            "DOCX reader: '%s' produced no text — file may be empty or image-only",
            path.name,
        )
    else:
        logger.info(
            "DOCX reader: '%s' → %d chars, ~%d section(s), tables=%d, textboxes=%d",
            path.name,
            char_count,
            page_estimate,
            len(doc.tables),
            len(textbox_lines),
        )

    return ExtractResult(
        file=str(path),
        type="docx",
        pages=page_estimate,
        method_used="python-docx",
        ocr_used=False,
        text=full_text,
    )
