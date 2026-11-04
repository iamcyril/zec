"""Tests for interview_ai/session.py."""

from __future__ import annotations

import pytest

from interview_ai.session import InterviewSession, InterviewStatus


class TestInterviewSessionLifecycle:
    def test_initial_status_is_created(self) -> None:
        session = InterviewSession(candidate_id="c-001", job_id="j-001")
        assert session.status == InterviewStatus.CREATED

    def test_start_transitions_to_in_progress(self) -> None:
        session = InterviewSession(candidate_id="c-002", job_id="j-001")
        session.start()
        assert session.status == InterviewStatus.IN_PROGRESS

    def test_end_transitions_to_completed(self) -> None:
        session = InterviewSession(candidate_id="c-003", job_id="j-001")
        session.start()
        session.end()
        assert session.status == InterviewStatus.COMPLETED

    def test_end_with_flagged_transitions_to_flagged(self) -> None:
        session = InterviewSession(candidate_id="c-004", job_id="j-001")
        session.start()
        session.end(flagged=True)
        assert session.status == InterviewStatus.FLAGGED

    def test_add_turn_appends_to_turns(self) -> None:
        session = InterviewSession(candidate_id="c-005", job_id="j-001")
        session.start()
        session.add_turn("What is your background?", "I have 3 years in MERN.")
        assert len(session.turns) == 1

    def test_add_multiple_turns(self) -> None:
        session = InterviewSession(candidate_id="c-006", job_id="j-001")
        session.start()
        for i in range(5):
            session.add_turn(f"Q{i}", f"A{i}")
        assert len(session.turns) == 5

    def test_turn_format(self) -> None:
        session = InterviewSession(candidate_id="c-007", job_id="j-001")
        session.start()
        session.add_turn("What is Python?", "A language.")
        turn = session.turns[0]
        assert turn["question"] == "What is Python?"
        assert turn["answer"] == "A language."

    def test_full_lifecycle(self) -> None:
        session = InterviewSession(candidate_id="c-008", job_id="j-002")
        assert session.status == InterviewStatus.CREATED
        session.start()
        session.add_turn("Intro?", "Hi, I'm Connor.")
        session.add_turn("Experience?", "3 years MERN.")
        session.end()
        assert session.status == InterviewStatus.COMPLETED
        assert len(session.turns) == 2


class TestInterviewSessionErrors:
    def test_add_turn_before_start_raises_runtime_error(self) -> None:
        session = InterviewSession(candidate_id="c-009", job_id="j-001")
        with pytest.raises(RuntimeError, match="in_progress"):
            session.add_turn("Hello?", "Hi.")

    def test_add_turn_after_end_raises_runtime_error(self) -> None:
        session = InterviewSession(candidate_id="c-010", job_id="j-001")
        session.start()
        session.end()
        with pytest.raises(RuntimeError, match="in_progress"):
            session.add_turn("Late Q?", "Late A.")

    def test_start_twice_raises_runtime_error(self) -> None:
        session = InterviewSession(candidate_id="c-011", job_id="j-001")
        session.start()
        with pytest.raises(RuntimeError):
            session.start()

    def test_end_before_start_raises_runtime_error(self) -> None:
        session = InterviewSession(candidate_id="c-012", job_id="j-001")
        with pytest.raises(RuntimeError, match="in_progress"):
            session.end()

    def test_session_id_is_unique(self) -> None:
        s1 = InterviewSession(candidate_id="c-013", job_id="j-001")
        s2 = InterviewSession(candidate_id="c-014", job_id="j-001")
        assert s1.session_id != s2.session_id

    def test_session_id_is_string(self) -> None:
        session = InterviewSession(candidate_id="c-015", job_id="j-001")
        assert isinstance(session.session_id, str)
