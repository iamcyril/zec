"""Resume parser for Zecpath AI Platform.

Extracts structured information from raw resume text using regex patterns and
a curated known-skills vocabulary.  Intentionally lightweight — no ML models
required at this stage.

Supported file types
--------------------
- ``.txt`` — plain text (read directly)
- ``.pdf`` — via :mod:`parsers.pdf_reader` (PyMuPDF + OCR fallback)
- ``.docx`` — via :mod:`parsers.docx_reader` (python-docx)
- ``.doc`` — converted via LibreOffice, then DOCX reader
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("zecpath.parsers.resume")

# Lazy import to avoid circular-import issues at module load time.
# reader_factory is only needed inside parse_file().

# ---------------------------------------------------------------------------
# Known-skills vocabulary
# ---------------------------------------------------------------------------
# Word-boundary patterns.  node.js requires a special pattern because
# the dot is not part of \w and would not be captured by plain \b.
_SKILL_PATTERNS: dict[str, re.Pattern[str]] = {
    "python": re.compile(r"\bpython\b", re.IGNORECASE),
    "java": re.compile(r"\bjava\b", re.IGNORECASE),
    "javascript": re.compile(r"\bjavascript\b", re.IGNORECASE),
    "typescript": re.compile(r"\btypescript\b", re.IGNORECASE),
    "react": re.compile(r"\breact\b", re.IGNORECASE),
    # node.js: match the literal token "node.js" (case-insensitive).
    # (?<!\w) / (?!\w) act as word boundaries around the full token.
    "node.js": re.compile(r"(?<!\w)node\.js(?!\w)", re.IGNORECASE),
    "mongodb": re.compile(r"\bmongodb\b", re.IGNORECASE),
    "express": re.compile(r"\bexpress\b", re.IGNORECASE),
    "sql": re.compile(r"\bsql\b", re.IGNORECASE),
    "postgresql": re.compile(r"\bpostgresql\b", re.IGNORECASE),
    "aws": re.compile(r"\baws\b", re.IGNORECASE),
    "docker": re.compile(r"\bdocker\b", re.IGNORECASE),
    "kubernetes": re.compile(r"\bkubernetes\b", re.IGNORECASE),
    "figma": re.compile(r"\bfigma\b", re.IGNORECASE),
    "git": re.compile(r"\bgit\b", re.IGNORECASE),
}

# Regex for common email addresses.
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Regex for phone numbers (international and local formats).
_PHONE_RE = re.compile(
    r"(?:\+\d{1,3}[\s\-]?)?"  # optional country code
    r"(?:\(?\d{2,4}\)?[\s\-]?)?"  # optional area code
    r"\d{3,4}[\s\-]?\d{4}"  # subscriber number
)

# Patterns for extracting years of experience from common phrasings.
_EXPERIENCE_PATTERNS = [
    re.compile(r"(\d+)\+?\s*years?\s+of\s+experience", re.IGNORECASE),
    re.compile(r"(\d+)\+?\s*years?\s+experience", re.IGNORECASE),
    re.compile(r"experience\s*[:\-]?\s*(\d+)\+?\s*years?", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ParsedResume:
    """Structured output from the resume parser.

    Attributes:
        email: First email address found in the text, or empty string.
        phone: First phone number found in the text, or empty string.
        skills: Sorted list of recognised skill names (lowercased canonical form).
        experience_years: Estimated total years of experience (0 if not found).
        raw_text: The original, unmodified input text.

    """

    email: str
    phone: str
    skills: list[str] = field(default_factory=list)
    experience_years: int = 0
    raw_text: str = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_text(text: str) -> ParsedResume:
    """Parse a resume from a plain-text string.

    Args:
        text: Raw resume content as a string.

    Returns:
        A :class:`ParsedResume` populated with extracted fields.

    """
    email_match = _EMAIL_RE.search(text)
    email = email_match.group(0) if email_match else ""

    phone_match = _PHONE_RE.search(text)
    phone = phone_match.group(0).strip() if phone_match else ""

    skills: list[str] = sorted(
        skill for skill, pattern in _SKILL_PATTERNS.items() if pattern.search(text)
    )

    experience_years = 0
    for pattern in _EXPERIENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            experience_years = int(match.group(1))
            break

    logger.info(
        "Resume parsed",
        extra={
            "email_found": bool(email),
            "skills_count": len(skills),
            "experience_years": experience_years,
        },
    )
    return ParsedResume(
        email=email,
        phone=phone,
        skills=skills,
        experience_years=experience_years,
        raw_text=text,
    )


def parse_file(path: str | Path) -> ParsedResume:
    """Parse a resume from a file on disk.

    Supported extensions: ``.txt``, ``.pdf``, ``.docx``, ``.doc``.
    PDF and DOCX/DOC files are routed through
    :func:`~parsers.reader_factory.read_file` before text extraction.

    Args:
        path: Filesystem path to the resume file.

    Returns:
        A :class:`ParsedResume` populated with extracted fields.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the extension is not supported.

    """
    from parsers.reader_factory import read_file  # noqa: PLC0415

    path = Path(path)
    if path.suffix.lower() == ".txt":
        text = path.read_text(encoding="utf-8")
        return parse_text(text)

    # Delegate binary formats to the reader factory
    result = read_file(path)
    return parse_text(result["text"])
