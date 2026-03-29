"""
V2 Rubric Schemas — array-based, domain-aware.

Design decisions:
- Criteria are Lists (ordered) instead of Dicts (unordered) so priority ordering is preserved.
- Each criterion has `name`, `display_name`, `priority`, and optional `value` (constraint text).
- `schema_version` in the saved JSONB ensures backward compatibility with old rubrics.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────

class NonNegotiableCategory(str, Enum):
    """Categories for non-negotiable criteria — binary dealbreakers."""
    LOCATION = "location"
    WORK_AUTHORIZATION = "work_authorization"
    DEGREE = "degree"
    CERTIFICATION = "certification"
    EXPERIENCE_YEARS = "experience_years"
    EMPLOYMENT_TYPE = "employment_type"
    SECURITY_CLEARANCE = "security_clearance"
    TRAVEL = "travel"
    OTHER = "other"


VALID_DOMAINS = [
    "technology", "finance", "sales", "marketing", "management",
    "operations", "healthcare", "legal", "education", "design",
    "human_resources", "engineering", "customer_support",
    "data_science", "other",
]


# ─── Sub-Criterion ───────────────────────────────────────────────────

class SubCriterionV2(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=150)
    # weight: display percentage within this criterion's sub-criteria group (sums to 100).
    #   Computed by rubric_post_processor from importance. DISPLAY ONLY — never used in scoring.
    weight: int = Field(default=0, ge=0, le=100)
    # importance: raw LLM signal (1-5) used only to derive sub-criterion display weight.
    #   Sub-criteria are display-only; neither importance nor weight affects the criterion score.
    importance: int = Field(default=3, ge=1, le=5)
    value: Optional[str] = None
    value_type: Literal["none"] = "none"


# ─── Non-Negotiable Criterion ────────────────────────────────────────

MAX_NON_NEGOTIABLES = 5

class NonNegotiableCriterion(BaseModel):
    """
    A binary dealbreaker criterion extracted from the JD.

    Non-negotiables are NOT scored on a 0-10 scale — they are pass/fail.
    If a resume fails ANY non-negotiable, it is auto-rejected before LLM scoring.
    """
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=150)
    requirement: str = Field(
        ..., min_length=1, max_length=300,
        description="What is required, e.g. 'Onsite in Bangalore', 'Bachelor's degree minimum'"
    )
    category: NonNegotiableCategory = NonNegotiableCategory.OTHER
    verification_question: str = Field(
        ..., min_length=10, max_length=500,
        description="Binary yes/no question for the LLM to verify against the resume"
    )


# ─── Criterion ───────────────────────────────────────────────────────

class CriterionV2(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=150)
    # weight: DISPLAY field — global percentage of overall score for this criterion (all criteria sum to 100).
    #   Computed by rubric_post_processor._apply_global_criterion_weights() from importance.
    #   Example: importance=10 on a rubric with 18 total criteria → weight≈7 (shown in UI as "7%").
    #   NOT read by the scoring engine; use importance for scoring math.
    weight: int = Field(default=0, ge=0, le=100)
    # importance: SCORING field — raw LLM-assigned signal (1-10, higher = more critical).
    #   Used directly by score_post_processor.compute_flat_score():
    #     overall = Σ(criterion_score × importance) / total_importance
    #   Equivalent to weight but avoids an extra normalization step at score time.
    importance: int = Field(default=5, ge=1, le=10)
    priority: int = Field(..., ge=1)
    value: Optional[str] = None
    value_type: Literal["none"] = "none"
    sub_criteria: Optional[List[SubCriterionV2]] = None


# ─── Section ─────────────────────────────────────────────────────────

class RubricSectionV2(BaseModel):
    key: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=100)
    # weight: DEPRECATED — accepted for backward compatibility but stripped by post-processor.
    #   Sections have no scoring weight in the flat model; all weighting lives on criteria.
    weight: Optional[int] = Field(default=None, ge=0, le=100)
    # importance: DISPLAY ONLY — hint for UI section ordering. Default=5, never used in scoring.
    #   The scoring engine does not read section importance at any point.
    importance: int = Field(default=5, ge=1, le=10)
    criteria: List[CriterionV2]


# ─── Job Data (shared across v1 & v2) ────────────────────────────────

class JobDataSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str
    location: Optional[str] = None
    salary: Optional[str] = None
    target_headcount: int = Field(default=1, ge=1)
    metadata: Optional[Dict[str, Any]] = None


class ExtendedJobDataSchema(JobDataSchema):
    voice_ai_enabled: bool = False
    manual_rounds_count: int = 0
    is_confidential: bool = False


# ─── LLM Output Schema (what generate_rubric returns) ────────────────

class ExtractedJDSchemaV2(BaseModel):
    """The output from the rubric generation LLM pipeline."""
    domain: str
    domain_confidence: float = Field(..., ge=0.0, le=1.0)
    job_data: JobDataSchema
    threshold_score: int = Field(..., ge=0, le=100)
    version: Optional[int] = 1
    sections: List[RubricSectionV2]
    non_negotiables: List[NonNegotiableCriterion] = Field(default_factory=list)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v):
        if v not in VALID_DOMAINS:
            return "other"
        return v

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, v):
        if not v:
            raise ValueError("At least one section is required")
        return v

    @field_validator("non_negotiables")
    @classmethod
    def validate_non_negotiables(cls, v):
        if len(v) > MAX_NON_NEGOTIABLES:
            return v[:MAX_NON_NEGOTIABLES]
        return v


class PipelineRubricOutput(BaseModel):
    """
    Contract for rubric output from the pipeline (LLM + post-processor).
    Only validates what the pipeline actually produces; job_data is added later by the API layer.
    Use this for validating pipeline output; use ExtractedJDSchemaV2 when job_data is present.
    """
    domain: str = "other"
    domain_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    threshold_score: int = Field(default=60, ge=0, le=100)
    version: Optional[int] = 1
    sections: List[RubricSectionV2]
    non_negotiables: List[NonNegotiableCriterion] = Field(default_factory=list)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        if v not in VALID_DOMAINS:
            return "other"
        return v

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, v: List) -> List:
        if not v:
            raise ValueError("At least one section is required")
        return v

    @field_validator("non_negotiables")
    @classmethod
    def validate_non_negotiables(cls, v: List) -> List:
        if len(v) > MAX_NON_NEGOTIABLES:
            return v[:MAX_NON_NEGOTIABLES]
        return v


# ─── API Request Schemas ─────────────────────────────────────────────

class SetRubricRequest(BaseModel):
    """
    Sent when user clicks 'Set Rubric' to create both Job + Rubric.
    This is the ONLY time the job and rubric are written to DB.
    """
    job_data: ExtendedJobDataSchema
    threshold_score: int = Field(..., ge=0, le=100)
    domain: str = "other"
    raw_jd_text: Optional[str] = None
    sections: List[RubricSectionV2]
    non_negotiables: List[NonNegotiableCriterion] = Field(default_factory=list)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v):
        if v not in VALID_DOMAINS:
            return "other"
        return v


class UpdateRubricRequest(BaseModel):
    """
    Used when updating rubric on an existing job (new version).
    """
    threshold_score: int = Field(..., ge=0, le=100)
    sections: List[RubricSectionV2]
    non_negotiables: List[NonNegotiableCriterion] = Field(default_factory=list)
    raw_jd_text: Optional[str] = None
    # Optional audit hints (backend still enforces core invariants)
    source: Optional[str] = None          # "ai" | "manual" | "combined"
    created_via: Optional[str] = None     # e.g. "ui_edit" | "ai_regen"
    change_reason: Optional[str] = None   # e.g. "edit" | "ai_regen" | "copy"
    change_type: Optional[str] = None     # e.g. "minor" | "major"


# ─── Generate Rubric Preview (Step 2 → Step 3) ───────────────────────

class GenerateRubricPreviewRequest(BaseModel):
    """
    Called when user clicks Next after editing job fields.
    Generates rubric JSON from raw JD text and returns it for UI editing.
    """
    raw_jd_text: str = Field(..., min_length=50)
    job_data: ExtendedJobDataSchema


# ─── Backward-Compatibility: V1 → V2 Converter ──────────────────────

def _snake_to_display(name: str) -> str:
    """Convert snake_case to Title Case for display_name."""
    return " ".join(word.capitalize() for word in name.split("_") if word)


def convert_v1_criteria_to_v2(criteria_dict: dict) -> dict:
    """
    Convert old dict-based criteria JSONB to v2 array-based format.

    Old format:
        {"mandatory_criteria": {"python": {"weight": 25, "value": null, "sub_criteria": {...}}}}

    New format:
        {"schema_version": 2, "sections": [{key: "mandatory_criteria", criteria: [...]}]}
    """
    sections = []

    for section_key, label in [
        ("mandatory_criteria", "Must-Have Requirements"),
        ("screening_criteria", "Preferred Qualifications"),
    ]:
        old_criteria = criteria_dict.get(section_key, {})
        criteria_list = []
        priority = 1

        for name, data in old_criteria.items():
            sub_criteria = None
            if data.get("sub_criteria"):
                sub_list = []
                sub_priority = 1
                for sub_name, sub_data in data["sub_criteria"].items():
                    sub_list.append({
                        "name": sub_name,
                        "display_name": _snake_to_display(sub_name),
                        "weight": sub_data.get("weight", 0),
                        "value": sub_data.get("value"),
                        "value_type": "none",
                    })
                    sub_priority += 1
                sub_criteria = sub_list

            criteria_list.append({
                "name": name,
                "display_name": _snake_to_display(name),
                "weight": data.get("weight", 0),
                "priority": priority,
                "value": data.get("value"),
                "value_type": "none",
                "sub_criteria": sub_criteria,
            })
            priority += 1

        sections.append({
            "key": section_key,
            "label": label,
            "weight": 60 if section_key == "mandatory_criteria" else 40,
            "importance": 8 if section_key == "mandatory_criteria" else 5,
            "criteria": criteria_list,
        })

    return {
        "schema_version": 2,
        "sections": sections,
    }


def read_rubric_criteria(criteria_jsonb: dict) -> dict:
    """
    Read rubric criteria from JSONB, handling both v1 and v2 formats.
    Always returns v2 format.
    """
    if criteria_jsonb.get("schema_version") == 2:
        return criteria_jsonb

    # v1 format — convert
    return convert_v1_criteria_to_v2(criteria_jsonb)
