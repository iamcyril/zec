"""Text normalisation utilities for Zecpath AI Platform.

Keep this module dependency-free so it can be imported anywhere without
pulling in heavy ML libraries.
"""

from __future__ import annotations

import re


def normalize(text: str) -> str:
    r"""Normalize a raw text string for consistent downstream processing.

    Transformations applied (in order):
    1. Strip leading/trailing whitespace.
    2. Convert to lower-case.
    3. Collapse runs of whitespace (spaces, tabs, newlines) to a single space.

    Args:
        text: The raw input string.

    Returns:
        A cleaned, lower-cased string with normalised whitespace.

    Example:
        >>> normalize("  Hello   World\\n")
        'hello world'

    """
    text = text.strip()
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text
