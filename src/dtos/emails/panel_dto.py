from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class PanelistBookingData(BaseModel):
    panelist_email: EmailStr
    panelist_name: Optional[str]
    candidate_name: str
    interview_round_title: str
    scheduled_start: datetime
    scheduled_end: datetime
    meet_link: Optional[str] = None
    reschedule_link: Optional[str] = None
    
class AvailableSlotsData(BaseModel):
    panelist_email: EmailStr
    panelist_name: str | None
    interview_round_title: str
    form_link: str
    
class ThankYouPanelistData(BaseModel):
    panelist_email: EmailStr
    panelist_name: str | None
    interview_round_title: str
    edit_slots_link: str
    validity_period: str | None = None,
    

class PanelistSlotReleasedData(BaseModel):
    panelist_email: str
    panelist_name: str | None
    candidate_name: str
    interview_round_title: str
    schedule_start: datetime
    schedule_end: datetime
    
    
class PanelistMeetingRescheduledData(BaseModel):
    panelist_email: str
    panelist_name: str | None
    candidate_name: str
    interview_round_title: str
    old_scheduled_start: datetime
    old_scheduled_end: datetime
    new_scheduled_start: datetime
    new_scheduled_end: datetime
    meet_link: str | None = None
    reschedule_link: str | None = None
    
    
class PanelistReminderAvailabilityData(BaseModel):
    panelist_email: str
    panelist_name: str | None
    interview_round_title: str
    form_link: str
    
    
    
class PanelistInterviewReminderData(BaseModel):
    panelist_email: str
    panelist_name: str | None
    candidate_name: str
    interview_round_title: str

    scheduled_start: datetime
    scheduled_end: datetime

    meet_link: str | None = None
    reschedule_link: str | None = None

# Same for feedback reminder 
class PanelistFeedbackData(BaseModel):
    panelist_email: str
    panelist_name: str | None
    candidate_name: str
    interview_round_title: str
    form_link: str
    form_valid_till: datetime | None = None
    