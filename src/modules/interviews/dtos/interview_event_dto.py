from pydantic import BaseModel
from typing import Optional




class CreateInterviewEventDTO(BaseModel):
    event_type: str
    actor: Optional[str] = None
    details: Optional[dict] = None