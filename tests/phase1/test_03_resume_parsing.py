"""
Phase 1 — Test 03: Resume PDF Parsing
=======================================
No LLM call — pure PDF text extraction.
Saves: outputs/03_resume_parsed_text.json
"""

import json
import pytest
from pathlib import Path

from src.utils.extract_pdf import extract_text_from_file_sync

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUTS  = Path(__file__).parent / "outputs"
OUTPUTS.mkdir(exist_ok=True)

RESUME_PDF = FIXTURES / "sample_resume.pdf"


# ── One extraction call for the whole module ──────────────────────────────────

@pytest.fixture(scope="module")
def parsed_resume():
    print(f"\n\n[TEST 03] Resume PDF Parsing — {RESUME_PDF.name}")
    text, pages, method = extract_text_from_file_sync(str(RESUME_PDF))

    (OUTPUTS / "03_resume_parsed_text.json").write_text(json.dumps({
        "source_file": RESUME_PDF.name,
        "file_size_bytes": RESUME_PDF.stat().st_size,
        "pages": pages,
        "extraction_method": method,
        "char_count": len(text),
        "full_text": text,
    }, indent=2))
    print(f"  [SAVED] outputs/03_resume_parsed_text.json")
    print(f"  pages={pages}, method={method}, chars={len(text)}")
    print(f"  preview: {text[:200]!r}")

    return text, pages, method


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_resume_text_non_empty(parsed_resume):
    text, _, _ = parsed_resume
    assert len(text.strip()) >= 50, f"Too little text extracted: {len(text)} chars"


def test_resume_page_count(parsed_resume):
    _, pages, _ = parsed_resume
    assert pages >= 1, f"Page count must be >= 1, got {pages}"


def test_resume_extraction_method_valid(parsed_resume):
    _, _, method = parsed_resume
    assert method in ("text", "ocr", "gemini_ocr", "native", "pdfplumber"), \
        f"Unexpected extraction method: {method!r}"


def test_resume_text_has_enough_content(parsed_resume):
    text, _, _ = parsed_resume
    char_count = len(text.strip())
    if char_count < 500:
        print(f"\n  ⚠ WARNING: low char count ({char_count}) — OCR may have been used")
    assert char_count >= 50
