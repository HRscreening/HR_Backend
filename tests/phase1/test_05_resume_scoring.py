"""
Phase 1 — Test 05: Resume Scoring
====================================
Two LLM calls total per module (rubric generation + resume scoring),
both cached via module-scoped fixtures.

Saves:
  outputs/05a_scoring_rubric_used.json    — rubric the resume was scored against
  outputs/05b_scoring_llm_raw_output.json — raw LLM output (sections, grounding, ai_analysis)
  outputs/05c_scoring_final_result.json   — final weighted score + full breakdown
"""

import json
import pytest
from pathlib import Path

from src.utils.extract_pdf import extract_text_from_file_sync
from src.pipelines.generate_rubric import generate_rubric_from_jd
from src.pipelines.score_resumes import score_resume_sync, chain as scoring_chain
from src.pipelines.score_post_processor import compute_weighted_score
from src.pipelines.extract_candidate_info import extract_candidate_info_sync
from src.schemas.user_schemas import ResumeDataSchema

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUTS  = Path(__file__).parent / "outputs"
OUTPUTS.mkdir(exist_ok=True)

RESUME_PDF = FIXTURES / "sample_resume.pdf"
JD_PDF     = FIXTURES / "sample_jd.pdf"


# ── Module-scoped fixtures (one call each) ────────────────────────────────────

@pytest.fixture(scope="module")
async def rubric():
    print("\n\n[TEST 05] Rubric Generation (for scoring) — calling LLM...")
    jd_text, _, _ = extract_text_from_file_sync(str(JD_PDF))
    result = await generate_rubric_from_jd(jd_text, use_cache=False)

    (OUTPUTS / "05a_scoring_rubric_used.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    print("  [SAVED] outputs/05a_scoring_rubric_used.json")
    return result


@pytest.fixture(scope="module")
def resume_text():
    text, _, _ = extract_text_from_file_sync(str(RESUME_PDF))
    return text


@pytest.fixture(scope="module")
def llm_raw_output(rubric, resume_text):
    """Direct scoring chain call — captures raw LLM output before post-processing."""
    print("\n  [TEST 05] Resume Scoring (raw LLM) — calling LLM...")

    section_keys = ", ".join(f'"{s["key"]}"' for s in rubric.get("sections", []))
    result = scoring_chain.invoke({
        "criteria": json.dumps(rubric),
        "resume_text": resume_text[:24000],
        "section_keys": section_keys,
    })

    raw_dict = result.model_dump() if hasattr(result, "model_dump") else vars(result)

    (OUTPUTS / "05b_scoring_llm_raw_output.json").write_text(
        json.dumps({
            "input": {
                "resume_source": RESUME_PDF.name,
                "jd_source": JD_PDF.name,
                "resume_char_count": len(resume_text),
                "rubric_sections": [s["key"] for s in rubric.get("sections", [])],
            },
            "raw_llm_output": raw_dict,
        }, indent=2, default=str)
    )
    print("  [SAVED] outputs/05b_scoring_llm_raw_output.json")
    print(f"  ai_confidence    : {result.ai_confidence}")
    print(f"  sections returned: {list(result.sections.keys())}")

    return result


@pytest.fixture(scope="module")
def final_score(rubric, resume_text):
    """Full pipeline via score_resume_sync — same path as the worker."""
    candidate_info = extract_candidate_info_sync(resume_text)

    resume = ResumeDataSchema(
        application_id="test-app-id-001",
        resume_id="test-resume-id-001",
        resume_text=resume_text,
    )

    results = score_resume_sync(
        resumes=[resume],
        criteria=rubric,
        candidate_infos={"test-resume-id-001": candidate_info},
    )
    assert len(results) == 1
    score = results[0].score
    score_dict = score.model_dump() if hasattr(score, "model_dump") else vars(score)

    (OUTPUTS / "05c_scoring_final_result.json").write_text(
        json.dumps({
            "candidate_info": {
                "full_name": candidate_info.full_name,
                "email": candidate_info.email,
                "current_title": candidate_info.current_title,
                "current_company": candidate_info.current_company,
            },
            "final_score": score_dict,
        }, indent=2, default=str)
    )
    print("  [SAVED] outputs/05c_scoring_final_result.json")
    print(f"  overall_score    : {score.overall_score}")
    print(f"  ai_confidence    : {score.ai_confidence}")
    for sk, sv in (score.breakdown or {}).items():
        sec = sv.get("score", "?") if isinstance(sv, dict) else "?"
        print(f"  [{sk}] score={sec}")

    return score


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_llm_raw_output_has_required_fields(llm_raw_output):
    assert hasattr(llm_raw_output, "sections")
    assert hasattr(llm_raw_output, "grounding_data")
    assert hasattr(llm_raw_output, "ai_confidence")
    assert hasattr(llm_raw_output, "ai_analysis")


def test_llm_sections_match_rubric_keys(llm_raw_output, rubric):
    rubric_keys = {s["key"] for s in rubric["sections"]}
    llm_keys    = set(llm_raw_output.sections.keys())
    missing = rubric_keys - llm_keys
    extra   = llm_keys - rubric_keys
    assert not missing, f"LLM missing sections: {missing}"
    assert not extra,   f"LLM returned unknown sections: {extra}"


def test_grounding_has_evidence(llm_raw_output):
    all_evidence = [
        ev
        for section in llm_raw_output.grounding_data.values()
        for crit in section.values()
        for ev in (crit.evidence or [])
    ]
    assert len(all_evidence) > 0, "No evidence found in grounding_data"
    print(f"\n  Total evidence snippets: {len(all_evidence)}")
    for ev in all_evidence[:3]:
        print(f"    › {ev[:120]!r}")


def test_final_score_in_range(final_score):
    assert 0 <= final_score.overall_score <= 100, \
        f"Score out of range: {final_score.overall_score}"


def test_final_score_has_breakdown(final_score):
    assert final_score.breakdown, "Breakdown is empty"
    assert len(final_score.breakdown) > 0


def test_final_score_has_grounding(final_score):
    assert final_score.grounding_data, "grounding_data is empty"


def test_ai_confidence_in_range(final_score):
    assert 0.0 <= final_score.ai_confidence <= 1.0, \
        f"ai_confidence out of range: {final_score.ai_confidence}"
