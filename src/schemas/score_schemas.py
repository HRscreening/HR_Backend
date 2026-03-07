from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Dict, Optional, Any, List
from dataclasses import dataclass

from uuid import UUID
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

# class CriterionScoreSchema(BaseModel):
#     score: float
#     reason: Optional[str] = None
#     evidence: Optional[List[str]] = None
#     sub_criteria: Optional[SubCriterionScoreSchema] = Field(default_factory=dict)

class CriterionScoreSchema(BaseModel):
    score: float
    reason: Optional[str] = None
    evidence: Optional[List[str]] = None
    sub_criteria: Optional[SubCriterionScoreSchema] = None  # ✅ None, not dict

    @field_validator("sub_criteria", mode="before")
    @classmethod
    def empty_dict_to_none(cls, v):
        # LLM returns {} when no sub_criteria — treat as None
        if v == {} or v is None:
            return None
        # LLM sometimes returns a named dict — flatten to None, scoring is at criterion level only
        if isinstance(v, dict) and not {"score", "reason", "evidence"}.intersection(v):
            return None
        return v


class BreakdownSchema(BaseModel):
    mandatory_criteria: Dict[str, CriterionScoreSchema] = Field(default_factory=dict)
    screening_criteria: Dict[str, CriterionScoreSchema] = Field(default_factory=dict)



class ScoreOutputSchema(BaseModel):
    candidate_info: CandidateInfoSchema
    ai_analysis: Optional[Dict[str,List[str]]] = None
    overall_score: float = Field(ge=0, le=100)
    ai_confidence: float = Field(ge=0.0, le=1.0)
    breakdown: BreakdownSchema



class ScoreRecordSchema(BaseModel):
    overall_score: float = Field(ge=0, le=100)
    ai_confidence: float = Field(ge=0.0, le=1.0)
    breakdown: Dict[str, Any]




class ResumeScoreResult(BaseModel):
    resume_id: str
    application_id: str
    score: ScoreOutputSchema

    @field_validator("resume_id", "application_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v)

class ResumeScoreFailure(BaseModel):
    resume_id: str
    application_id: str
    error: str

    @field_validator("resume_id", "application_id", mode="before")
    @classmethod
    def coerce_uuid(cls, v):
        return str(v)


@dataclass
class ResumeDataSchema:
    application_id : str | UUID
    resume_id :str | UUID
    resume_text : str
    
@dataclass
class ResumeDataSchemaURL:
    application_id : str | UUID
    resume_id :str | UUID
    resume_url : str 

@dataclass
class BatchResumeDataSchema:
    application_id : str
    resume_id :str
    score: Optional[ScoreOutputSchema] = None
    error: Optional[str] = None
    
@dataclass
class Candidate_info_task:
    candidate_info: CandidateInfoSchema
    resume_id:str
    batch_id:str