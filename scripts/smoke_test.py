#!/usr/bin/env python
"""End-to-end smoke test for Zecpath AI Platform.

Runs the complete pipeline on the sample resume:
    1. Parse sample_resume.txt
    2. Score against a MERN job description (ATS)
    3. Aggregate with mock screening + interview scores

Prints "SMOKE TEST PASSED" on success; exits with code 1 on failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on the path when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ats_engine.matcher import JobRequirements, score_resume
from parsers.resume_parser import parse_file
from scoring.aggregator import aggregate
from utils.logger import get_logger, setup_logging

setup_logging()
logger = get_logger("zecpath.smoke")


def main() -> None:
    """Run the end-to-end smoke test pipeline."""
    sample_path = Path("data/samples/sample_resume.txt")

    # ── Step 1: Parse ────────────────────────────────────────────────────
    print("[1/3] Parsing sample resume…")
    resume = parse_file(sample_path)
    assert resume.email == "ct@example.com", f"Unexpected email: {resume.email}"
    assert "node.js" in resume.skills, "node.js skill not detected"
    assert resume.experience_years == 3, f"Unexpected experience: {resume.experience_years}"
    print(f"      Skills detected   : {sorted(resume.skills)}")
    print(f"      Experience (years): {resume.experience_years}")
    print(f"      Email             : {resume.email}")

    # ── Step 2: ATS Score ────────────────────────────────────────────────
    print("[2/3] Running ATS scoring…")
    job = JobRequirements(
        job_id="j-smoke-001",
        required_skills=["react", "node.js", "mongodb", "express", "git", "docker"],
        min_experience_years=3,
    )
    ats = score_resume(resume, job, candidate_id="c-smoke-001")
    assert ats.score > 0, "ATS score must be positive"
    assert ats.meets_experience is True, "Candidate should meet experience requirement"
    print(f"      ATS score         : {ats.score}")
    print(f"      Matched skills    : {ats.matched_skills}")
    print(f"      Missing skills    : {ats.missing_skills}")
    print(f"      Meets experience  : {ats.meets_experience}")

    # ── Step 3: Aggregate ────────────────────────────────────────────────
    print("[3/3] Aggregating scores…")
    scores = {
        "ats": ats.score,
        "screening": 78.0,  # mock screening score
        "interview": 82.0,  # mock interview score
        "technical": 75.0,  # mock technical score
    }
    final = aggregate(
        scores,
        candidate_id="c-smoke-001",
        job_id="j-smoke-001",
    )
    assert final["decision"] in {"selected", "hold", "rejected"}, (
        f"Unexpected decision: {final['decision']}"
    )
    print(f"      Final score       : {final['final_score']}")
    print(f"      Decision          : {final['decision']}")

    print()
    print("=" * 40)
    print("  SMOKE TEST PASSED")
    print("=" * 40)
    logger.info("Smoke test completed successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n❌  SMOKE TEST FAILED: {exc}", file=sys.stderr)
        logger.exception("Smoke test failed")
        sys.exit(1)
