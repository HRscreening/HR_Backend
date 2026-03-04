from pydantic import BaseModel, Field, EmailStr, model_validator
from typing import List, Optional,Literal
from src.models.enums import InterviewType
from uuid import UUID
from datetime import datetime


class BookSlotRequest(BaseModel):
    """PANEL mode: candidate picks one slot from the shared pool."""
    slot_id: UUID


class SequentialBookingItem(BaseModel):
    """One slot picked per panelist for SEQUENTIAL mode."""
    panelist_email: EmailStr
    slot_id: UUID


class BookSequentialSlotsRequest(BaseModel):
    """SEQUENTIAL mode: candidate picks one slot per panelist."""
    bookings: List[SequentialBookingItem] = Field(..., min_length=1)


class SlotOut(BaseModel):
    """Returned in the booking form so the candidate can pick slots."""
    id: UUID
    slot_start: datetime
    slot_end: datetime
    panelist_email: Optional[str] = None  # Only set in SEQUENTIAL mode

    class Config:
        from_attributes = True

class Reminders(BaseModel):
    method: Literal["email", "popup"]
    minutes_before: int


class MeetingDetails(BaseModel):
        summary: str
        description: str
        location: str
        start_time: str
        end_time: str
        timezone: str
        attendees_emails: Optional[List[str]] = None
        application_id: Optional[str] = None
        reminders: Optional[List[Reminders]] = None
        visibility: Literal["private", "public"] = "public"  