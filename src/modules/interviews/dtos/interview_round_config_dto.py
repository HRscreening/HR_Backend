from pydantic import BaseModel, Field, EmailStr, model_validator,HttpUrl,field_validator
from typing import List, Optional,Any
from src.modules.interviews.dtos.panel_dto import PanelistDTO, PanelistEditDTO
from src.models.enums import InterviewType,PanelMode
from datetime import datetime
import zoneinfo

def parse_iso_datetime(v):
    """Accept either a datetime object or an ISO 8601 string."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        # Handle the trailing 'Z' that JavaScript sends
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    raise ValueError(f"Cannot parse datetime from: {v!r}")
 

class PanelistDTO(BaseModel):
    name: str = Field(..., example="John Doe")
    email: EmailStr = Field(..., example="JohnDoe@example.com")
    role: str = Field(..., example="Interviewer")



class CreateInterviewRoundConfigDTO(BaseModel):
    title:str = Field(..., example="Technical Interview")
    round_number: int = Field(..., example=1)
    interview_type: InterviewType = Field(..., example=InterviewType.VIDEO_CALL.value)
    instructions: Optional[str] = Field(None, example="Please be prepared to discuss your previous projects and answer technical questions.")
    duration_minutes: int = Field(..., example=60)
    panelists: list[PanelistDTO] = Field(default_factory=list)
    assessment_criterias: Optional[List[str]] = Field(default_factory=list, example=["Problem Solving", "Communication Skills"])
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


from typing import Any, List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class PanelistDiffDTO(BaseModel):
    """
    Structured diff for panelist mutations.

    Shape sent from the frontend:
    {
        "add":    [{ "name": "...", "email": "...", "role": "..." }],
        "edit":   [{ "id": "...", "name": "...", "email": "...", "role": "..." }],
        "delete": ["uuid1", "uuid2"]
    }
    """
    add: List[PanelistDTO] = Field(default_factory=list)
    edit: List[PanelistEditDTO] = Field(default_factory=list)
    delete: List[str] = Field(default_factory=list, description="List of panelist IDs to delete")

    @model_validator(mode="after")
    def check_no_duplicate_emails(self) -> "PanelistDiffDTO":
        """Emails across add + edit must be unique within this diff."""
        emails = [p.email.lower() for p in self.add] + [p.email.lower() for p in self.edit]
        seen: set[str] = set()
        for email in emails:
            if email in seen:
                raise ValueError(f"Duplicate email in panelist diff: {email}")
            seen.add(email)
        return self

    @model_validator(mode="after")
    def check_delete_ids_not_in_edit(self) -> "PanelistDiffDTO":
        """An id cannot appear in both edit[] and delete[] at the same time."""
        edit_ids = {p.id for p in self.edit}
        conflict = edit_ids & set(self.delete)
        if conflict:
            raise ValueError(
                f"Panelist id(s) appear in both edit and delete: {conflict}"
            )
        return self


# ─── Main update DTO ──────────────────────────────────────────────────────────

class UpdateInterviewRoundConfigDTO(BaseModel):
    title: Optional[str] = Field(None)
    round_number: Optional[int] = Field(None)
    interview_type: Optional[str] = Field(None)
    instructions: Optional[str] = Field(None)
    duration_minutes: Optional[int] = Field(None)
    panelists: Optional[PanelistDiffDTO] = None
    assessment_criterias: Optional[List[str]] = Field(default_factory=list)
    start_date: Optional[datetime] = None   # ← datetime, not str
    end_date: Optional[datetime] = None     # ← datetime, not str
    timezone: Optional[str] = Field(None)
    panel_mode: Optional[str] = Field(None)
 
    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_dates(cls, v):
        return parse_iso_datetime(v)
 
    @field_validator("*", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v
 
    @field_validator("interview_type", mode="before")
    @classmethod
    def normalize_interview_type(cls, v):
        if not v:
            return v
        return str(v).upper().replace(" ", "_")
 
    @field_validator("panel_mode", mode="before")
    @classmethod
    def normalize_panel_mode(cls, v):
        if not v:
            return v
        return str(v).upper()
 
    @model_validator(mode="before")
    @classmethod
    def check_at_least_one_field(cls, values: Any):
        if not any(v is not None for v in values.values()):
            raise ValueError("At least one field must be provided for update")
        return values
 
class RequestPanelistsForSlotsDTO(BaseModel):
    panelist_ids: List[str]