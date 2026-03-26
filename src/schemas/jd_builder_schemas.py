"""
Pydantic schemas for the JD Builder feature.

JDBuilderAnswers   — the Q&A form data submitted by the recruiter
GeneratedJDOutput  — the structured response from the AI generation pipeline
JDVersionResponse  — a single JD version record returned from the API
JDVersionListResponse — paginated list of JD versions for a job
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── Input: recruiter Q&A answers ──────────────────────────────────────────────

class JDBuilderAnswers(BaseModel):
    """All fields the recruiter fills in during the JD Builder wizard."""

    # Step 1 — Role Basics
    role_title: str = Field(..., min_length=2, max_length=200)
    department: Optional[str] = Field(None, max_length=100)
    openings: Optional[int] = Field(None, ge=1, le=500)
    experience_level: str = Field(
        ...,
        description="One of: intern, junior, mid, senior, lead, director",
    )
    experience_years_min: Optional[int] = Field(None, ge=0, le=50)
    experience_years_max: Optional[int] = Field(None, ge=0, le=50)

    # Step 2 — Role Details
    responsibilities: str = Field(..., min_length=10, max_length=5000)
    skills_required: List[str] = Field(..., min_length=1)
    skills_nice_to_have: Optional[List[str]] = None
    education: Optional[str] = Field(None, max_length=300)
    certifications: Optional[str] = Field(None, max_length=300)

    # Step 3 — Workplace
    location: Optional[str] = Field(None, max_length=200)
    work_mode: Optional[str] = Field(
        None,
        description="One of: remote, hybrid, onsite",
    )
    employment_type: Optional[str] = Field(
        None,
        description="One of: full_time, part_time, contract, internship",
    )
    salary_range: Optional[str] = Field(None, max_length=100)

    # Step 4 — Company & Culture
    company_description: Optional[str] = Field(None, max_length=1000)
    role_highlights: Optional[str] = Field(None, max_length=1000)
    benefits: Optional[str] = Field(None, max_length=1000)
    special_requirements: Optional[str] = Field(None, max_length=500)

    @field_validator("experience_level")
    @classmethod
    def validate_experience_level(cls, v: str) -> str:
        allowed = {"intern", "junior", "mid", "senior", "lead", "director"}
        if v.lower() not in allowed:
            raise ValueError(f"experience_level must be one of: {', '.join(sorted(allowed))}")
        return v.lower()

    @field_validator("work_mode")
    @classmethod
    def validate_work_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"remote", "hybrid", "onsite"}
        if v.lower() not in allowed:
            raise ValueError(f"work_mode must be one of: {', '.join(sorted(allowed))}")
        return v.lower()

    @field_validator("employment_type")
    @classmethod
    def validate_employment_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"full_time", "part_time", "contract", "internship"}
        if v.lower() not in allowed:
            raise ValueError(f"employment_type must be one of: {', '.join(sorted(allowed))}")
        return v.lower()

    @field_validator("experience_years_max")
    @classmethod
    def max_gte_min(cls, v: Optional[int], info) -> Optional[int]:
        min_val = info.data.get("experience_years_min")
        if v is not None and min_val is not None and v < min_val:
            raise ValueError("experience_years_max must be >= experience_years_min")
        return v

    @field_validator("skills_required")
    @classmethod
    def skills_not_empty_strings(cls, v: List[str]) -> List[str]:
        cleaned = [s.strip() for s in v if s.strip()]
        if not cleaned:
            raise ValueError("skills_required must contain at least one non-empty skill")
        return cleaned


# ── Output: AI-generated JD ───────────────────────────────────────────────────

class GeneratedJDOutput(BaseModel):
    """Returned by POST /api/jd-builder/generate."""

    generated_jd_text: str = Field(
        ...,
        description="Full markdown-formatted Job Description text",
    )
    suggested_title: str
    suggested_location: Optional[str] = None
    suggested_salary: Optional[str] = None


# ── JD version CRUD schemas ───────────────────────────────────────────────────

class JDVersionResponse(BaseModel):
    """A single JD version as returned by the API."""

    id: UUID
    job_id: UUID
    version_number: int
    title: str
    content: str
    generation_method: Optional[str]
    status: str
    created_by_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JDVersionListResponse(BaseModel):
    job_id: UUID
    active_jd_id: Optional[UUID]
    versions: List[JDVersionResponse]


class CreateManualJDRequest(BaseModel):
    """Recruiter writes or pastes JD content manually."""

    title: str = Field(..., min_length=2, max_length=200)
    content: str = Field(..., min_length=10)


class UpdateJDRequest(BaseModel):
    """Partial update to a draft JD version."""

    title: Optional[str] = Field(None, min_length=2, max_length=200)
    content: Optional[str] = Field(None, min_length=10)


class JDFromPromptRequest(BaseModel):
    """Free-form recruiter prompt → AI generates the full JD."""
    prompt: str = Field(..., min_length=3, max_length=5000)


class ActivateJDResponse(BaseModel):
    """Response after activating a JD version."""

    activated_jd_id: UUID
    version_number: int
    message: str
