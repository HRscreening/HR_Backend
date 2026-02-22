"""
Basic JD analysis schema (fast UI prefill).

This is intentionally lighter than the full rubric generation schema.
It powers Step 1 (Upload JD) so the user can quickly move to editing job fields.
"""

from pydantic import BaseModel, Field

from src.schemas.rubric_schemas import JobDataSchema


class JDBasicAnalysisSchema(BaseModel):
    domain: str = "other"
    domain_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    job_data: JobDataSchema

