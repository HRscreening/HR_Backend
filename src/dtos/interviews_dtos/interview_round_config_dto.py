from pydantic import BaseModel, Field, EmailStr, model_validator,HttpUrl
from typing import List, Optional
from src.models.enums import InterviewType
from datetime import datetime
import zoneinfo

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
    panelists: list[Panelist] = Field(default_factory=list)
    meet_link:  Optional[HttpUrl] = Field(None)
    start_date: datetime
    end_date: datetime
    timezone: str = Field(default="UTC", example="Asia/Kolkata")

    @model_validator(mode="after")
    def validate_timezone(self):
        try:
            zoneinfo.ZoneInfo(self.timezone)
        except (KeyError, Exception):
            raise ValueError(f"Invalid IANA timezone: {self.timezone}")
        return self


class BulkCreateInterviewRoundConfigDTO(BaseModel):
    """Send job_id + all rounds in a single request."""
    job_id: str = Field(..., example="550e8400-e29b-41d4-a716-446655440000")
    rounds: List[CreateInterviewRoundConfigDTO] = Field(..., min_length=1)

    
class UpdateInterviewRoundConfigDTO(BaseModel):
    title: Optional[str] = Field(None, example="Technical Interview")
    round_number: Optional[int] = Field(None, example=1)
    interview_type: Optional[InterviewType] = Field(None, example=InterviewType.VIDEO_CALL.value)
    instructions: Optional[str] = Field(None, example="Please be prepared to discuss your previous projects and answer technical questions.")
    duration_minutes: Optional[int] = Field(None, example=60)
    panelists: Optional[List[Panelist]] = None
    meet_link:  Optional[HttpUrl] = Field(None)
    timezone: Optional[str] = Field(None, example="Asia/Kolkata")

    @model_validator(mode="before")
    @classmethod
    def check_at_least_one_field(cls, values):
        if not any(v is not None for k, v in values.items()):
            raise ValueError("At least one field must be provided for update")
        return values
    
    
