"""
Phase 1 — Test 04: Candidate Info Extraction
=============================================
One LLM call per module (module-scoped fixture).
Saves: outputs/04_candidate_info.json
"""

import json
import pytest
from pathlib import Path

from src.utils.extract_pdf import extract_text_from_file_sync
from src.pipelines.extract_candidate_info import extract_candidate_info_sync
from src.schemas.user_schemas import CandidateInfoSchema

FIXTURES = Path(__file__).parent.parent / "fixtures"
OUTPUTS  = Path(__file__).parent / "outputs"
OUTPUTS.mkdir(exist_ok=True)

RESUME_PDF = FIXTURES / "sample_resume.pdf"


# ── One LLM call for the whole module ─────────────────────────────────────────

@pytest.fixture(scope="module")
def candidate_info():
    print(f"\n\n[TEST 04] Candidate Info Extraction — calling LLM (once)...")

    resume_text, _, _ = extract_text_from_file_sync(str(RESUME_PDF))
    header = resume_text[:2000]

    result = extract_candidate_info_sync(resume_text)

    (OUTPUTS / "04_candidate_info.json").write_text(json.dumps({
        "input": {
            "source_file": RESUME_PDF.name,
            "total_resume_chars": len(resume_text),
            "llm_input_header_chars": len(header),
            "llm_input_header": header,
        },
        "output": {
            "full_name": result.full_name,
            "email": result.email,
            "phone": result.phone,
            "current_title": result.current_title,
            "current_company": result.current_company,
        },
    }, indent=2))
    print("  [SAVED] outputs/04_candidate_info.json")

    print(f"  full_name      : {result.full_name!r}")
    print(f"  email          : {result.email!r}")
    print(f"  phone          : {result.phone!r}")
    print(f"  current_title  : {result.current_title!r}")
    print(f"  current_company: {result.current_company!r}")

    return result


# ── Tests (all use the same cached result) ─────────────────────────────────────

def test_candidate_has_identity(candidate_info):
    """Must extract at least a name or email."""
    assert candidate_info.full_name or candidate_info.email, (
        f"No name or email found: name={candidate_info.full_name!r}, email={candidate_info.email!r}"
    )


def test_candidate_name_not_placeholder(candidate_info):
    placeholders = {"john doe", "jane doe", "john smith", "name", "candidate"}
    if candidate_info.full_name:
        assert candidate_info.full_name.lower() not in placeholders, (
            f"Name looks like a placeholder: {candidate_info.full_name!r}"
        )


def test_candidate_email_has_at_sign(candidate_info):
    if candidate_info.email:
        assert "@" in candidate_info.email, f"Invalid email: {candidate_info.email!r}"


def test_candidate_result_is_correct_schema(candidate_info):
    assert isinstance(candidate_info, CandidateInfoSchema)
    assert hasattr(candidate_info, "current_title")
    assert hasattr(candidate_info, "current_company")
