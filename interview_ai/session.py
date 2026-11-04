"""Interview session management for Zecpath AI Platform.

Provides a simple, auditable state machine for AI-assisted interview sessions:

    created → in_progress → completed | flagged

Lifecycle methods
-----------------
* :meth:`InterviewSession.start` — transition ``created → in_progress``.
* :meth:`InterviewSession.add_turn` — append a Q&A exchange.
* :meth:`InterviewSession.end` — transition to ``completed`` or ``flagged``.

All state transitions are recorded via :func:`~utils.logger.log_ai_event`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from utils.logger import get_logger, log_ai_event

logger = get_logger("zecpath.interview")


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class InterviewStatus(str, Enum):
    """Possible lifecycle states for an :class:`InterviewSession`.

    Inherits from ``str`` so values can be serialised directly to JSON.
    """

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FLAGGED = "flagged"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class InterviewSession:
    """Stateful record of a single AI interview session.

    Attributes:
        session_id: Unique identifier for this session (UUID4 string).
        candidate_id: Opaque identifier for the candidate (never PII).
        job_id: Identifier for the associated job posting.
        status: Current lifecycle status.
        turns: Ordered list of Q&A turn dicts
            (keys: ``question``, ``answer``).

    """

    candidate_id: str
    job_id: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: InterviewStatus = InterviewStatus.CREATED
    turns: list[dict[str, Any]] = field(default_factory=list)

    # ── Lifecycle methods ────────────────────────────────────────────────

    def start(self) -> None:
        """Transition the session from ``created`` to ``in_progress``.

        Raises:
            RuntimeError: If the session is not in ``created`` state.

        """
        if self.status != InterviewStatus.CREATED:
            raise RuntimeError(
                f"Cannot start session {self.session_id!r}: "
                f"already in state '{self.status.value}'."
            )
        self.status = InterviewStatus.IN_PROGRESS
        log_ai_event(
            "interview.started",
            session_id=self.session_id,
            candidate_id=self.candidate_id,
            job_id=self.job_id,
        )
        logger.info(
            "Interview session %s started (candidate=%s, job=%s)",
            self.session_id,
            self.candidate_id,
            self.job_id,
        )

    def add_turn(self, question: str, answer: str) -> None:
        """Append a Q&A exchange to the session transcript.

        Args:
            question: The question asked by the AI interviewer.
            answer: The candidate's response.

        Raises:
            RuntimeError: If the session is not ``in_progress``.

        """
        if self.status != InterviewStatus.IN_PROGRESS:
            raise RuntimeError(
                f"Cannot add turn to session {self.session_id!r}: "
                f"status is '{self.status.value}' (must be 'in_progress')."
            )
        turn_index = len(self.turns)
        self.turns.append({"question": question, "answer": answer})
        logger.debug(
            "Interview session %s — turn %d recorded.",
            self.session_id,
            turn_index,
        )

    def end(self, flagged: bool = False) -> None:
        """Finalise the session, marking it as completed or flagged.

        Args:
            flagged: If ``True``, the session is marked ``flagged`` for
                human review (e.g. suspicious answers detected).

        Raises:
            RuntimeError: If the session is not ``in_progress``.

        """
        if self.status != InterviewStatus.IN_PROGRESS:
            raise RuntimeError(
                f"Cannot end session {self.session_id!r}: "
                f"status is '{self.status.value}' (must be 'in_progress')."
            )
        self.status = InterviewStatus.FLAGGED if flagged else InterviewStatus.COMPLETED
        log_ai_event(
            "interview.ended",
            session_id=self.session_id,
            candidate_id=self.candidate_id,
            job_id=self.job_id,
            status=self.status.value,
            total_turns=len(self.turns),
            flagged=flagged,
        )
        logger.info(
            "Interview session %s ended — status=%s, turns=%d",
            self.session_id,
            self.status.value,
            len(self.turns),
        )
