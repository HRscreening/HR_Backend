from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class CandidateBookingLinkData(BaseModel):
    candidate_email: EmailStr
    candidate_name: str
    interview_round_title: str
    booking_link: str

class CandidateBookingConfirmationData(BaseModel):
    candidate_email: EmailStr
    candidate_name: str
    interview_round_title: str
    scheduled_start: datetime
    scheduled_end: datetime
    meet_link: Optional[str] = None
    reschedule_link: Optional[str] = None

class CandidateRescheduleNewSlotsData(BaseModel):
    candidate_email: EmailStr
    candidate_name: str
    interview_round_title: str
    scheduled_start: datetime
    scheduled_end: datetime
    reschedule_link: str
    reason: Optional[str] = None

class CandidateBookingLinkReminderData(BaseModel):
    candidate_email: EmailStr
    candidate_name: str
    interview_round_title: str
    booking_link: str

class CandidateInterviewReminderData(BaseModel):
    candidate_email: EmailStr
    candidate_name: str
    interview_round_title: str
    scheduled_start: datetime
    scheduled_end: datetime
    meet_link: Optional[str] = None
    reschedule_link: Optional[str] = None

class CandidateShortlistedData(BaseModel):
    candidate_email: EmailStr
    candidate_name: str
    job_title: str