# Zecpath AI Platform

> **AI-powered hiring platform** — Resume parsing, ATS scoring, voice screening, AI interviews, and multi-signal score aggregation.

[![CI](https://github.com/your-org/zecpath-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/zecpath-ai/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/your-org/zecpath-ai.git
cd zecpath-ai

# 2. Bootstrap (Windows PowerShell)
.\scripts\setup.ps1

# 3. Activate virtual environment
.\.venv\Scripts\Activate.ps1    # Windows
# source .venv/bin/activate     # macOS/Linux

# 4. Run all tests
python -m pytest tests/ -v

# 5. Run smoke test (end-to-end pipeline)
python scripts/smoke_test.py
```

---

## Repository Layout

```
zecpath-ai/
├── .github/workflows/ci.yml   # GitHub Actions CI (Python 3.10–3.12)
├── ats_engine/
│   └── matcher.py             # Resume ↔ job scoring (70% skills + 30% exp)
├── data/
│   ├── raw/                   # Raw uploads (gitignored)
│   ├── processed/             # Processed artefacts (gitignored)
│   └── samples/
│       └── sample_resume.txt  # MERN developer sample resume
├── docs/
│   └── CODE_STANDARDS.md      # Coding standards & git workflow
├── interview_ai/
│   └── session.py             # AI interview session state machine
├── logs/                      # Runtime log files (gitignored)
├── parsers/
│   └── resume_parser.py       # Regex-based resume structured extraction
├── scoring/
│   └── aggregator.py          # Multi-signal weighted score aggregation
├── screening_ai/
│   └── questions.py           # Ordered voice-screening question bank
├── scripts/
│   ├── setup.ps1              # Windows bootstrap script
│   ├── setup.sh               # Unix bootstrap script
│   └── smoke_test.py          # End-to-end pipeline smoke test
├── tests/                     # pytest suite (one file per module)
├── utils/
│   ├── config.py              # Frozen Settings dataclass (from_env)
│   ├── logger.py              # Structured logging stack
│   └── text.py                # Text normalisation utilities
├── .env.example               # Environment variable template
├── .gitignore
├── .pre-commit-config.yaml
├── Makefile
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

---

## Module Table

| Module | File | PRD Phase | Description |
|--------|------|-----------|-------------|
| **parsers/docx_reader** | `parsers/docx_reader.py` | 1 | DOCX text extraction (paragraphs, tables, headers, textboxes) |
| **parsers/pdf_reader** | `parsers/pdf_reader.py` | 1 | PDF extraction: PyMuPDF + pdfplumber tables + OCR fallback |
| **parsers/reader_factory** | `parsers/reader_factory.py` | 1 | Route by extension → uniform ExtractResult |
| **parsers/extractor** | `parsers/extractor.py` | 1 | Orchestrator: read → clean → write .txt + .json |
| **parsers/resume_parser** | `parsers/resume_parser.py` | 1–2 | Extract email, phone, skills, experience from resume text |
| **utils/text_cleaner** | `utils/text_cleaner.py` | 1 | Unicode NFKC, bullet normalise, heading synonym map |
| **ats_engine** | `ats_engine/matcher.py` | 2 | Score resume vs. job requirements (0–100) |
| **screening_ai** | `screening_ai/questions.py` | 3–5 | AI voice screening question bank (7 questions) |
| **interview_ai** | `interview_ai/session.py` | 11–25 | Interview session lifecycle state machine |
| **scoring** | `scoring/aggregator.py` | 20, 44, 70, 88 | Weighted multi-signal aggregation → hiring decision |
| **utils/config** | `utils/config.py` | All | Environment-based settings (frozen dataclass) |
| **utils/logger** | `utils/logger.py` | All | Console + rotating file + JSON AI activity logging |
| **utils/text** | `utils/text.py` | All | Legacy text normalisation utilities |

---

## Resume Text Extraction Engine

### Quick usage

```python
from parsers.extractor import extract_file

# Single file
result = extract_file("data/raw/john_smith.pdf")
print(result["status"])  # "ok" or "error"
print(result["sections"])  # ["Summary", "Experience", "Skills", ...]
print(result["char_count"])  # int
```

On success, two files are written:
- `data/extracted/<stem>.txt` — cleaned plain text
- `data/extracted/<stem>.json` — full structured record

### JSON record format

```json
{
  "file": "data/raw/john_smith.pdf",
  "type": "pdf",
  "pages": 2,
  "method_used": "pymupdf",
  "ocr_used": false,
  "sections": ["Summary", "Experience", "Skills", "Education"],
  "char_count": 3471,
  "warnings": [],
  "text": "..."
}
```

### Batch processing

```bash
# Drop resumes into data/raw/, then:
python run_batch.py

# With verbose per-file output:
python run_batch.py --verbose

# Custom directories:
python run_batch.py --raw-dir /my/resumes --log-dir /my/logs
```

The summary report is written to `logs/test_results.log`.

### Supported file types

| Extension | Reader | Notes |
|-----------|--------|-------|
| `.pdf` | PyMuPDF + pdfplumber | Two-column layout sorted correctly; OCR fallback for scanned pages |
| `.docx` | python-docx | Paragraphs, tables, headers/footers, text boxes |
| `.doc` | LibreOffice → DOCX | Requires LibreOffice (`winget install LibreOffice.LibreOffice`) |

### OCR setup (optional)

OCR triggers only when a PDF page yields fewer than 50 characters.
If Tesseract is absent, OCR is skipped with a warning — no crash.

```bash
# Windows
winget install UB-Mannheim.TesseractOCR
pip install pytesseract pdf2image
```

### Text cleaning pipeline

`utils/text_cleaner.clean(text)` applies in order:

1. Unicode NFKC normalisation
2. Strip control characters and zero-width spaces
3. Fix soft-hyphen line-breaks
4. Normalise all bullet markers (`•`, `▪`, `●`, `➤`, `*`, `-`) → `- `
5. Collapse extra whitespace
6. Map heading synonyms → canonical names (`WORK HISTORY` → `Experience`)

Tech-term capitalisation (`React`, `Node.js`, `AWS`) is **preserved** — only
heading lines are case-normalised.

---

## Logging Usage


```python
from utils.logger import get_logger, log_ai_event

logger = get_logger("zecpath.my_module")

# Standard application log
logger.info("Processing started for job %s", job_id)

# AI decision event (written to logs/ai_activity.log as JSON)
log_ai_event(
    "ats.scored",
    candidate_id="c-001",  # opaque ID only — never PII
    job_id="j-042",
    score=87.5,
    decision="selected",
)
```

**Log files** (auto-created in `logs/`):
- `logs/app.log` — rotating plain text, all levels, 10 MB × 5 backups
- `logs/ai_activity.log` — rotating JSON Lines, AI events only, 5 MB × 10 backups

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# With coverage report
python -m pytest tests/ --cov=. --cov-report=term-missing

# Single file
python -m pytest tests/test_ats.py -v
```

---

## Linting & Formatting

```bash
# Check only
python -m ruff check .

# Auto-fix
python -m ruff check --fix .
python -m ruff format .

# Type checking
python -m mypy .
```

---

## Code Standards

See [docs/CODE_STANDARDS.md](docs/CODE_STANDARDS.md) for:
- PEP 8 & ruff rules in use
- Google-style docstring guide
- AI decision logging requirements
- No-PII policy
- Scoring explainability requirements
- How to add a new module (12-step checklist)

---

## Git Workflow

```bash
# Feature branch workflow
git checkout develop
git pull
git checkout -b feature/my-new-module

# ... make changes ...

git add .
git commit -m "feat(module): add my new module"
git push origin feature/my-new-module
# Open PR: feature/my-new-module → develop
```

### Conventional Commit Types

| Type | Use for |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `chore` | Tooling, deps, config |
| `docs` | Documentation only |
| `refactor` | Code restructure (no behaviour change) |
| `test` | Tests only |
| `ci` | CI/CD pipeline changes |
| `perf` | Performance improvements |

---

## GitHub Repository Setup

If the `gh` CLI is authenticated, run:

```bash
gh repo create zecpath-ai --private --source=. --push
```

Otherwise, create the repo manually and then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/zecpath-ai.git
git push -u origin main
git push -u origin develop
```

---

## Environment Variables

Copy `.env.example` to `.env` and edit as needed:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Runtime environment name |
| `LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_DIR` | `logs` | Directory for log files |
| `LOG_JSON` | `false` | Set `true` for JSON console output |
