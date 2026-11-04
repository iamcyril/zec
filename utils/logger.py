"""Logging configuration for Zecpath AI Platform.

Provides three public helpers:

* :func:`setup_logging` — idempotent initialisation of the logging hierarchy.
* :func:`get_logger` — retrieve a named :class:`logging.Logger` instance.
* :func:`log_ai_event` — emit a structured JSON line to ``ai_activity.log``.

Log Layout
----------
- **Console** — human-readable, coloured by level.
- **logs/app.log** — rotating (10 MB × 5), plain text, all levels.
- **logs/ai_activity.log** — rotating (5 MB × 10), JSON Lines, AI events only.
  Handler isolation: ``propagate=False`` so AI events do not bleed to app.log.

Privacy
-------
**Never pass PII** (names, CVs, raw resumes) as field values to any logging
call.  Use opaque identifiers (``candidate_id``, ``job_id``) only.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from typing import Any

from utils.config import settings

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------
_AI_LOGGER_NAME = "zecpath.ai_activity"
_SETUP_DONE = False  # idempotency guard


# ---------------------------------------------------------------------------
# JSON Lines formatter
# ---------------------------------------------------------------------------
class _JsonFormatter(logging.Formatter):
    """Format a :class:`logging.LogRecord` as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any extra fields attached to the record (excluding stdlib fields).
        _stdlib_keys = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in _stdlib_keys:
                payload[key] = value
        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logging() -> None:
    """Initialise the Zecpath logging stack.

    Safe to call multiple times — subsequent calls are no-ops.

    Log files are created inside the directory specified by
    :attr:`utils.config.Settings.log_dir`.  The directory is created
    automatically if it does not exist.
    """
    global _SETUP_DONE  # noqa: PLW0603
    if _SETUP_DONE:
        return
    _SETUP_DONE = True

    log_dir = settings.log_dir
    os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))

    # ── Console handler ──────────────────────────────────────────────────
    console = logging.StreamHandler()
    console.setLevel(getattr(logging, settings.log_level, logging.INFO))
    console.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(console)

    # ── Rotating app.log (plain text) ────────────────────────────────────
    app_log_path = os.path.join(log_dir, "app.log")
    file_handler = logging.handlers.RotatingFileHandler(
        app_log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    root.addHandler(file_handler)

    # ── Rotating ai_activity.log (JSON Lines, isolated) ──────────────────
    ai_log_path = os.path.join(log_dir, "ai_activity.log")
    ai_handler = logging.handlers.RotatingFileHandler(
        ai_log_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=10,
        encoding="utf-8",
    )
    ai_handler.setLevel(logging.DEBUG)
    ai_handler.setFormatter(_JsonFormatter())

    ai_logger = logging.getLogger(_AI_LOGGER_NAME)
    ai_logger.setLevel(logging.DEBUG)
    ai_logger.addHandler(ai_handler)
    ai_logger.propagate = False  # do NOT bubble up to app.log or console


def get_logger(name: str) -> logging.Logger:
    """Return a named :class:`logging.Logger`, initialising logging if needed.

    Args:
        name: Dotted logger name, e.g. ``"zecpath.ats"``.

    Returns:
        A configured :class:`logging.Logger` instance.

    """
    setup_logging()
    return logging.getLogger(name)


def log_ai_event(event: str, **fields: Any) -> None:
    """Emit a structured AI decision event to ``ai_activity.log``.

    Each call writes exactly one JSON line with at minimum:
    ``ts``, ``level``, ``logger``, ``message``, ``event``, plus any
    additional ``fields`` supplied by the caller.

    Args:
        event: Short dot-separated event name, e.g. ``"ats.scored"``.
        **fields: Additional structured fields.  **Never pass PII** —
            use ``candidate_id`` / ``job_id`` as opaque identifiers only.

    Example:
        >>> log_ai_event("ats.scored", candidate_id="c-001", job_id="j-42", score=87.5)

    """
    setup_logging()
    ai_logger = logging.getLogger(_AI_LOGGER_NAME)
    # Pass extra fields directly onto the log record so _JsonFormatter picks them up.
    ai_logger.info(event, extra={"event": event, **fields})
