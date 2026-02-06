from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Dict, Optional, Any, List
from dataclasses import dataclass


class NewOrgSchema(BaseModel):
    name: str = Field(max_length=100)
    email: EmailStr
    address: str | None = None




from pydantic import BaseModel, field_validator
from typing import Dict, Optional,Any


class SubCriterionSchema(BaseModel):
    weight: int
    value: Optional[str] = None

class CriterionSchema(BaseModel):
    weight: int
    value: Optional[str] = None
    sub_criteria: Optional[Dict[str, SubCriterionSchema]] = None

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v):
        if v < 0:
            raise ValueError("weight must be non-negative")
        return v


    @field_validator("sub_criteria")
    @classmethod
    def validate_sub_criteria(cls, sub, info):
        if not sub:
            return sub

        total = sum(c.weight for c in sub.values())

        if total != 100:
            raise ValueError(
                f"sub_criteria weights must sum to 100 (got {total})"
            )

        return sub


class JobDataSchema(BaseModel):
    title: str
    description: str
    location: str | None = None
    salary: str | None = None
    target_headcount: int
    metadata: Dict[str, Any] | None = None
    


class ExtractedJDSchema(BaseModel):
    job_data: JobDataSchema
    threshold_score: int
    mandatory_criteria: Dict[str, CriterionSchema]
    screening_criteria: Dict[str, CriterionSchema]

    @field_validator("threshold_score")
    @classmethod
    def validate_threshold_score(cls, v):
        if v < 0:
            raise ValueError("threshold_score must be non-negative")
        return v

class Criterion(BaseModel):
    mandatory_criteria: Dict[str, CriterionSchema]
    screening_criteria: Dict[str, CriterionSchema]
    

class ExtendedJobDataSchema(JobDataSchema):
    metadata: Dict[str, Any] | None = None
    voice_ai_enabled: bool = False
    manual_rounds_count: int = 0
    is_confidential: bool = False

class NewJobSchema(BaseModel):  
    job_data:ExtendedJobDataSchema
    threshold_score:int
    criteria:Criterion
    
    
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
    ai_analysis: Optional[Dict[str,List[str]]] = None
    overall_score: float = Field(ge=0, le=100)
    ai_confidence: float = Field(ge=0.0, le=1.0)
    breakdown: BreakdownSchema
    grounding_data: Dict[str, Any]


@dataclass
class ResumeScoreResult:
    resume_id: str
    application_id: str
    score: ScoreOutputSchema


@dataclass
class ResumeDataSchema:
    application_id : str
    resume_id :str
    resume_text : str

@dataclass
class BatchResumeDataSchema:
    application_id : str
    resume_id :str
    score: Optional[ScoreOutputSchema] = None
    error: Optional[str] = None
    

    