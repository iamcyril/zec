"""Pre-screening question bank for Zecpath AI Platform.

Returns an ordered list of standard voice-screening questions that the
AI screening agent asks every candidate in a consistent sequence.

Questions are designed to be open, non-discriminatory, and relevant only
to professional qualifications and logistics.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Question definitions
# ---------------------------------------------------------------------------

_QUESTIONS: list[dict[str, str]] = [
    {
        "key": "introduction",
        "text": (
            "Could you please introduce yourself and give us a brief overview "
            "of your professional background?"
        ),
    },
    {
        "key": "education",
        "text": (
            "Could you tell us about your educational qualifications and any "
            "certifications that are relevant to this role?"
        ),
    },
    {
        "key": "experience",
        "text": (
            "How many years of professional experience do you have, and what "
            "types of projects or industries have you worked in?"
        ),
    },
    {
        "key": "skills",
        "text": (
            "Which technical skills and tools are you most proficient in, "
            "and how have you applied them in your recent roles?"
        ),
    },
    {
        "key": "location",
        "text": (
            "Are you currently located in, or willing to relocate to, the "
            "area where this position is based?"
        ),
    },
    {
        "key": "notice_period",
        "text": (
            "What is your current notice period, and when would you be "
            "available to start if selected?"
        ),
    },
    {
        "key": "expected_salary",
        "text": (
            "What is your expected compensation range for this role, "
            "keeping in mind our posted salary band?"
        ),
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_questions() -> list[dict[str, str]]:
    """Return the ordered list of pre-screening interview questions.

    Each question is a dict with two keys:

    * ``"key"`` — a unique machine-readable identifier for the question.
    * ``"text"`` — the full question text to be presented to the candidate.

    Returns:
        A list of exactly 7 question dicts in presentation order.

    """
    return list(_QUESTIONS)  # return a shallow copy to protect the source list
