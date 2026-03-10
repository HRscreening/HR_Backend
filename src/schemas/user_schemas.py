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
    current_title: Optional[str] = None   # Most recent job title
    current_company: Optional[str] = None  # Most recent employer


# ─── LLM Raw Output (what the LLM returns — NO overall_score) ───────

class SubCriterionRawScore(BaseModel):
    score: float = Field(ge=0, le=100)
    reasoning: str = Field(default="", max_length=300)


class CriterionRawScore(BaseModel):
    score: float = Field(ge=0, le=100)
    reasoning: str = Field(default="", max_length=300)
    sub_criteria: Optional[Dict[str, SubCriterionRawScore]] = Field(default_factory=dict)


class SectionRawScore(BaseModel):
    """Scores for all criteria in one section."""
    criteria: Dict[str, CriterionRawScore]


class GroundingCriterionData(BaseModel):
    jd_requirement: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    match_assessment: Optional[str] = None  # "exceeds" | "strong" | "partial" | "weak" | "none"


class LLMScoringOutput(BaseModel):
    """What the LLM returns — NO overall_score. Post-processor computes it.
    candidate_info is extracted separately via extract_candidate_info pipeline,
    but kept here for backward compatibility with any code that reads it."""
    candidate_info: Optional[CandidateInfoSchema] = None
    ai_analysis: Optional[Dict[str, List[str]]] = None
    ai_confidence: float = Field(ge=0.0, le=1.0)
    sections: Dict[str, SectionRawScore]
    grounding_data: Dict[str, Dict[str, GroundingCriterionData]]
    distinguishing_factors: Optional[List[str]] = None


class LLMScoringOnlyOutput(BaseModel):
    """Scoring-only LLM output — used with with_structured_output().
    Does NOT include candidate_info (extracted separately)."""
    ai_analysis: Dict[str, List[str]] = Field(
        description="Two keys: 'good_points' and 'bad_points', each a list of bullet strings"
    )
    ai_confidence: float = Field(ge=0.0, le=1.0, description="How confident the model is in its scoring, 0.0 to 1.0")
    sections: Dict[str, SectionRawScore] = Field(
        description="Keys MUST exactly match the rubric section keys. Each section contains criteria scores."
    )
    grounding_data: Dict[str, Dict[str, GroundingCriterionData]] = Field(
        description="Evidence for each criterion. Keys: grounding_data[section_key][criterion_name]"
    )
    distinguishing_factors: Optional[List[str]] = Field(
        default=None,
        description="2-4 unique or rare qualifications that make this candidate stand out"
    )


# ─── Final Score Output (what gets stored in DB) ─────────────────────

class ScoreOutputSchema(BaseModel):
    candidate_info: CandidateInfoSchema
    ai_analysis: Optional[Dict[str, List[str]]] = None
    overall_score: float = Field(ge=0, le=100)
    raw_overall_score: Optional[float] = None
    ai_confidence: float = Field(ge=0.0, le=1.0)
    breakdown: Dict[str, Any]
    grounding_data: Dict[str, Any]
    distinguishing_factors: Optional[List[str]] = None
    scoring_method: str = "weighted_v2"


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
