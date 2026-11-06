"""Reader factory for Zecpath AI Platform.

Dispatches file-reading to the correct reader based on file extension:

==========  =========================================================
Extension   Strategy
==========  =========================================================
``.pdf``    :func:`~parsers.pdf_reader.read`
``.docx``   :func:`~parsers.docx_reader.read`
``.doc``    Convert to DOCX via LibreOffice headless, then DOCX reader
==========  =========================================================

Usage::

    from parsers.reader_factory import read_file

    result = read_file("path/to/resume.pdf")
    print(result["text"])

"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from parsers.docx_reader import ExtractResult, read as read_docx
from parsers.pdf_reader import read as read_pdf
from utils.logger import get_logger

logger = get_logger("zecpath.parsers.factory")

_SUPPORTED = {".pdf", ".docx", ".doc"}


# ---------------------------------------------------------------------------
# .doc → .docx converter
# ---------------------------------------------------------------------------


def _convert_doc_to_docx(path: Path) -> Path:
    """Convert an old ``.doc`` file to ``.docx`` via LibreOffice headless.

    The converted file is placed in a temporary directory.

    Args:
        path: Path to the source ``.doc`` file.

    Returns:
        Path to the converted ``.docx`` file.

    Raises:
        RuntimeError: If LibreOffice is not installed or conversion fails.

    """
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        raise RuntimeError(
            "LibreOffice ('soffice') is not installed or not on PATH. "
            "Install LibreOffice to read .doc files, or convert the file to .docx manually."
        )

    tmp_dir = tempfile.mkdtemp(prefix="zecpath_doc_")
    logger.info("Converting '%s' → .docx via LibreOffice (tmp: %s)", path.name, tmp_dir)

    try:
        result = subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to", "docx",
                "--outdir", tmp_dir,
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"LibreOffice conversion timed out for '{path.name}'") from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"LibreOffice conversion failed for '{path.name}': {result.stderr.strip()}"
        )

    converted = Path(tmp_dir) / path.with_suffix(".docx").name
    if not converted.exists():
        raise RuntimeError(
            f"LibreOffice ran but output DOCX not found at '{converted}'"
        )

    logger.info("Conversion complete → '%s'", converted.name)
    return converted


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_file(path: str | Path) -> ExtractResult:
    """Read a resume file and return a common :class:`ExtractResult`.

    Supported extensions: ``.pdf``, ``.docx``, ``.doc``.

    Args:
        path: Filesystem path to the resume file.

    Returns:
        An :class:`~parsers.docx_reader.ExtractResult` dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the extension is not supported.
        RuntimeError: If a ``.doc`` conversion fails (LibreOffice unavailable).

    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()

    if suffix not in _SUPPORTED:
        raise ValueError(
            f"Unsupported file extension '{suffix}'. "
            f"Supported: {', '.join(sorted(_SUPPORTED))}"
        )

    logger.info("reader_factory: routing '%s' (ext=%s)", path.name, suffix)

    if suffix == ".pdf":
        return read_pdf(path)

    if suffix == ".docx":
        return read_docx(path)

    # .doc — convert first
    converted_path = _convert_doc_to_docx(path)
    result = read_docx(converted_path)
    # Patch the result to reflect the original file
    return ExtractResult(
        file=str(path),
        type="doc",
        pages=result["pages"],
        method_used="libreoffice+" + result["method_used"],
        ocr_used=result["ocr_used"],
        text=result["text"],
    )
