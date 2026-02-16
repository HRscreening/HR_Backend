from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Dict, Optional, Any, List
from dataclasses import dataclass


from pydantic import BaseModel, field_validator
from typing import Dict, Optional,Any

    
class CandidateInfoSchema(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class SubCriterionScoreSchema(BaseModel):
    score: float = Field(ge=0, le=100)
    reason: Optional[str] = None
    evidence: Optional[List[str]] = None

class CriterionScoreSchema(BaseModel):
    score: float
    reason: Optional[str] = None
    evidence: Optional[List[str]] = None
    sub_criteria: Dict[str, float] = Field(default_factory=dict)


class BreakdownSchema(BaseModel):
    mandatory_criteria: Dict[str, CriterionScoreSchema]
    screening_criteria: Dict[str, CriterionScoreSchema]



class ScoreOutputSchema(BaseModel):
    candidate_info: CandidateInfoSchema
    ai_analysis: Optional[Dict[str,List[str]]] = None
    overall_score: float = Field(ge=0, le=100)
    ai_confidence: float = Field(ge=0.0, le=1.0)
    breakdown: BreakdownSchema

