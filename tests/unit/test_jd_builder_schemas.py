"""
Unit tests for JDBuilderAnswers and related schemas in jd_builder_schemas.py.

These tests are pure Pydantic validation — no DB, no LLM, no I/O.
"""

import pytest
from pydantic import ValidationError

from src.schemas.jd_builder_schemas import (
    JDBuilderAnswers,
    CreateManualJDRequest,
    UpdateJDRequest,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _valid_answers(**overrides) -> dict:
    """Return a minimal valid JDBuilderAnswers payload."""
    base = {
        "role_title": "Senior Backend Engineer",
        "experience_level": "senior",
        "responsibilities": "Design and build scalable APIs for our platform.",
        "skills_required": ["Python", "FastAPI", "PostgreSQL"],
    }
    base.update(overrides)
    return base


# ── JDBuilderAnswers: happy path ───────────────────────────────────────────────

class TestJDBuilderAnswersValid:
    def test_minimal_required_fields(self):
        obj = JDBuilderAnswers(**_valid_answers())
        assert obj.role_title == "Senior Backend Engineer"
        assert obj.experience_level == "senior"
        assert obj.skills_required == ["Python", "FastAPI", "PostgreSQL"]

    def test_all_optional_fields_accepted(self):
        obj = JDBuilderAnswers(**_valid_answers(
            department="Engineering",
            openings=3,
            experience_years_min=5,
            experience_years_max=10,
            skills_nice_to_have=["Docker", "Redis"],
            education="B.Tech in Computer Science",
            certifications="AWS Certified",
            location="Bangalore, India",
            work_mode="hybrid",
            employment_type="full_time",
            salary_range="25–40 LPA",
            company_description="DeskZero is an AI-powered HR platform.",
            role_highlights="Work with cutting-edge LLMs.",
            benefits="Health insurance, flexible hours.",
            special_requirements="Travel required quarterly.",
        ))
        assert obj.work_mode == "hybrid"
        assert obj.employment_type == "full_time"
        assert obj.openings == 3

    def test_experience_level_normalised_to_lowercase(self):
        obj = JDBuilderAnswers(**_valid_answers(experience_level="SENIOR"))
        assert obj.experience_level == "senior"

    def test_work_mode_normalised_to_lowercase(self):
        obj = JDBuilderAnswers(**_valid_answers(work_mode="REMOTE"))
        assert obj.work_mode == "remote"

    def test_skills_required_whitespace_stripped(self):
        obj = JDBuilderAnswers(**_valid_answers(skills_required=["  Python  ", "FastAPI"]))
        assert obj.skills_required == ["Python", "FastAPI"]

    def test_experience_years_equal_min_max_accepted(self):
        obj = JDBuilderAnswers(**_valid_answers(experience_years_min=5, experience_years_max=5))
        assert obj.experience_years_min == 5
        assert obj.experience_years_max == 5


# ── JDBuilderAnswers: validation errors ───────────────────────────────────────

class TestJDBuilderAnswersInvalid:
    def test_missing_role_title(self):
        data = _valid_answers()
        del data["role_title"]
        with pytest.raises(ValidationError, match="role_title"):
            JDBuilderAnswers(**data)

    def test_missing_experience_level(self):
        data = _valid_answers()
        del data["experience_level"]
        with pytest.raises(ValidationError, match="experience_level"):
            JDBuilderAnswers(**data)

    def test_invalid_experience_level(self):
        with pytest.raises(ValidationError, match="experience_level"):
            JDBuilderAnswers(**_valid_answers(experience_level="god_mode"))

    def test_invalid_work_mode(self):
        with pytest.raises(ValidationError, match="work_mode"):
            JDBuilderAnswers(**_valid_answers(work_mode="moon"))

    def test_invalid_employment_type(self):
        with pytest.raises(ValidationError, match="employment_type"):
            JDBuilderAnswers(**_valid_answers(employment_type="gig"))

    def test_experience_years_max_less_than_min(self):
        with pytest.raises(ValidationError, match="experience_years_max"):
            JDBuilderAnswers(**_valid_answers(experience_years_min=8, experience_years_max=3))

    def test_skills_required_empty_list(self):
        with pytest.raises(ValidationError, match="skills_required"):
            JDBuilderAnswers(**_valid_answers(skills_required=[]))

    def test_skills_required_only_whitespace(self):
        with pytest.raises(ValidationError, match="skills_required"):
            JDBuilderAnswers(**_valid_answers(skills_required=["   ", "  "]))

    def test_role_title_too_short(self):
        with pytest.raises(ValidationError, match="role_title"):
            JDBuilderAnswers(**_valid_answers(role_title="A"))

    def test_responsibilities_too_short(self):
        with pytest.raises(ValidationError, match="responsibilities"):
            JDBuilderAnswers(**_valid_answers(responsibilities="Short"))

    def test_negative_openings(self):
        with pytest.raises(ValidationError, match="openings"):
            JDBuilderAnswers(**_valid_answers(openings=0))


# ── CreateManualJDRequest ─────────────────────────────────────────────────────

class TestCreateManualJDRequest:
    def test_valid(self):
        obj = CreateManualJDRequest(title="Backend Engineer", content="We are looking for...")
        assert obj.title == "Backend Engineer"

    def test_title_too_short(self):
        with pytest.raises(ValidationError, match="title"):
            CreateManualJDRequest(title="A", content="Some content here")

    def test_content_too_short(self):
        with pytest.raises(ValidationError, match="content"):
            CreateManualJDRequest(title="Backend Engineer", content="Hi")


# ── UpdateJDRequest ───────────────────────────────────────────────────────────

class TestUpdateJDRequest:
    def test_all_fields_optional(self):
        # Both fields optional — empty update is valid
        obj = UpdateJDRequest()
        assert obj.title is None
        assert obj.content is None

    def test_partial_update_title_only(self):
        obj = UpdateJDRequest(title="New Title")
        assert obj.title == "New Title"
        assert obj.content is None

    def test_title_too_short(self):
        with pytest.raises(ValidationError, match="title"):
            UpdateJDRequest(title="X")
