"""Extraction orchestrator for Zecpath AI Platform.

Ties together the reader factory and text cleaner, then persists outputs:

- ``data/extracted/<stem>.txt`` — cleaned plain text
- ``data/extracted/<stem>.json`` — structured JSON record

Any per-file exception is caught, logged, and returned as an error record
so that batch processing never crashes on a bad file.

Usage::

    from parsers.extractor import extract_file

    record = extract_file("data/raw/jane_smith.pdf")
    print(record)   # {"status": "ok", "file": ..., "sections": [...], ...}

"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from parsers.reader_factory import read_file
from utils.logger import get_logger, log_ai_event
from utils.text_cleaner import clean

logger = get_logger("zecpath.parsers.extractor")

_EXTRACTED_DIR = Path("data/extracted")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_dirs() -> None:
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    _EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)


def _write_outputs(stem: str, cleaned_text: str, record: dict[str, Any]) -> None:
    """Write .txt and .json artefacts to data/extracted/."""
    txt_path = _EXTRACTED_DIR / f"{stem}.txt"
    json_path = _EXTRACTED_DIR / f"{stem}.json"

    txt_path.write_text(cleaned_text, encoding="utf-8")
    json_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(
        "Extractor: wrote '%s.txt' and '%s.json' to %s",
        stem,
        stem,
        _EXTRACTED_DIR,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_file(path: str | Path) -> dict[str, Any]:
    """Extract, clean, and persist text from a single resume file.

    Args:
        path: Path to the resume file (PDF, DOCX, or DOC).

    Returns:
        A dict with at minimum:

        - ``status``: ``"ok"`` or ``"error"``
        - ``file``: Original file path string

        On success, also includes:

        - ``type``, ``pages``, ``method_used``, ``ocr_used``
        - ``sections``: Detected canonical section headings
        - ``char_count``: Character count of cleaned text
        - ``text``: Cleaned text (first 500 chars preview)

        On error, also includes:

        - ``error``: Error class and message

    """
    path = Path(path)
    _ensure_dirs()

    logger.info("Extractor: starting '%s'", path.name)

    try:
        # 1. Read raw text
        extract_result = read_file(path)
        raw_text = extract_result["text"]

        warnings_list: list[str] = []
        if not raw_text.strip():
            msg = f"'{path.name}' produced no text after reading"
            logger.warning("Extractor: %s", msg)
            warnings_list.append(msg)

        # 2. Clean text
        cleaned = clean(raw_text)
        cleaned_text = cleaned["text"]
        sections = cleaned["sections"]

        # 3. Build JSON record
        record: dict[str, Any] = {
            "file": str(path),
            "type": extract_result["type"],
            "pages": extract_result["pages"],
            "method_used": extract_result["method_used"],
            "ocr_used": extract_result["ocr_used"],
            "sections": sections,
            "char_count": len(cleaned_text),
            "warnings": warnings_list,
            "text": cleaned_text,
        }

        # 4. Persist
        stem = path.stem
        _write_outputs(stem, cleaned_text, record)

        # 5. Structured AI event log (no PII — only metadata)
        log_ai_event(
            "extraction.completed",
            file_stem=stem,
            file_type=extract_result["type"],
            pages=extract_result["pages"],
            char_count=len(cleaned_text),
            method_used=extract_result["method_used"],
            ocr_used=extract_result["ocr_used"],
            sections_found=sections,
            has_warnings=bool(warnings_list),
        )

        logger.info(
            "Extractor: '%s' completed — %d chars, sections=%s, ocr=%s",
            path.name,
            len(cleaned_text),
            sections,
            extract_result["ocr_used"],
        )

        return {"status": "ok", **record}

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Extractor: failed to process '%s': %s",
            path.name,
            exc,
            exc_info=True,
        )
        log_ai_event(
            "extraction.failed",
            file_stem=path.stem,
            error_type=type(exc).__name__,
        )
        return {
            "status": "error",
            "file": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
