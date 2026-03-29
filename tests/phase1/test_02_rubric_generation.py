"""
Phase 1 — Test 02: Rubric Generation
======================================
One LLM call per module (module-scoped fixture).
Saves:
  outputs/02a_rubric_llm_input.json  — JD text sent to LLM
  outputs/02b_rubric_final.json      — post-processed rubric with all weights
"""

import json
import pytest
from pathlib import Path

from src.utils.extract_pdf import extract_text_from_file_sync
from src.pipelines.generate_rubric import generate_rubric_from_jd
from src.pipelines.rubric_post_processor import validate_rubric_json

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUTS  = Path(__file__).parent / "outputs"
OUTPUTS.mkdir(exist_ok=True)

JD_PDF = FIXTURES / "sample_jd.pdf"


# ── One LLM call for the whole module ─────────────────────────────────────────

@pytest.fixture(scope="module")
def jd_text():
    text, _, _ = extract_text_from_file_sync(str(JD_PDF))
    return text


@pytest.fixture(scope="module")
async def rubric(jd_text):
    """Single LLM call (2-pass: generate + fixup) — reused by all tests."""
    print("\n\n[TEST 02] Rubric Generation — calling LLM (2-pass, once)...")

    (OUTPUTS / "02a_rubric_llm_input.json").write_text(json.dumps({
        "source_file": JD_PDF.name,
        "jd_text": jd_text,
        "jd_char_count": len(jd_text),
    }, indent=2))
    print("  [SAVED] outputs/02a_rubric_llm_input.json")

    result = await generate_rubric_from_jd(jd_text, use_cache=False)

    (OUTPUTS / "02b_rubric_final.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    print("  [SAVED] outputs/02b_rubric_final.json")

    print(f"  threshold_score  : {result.get('threshold_score')}")
    print(f"  total sections   : {len(result.get('sections', []))}")
    all_cw = sum(c.get("weight", 0) for s in result.get("sections", []) for c in s.get("criteria", []))
    print(f"  global_criteria_weight_sum: {all_cw:.1f}")
    for s in result.get("sections", []):
        print(f"  [{s['key']}]  criteria={len(s.get('criteria', []))}")
        for c in s["criteria"]:
            print(f"    - {c['name']} (importance={c.get('importance')}, global_weight={c.get('weight')}%)")

    return result


# ── Tests (all use the same cached rubric) ────────────────────────────────────

async def test_rubric_has_sections(rubric):
    assert isinstance(rubric, dict)
    assert "sections" in rubric
    assert len(rubric["sections"]) > 0


async def test_rubric_sections_have_no_weight(rubric):
    """Sections are UI grouping only — they must not carry a scoring weight."""
    for s in rubric["sections"]:
        assert s.get("weight") is None, (
            f"Section '{s['key']}' has weight={s.get('weight')} but sections should be weightless"
        )


async def test_rubric_global_criteria_weights_sum_to_100(rubric):
    """Global criterion weights across ALL sections must sum to 100."""
    total = sum(c.get("weight", 0) for s in rubric["sections"] for c in s.get("criteria", []))
    assert abs(total - 100) < 1.0, f"Global criterion weights sum to {total:.1f}, expected ~100"


async def test_rubric_passes_validation(rubric):
    ok, errors = validate_rubric_json(rubric)
    assert ok, "Rubric validation failed:\n" + "\n".join(f"  • {e}" for e in errors)
