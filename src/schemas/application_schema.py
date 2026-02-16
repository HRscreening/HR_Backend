from pydantic import BaseModel
from src.models.enums import ApplicationStatus

class UpdateApplicationStatusRequest(BaseModel):
    new_status: ApplicationStatus

class FlagApplicationRequest(BaseModel):
    flag_reason: str 