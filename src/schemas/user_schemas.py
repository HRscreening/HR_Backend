"""
User & Scoring Schemas.

Rubric schemas (CriterionV2, RubricSectionV2, etc.) have been moved
to src/schemas/rubric_schemas.py.

This file retains:
  - Org schema
  - Candidate info schema
  - Score output schemas (used by the scoring pipeline)
  - Resume data schemas (used by workers)
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Dict, Optional, Any, List
from dataclasses import dataclass


# ─── Organization ────────────────────────────────────────────────────

class NewOrgSchema(BaseModel):
    name: str = Field(max_length=100)
    email: EmailStr
    address: str | None = None


# ─── Scoring Pipeline Schemas ────────────────────────────────────────

class CandidateInfoSchema(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class SubCriterionScoreSchema(BaseModel):
    score: float = Field(ge=0, le=100)


class CriterionScoreSchema(BaseModel):
    score: float
    sub_criteria: Dict[str, float] = Field(default_factory=dict)


class BreakdownSchema(BaseModel):
    mandatory_criteria: Dict[str, CriterionScoreSchema]
    screening_criteria: Dict[str, CriterionScoreSchema]


class ScoreOutputSchema(BaseModel):
    candidate_info: CandidateInfoSchema
    ai_analysis: Optional[Dict[str, List[str]]] = None
    overall_score: float = Field(ge=0, le=100)
    ai_confidence: float = Field(ge=0.0, le=1.0)
    breakdown: BreakdownSchema
    grounding_data: Dict[str, Any]


# ─── Resume Worker Schemas ───────────────────────────────────────────

@dataclass
class ResumeScoreResult:
    resume_id: str
    application_id: str
    score: ScoreOutputSchema


@dataclass
class ResumeDataSchema:
    application_id: str
    resume_id: str
    resume_text: str


@dataclass
class BatchResumeDataSchema:
    application_id: str
    resume_id: str
    score: Optional[ScoreOutputSchema] = None
    error: Optional[str] = None