"""Tests for utils/logger.py — verifies JSON writing to ai_activity.log."""

from __future__ import annotations

import json
import logging
import os

import pytest


def _reset_logging_state() -> None:
    """Remove all handlers from root logger and the AI activity logger."""
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()
    ai_logger = logging.getLogger("zecpath.ai_activity")
    for h in ai_logger.handlers[:]:
        ai_logger.removeHandler(h)
        h.close()


@pytest.fixture()
def log_dir(tmp_path: object) -> str:
    """Provide a temporary log directory and reset logger state after the test."""
    import utils.logger as logger_mod  # noqa: PLC0415

    _reset_logging_state()
    # Force re-initialisation
    logger_mod._SETUP_DONE = False  # type: ignore[attr-defined]

    original_log_dir = os.environ.get("LOG_DIR")
    log_directory = str(tmp_path)  # type: ignore[union-attr]
    os.environ["LOG_DIR"] = log_directory

    # Reload config so Settings picks up new LOG_DIR
    import importlib  # noqa: PLC0415

    import utils.config as cfg_mod  # noqa: PLC0415

    importlib.reload(cfg_mod)
    importlib.reload(logger_mod)

    yield log_directory  # type: ignore[misc]

    # Teardown
    _reset_logging_state()
    logger_mod._SETUP_DONE = False  # type: ignore[attr-defined]
    if original_log_dir is None:
        os.environ.pop("LOG_DIR", None)
    else:
        os.environ["LOG_DIR"] = original_log_dir
    importlib.reload(cfg_mod)
    importlib.reload(logger_mod)


def test_setup_logging_creates_log_files(log_dir: str) -> None:
    """setup_logging() should create both log files in the configured directory."""
    from utils.logger import setup_logging  # noqa: PLC0415

    setup_logging()

    assert os.path.exists(os.path.join(log_dir, "app.log")), "app.log was not created"
    assert os.path.exists(os.path.join(log_dir, "ai_activity.log")), (
        "ai_activity.log was not created"
    )


def test_setup_logging_is_idempotent(log_dir: str) -> None:
    """Calling setup_logging() more than once must not add duplicate handlers."""
    from utils.logger import setup_logging  # noqa: PLC0415

    setup_logging()
    root_handler_count = len(logging.getLogger().handlers)
    ai_handler_count = len(logging.getLogger("zecpath.ai_activity").handlers)

    setup_logging()  # second call

    assert len(logging.getLogger().handlers) == root_handler_count
    assert len(logging.getLogger("zecpath.ai_activity").handlers) == ai_handler_count


def test_log_ai_event_writes_valid_json(log_dir: str) -> None:
    """log_ai_event() should write a valid JSON object to ai_activity.log."""
    from utils.logger import log_ai_event, setup_logging  # noqa: PLC0415

    setup_logging()
    log_ai_event(
        "test.event",
        candidate_id="c-test-001",
        job_id="j-test-007",
        score=99.5,
    )

    # Flush handlers
    for handler in logging.getLogger("zecpath.ai_activity").handlers:
        handler.flush()

    ai_log = os.path.join(log_dir, "ai_activity.log")
    assert os.path.exists(ai_log)

    lines = [ln for ln in open(ai_log, encoding="utf-8").readlines() if ln.strip()]
    assert lines, "ai_activity.log is empty"

    # Every line must be valid JSON with required keys
    for line in lines:
        payload = json.loads(line)
        assert "ts" in payload
        assert "level" in payload
        assert "message" in payload


def test_ai_event_contains_expected_fields(log_dir: str) -> None:
    """AI event JSON should contain the custom fields passed to log_ai_event."""
    from utils.logger import log_ai_event, setup_logging  # noqa: PLC0415

    setup_logging()
    log_ai_event("ats.scored", candidate_id="c-abc", job_id="j-xyz", score=82.0)

    for handler in logging.getLogger("zecpath.ai_activity").handlers:
        handler.flush()

    ai_log = os.path.join(log_dir, "ai_activity.log")
    lines = [ln for ln in open(ai_log, encoding="utf-8").readlines() if ln.strip()]
    last = json.loads(lines[-1])

    assert last.get("event") == "ats.scored"
    assert last.get("candidate_id") == "c-abc"
    assert last.get("job_id") == "j-xyz"
    assert last.get("score") == pytest.approx(82.0)
