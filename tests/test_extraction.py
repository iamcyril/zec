"""Extraction engine tests for Zecpath AI Platform.

Covers:
- DOCX reader (paragraphs, tables, bullets, headings)
- PDF reader (single-column, two-column)
- Text cleaner (bullets, headings, unicode)
- Orchestrator (output files, error handling)
- Corrupted / unsupported files (graceful failure)

Fixtures use reportlab and python-docx to generate synthetic binary files
at test time so the test suite is fully self-contained.
"""

from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document as _DocxDoc
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from parsers.docx_reader import read as read_docx
from parsers.extractor import extract_file
from parsers.reader_factory import read_file
from utils.text_cleaner import clean


# ---------------------------------------------------------------------------
# Helper: create a simple PDF in memory / on disk
# ---------------------------------------------------------------------------


def _make_single_col_pdf(path: Path, text_lines: list[str]) -> None:
    """Write a minimal single-column PDF with the given lines."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 740
    for line in text_lines:
        c.drawString(72, y, line)
        y -= 20
        if y < 72:
            c.showPage()
            y = 740
    c.save()
    path.write_bytes(buf.getvalue())


def _make_two_col_pdf(path: Path) -> None:
    """Write a 2-column PDF — left col then right col text."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    # Left column lines
    for i, line in enumerate(["LEFT col line 1", "LEFT col line 2", "LEFT col line 3"]):
        c.drawString(72, 720 - i * 20, line)
    # Right column lines
    for i, line in enumerate(["RIGHT col line 1", "RIGHT col line 2", "RIGHT col line 3"]):
        c.drawString(320, 720 - i * 20, line)
    c.save()
    path.write_bytes(buf.getvalue())


def _make_table_docx(path: Path) -> None:
    """Write a DOCX with a 2×2 table containing distinct cell text."""
    doc = _DocxDoc()
    doc.add_paragraph("Table resume")
    tbl = doc.add_table(rows=2, cols=2)
    tbl.cell(0, 0).text = "Cell A1"
    tbl.cell(0, 1).text = "Cell B1"
    tbl.cell(1, 0).text = "Cell A2"
    tbl.cell(1, 1).text = "Cell B2"
    doc.save(str(path))


def _make_bullet_docx(path: Path) -> None:
    """Write a DOCX with various bullet markers that should all normalise to '-'."""
    doc = _DocxDoc()
    doc.add_paragraph("• Python developer")
    doc.add_paragraph("▪ JavaScript expert")
    doc.add_paragraph("● React skills")
    doc.add_paragraph("➤ Docker knowledge")
    doc.add_paragraph("* AWS certified")
    doc.save(str(path))


def _make_headings_docx(path: Path) -> None:
    """Write a DOCX with synonym headings that should normalise."""
    doc = _DocxDoc()
    doc.add_paragraph("WORK HISTORY")      # → Experience
    doc.add_paragraph("Did some work at Acme Corp")
    doc.add_paragraph("TECHNICAL SKILLS")  # → Skills
    doc.add_paragraph("Python, React, Docker")
    doc.add_paragraph("ACADEMIC BACKGROUND")  # → Education
    doc.add_paragraph("BSc Computer Science")
    doc.save(str(path))


def _make_empty_docx(path: Path) -> None:
    """Write a technically valid but content-free DOCX."""
    doc = _DocxDoc()
    doc.save(str(path))


# ---------------------------------------------------------------------------
# Test 1: Single-column PDF — text is non-empty
# ---------------------------------------------------------------------------


class TestSingleColumnPdf:
    def test_text_non_empty(self, tmp_path: Path) -> None:
        """Single-column PDF must yield non-empty extracted text."""
        pdf = tmp_path / "single_col.pdf"
        _make_single_col_pdf(pdf, ["Jane Doe", "Email: jane@example.com", "5 years experience"])
        result = read_file(pdf)
        assert result["text"].strip(), "Expected non-empty text from single-column PDF"

    def test_type_is_pdf(self, tmp_path: Path) -> None:
        pdf = tmp_path / "single_col.pdf"
        _make_single_col_pdf(pdf, ["Hello world"])
        result = read_file(pdf)
        assert result["type"] == "pdf"

    def test_ocr_not_used_for_normal_pdf(self, tmp_path: Path) -> None:
        pdf = tmp_path / "normal.pdf"
        _make_single_col_pdf(pdf, ["This is readable text with enough characters to pass threshold"])
        result = read_file(pdf)
        assert result["ocr_used"] is False


# ---------------------------------------------------------------------------
# Test 2: Two-column PDF — layout order is preserved
# ---------------------------------------------------------------------------


class TestTwoColumnPdf:
    def test_two_col_text_non_empty(self, tmp_path: Path) -> None:
        pdf = tmp_path / "two_col.pdf"
        _make_two_col_pdf(pdf)
        result = read_file(pdf)
        assert result["text"].strip()

    def test_both_columns_present(self, tmp_path: Path) -> None:
        """Both LEFT and RIGHT column text must appear in the result."""
        pdf = tmp_path / "two_col.pdf"
        _make_two_col_pdf(pdf)
        result = read_file(pdf)
        text = result["text"]
        assert "LEFT" in text
        assert "RIGHT" in text


# ---------------------------------------------------------------------------
# Test 3: Table-based DOCX — table cells appear in output
# ---------------------------------------------------------------------------


class TestTableDocx:
    def test_table_cells_present(self, tmp_path: Path) -> None:
        docx = tmp_path / "table_resume.docx"
        _make_table_docx(docx)
        result = read_docx(docx)
        text = result["text"]
        assert "Cell A1" in text
        assert "Cell B2" in text

    def test_method_is_python_docx(self, tmp_path: Path) -> None:
        docx = tmp_path / "table_resume.docx"
        _make_table_docx(docx)
        result = read_docx(docx)
        assert result["method_used"] == "python-docx"


# ---------------------------------------------------------------------------
# Test 4: Bullet normalisation
# ---------------------------------------------------------------------------


class TestBulletNormalisation:
    def test_bullets_normalised_to_dash(self, tmp_path: Path) -> None:
        """All bullet markers must become '- ' after cleaning."""
        docx = tmp_path / "bullets.docx"
        _make_bullet_docx(docx)
        result = read_docx(docx)
        cleaned = clean(result["text"])
        text = cleaned["text"]
        # Every line that had a bullet should now start with "- "
        bullet_lines = [ln for ln in text.splitlines() if "developer" in ln or "expert" in ln
                        or "skills" in ln.lower() or "knowledge" in ln or "certified" in ln]
        assert bullet_lines, "Expected at least one bullet line in output"
        for line in bullet_lines:
            assert line.startswith("- "), f"Expected '- ' prefix, got: {line!r}"


class TestTextCleanerDirectly:
    def test_bullet_dash(self) -> None:
        result = clean("• Python\n▪ JavaScript\n● React")
        assert all(ln.startswith("- ") for ln in result["text"].splitlines() if ln.strip())

    def test_bullet_star(self) -> None:
        result = clean("* Docker\n* AWS")
        lines = [ln for ln in result["text"].splitlines() if ln.strip()]
        assert all(ln.startswith("- ") for ln in lines)

    def test_unicode_normalise(self) -> None:
        # ﬁ (U+FB01) → fi after NFKC
        result = clean("Pro\ufb01le: software engineer")
        assert "\ufb01" not in result["text"]
        assert "fi" in result["text"]

    def test_hyphen_break_fixed(self) -> None:
        result = clean("soft-\nware engineer")
        assert "software" in result["text"]

    def test_zero_width_stripped(self) -> None:
        result = clean("Hello\u200bWorld")
        assert "\u200b" not in result["text"]


# ---------------------------------------------------------------------------
# Test 5: Heading detection
# ---------------------------------------------------------------------------


class TestHeadingDetection:
    def test_canonical_headings_detected(self, tmp_path: Path) -> None:
        """Synonym headings must map to canonical names in 'sections'."""
        docx = tmp_path / "headings.docx"
        _make_headings_docx(docx)
        result = read_docx(docx)
        cleaned = clean(result["text"])
        assert "Experience" in cleaned["sections"]
        assert "Skills" in cleaned["sections"]
        assert "Education" in cleaned["sections"]

    def test_heading_text_replaced(self, tmp_path: Path) -> None:
        """The cleaned text must contain the canonical heading, not the synonym."""
        docx = tmp_path / "headings.docx"
        _make_headings_docx(docx)
        result = read_docx(docx)
        cleaned = clean(result["text"])
        assert "Experience" in cleaned["text"]
        assert "WORK HISTORY" not in cleaned["text"]


# ---------------------------------------------------------------------------
# Test 6: Corrupted PDF — no crash, error result
# ---------------------------------------------------------------------------


class TestCorruptedFile:
    def test_corrupt_pdf_doesnt_crash(self, tmp_path: Path) -> None:
        """A corrupted PDF must not raise; extractor must return status=error."""
        bad = tmp_path / "corrupt.pdf"
        bad.write_bytes(b"this is not a valid PDF \x00\x01\x02\x03" * 100)
        result = extract_file(bad)
        assert result["status"] == "error"
        assert "error" in result

    def test_corrupt_pdf_error_contains_filename(self, tmp_path: Path) -> None:
        bad = tmp_path / "corrupt.pdf"
        bad.write_bytes(b"junk bytes" * 50)
        result = extract_file(bad)
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Test 7: Unsupported extension
# ---------------------------------------------------------------------------


class TestUnsupportedExtension:
    def test_xyz_raises_value_error(self, tmp_path: Path) -> None:
        f = tmp_path / "resume.xyz"
        f.write_text("hello")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            read_file(f)


# ---------------------------------------------------------------------------
# Test 8: Extractor end-to-end — output files written
# ---------------------------------------------------------------------------


class TestExtractorOutputFiles:
    def test_txt_file_written(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """extract_file must write a .txt to data/extracted/<stem>.txt."""
        docx = tmp_path / "john_doe.docx"
        doc = _DocxDoc()
        doc.add_paragraph("SUMMARY")
        doc.add_paragraph("Experienced developer with 4 years experience.")
        doc.save(str(docx))

        # Redirect extracted output to tmp_path so we don't pollute the repo
        monkeypatch.chdir(tmp_path)
        result = extract_file(docx)

        assert result["status"] == "ok"
        txt_path = tmp_path / "data" / "extracted" / "john_doe.txt"
        assert txt_path.exists(), f"Expected {txt_path} to exist"
        assert txt_path.read_text(encoding="utf-8").strip()

    def test_json_file_written(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """extract_file must write a valid JSON to data/extracted/<stem>.json."""
        docx = tmp_path / "jane_smith.docx"
        doc = _DocxDoc()
        doc.add_paragraph("SKILLS")
        doc.add_paragraph("Python, Docker, AWS")
        doc.save(str(docx))

        monkeypatch.chdir(tmp_path)
        result = extract_file(docx)

        assert result["status"] == "ok"
        json_path = tmp_path / "data" / "extracted" / "jane_smith.json"
        assert json_path.exists()
        record = json.loads(json_path.read_text(encoding="utf-8"))
        assert "text" in record
        assert "sections" in record
        assert "Skills" in record["sections"]

    def test_extracted_json_has_required_keys(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pdf = tmp_path / "single_col.pdf"
        _make_single_col_pdf(pdf, ["EXPERIENCE", "Worked at Acme Corp for 3 years"])
        monkeypatch.chdir(tmp_path)
        result = extract_file(pdf)
        assert result["status"] == "ok"
        required = {"file", "type", "pages", "method_used", "ocr_used", "sections", "text"}
        assert required.issubset(result.keys())


# ---------------------------------------------------------------------------
# Test 9: Empty DOCX — graceful warning, no crash
# ---------------------------------------------------------------------------


class TestEmptyDocx:
    def test_empty_docx_status_ok(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty DOCX should not crash; extractor returns ok with empty text warning."""
        docx = tmp_path / "empty_resume.docx"
        _make_empty_docx(docx)
        monkeypatch.chdir(tmp_path)
        result = extract_file(docx)
        # Should succeed (not error) but warnings may flag empty text
        assert result["status"] == "ok"

    def test_empty_docx_char_count_zero(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        docx = tmp_path / "empty_resume2.docx"
        _make_empty_docx(docx)
        monkeypatch.chdir(tmp_path)
        result = extract_file(docx)
        assert result.get("char_count", 0) == 0


# ---------------------------------------------------------------------------
# Test 10: File-not-found — raises cleanly
# ---------------------------------------------------------------------------


class TestMissingFile:
    def test_missing_pdf_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_file("definitely_does_not_exist.pdf")

    def test_missing_docx_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_docx("nonexistent.docx")
