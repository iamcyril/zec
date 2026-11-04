"""Tests for parsers/resume_parser.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from parsers.resume_parser import ParsedResume, parse_file, parse_text

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_FILE = Path("data/samples/sample_resume.txt")

MINIMAL_RESUME = """\
John Doe
Email: john@example.com
Phone: 555-1234

3 years of experience.

Skills: Python, Docker, Git
"""

MERN_RESUME = """\
Jane Smith  jane@test.io  +44 20 7946 0958
4 years of experience in full-stack development.
Tech: React, Node.js, MongoDB, Express, TypeScript, Git
"""


# ---------------------------------------------------------------------------
# parse_text tests
# ---------------------------------------------------------------------------

class TestParseText:
    def test_extracts_email(self) -> None:
        result = parse_text(MINIMAL_RESUME)
        assert result.email == "john@example.com"

    def test_extracts_phone(self) -> None:
        result = parse_text(MINIMAL_RESUME)
        assert "555-1234" in result.phone

    def test_detects_python_skill(self) -> None:
        result = parse_text(MINIMAL_RESUME)
        assert "python" in result.skills

    def test_detects_docker_skill(self) -> None:
        result = parse_text(MINIMAL_RESUME)
        assert "docker" in result.skills

    def test_detects_git_skill(self) -> None:
        result = parse_text(MINIMAL_RESUME)
        assert "git" in result.skills

    def test_experience_years_extracted(self) -> None:
        result = parse_text(MINIMAL_RESUME)
        assert result.experience_years == 3

    def test_raw_text_preserved(self) -> None:
        result = parse_text(MINIMAL_RESUME)
        assert result.raw_text == MINIMAL_RESUME

    def test_detects_node_js_with_dot(self) -> None:
        """node.js must be matched including its literal dot."""
        result = parse_text(MERN_RESUME)
        assert "node.js" in result.skills

    def test_detects_react(self) -> None:
        result = parse_text(MERN_RESUME)
        assert "react" in result.skills

    def test_detects_mongodb(self) -> None:
        result = parse_text(MERN_RESUME)
        assert "mongodb" in result.skills

    def test_no_false_positive_nodejs_without_dot(self) -> None:
        """'nodejs' (no dot) must NOT match the 'node.js' skill entry."""
        result = parse_text("I know nodejs very well.")
        assert "node.js" not in result.skills

    def test_empty_text_returns_empty_fields(self) -> None:
        result = parse_text("")
        assert result.email == ""
        assert result.phone == ""
        assert result.skills == []
        assert result.experience_years == 0

    def test_returns_parsed_resume_instance(self) -> None:
        result = parse_text(MINIMAL_RESUME)
        assert isinstance(result, ParsedResume)


# ---------------------------------------------------------------------------
# parse_file tests
# ---------------------------------------------------------------------------

class TestParseFile:
    def test_parses_sample_txt_file(self) -> None:
        """Should successfully parse the shipped sample resume."""
        result = parse_file(SAMPLE_FILE)
        assert isinstance(result, ParsedResume)

    def test_sample_file_email(self) -> None:
        result = parse_file(SAMPLE_FILE)
        assert result.email == "ct@example.com"

    def test_sample_file_has_skills(self) -> None:
        result = parse_file(SAMPLE_FILE)
        assert len(result.skills) > 0

    def test_sample_file_node_js_detected(self) -> None:
        result = parse_file(SAMPLE_FILE)
        assert "node.js" in result.skills

    def test_sample_file_experience_years(self) -> None:
        result = parse_file(SAMPLE_FILE)
        assert result.experience_years == 3

    def test_unsupported_extension_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match=r"\.pdf"):
            parse_file("resume.pdf")

    def test_docx_extension_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match=r"\.docx"):
            parse_file("resume.docx")
