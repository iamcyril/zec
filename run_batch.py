"""Batch extraction runner for Zecpath AI Platform.

Processes every supported resume file in ``data/raw/`` and writes a
human-readable summary report to ``logs/test_results.log``.

Usage::

    python run_batch.py [--raw-dir PATH] [--log-dir PATH]

Arguments:
---------
--raw-dir   Directory to scan for input files (default: data/raw)
--log-dir   Directory to write the summary report (default: logs)
--verbose   Also print each result to stdout

"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path so imports work when run directly.
_PROJECT_ROOT = Path(__file__).parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from parsers.extractor import extract_file  # noqa: E402
from utils.logger import get_logger, setup_logging  # noqa: E402

setup_logging()
logger = get_logger("zecpath.run_batch")

_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc"}


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------


def _collect_files(raw_dir: Path) -> list[Path]:
    """Return all supported resume files in *raw_dir* (non-recursive)."""
    files = [
        f
        for f in sorted(raw_dir.iterdir())
        if f.is_file() and f.suffix.lower() in _SUPPORTED_EXTENSIONS
    ]
    return files


def _format_report(
    results: list[dict],
    *,
    raw_dir: Path,
    started_at: datetime,
    finished_at: datetime,
) -> str:
    """Build a plain-text summary report string."""
    ok = [r for r in results if r.get("status") == "ok"]
    errors = [r for r in results if r.get("status") == "error"]
    duration = (finished_at - started_at).total_seconds()

    lines = [
        "=" * 72,
        "ZECPATH BATCH EXTRACTION REPORT",
        f"Run started : {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Run finished: {finished_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Duration    : {duration:.1f}s",
        f"Input dir   : {raw_dir}",
        f"Total files : {len(results)}",
        f"Successes   : {len(ok)}",
        f"Failures    : {len(errors)}",
        "=" * 72,
        "",
    ]

    if ok:
        lines.append("── SUCCESSFUL EXTRACTIONS ──────────────────────────────────────────")
        for r in ok:
            file_path = Path(r.get("file", ""))
            lines.append(
                f"  ✔  {file_path.name:<40} "
                f"type={r.get('type', '?'):<5} "
                f"chars={r.get('char_count', 0):<8} "
                f"pages={r.get('pages', '?'):<4} "
                f"ocr={str(r.get('ocr_used', False)):<6} "
                f"sections={r.get('sections', [])}"
            )
        lines.append("")

    if errors:
        lines.append("── FAILURES ─────────────────────────────────────────────────────────")
        for r in errors:
            file_path = Path(r.get("file", ""))
            lines.append(f"  ✘  {file_path.name:<40} error={r.get('error', 'unknown')}")
        lines.append("")

    lines.append("=" * 72)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Batch-extract all resumes in the raw directory and write a summary report."""
    parser = argparse.ArgumentParser(description="Batch-extract all resumes in data/raw/")
    parser.add_argument("--raw-dir", default="data/raw", help="Input directory (default: data/raw)")
    parser.add_argument("--log-dir", default="logs", help="Log directory (default: logs)")
    parser.add_argument("--verbose", action="store_true", help="Print each result to stdout")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    if not raw_dir.exists():
        print(f"[run_batch] Input directory '{raw_dir}' does not exist. Creating it.")
        raw_dir.mkdir(parents=True, exist_ok=True)

    files = _collect_files(raw_dir)
    if not files:
        print(f"[run_batch] No supported files found in '{raw_dir}'.")
        print("  Drop .pdf, .docx, or .doc files there and re-run.")
        return 0

    print(f"[run_batch] Processing {len(files)} file(s) from '{raw_dir}' …")
    logger.info("Batch run starting: %d files in '%s'", len(files), raw_dir)

    results = []
    started_at = datetime.now(tz=timezone.utc)

    for path in files:
        print(f"  Processing: {path.name} …", end=" ", flush=True)
        result = extract_file(path)
        results.append(result)
        status_icon = "✔" if result["status"] == "ok" else "✘"
        print(status_icon)
        if args.verbose:
            if result["status"] == "ok":
                print(f"    chars={result.get('char_count')}  sections={result.get('sections')}")
            else:
                print(f"    ERROR: {result.get('error')}")

    finished_at = datetime.now(tz=timezone.utc)

    # Write summary report
    report = _format_report(
        results, raw_dir=raw_dir, started_at=started_at, finished_at=finished_at
    )
    report_path = log_dir / "test_results.log"
    report_path.write_text(report, encoding="utf-8")

    print(f"\n[run_batch] Report written to '{report_path}'")
    print(report)

    ok_count = sum(1 for r in results if r["status"] == "ok")
    logger.info(
        "Batch run complete: %d/%d succeeded, report at '%s'",
        ok_count,
        len(results),
        report_path,
    )

    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
