from pydantic import BaseModel, Field
from typing import List, Literal


class CriteriaRating(BaseModel):
    criteria: str
    rating: int = Field(..., ge=1, le=10)  # enforce 1–10 scale
    comment: str | None = None  # optional comment for each criteria


class InterviewAssessmentCreate(BaseModel):
    criteria_ratings: List[CriteriaRating]
    final_verdict: Literal["Hire", "No Hire"]