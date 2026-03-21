"""
Unit tests for public_apply_schemas.py.

Covers:
  - FormQuestionSchema validation
  - UpdateFormConfigRequest (core fields, duplicate keys)
  - GeneratePublicLinkRequest (slug format)
  - PublicApplyRequest (candidate submission fields)

No DB, no network — pure Pydantic validation.
"""

import pytest
from pydantic import ValidationError

from src.schemas.public_apply_schemas import (
    FormQuestionSchema,
    GeneratePublicLinkRequest,
    PublicApplyRequest,
    UpdateFormConfigRequest,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _question(**overrides) -> dict:
    base = {
        "id": "q_001",
        "key": "full_name",
        "label": "Full Name",
        "type": "text",
        "required": True,
        "removable": False,
    }
    base.update(overrides)
    return base


def _core_questions() -> list[dict]:
    """The three non-removable core questions every form must include."""
    return [
        {"id": "q_full_name", "key": "full_name", "label": "Full Name", "type": "text", "required": True, "removable": False},
        {"id": "q_email", "key": "email", "label": "Email", "type": "email", "required": True, "removable": False},
        {"id": "q_resume", "key": "resume", "label": "Resume", "type": "file", "required": True, "removable": False},
    ]


# ── FormQuestionSchema ─────────────────────────────────────────────────────────

class TestFormQuestionSchema:
    def test_valid_text_question(self):
        q = FormQuestionSchema(**_question())
        assert q.key == "full_name"
        assert q.type == "text"

    def test_valid_select_question_with_options(self):
        q = FormQuestionSchema(**_question(
            id="q_work_mode",
            key="work_mode",
            label="Preferred Work Mode",
            type="select",
            required=False,
            removable=True,
            options=["Remote", "Hybrid", "On-site"],
        ))
        assert q.options == ["Remote", "Hybrid", "On-site"]

    def test_all_allowed_types_accepted(self):
        allowed = ["text", "email", "number", "url", "textarea", "file", "select", "boolean"]
        for t in allowed:
            opts = ["A", "B"] if t == "select" else None
            q = FormQuestionSchema(**_question(type=t, options=opts, removable=True))
            assert q.type == t

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError, match="type"):
            FormQuestionSchema(**_question(type="magic"))

    def test_select_without_options_rejected(self):
        with pytest.raises(ValidationError, match="options"):
            FormQuestionSchema(**_question(type="select", options=None))

    def test_key_must_start_with_lowercase_letter(self):
        with pytest.raises(ValidationError, match="key"):
            FormQuestionSchema(**_question(key="1badkey"))

    def test_key_with_uppercase_rejected(self):
        with pytest.raises(ValidationError, match="key"):
            FormQuestionSchema(**_question(key="FullName"))

    def test_key_with_hyphen_rejected(self):
        with pytest.raises(ValidationError, match="key"):
            FormQuestionSchema(**_question(key="full-name"))

    def test_key_with_underscore_accepted(self):
        q = FormQuestionSchema(**_question(key="full_name_2"))
        assert q.key == "full_name_2"

    def test_empty_label_rejected(self):
        with pytest.raises(ValidationError, match="label"):
            FormQuestionSchema(**_question(label=""))


# ── UpdateFormConfigRequest ────────────────────────────────────────────────────

class TestUpdateFormConfigRequest:
    def test_valid_with_core_questions_only(self):
        req = UpdateFormConfigRequest(questions=_core_questions())
        assert len(req.questions) == 3

    def test_valid_with_extra_questions(self):
        questions = _core_questions() + [
            {"id": "q_phone", "key": "phone", "label": "Phone", "type": "text", "required": False, "removable": True},
        ]
        req = UpdateFormConfigRequest(questions=questions)
        assert len(req.questions) == 4

    def test_missing_full_name_rejected(self):
        questions = [q for q in _core_questions() if q["key"] != "full_name"]
        with pytest.raises(ValidationError, match="full_name"):
            UpdateFormConfigRequest(questions=questions)

    def test_missing_email_rejected(self):
        questions = [q for q in _core_questions() if q["key"] != "email"]
        with pytest.raises(ValidationError, match="email"):
            UpdateFormConfigRequest(questions=questions)

    def test_missing_resume_rejected(self):
        questions = [q for q in _core_questions() if q["key"] != "resume"]
        with pytest.raises(ValidationError, match="resume"):
            UpdateFormConfigRequest(questions=questions)

    def test_duplicate_keys_rejected(self):
        questions = _core_questions() + [
            {"id": "q_phone_a", "key": "phone", "label": "Phone A", "type": "text", "required": False, "removable": True},
            {"id": "q_phone_b", "key": "phone", "label": "Phone B", "type": "text", "required": False, "removable": True},
        ]
        with pytest.raises(ValidationError, match="Duplicate"):
            UpdateFormConfigRequest(questions=questions)

    def test_empty_questions_list_rejected(self):
        with pytest.raises(ValidationError):
            UpdateFormConfigRequest(questions=[])


# ── GeneratePublicLinkRequest ──────────────────────────────────────────────────

class TestGeneratePublicLinkRequest:
    def test_no_slug_is_valid(self):
        req = GeneratePublicLinkRequest()
        assert req.custom_slug is None

    def test_valid_custom_slug(self):
        req = GeneratePublicLinkRequest(custom_slug="senior-backend-engineer-2026")
        assert req.custom_slug == "senior-backend-engineer-2026"

    def test_slug_with_digits_accepted(self):
        req = GeneratePublicLinkRequest(custom_slug="role-2026-batch1")
        assert req.custom_slug == "role-2026-batch1"

    def test_slug_too_short_rejected(self):
        with pytest.raises(ValidationError, match="custom_slug"):
            GeneratePublicLinkRequest(custom_slug="abc")

    def test_slug_uppercase_rejected(self):
        with pytest.raises(ValidationError, match="custom_slug"):
            GeneratePublicLinkRequest(custom_slug="Senior-Backend-Engineer")

    def test_slug_starts_with_hyphen_rejected(self):
        with pytest.raises(ValidationError, match="custom_slug"):
            GeneratePublicLinkRequest(custom_slug="-senior-backend")

    def test_slug_ends_with_hyphen_rejected(self):
        with pytest.raises(ValidationError, match="custom_slug"):
            GeneratePublicLinkRequest(custom_slug="senior-backend-")

    def test_slug_with_spaces_rejected(self):
        with pytest.raises(ValidationError, match="custom_slug"):
            GeneratePublicLinkRequest(custom_slug="senior backend engineer")


# ── PublicApplyRequest ─────────────────────────────────────────────────────────

class TestPublicApplyRequest:
    def test_minimal_valid_submission(self):
        req = PublicApplyRequest(full_name="Jane Doe", email="jane@example.com")
        assert req.full_name == "Jane Doe"
        assert str(req.email) == "jane@example.com"

    def test_all_optional_fields_accepted(self):
        req = PublicApplyRequest(
            full_name="Jane Doe",
            email="jane@example.com",
            phone="+91 9876543210",
            current_role="Software Engineer",
            current_company="TechCorp",
            experience_years=5,
            location="Bangalore",
            linkedin_url="https://linkedin.com/in/janedoe",
            portfolio_url="https://github.com/janedoe",
            notice_period="30 days",
            expected_salary="18 LPA",
            custom_answers={"why_interested": "Great opportunity"},
        )
        assert req.experience_years == 5
        assert req.current_company == "TechCorp"

    def test_missing_full_name_rejected(self):
        with pytest.raises(ValidationError, match="full_name"):
            PublicApplyRequest(email="jane@example.com")

    def test_missing_email_rejected(self):
        with pytest.raises(ValidationError, match="email"):
            PublicApplyRequest(full_name="Jane Doe")

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError, match="email"):
            PublicApplyRequest(full_name="Jane Doe", email="not-an-email")

    def test_negative_experience_years_rejected(self):
        with pytest.raises(ValidationError, match="experience_years"):
            PublicApplyRequest(
                full_name="Jane Doe", email="jane@example.com", experience_years=-1
            )

    def test_experience_years_above_70_rejected(self):
        with pytest.raises(ValidationError, match="experience_years"):
            PublicApplyRequest(
                full_name="Jane Doe", email="jane@example.com", experience_years=71
            )

    def test_empty_full_name_rejected(self):
        with pytest.raises(ValidationError, match="full_name"):
            PublicApplyRequest(full_name="", email="jane@example.com")
