# Code Standards — Zecpath AI Platform

> **Version:** 1.0 | **Owner:** Zecpath Engineering | **Applies to:** All `*.py` files in this repo

---

## 1. Language & Runtime

| Item | Standard |
|------|----------|
| Python version | **≥ 3.10** |
| Type annotations | Mandatory on all public functions, methods, and class attributes |
| Future annotations | Always include `from __future__ import annotations` in every module |
| Formatting | **ruff format** (line length 100) |
| Linting | **ruff check** (rules: E F I N UP B D) |
| Type checking | **mypy** with `disallow_untyped_defs = true` |

---

## 2. Style Guide

- Follow **PEP 8** (enforced via ruff).
- Use `snake_case` for functions, variables, and modules.
- Use `PascalCase` for classes and dataclasses.
- Use `SCREAMING_SNAKE_CASE` for module-level constants.
- Maximum line length: **100 characters**.
- Prefer `f-strings` over `.format()` or `%` formatting.

---

## 3. Docstrings

All public modules, classes, functions, and methods **must** have a Google-style docstring.

```python
def score_resume(resume: ParsedResume, requirements: JobRequirements) -> ATSResult:
    """Score a parsed resume against job requirements.

    Args:
        resume: Parsed resume to evaluate.
        requirements: Job requirements definition.

    Returns:
        An ATSResult containing the score and breakdowns.

    Raises:
        ValueError: If requirements are malformed.
    """
```

Private helpers (prefixed `_`) may have a shorter single-line docstring.

---

## 4. No `print()` in Library Code

- **Never** use `print()` inside `utils/`, `parsers/`, `ats_engine/`, `screening_ai/`,
  `interview_ai/`, or `scoring/`.
- Use `get_logger(__name__)` and emit log records instead.
- `print()` is permitted **only** in `scripts/` (smoke test, setup scripts).

---

## 5. No Secrets in Code

- API keys, database passwords, and credentials are **never** hardcoded.
- All secrets must be loaded from environment variables via `.env` / `Settings.from_env()`.
- The `.env` file is listed in `.gitignore` and must never be committed.

---

## 6. AI Decision Logging

Every AI decision point **must** call `log_ai_event()` with at minimum:

| Field | Description |
|-------|-------------|
| `event` | Dot-separated name e.g. `"ats.scored"` |
| `candidate_id` | Opaque ID — never the candidate's real name or email |
| `job_id` | Job posting identifier |
| `outcome` | Machine-readable result (score, decision string, etc.) |

```python
log_ai_event(
    "ats.scored",
    candidate_id=candidate_id,   # opaque ID only
    job_id=requirements.job_id,
    score=total_score,
)
```

---

## 7. Privacy & PII

- **Never** log names, email addresses, phone numbers, or full resume text.
- Use opaque identifiers (`candidate_id`, `job_id`) throughout all modules.
- `raw_text` in `ParsedResume` must **not** be passed to any logging call.
- Protected attributes (age, gender, ethnicity, disability) are **never** accepted
  as inputs to any scoring or ranking function.

---

## 8. Scores

- All scores are `float` values in the range **[0, 100]**.
- Scores must be rounded to **2 decimal places** before being stored or returned.
- Score formulas must be documented in the module-level docstring (explainability).
- Use weighted sums only; never use black-box sorting that is not traceable.

---

## 9. Error Handling

- Raise typed exceptions (`ValueError`, `RuntimeError`, `NotImplementedError`) with descriptive messages.
- Never swallow exceptions silently (`except: pass` is forbidden).
- Log exceptions at `ERROR` level before re-raising or returning a safe default.

---

## 10. Testing

- Minimum one test file per module (naming: `tests/test_<module>.py`).
- No network calls or external services in tests — mock all I/O.
- Use `pytest` fixtures for temporary files and patching.
- Aim for ≥ 90% line coverage per module.

---

## 11. Git Workflow

### Commit Conventions (Conventional Commits)

```
<type>(<scope>): <description>

Types: feat | fix | chore | docs | refactor | test | ci | perf
```

Examples:
```
feat(ats): add experience scoring component
fix(parser): escape node.js dot in regex
chore: add pre-commit hooks
docs: update CODE_STANDARDS.md
```

### Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code only; protected |
| `develop` | Integration branch; all features merge here first |
| `feature/<name>` | Individual feature work |
| `fix/<name>` | Bug fixes |

---

## 12. How to Add a New Module

Follow this checklist whenever adding a new AI component (e.g., `background_check/`):

- [ ] **Create the package directory** with `__init__.py` containing a one-line docstring.
- [ ] **Write the module** (`background_check/checker.py`) with:
  - [ ] `from __future__ import annotations` at the top
  - [ ] Google-style docstrings on all public symbols
  - [ ] Full type annotations
  - [ ] `get_logger("zecpath.<module>")` for logging
  - [ ] `log_ai_event(...)` on every AI decision
- [ ] **Add dataclasses** for inputs and outputs (no ad-hoc dicts in the public API).
- [ ] **Write tests** in `tests/test_<module>.py` covering:
  - [ ] Happy path
  - [ ] Edge cases (empty inputs, boundary scores)
  - [ ] Error cases (expected exceptions)
- [ ] **Update smoke_test.py** to include the new module in the pipeline.
- [ ] **Update README.md** module table with the new component and its PRD phase.
- [ ] **Run** `make lint test smoke` — all must pass before opening a PR.
- [ ] **Open a PR** from `feature/<module-name>` → `develop`.
