"""
Phase 1 — Test 06: Non-Negotiable Screening
=============================================
Tests the non-negotiable extraction in rubric generation
and the binary pass/fail screening pipeline.

Unit tests for:
  - Schema validation (NonNegotiableCriterion)
  - Post-processor non-negotiable handling
  - Screener result evaluation logic
  - Quality of non-negotiable extraction from rubric generation (LLM)
"""

import json
import pytest
from pathlib import Path

from src.schemas.rubric_schemas import (
    NonNegotiableCriterion,
    NonNegotiableCategory,
    PipelineRubricOutput,
    MAX_NON_NEGOTIABLES,
)
from src.pipelines.rubric_post_processor import post_process_rubric, validate_rubric_json
from src.pipelines.non_negotiable_screener import (
    _evaluate_results,
    NonNegotiableCheckResult,
    CONFIDENCE_THRESHOLD,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUTS  = Path(__file__).parent / "outputs"
OUTPUTS.mkdir(exist_ok=True)

JD_PDF = FIXTURES / "sample_jd.pdf"


# ── Schema Tests ─────────────────────────────────────────────────────

def test_non_negotiable_criterion_valid():
    nn = NonNegotiableCriterion(
        name="location_bangalore",
        display_name="Location: Bangalore Onsite",
        requirement="Must be onsite in Bangalore",
        category=NonNegotiableCategory.LOCATION,
        verification_question="Does the candidate's resume indicate they are located in or willing to relocate to Bangalore?",
    )
    assert nn.name == "location_bangalore"
    assert nn.category == NonNegotiableCategory.LOCATION


def test_non_negotiable_criterion_rejects_short_question():
    with pytest.raises(Exception):
        NonNegotiableCriterion(
            name="test",
            display_name="Test",
            requirement="Test requirement",
            category=NonNegotiableCategory.OTHER,
            verification_question="Yes?",  # too short (<10 chars)
        )


def test_pipeline_output_accepts_non_negotiables():
    rubric = PipelineRubricOutput(
        sections=[{
            "key": "technical_skills",
            "label": "Technical Skills",
            "criteria": [{
                "name": "python",
                "display_name": "Python",
                "importance": 8,
                "priority": 1,
                "weight": 100,
                "value": None,
                "value_type": "none",
                "sub_criteria": [],
            }],
        }],
        non_negotiables=[
            NonNegotiableCriterion(
                name="min_experience",
                display_name="Minimum Experience",
                requirement="7+ years of ML experience",
                category=NonNegotiableCategory.EXPERIENCE_YEARS,
                verification_question="Does the candidate have 7 or more years of ML or AI experience?",
            )
        ],
    )
    assert len(rubric.non_negotiables) == 1


def test_pipeline_output_caps_non_negotiables():
    many_nns = [
        NonNegotiableCriterion(
            name=f"nn_{i}",
            display_name=f"NN {i}",
            requirement=f"Requirement {i}",
            category=NonNegotiableCategory.OTHER,
            verification_question=f"Does the candidate meet requirement number {i}?",
        )
        for i in range(10)
    ]
    rubric = PipelineRubricOutput(
        sections=[{
            "key": "skills",
            "label": "Skills",
            "criteria": [{
                "name": "skill_1",
                "display_name": "Skill 1",
                "importance": 5,
                "priority": 1,
                "weight": 100,
                "value": None,
                "value_type": "none",
                "sub_criteria": [],
            }],
        }],
        non_negotiables=many_nns,
    )
    assert len(rubric.non_negotiables) == MAX_NON_NEGOTIABLES


# ── Post-Processor Tests ─────────────────────────────────────────────

def test_post_processor_cleans_non_negotiables():
    raw = {
        "domain": "other",
        "domain_confidence": 0.5,
        "threshold_score": 65,
        "version": 1,
        "sections": [{
            "key": "technical_skills",
            "label": "Technical Skills",
            "criteria": [
                {
                    "name": "python_expertise",
                    "display_name": "Python Expertise",
                    "importance": 8,
                    "priority": 1,
                    "value": None,
                    "value_type": "none",
                    "sub_criteria": [],
                },
            ],
        }],
        "non_negotiables": [
            {
                "name": "location_onsite",
                "display_name": "Onsite in Bangalore",
                "requirement": "Must work onsite in Bangalore office",
                "category": "location",
                "verification_question": "Does the candidate indicate they are in or willing to relocate to Bangalore?",
            },
        ],
    }
    result = post_process_rubric(raw)
    assert len(result["non_negotiables"]) == 1
    assert result["non_negotiables"][0]["category"] == "location"
    assert result["non_negotiables"][0]["name"] == "location_onsite"


def test_post_processor_removes_duplicate_criteria():
    """If a non-negotiable duplicates a section criterion, the criterion should be removed."""
    raw = {
        "domain": "other",
        "domain_confidence": 0.5,
        "threshold_score": 65,
        "version": 1,
        "sections": [{
            "key": "required_qualifications",
            "label": "Required Qualifications",
            "criteria": [
                {
                    "name": "location_onsite",
                    "display_name": "Onsite in Bangalore",
                    "importance": 10,
                    "priority": 1,
                    "value": "Bangalore (onsite)",
                    "value_type": "none",
                    "sub_criteria": [],
                },
                {
                    "name": "ml_experience",
                    "display_name": "ML Experience",
                    "importance": 9,
                    "priority": 2,
                    "value": "7+ years",
                    "value_type": "none",
                    "sub_criteria": [],
                },
            ],
        }],
        "non_negotiables": [
            {
                "name": "location_onsite",
                "display_name": "Onsite in Bangalore",
                "requirement": "Must work onsite in Bangalore",
                "category": "location",
                "verification_question": "Does the candidate indicate they are in Bangalore?",
            },
        ],
    }
    result = post_process_rubric(raw)

    # The location criterion should have been removed from the section
    req_section = next(
        (s for s in result["sections"] if s["key"] == "required_qualifications"),
        None,
    )
    if req_section:
        criterion_names = [c["name"] for c in req_section["criteria"]]
        assert "location_onsite" not in criterion_names, (
            "Non-negotiable criterion was not removed from sections"
        )


def test_post_processor_handles_empty_non_negotiables():
    raw = {
        "domain": "other",
        "domain_confidence": 0.5,
        "threshold_score": 65,
        "version": 1,
        "sections": [{
            "key": "skills",
            "label": "Skills",
            "criteria": [{
                "name": "python",
                "display_name": "Python",
                "importance": 8,
                "priority": 1,
                "value": None,
                "value_type": "none",
                "sub_criteria": [],
            }],
        }],
    }
    result = post_process_rubric(raw)
    assert result["non_negotiables"] == []


def test_post_processor_validates_non_negotiables():
    raw = {
        "domain": "other",
        "domain_confidence": 0.5,
        "threshold_score": 65,
        "version": 1,
        "sections": [{
            "key": "skills",
            "label": "Skills",
            "criteria": [{
                "name": "python",
                "display_name": "Python",
                "importance": 8,
                "priority": 1,
                "weight": 100,
                "value": None,
                "value_type": "none",
                "sub_criteria": [],
            }],
        }],
        "non_negotiables": [
            {
                "name": "valid_nn",
                "display_name": "Valid NN",
                "requirement": "Must have this",
                "category": "other",
                "verification_question": "Does the candidate have this requirement?",
            },
        ],
    }
    result = post_process_rubric(raw)
    ok, errors = validate_rubric_json(result)
    assert ok, f"Validation failed: {errors}"


# ── Screening Evaluation Tests ───────────────────────────────────────

def test_evaluate_results_all_pass():
    results = [
        NonNegotiableCheckResult(
            criterion_name="location",
            passed=True,
            confidence=0.9,
            evidence="Based in Bangalore",
        ),
        NonNegotiableCheckResult(
            criterion_name="degree",
            passed=True,
            confidence=0.85,
            evidence="B.Tech in Computer Science",
        ),
    ]
    screening = _evaluate_results("resume-1", results)
    assert screening.passed is True
    assert len(screening.failed_criteria) == 0
    assert len(screening.flagged_criteria) == 0


def test_evaluate_results_high_confidence_fail():
    results = [
        NonNegotiableCheckResult(
            criterion_name="location",
            passed=False,
            confidence=0.9,
            evidence="Currently based in New York",
        ),
    ]
    screening = _evaluate_results("resume-1", results)
    assert screening.passed is False
    assert "location" in screening.failed_criteria


def test_evaluate_results_low_confidence_flagged():
    results = [
        NonNegotiableCheckResult(
            criterion_name="location",
            passed=False,
            confidence=0.5,  # below CONFIDENCE_THRESHOLD
            evidence="No evidence found",
        ),
    ]
    screening = _evaluate_results("resume-1", results)
    assert screening.passed is True  # low confidence = flagged, NOT rejected
    assert "location" in screening.flagged_criteria
    assert len(screening.failed_criteria) == 0


def test_evaluate_results_null_passed_flagged():
    results = [
        NonNegotiableCheckResult(
            criterion_name="work_auth",
            passed=None,
            confidence=0.3,
            evidence="No evidence found",
        ),
    ]
    screening = _evaluate_results("resume-1", results)
    assert screening.passed is True  # null = unclear, flagged for review
    assert "work_auth" in screening.flagged_criteria


def test_evaluate_results_mixed():
    results = [
        NonNegotiableCheckResult(
            criterion_name="location",
            passed=True,
            confidence=0.95,
            evidence="Bangalore office",
        ),
        NonNegotiableCheckResult(
            criterion_name="experience_years",
            passed=False,
            confidence=0.85,
            evidence="3 years of experience (requires 7+)",
        ),
        NonNegotiableCheckResult(
            criterion_name="degree",
            passed=None,
            confidence=0.4,
            evidence="No evidence found",
        ),
    ]
    screening = _evaluate_results("resume-1", results)
    assert screening.passed is False  # one high-confidence failure
    assert "experience_years" in screening.failed_criteria
    assert "degree" in screening.flagged_criteria
    assert len(screening.details) == 3


# ── Rubric Generation with Non-Negotiables (LLM test) ────────────────

@pytest.fixture(scope="module")
def jd_text():
    from src.utils.extract_pdf import extract_text_from_file_sync
    text, _, _ = extract_text_from_file_sync(str(JD_PDF))
    return text


@pytest.fixture(scope="module")
async def rubric_with_nn(jd_text):
    """Generate a rubric and check if non-negotiables are extracted."""
    from src.pipelines.generate_rubric import generate_rubric_from_jd

    result = await generate_rubric_from_jd(jd_text, use_cache=False)

    (OUTPUTS / "06a_rubric_with_non_negotiables.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False)
    )
    print(f"\n  [TEST 06] Non-negotiables extracted: {len(result.get('non_negotiables', []))}")
    for nn in result.get("non_negotiables", []):
        print(f"    - {nn['display_name']} ({nn['category']}): {nn['requirement']}")
    return result


async def test_rubric_has_non_negotiables_key(rubric_with_nn):
    """The rubric must always have a non_negotiables key (may be empty)."""
    assert "non_negotiables" in rubric_with_nn
    assert isinstance(rubric_with_nn["non_negotiables"], list)


async def test_non_negotiables_within_limit(rubric_with_nn):
    assert len(rubric_with_nn["non_negotiables"]) <= MAX_NON_NEGOTIABLES


async def test_non_negotiables_have_required_fields(rubric_with_nn):
    for nn in rubric_with_nn.get("non_negotiables", []):
        assert nn.get("name"), "Non-negotiable missing name"
        assert nn.get("display_name"), "Non-negotiable missing display_name"
        assert nn.get("requirement"), "Non-negotiable missing requirement"
        assert nn.get("category"), "Non-negotiable missing category"
        assert nn.get("verification_question"), "Non-negotiable missing verification_question"
        assert len(nn["verification_question"]) >= 10, "Verification question too short"


async def test_non_negotiables_not_duplicated_in_sections(rubric_with_nn):
    """Non-negotiable items must not also appear in sections."""
    nn_names = {nn["name"] for nn in rubric_with_nn.get("non_negotiables", [])}
    if not nn_names:
        pytest.skip("No non-negotiables extracted from this JD")

    for section in rubric_with_nn.get("sections", []):
        for criterion in section.get("criteria", []):
            assert criterion["name"] not in nn_names, (
                f"Non-negotiable '{criterion['name']}' duplicated in section '{section['key']}'"
            )


async def test_rubric_still_valid_with_non_negotiables(rubric_with_nn):
    ok, errors = validate_rubric_json(rubric_with_nn)
    assert ok, "Rubric validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
