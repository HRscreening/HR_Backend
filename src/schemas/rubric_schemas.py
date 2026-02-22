"""
V2 Rubric Schemas — array-based, domain-aware.

Design decisions:
- Criteria are Lists (ordered) instead of Dicts (unordered) so priority ordering is preserved.
- Each criterion has `name`, `display_name`, `priority`, and optional `value` (constraint text).
- `schema_version` in the saved JSONB ensures backward compatibility with old rubrics.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Literal


# ─── Enums ────────────────────────────────────────────────────────────

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
    weight: int = Field(default=0, ge=0, le=100)
    importance: int = Field(default=3, ge=1, le=5)
    value: Optional[str] = None
    value_type: Literal["none"] = "none"


# ─── Criterion ───────────────────────────────────────────────────────

class CriterionV2(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=150)
    weight: int = Field(default=0, ge=0, le=100)
    importance: int = Field(default=5, ge=1, le=10)
    priority: int = Field(..., ge=1)
    value: Optional[str] = None
    value_type: Literal["none"] = "none"
    sub_criteria: Optional[List[SubCriterionV2]] = None


# ─── Section ─────────────────────────────────────────────────────────

class RubricSectionV2(BaseModel):
    key: str = Field(..., min_length=1, max_length=80)
    label: str = Field(..., min_length=1, max_length=100)
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
    sections: List[RubricSectionV2]

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


class PipelineRubricOutput(BaseModel):
    """
    Contract for rubric output from the pipeline (LLM + post-processor).
    Only validates what the pipeline actually produces; job_data is added later by the API layer.
    Use this for validating pipeline output; use ExtractedJDSchemaV2 when job_data is present.
    """
    domain: str = "other"
    domain_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    threshold_score: int = Field(default=60, ge=0, le=100)
    sections: List[RubricSectionV2]

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
