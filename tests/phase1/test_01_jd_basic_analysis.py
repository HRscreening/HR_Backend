"""
Phase 1 — Test 01: JD Basic Analysis
=====================================
One LLM call per module (module-scoped fixture).
Saves: outputs/01_jd_basic_analysis.json
"""

import json
import pytest
from pathlib import Path

from src.utils.extract_pdf import extract_text_from_file_sync
from src.pipelines.jd_basic_analysis import analyze_jd_basic

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUTS  = Path(__file__).parent / "outputs"
OUTPUTS.mkdir(exist_ok=True)

JD_PDF = FIXTURES / "sample_jd.pdf"


# ── One LLM call for the whole module ─────────────────────────────────────────

@pytest.fixture(scope="module")
def jd_text():
    text, pages, method = extract_text_from_file_sync(str(JD_PDF))
    # Save the raw extracted text so you can inspect what the LLM receives
    (OUTPUTS / "01_jd_extracted_text.json").write_text(json.dumps({
        "source_file": JD_PDF.name,
        "pages": pages,
        "extraction_method": method,
        "char_count": len(text),
        "full_text": text,
    }, indent=2))
    print(f"\n  [SAVED] outputs/01_jd_extracted_text.json  (pages={pages}, method={method}, chars={len(text)})")
    return text


@pytest.fixture(scope="module")
async def jd_analysis(jd_text):
    """Single LLM call — result reused by all tests in this module."""
    print("\n\n[TEST 01] JD Basic Analysis — calling LLM (once)...")
    result = await analyze_jd_basic(jd_text)

    (OUTPUTS / "01_jd_basic_analysis.json").write_text(json.dumps({
        "input": {"source_file": JD_PDF.name, "jd_text": jd_text},
        "output": result,
    }, indent=2))
    print(f"  [SAVED] outputs/01_jd_basic_analysis.json")

    print(f"  domain           : {result.get('domain')}")
    print(f"  domain_confidence: {result.get('domain_confidence')}")
    print(f"  title            : {(result.get('job_data') or {}).get('title')}")
    print(f"  location         : {(result.get('job_data') or {}).get('location')}")
    print(f"  salary           : {(result.get('job_data') or {}).get('salary')}")
    return result


# ── Tests (all use the same cached result) ─────────────────────────────────────

async def test_jd_basic_analysis_shape(jd_analysis):
    assert isinstance(jd_analysis, dict)
    assert "domain" in jd_analysis
    assert "domain_confidence" in jd_analysis
    assert "job_data" in jd_analysis
    jd = jd_analysis["job_data"]
    assert "title" in jd
    assert "description" in jd
    assert "target_headcount" in jd


async def test_jd_basic_analysis_domain_confidence_in_range(jd_analysis):
    conf = jd_analysis.get("domain_confidence", -1)
    assert isinstance(conf, (int, float))
    assert 0.0 <= conf <= 1.0, f"domain_confidence out of range: {conf}"


async def test_jd_basic_analysis_description_non_empty(jd_analysis):
    desc = (jd_analysis.get("job_data") or {}).get("description") or ""
    assert len(desc.strip()) > 20, f"Description too short: {desc!r}"
