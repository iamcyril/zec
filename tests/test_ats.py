"""Tests for ats_engine/matcher.py."""

from __future__ import annotations

import pytest

from ats_engine.matcher import ATSResult, JobRequirements, score_resume
from parsers.resume_parser import ParsedResume

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_resume(
    skills: list[str],
    experience_years: int = 0,
    email: str = "test@example.com",
) -> ParsedResume:
    return ParsedResume(
        email=email,
        phone="",
        skills=skills,
        experience_years=experience_years,
        raw_text="",
    )


def _make_job(
    job_id: str,
    required_skills: list[str],
    min_experience_years: int = 0,
) -> JobRequirements:
    return JobRequirements(
        job_id=job_id,
        required_skills=required_skills,
        min_experience_years=min_experience_years,
    )


# ---------------------------------------------------------------------------
# Perfect match tests
# ---------------------------------------------------------------------------


class TestPerfectMatch:
    def test_perfect_skill_and_experience_gives_100(self) -> None:
        """Candidate matching all skills + meeting experience must score 100."""
        skills = ["python", "docker", "git"]
        resume = _make_resume(skills=skills, experience_years=5)
        job = _make_job("j-001", required_skills=skills, min_experience_years=5)
        result = score_resume(resume, job, candidate_id="c-001")
        assert result.score == pytest.approx(100.0)

    def test_perfect_match_no_missing_skills(self) -> None:
        skills = ["react", "node.js"]
        resume = _make_resume(skills=skills, experience_years=3)
        job = _make_job("j-002", required_skills=skills, min_experience_years=3)
        result = score_resume(resume, job)
        assert result.missing_skills == []

    def test_perfect_match_all_skills_listed(self) -> None:
        skills = ["react", "node.js"]
        resume = _make_resume(skills=skills)
        job = _make_job("j-003", required_skills=skills)
        result = score_resume(resume, job)
        assert sorted(result.matched_skills) == sorted(skills)

    def test_perfect_match_meets_experience_true(self) -> None:
        resume = _make_resume(skills=["python"], experience_years=3)
        job = _make_job("j-004", required_skills=["python"], min_experience_years=3)
        result = score_resume(resume, job)
        assert result.meets_experience is True


# ---------------------------------------------------------------------------
# Partial match tests
# ---------------------------------------------------------------------------


class TestPartialMatch:
    def test_partial_skill_match_lowers_score(self) -> None:
        resume = _make_resume(skills=["python"], experience_years=5)
        job = _make_job("j-005", required_skills=["python", "docker"], min_experience_years=5)
        result = score_resume(resume, job)
        # 50% skill match × 70 + 100% exp × 30 = 65
        assert result.score == pytest.approx(65.0)

    def test_partial_match_lists_missing_skill(self) -> None:
        resume = _make_resume(skills=["python"])
        job = _make_job("j-006", required_skills=["python", "docker"])
        result = score_resume(resume, job)
        assert "docker" in result.missing_skills
        assert "python" not in result.missing_skills

    def test_zero_skills_no_experience_gives_zero(self) -> None:
        resume = _make_resume(skills=[], experience_years=0)
        job = _make_job("j-007", required_skills=["python", "git"], min_experience_years=2)
        result = score_resume(resume, job)
        assert result.score == pytest.approx(0.0)

    def test_experience_below_minimum_partial_exp_score(self) -> None:
        """1 year when 4 required → exp_ratio=0.25 → exp_component=0.25*30=7.5."""
        resume = _make_resume(skills=["python", "docker"], experience_years=1)
        job = _make_job("j-008", required_skills=["python", "docker"], min_experience_years=4)
        result = score_resume(resume, job)
        expected = 70.0 + 0.25 * 30
        assert result.score == pytest.approx(expected, abs=0.01)

    def test_meets_experience_false_when_below_minimum(self) -> None:
        resume = _make_resume(skills=["python"], experience_years=1)
        job = _make_job("j-009", required_skills=["python"], min_experience_years=3)
        result = score_resume(resume, job)
        assert result.meets_experience is False

    def test_returns_ats_result_instance(self) -> None:
        resume = _make_resume(skills=["python"])
        job = _make_job("j-010", required_skills=["python"])
        result = score_resume(resume, job)
        assert isinstance(result, ATSResult)

    def test_score_is_two_decimal_places(self) -> None:
        resume = _make_resume(skills=["python"], experience_years=1)
        job = _make_job("j-011", required_skills=["python", "docker"], min_experience_years=4)
        result = score_resume(resume, job)
        # Score should be a float with at most 2 decimal places
        assert result.score == round(result.score, 2)

    def test_no_required_skills_gives_full_skill_score(self) -> None:
        """When no skills are required, skill component should be full (70 pts)."""
        resume = _make_resume(skills=[], experience_years=3)
        job = _make_job("j-012", required_skills=[], min_experience_years=3)
        result = score_resume(resume, job)
        assert result.score == pytest.approx(100.0)
