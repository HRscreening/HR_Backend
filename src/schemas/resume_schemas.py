from pydantic import BaseModel, Field
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from src.models.enums import ResumeStatus
from src.schemas.user_schemas import CandidateInfoSchema,ScoreOutputSchema

class ResumeCreateSchema(BaseModel):
    application_id: str = Field(..., description="ID of the application this resume is associated with")
    raw_file_url: str = Field(..., description="URL where the raw resume file is stored")
    parsed_text: str = Field(..., description="Extracted text content from the resume")
    page_count: int = Field(..., description="Number of pages in the resume")
    status: ResumeStatus = Field(..., description="Processing status of the resume (e.g., 'pending', 'processed', 'error')")


@dataclass
class ResumeScoreResult:
    resume_id: str
    application_id: str
    score: ScoreOutputSchema

@dataclass
class ResumeScoreFailure(BaseModel):
    resume_id: str
    application_id: str
    error: str



@dataclass
class ResumeDataSchema:
    application_id : str
    resume_id :str
    resume_text : str
    
@dataclass
class ResumeDataSchemaURL:
    application_id : str
    resume_id :str
    resume_url : str 

@dataclass
class BatchResumeDataSchema:
    application_id : str
    resume_id :str
    score: Optional[ScoreOutputSchema] = None
    error: Optional[str] = None
    

    