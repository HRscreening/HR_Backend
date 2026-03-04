from pydantic import BaseModel, Field, EmailStr, model_validator, field_validator
from typing import List, Optional,Dict
from src.models.enums import InterviewType
from datetime import datetime,date,timezone

class CreatePanelDTO(BaseModel):
    panelist_name : str 
    panelist_email : EmailStr
    availability_token : str
    token_expires_at : datetime
    
class SlotTime(BaseModel):
    start_time: datetime
    end_time: datetime

    @field_validator("start_time", "end_time", mode="after")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError(
                "Datetime must include a timezone offset (e.g. 2026-03-10T14:00:00+05:30). "
                "Naive datetimes without timezone are not accepted."
            )
        return v.astimezone(timezone.utc)  # normalise to UTC for storage
    
class AvailableSlot(BaseModel):
    date: date
    time: List[SlotTime]
    
