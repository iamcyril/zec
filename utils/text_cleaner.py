r"""Resume text cleaning pipeline for Zecpath AI Platform.

Transforms raw extracted text into a normalised, consistent form ready for
downstream parsing and section detection.  All transformations preserve the
original case of body text — only section headings are title-cased during
the synonym-mapping step so that tech terms like ``React`` and ``Node.js``
are left intact.

Pipeline (applied in order)
----------------------------
1. Unicode NFKC normalisation (compatibility decomposition + composition)
2. Strip control characters (C0/C1 ranges) and zero-width / invisible chars
3. Fix soft-hyphen line-breaks (``word-\\n`` → ``word``)
4. Normalise bullet markers to ``-``
5. Collapse runs of spaces/tabs on each line; preserve paragraph breaks
6. Normalise section headings via synonym map
7. Strip trailing whitespace from every line

Public API
----------
:func:`clean` — main entry point, returns a :class:`CleanedResult` dict.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TypedDict

from utils.logger import get_logger

logger = get_logger("zecpath.utils.text_cleaner")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


class CleanedResult(TypedDict):
    """Output of the text-cleaning pipeline."""

    text: str  # Fully cleaned text
    sections: list[str]  # Canonical section headings detected (in order)


# ---------------------------------------------------------------------------
# Heading synonym map
# ---------------------------------------------------------------------------
# Keys are canonical names; values are sets of alternate title strings that
# map to that canonical name (all uppercase for case-insensitive matching).

_HEADING_SYNONYMS: dict[str, set[str]] = {
    "Summary": {
        "SUMMARY",
        "PROFESSIONAL SUMMARY",
        "PROFILE",
        "PROFESSIONAL PROFILE",
        "OBJECTIVE",
        "CAREER OBJECTIVE",
        "ABOUT ME",
        "ABOUT",
        "INTRODUCTION",
        "OVERVIEW",
    },
    "Skills": {
        "SKILLS",
        "TECHNICAL SKILLS",
        "CORE COMPETENCIES",
        "KEY SKILLS",
        "SKILLS & COMPETENCIES",
        "SKILLS AND COMPETENCIES",
        "TECHNOLOGIES",
        "TECH STACK",
        "COMPETENCIES",
        "AREAS OF EXPERTISE",
        "EXPERTISE",
    },
    "Experience": {
        "EXPERIENCE",
        "WORK EXPERIENCE",
        "PROFESSIONAL EXPERIENCE",
        "WORK HISTORY",
        "EMPLOYMENT",
        "EMPLOYMENT HISTORY",
        "CAREER HISTORY",
        "JOB HISTORY",
        "PROFESSIONAL BACKGROUND",
    },
    "Education": {
        "EDUCATION",
        "ACADEMIC BACKGROUND",
        "ACADEMIC HISTORY",
        "QUALIFICATIONS",
        "ACADEMIC QUALIFICATIONS",
        "EDUCATION & TRAINING",
        "EDUCATIONAL BACKGROUND",
        "DEGREES",
    },
    "Projects": {
        "PROJECTS",
        "PERSONAL PROJECTS",
        "SIDE PROJECTS",
        "PORTFOLIO",
        "KEY PROJECTS",
        "NOTABLE PROJECTS",
        "OPEN SOURCE",
        "OPEN-SOURCE CONTRIBUTIONS",
    },
    "Certifications": {
        "CERTIFICATIONS",
        "CERTIFICATES",
        "CERTIFICATION",
        "LICENSES",
        "LICENSES & CERTIFICATIONS",
        "CREDENTIALS",
        "PROFESSIONAL CERTIFICATIONS",
        "ACCREDITATIONS",
    },
}

# Build a reverse lookup: UPPERCASE_SYNONYM -> canonical name
_SYNONYM_LOOKUP: dict[str, str] = {}
for _canonical, _synonyms in _HEADING_SYNONYMS.items():
    for _syn in _synonyms:
        _SYNONYM_LOOKUP[_syn] = _canonical
    # The canonical name itself maps to itself
    _SYNONYM_LOOKUP[_canonical.upper()] = _canonical


# ---------------------------------------------------------------------------
# Regex constants
# ---------------------------------------------------------------------------

# Characters in Unicode general categories Cc (control) and Cf (format)
# that we want to strip.  We keep \t, \n, \r which are useful whitespace.
_CTRL_CHAR_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f"  # C0 control (excl. \t\n\r)
    r"\x80-\x9f"  # C1 control
    r"\u00ad"  # soft hyphen (U+00AD)
    r"\u200b-\u200f"  # zero-width chars
    r"\u2028\u2029"  # line/paragraph separator
    r"\ufeff"  # BOM / zero-width no-break space
    r"\u2060\u2061\u2062\u2063\u2064"  # word joiner and invisible operators
    r"]"
)

# Hyphenated line-breaks: "some-\nword" → "someword", "some-\n  word" → "someword"
_HYPHEN_BREAK_RE = re.compile(r"-\n\s*")

# Bullet markers to normalise → "-"
_BULLET_RE = re.compile(r"^[\s]*[•▪●○◦▸►➤✔✓★→\-–—*]+[\s]+", re.MULTILINE)

# Runs of horizontal whitespace (spaces + tabs) within a line
_HORIZ_WS_RE = re.compile(r"[ \t]+")

# Three or more consecutive newlines → two newlines (one blank line)
_MULTI_NL_RE = re.compile(r"\n{3,}")


# ---------------------------------------------------------------------------
# Pipeline steps (private)
# ---------------------------------------------------------------------------


def _unicode_normalise(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _strip_control_chars(text: str) -> str:
    return _CTRL_CHAR_RE.sub("", text)


def _fix_hyphen_breaks(text: str) -> str:
    """Join words split across lines with a trailing hyphen."""
    return _HYPHEN_BREAK_RE.sub("", text)


def _normalise_bullets(text: str) -> str:
    """Replace any bullet marker at the start of a line with '- '."""
    return _BULLET_RE.sub("- ", text)


def _collapse_whitespace(text: str) -> str:
    """Collapse horizontal whitespace on each line; trim paragraph gaps."""
    lines = text.split("\n")
    lines = [_HORIZ_WS_RE.sub(" ", line).rstrip() for line in lines]
    text = "\n".join(lines)
    text = _MULTI_NL_RE.sub("\n\n", text)
    return text.strip()


def _normalise_headings(text: str, detected: list[str]) -> str:
    """Replace known heading synonyms with their canonical name.

    A heading line is defined as a line whose stripped, uppercased content
    matches an entry in :data:`_SYNONYM_LOOKUP`.  Only such lines are
    case-modified; all other lines are left as-is.
    """
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if upper in _SYNONYM_LOOKUP:
            canonical = _SYNONYM_LOOKUP[upper]
            result.append(canonical)
            if canonical not in detected:
                detected.append(canonical)
        else:
            result.append(line)
    return "\n".join(result)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def clean(text: str) -> CleanedResult:
    """Run the full cleaning pipeline on raw extracted text.

    Args:
        text: Raw text as returned by a file reader.

    Returns:
        A :class:`CleanedResult` dict containing:

        - ``text``: Cleaned text string.
        - ``sections``: List of canonical section headings found, in order.

    """
    if not text:
        logger.warning("text_cleaner.clean() received empty input")
        return CleanedResult(text="", sections=[])

    detected_sections: list[str] = []

    text = _unicode_normalise(text)
    text = _strip_control_chars(text)
    text = _fix_hyphen_breaks(text)
    text = _normalise_bullets(text)
    text = _collapse_whitespace(text)
    text = _normalise_headings(text, detected_sections)
    # Final whitespace pass after heading normalisation
    text = _collapse_whitespace(text)

    logger.info(
        "text_cleaner: %d chars, sections detected: %s",
        len(text),
        detected_sections or "(none)",
    )

    return CleanedResult(text=text, sections=detected_sections)
