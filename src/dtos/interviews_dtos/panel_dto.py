from pydantic import BaseModel, Field, EmailStr, model_validator
from typing import List, Optional,Dict
from src.models.enums import InterviewType
from datetime import datetime,date

class CreatePanelDTO(BaseModel):
    panelist_name : str 
    panelist_email : EmailStr
    availability_token : str
    token_expires_at : datetime
    
class SlotTime(BaseModel):
    start_time: datetime
    end_time: datetime
    
class AvailableSlot(BaseModel):
    date: date
    time: List[SlotTime]
    
