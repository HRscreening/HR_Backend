from pydantic import BaseModel, Field, EmailStr, model_validator,HttpUrl
from typing import List, Optional
from src.models.enums import InterviewType
from datetime import datetime

class Panelist(BaseModel):
    name: str = Field(..., example="John Doe")
    email: EmailStr = Field(..., example="JohnDoe@example.com")
    role: str = Field(..., example="Interviewer")



class CreateInterviewRoundConfigDTO(BaseModel):
    title:str = Field(..., example="Technical Interview")
    round_number: int = Field(..., example=1)
    interview_type: InterviewType = Field(..., example=InterviewType.VIDEO_CALL.value)
    instructions: Optional[str] = Field(None, example="Please be prepared to discuss your previous projects and answer technical questions.")
    duration_minutes: int = Field(..., example=60)
    panelists: list[Panelist] = Field(default=list)
    meet_link:  Optional[HttpUrl] = Field(None)
    start_date: datetime
    end_date: datetime

    
    
class UpdateInterviewRoundConfigDTO(BaseModel):
    title: Optional[str] = Field(None, example="Technical Interview")
    round_number: Optional[int] = Field(None, example=1)
    interview_type: Optional[InterviewType] = Field(None, example=InterviewType.VIDEO_CALL.value)
    instructions: Optional[str] = Field(None, example="Please be prepared to discuss your previous projects and answer technical questions.")
    duration_minutes: Optional[int] = Field(None, example=60)
    panelists: Optional[List[Panelist]] = None
    meet_link:  Optional[HttpUrl] = Field(None)

    @model_validator(mode="before")
    @classmethod
    def check_at_least_one_field(cls, values):
        if not any(v is not None for k, v in values.items()):
            raise ValueError("At least one field must be provided for update")
        return values
    
    
