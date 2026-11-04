"""ATS resume scoring engine for Zecpath AI Platform.

Scores a :class:`~parsers.resume_parser.ParsedResume` against a
:class:`JobRequirements` definition using a transparent, explainable formula:

    score = (skill_match_ratio × 0.70) + (experience_fit × 0.30)

Both components are normalised to [0, 100].

All scoring decisions are emitted to the AI activity log via
:func:`~utils.logger.log_ai_event` with ``event="ats.scored"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parsers.resume_parser import ParsedResume
from utils.logger import get_logger, log_ai_event

logger = get_logger("zecpath.ats")

# Scoring weights — must sum to 1.0
_SKILL_WEIGHT = 0.70
_EXPERIENCE_WEIGHT = 0.30


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class JobRequirements:
    """Specification of the skills and experience required for a role.

    Attributes:
        job_id: Unique identifier for the job posting.
        required_skills: List of skill names that candidates must have (lowercased).
        min_experience_years: Minimum number of years of relevant experience.

    """

    job_id: str
    required_skills: list[str] = field(default_factory=list)
    min_experience_years: int = 0


@dataclass
class ATSResult:
    """Output of the ATS scoring step.

    Attributes:
        score: Overall ATS score in [0, 100], rounded to 2 decimal places.
        matched_skills: Skills present in both the resume and the job requirements.
        missing_skills: Required skills absent from the resume.
        meets_experience: ``True`` if the candidate meets the min experience threshold.

    """

    score: float
    matched_skills: list[str]
    missing_skills: list[str]
    meets_experience: bool


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_resume(
    resume: ParsedResume,
    requirements: JobRequirements,
    candidate_id: str = "unknown",
) -> ATSResult:
    """Score a parsed resume against job requirements.

    Formula:
        ``score = skill_match_ratio × 70 + experience_fit × 30``

    Where:
        - ``skill_match_ratio`` = matched / total required  (0–1).  0 when no
          required skills are specified (no penalty).
        - ``experience_fit`` = 1.0 if ``resume.experience_years >=
          requirements.min_experience_years``, else a proportional score capped
          at 1.0.

    Args:
        resume: Parsed resume to evaluate.
        requirements: Job requirements to score against.
        candidate_id: Opaque identifier used in audit logs (never PII).

    Returns:
        An :class:`ATSResult` with score, breakdowns, and experience flag.

    """
    # ── Skill scoring ────────────────────────────────────────────────────
    required = [s.lower() for s in requirements.required_skills]
    candidate_skills = [s.lower() for s in resume.skills]

    if required:
        matched = sorted(s for s in required if s in candidate_skills)
        missing = sorted(s for s in required if s not in candidate_skills)
        skill_ratio = len(matched) / len(required)
    else:
        matched = []
        missing = []
        skill_ratio = 1.0  # no requirements → full skill score

    skill_score = skill_ratio * 100 * _SKILL_WEIGHT

    # ── Experience scoring ───────────────────────────────────────────────
    min_exp = requirements.min_experience_years
    if min_exp <= 0:
        exp_ratio = 1.0
    elif resume.experience_years >= min_exp:
        exp_ratio = 1.0
    else:
        exp_ratio = resume.experience_years / min_exp

    exp_score = exp_ratio * 100 * _EXPERIENCE_WEIGHT
    meets_experience = resume.experience_years >= min_exp

    total_score = round(skill_score + exp_score, 2)

    result = ATSResult(
        score=total_score,
        matched_skills=matched,
        missing_skills=missing,
        meets_experience=meets_experience,
    )

    log_ai_event(
        "ats.scored",
        candidate_id=candidate_id,
        job_id=requirements.job_id,
        score=total_score,
        matched_skills=matched,
        missing_skills=missing,
        meets_experience=meets_experience,
        skill_ratio=round(skill_ratio, 4),
        experience_years=resume.experience_years,
        min_experience_years=min_exp,
    )
    logger.info(
        "ATS scored candidate %s for job %s: %.2f",
        candidate_id,
        requirements.job_id,
        total_score,
    )
    return result
