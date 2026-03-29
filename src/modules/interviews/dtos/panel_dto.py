from pydantic import BaseModel, EmailStr, field_validator, model_validator,Field
from typing import List
from datetime import datetime, date, timezone
from uuid import UUID


# ─── Panelist DTOs ────────────────────────────────────────────────────────────

class PanelistDTO(BaseModel):
    """Used when creating a brand-new panelist (no id yet)."""
    name: str = Field(..., example="John Doe")
    email: EmailStr = Field(..., example="john.doe@example.com")
    role: str = Field(..., example="Interviewer")


class PanelistEditDTO(BaseModel):
    """Used when editing an existing panelist (must supply id)."""
    id: str = Field(..., example="uuid-of-existing-panelist")
    name: str = Field(..., example="John Doe")
    email: EmailStr = Field(..., example="john.doe@example.com")
    role: str = Field(..., example="Interviewer")



class CreatePanelDTO(BaseModel):
    panelist_name: str
    panelist_email: EmailStr
    availability_token: str
    token_expires_at: datetime

class updatePanelistLists(BaseModel):
    name: str
    email: EmailStr
    role: str

# ── Shared validator ──────────────────────────────────────────────────────────

def normalise_to_utc(v: datetime) -> datetime:
    if v.tzinfo is None:
        raise ValueError(
            "Datetime must include a timezone offset (e.g. 2026-03-10T14:00:00+05:30). "
            "Naive datetimes are not accepted."
        )
    return v.astimezone(timezone.utc)


# ── First-time submission  (POST /panel/submit-availability) ──────────────────

class SlotTime(BaseModel):
    start_time: datetime
    end_time: datetime

    @field_validator("start_time", "end_time", mode="after")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        return normalise_to_utc(v)


class AvailableSlot(BaseModel):
    date: date
    time: List[SlotTime]


# ── Edit submission  (PATCH /panel/edit-slots) ────────────────────────────────

class SlotAddItem(BaseModel):
    date: date
    slot_start: datetime
    slot_end: datetime

    @field_validator("slot_start", "slot_end", mode="after")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        return normalise_to_utc(v)


class SlotUpdateItem(BaseModel):
    id: UUID
    slot_start: datetime
    slot_end: datetime

    @field_validator("slot_start", "slot_end", mode="after")
    @classmethod
    def must_be_utc(cls, v: datetime) -> datetime:
        return normalise_to_utc(v)


class EditSlotsPayload(BaseModel):
    add: List[SlotAddItem] = []
    delete: List[UUID] = []
    update: List[SlotUpdateItem] = []

    @model_validator(mode="after")
    def must_have_at_least_one_change(self) -> "EditSlotsPayload":
        if not self.add and not self.delete and not self.update:
            raise ValueError("Payload must contain at least one change (add, delete, or update).")
        return self
 
 
class RescheduleSlotItem(BaseModel):
    id: UUID
    slot_start: datetime
    slot_end: datetime

    @field_validator("slot_start", "slot_end", mode="after")
    @classmethod
    def must_be_utc(cls, v): return normalise_to_utc(v)


class RescheduleSlotsPayload(BaseModel):
    reschedule_slot: RescheduleSlotItem
    add: List[SlotAddItem] = []

    # @model_validator(mode="after")
    # def must_have_new_slots(self):
    #     if not self.add:
    #         raise ValueError("At least one new slot must be provided for rescheduling.")
    #     return self