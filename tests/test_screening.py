"""Tests for screening_ai/questions.py."""

from __future__ import annotations

from screening_ai.questions import get_questions

EXPECTED_KEYS = [
    "introduction",
    "education",
    "experience",
    "skills",
    "location",
    "notice_period",
    "expected_salary",
]


class TestGetQuestions:
    def test_returns_exactly_7_questions(self) -> None:
        assert len(get_questions()) == 7

    def test_each_item_has_key_and_text(self) -> None:
        for q in get_questions():
            assert "key" in q, f"Missing 'key' in question: {q}"
            assert "text" in q, f"Missing 'text' in question: {q}"

    def test_keys_match_expected_order(self) -> None:
        keys = [q["key"] for q in get_questions()]
        assert keys == EXPECTED_KEYS

    def test_texts_are_non_empty_strings(self) -> None:
        for q in get_questions():
            assert isinstance(q["text"], str)
            assert len(q["text"].strip()) > 0

    def test_returns_new_list_each_call(self) -> None:
        """Mutations to the returned list must not affect future calls."""
        q1 = get_questions()
        q1.clear()
        q2 = get_questions()
        assert len(q2) == 7

    def test_introduction_is_first(self) -> None:
        assert get_questions()[0]["key"] == "introduction"

    def test_expected_salary_is_last(self) -> None:
        assert get_questions()[-1]["key"] == "expected_salary"
