"""
Pydantic schemas for the Public Application Portal.

PublicJobInfoResponse      — job info shown on the candidate form page
FormQuestionSchema         — a single form question definition
ApplicationFormConfigResponse — the full form config (questions list)
PublicApplyRequest         — candidate's form submission (non-file fields)
PublicApplyResponse        — returned after successful submission
PublicLinkResponse         — returned after generating / fetching the public link
UpdateFormConfigRequest    — recruiter edits the question list
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.models.application_form_config_model import ALLOWED_QUESTION_TYPES


# ── Candidate-facing: public job info ─────────────────────────────────────────

class PublicJobInfoResponse(BaseModel):
    """Minimal job data shown on the public application page."""

    job_id: UUID
    title: str
    location: Optional[str]
    description: Optional[str]
    organization_name: Optional[str]
    # The ordered list of questions to render on the form
    form_questions: List[FormQuestionSchema]


# ── Form question definition ──────────────────────────────────────────────────

class FormQuestionSchema(BaseModel):
    """A single form field definition stored inside ApplicationFormConfig.questions."""

    id: str = Field(..., min_length=1, max_length=100)
    key: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=200)
    type: str
    required: bool
    removable: bool
    placeholder: Optional[str] = Field(None, max_length=300)
    # Only used for 'select' type
    options: Optional[List[str]] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ALLOWED_QUESTION_TYPES:
            raise ValueError(
                f"Question type '{v}' is not allowed. Must be one of: "
                f"{', '.join(sorted(ALLOWED_QUESTION_TYPES))}"
            )
        return v

    @field_validator("options")
    @classmethod
    def options_required_for_select(cls, v: Optional[List[str]], info) -> Optional[List[str]]:
        if info.data.get("type") == "select" and not v:
            raise ValueError("options must be provided for 'select' type questions")
        return v


# ── Recruiter: update form config ─────────────────────────────────────────────

class UpdateFormConfigRequest(BaseModel):
    """Recruiter submits the edited question list to save a new form config version."""

    questions: List[FormQuestionSchema] = Field(..., min_length=1)

    @field_validator("questions")
    @classmethod
    def core_fields_present(cls, questions: List[FormQuestionSchema]) -> List[FormQuestionSchema]:
        """Ensure the three non-removable core fields are always present."""
        core_keys = {"full_name", "email", "resume"}
        present_keys = {q.key for q in questions}
        missing = core_keys - present_keys
        if missing:
            raise ValueError(
                f"Core fields cannot be removed: {', '.join(sorted(missing))}"
            )
        return questions

    @field_validator("questions")
    @classmethod
    def no_duplicate_keys(cls, questions: List[FormQuestionSchema]) -> List[FormQuestionSchema]:
        keys = [q.key for q in questions]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate question keys are not allowed")
        return questions


class ApplicationFormConfigResponse(BaseModel):
    """The active/draft form config for a job returned to the recruiter UI."""

    id: UUID
    job_id: UUID
    version_number: int
    status: str
    questions: List[FormQuestionSchema]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Public link management ────────────────────────────────────────────────────

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{3,78}[a-z0-9]$")


class GeneratePublicLinkRequest(BaseModel):
    """Recruiter optionally supplies a custom slug when generating the link."""

    custom_slug: Optional[str] = Field(None, min_length=5, max_length=80)

    @field_validator("custom_slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not _SLUG_PATTERN.match(v):
            raise ValueError(
                "Slug must be 5–80 characters, lowercase letters/digits/hyphens only, "
                "and cannot start or end with a hyphen."
            )
        return v


class PublicLinkResponse(BaseModel):
    """Returned after generating or fetching the public link for a job."""

    job_id: UUID
    public_slug: Optional[str]
    public_apply_enabled: bool
    active_jd_id: Optional[UUID]
    active_form_config_id: Optional[UUID]
    # Constructed by the API layer — not stored in DB
    public_url: Optional[str] = None


# ── Candidate submission ──────────────────────────────────────────────────────

class PublicApplyRequest(BaseModel):
    """
    Non-file form fields submitted by the candidate.
    Only full_name and email are always required.
    Additional fields are present / absent based on the job's form config.
    """

    full_name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=30)
    current_role: Optional[str] = Field(None, max_length=200)
    current_company: Optional[str] = Field(None, max_length=200)
    experience_years: Optional[int] = Field(None, ge=0, le=70)
    location: Optional[str] = Field(None, max_length=200)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    portfolio_url: Optional[str] = Field(None, max_length=500)
    notice_period: Optional[str] = Field(None, max_length=100)
    expected_salary: Optional[str] = Field(None, max_length=100)
    # Answers to any custom questions the recruiter added, keyed by question.key
    custom_answers: Optional[Dict[str, Any]] = None


class PublicApplyResponse(BaseModel):
    """Returned after a successful public application submission."""

    status: Literal["success"]
    message: str
    application_id: UUID
