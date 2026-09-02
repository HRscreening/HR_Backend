from pydantic import BaseModel
from enum import Enum
from typing import Union

class Channel(str, Enum):
    ALL = "ALL"
    EMAIL = "EMAIL"
    SMS = "SMS"
    IN_APP = "IN_APP"

from src.modules.notifications.model.notification_enum import RecipientType,NotificationChannel,EntityType

class Email_Template_Keys(str, Enum):
    """Enum to define the keys for different email templates. This should be kept in sync with the templates available in the email template map in All email services."""
    Candidate_Shortlisted = "shortlisted"
    Candidate_BOOKING_LINK = "candidate_booking_link"
    Candidate_Interview_Booking_Confirmation = "candidate_booking_confirmation"
    INTERVIEW_UPCOMING = "interview_reminder"
    Candidate_BOOKING_LINK_REMINDER = "candidate_booking_link_reminder"
    FEEDBACK_PENDING = "send_feedback_reminder_email"
    RESCHEDULE = "interview_rescheduled"
    FORM_SUBMISSION = "send_form_reminder_email_to_panelist"
    
    # Panelist templates
    SLOT_AVAILABILITY = "slot_availability"
    BOOKING_CONFIRMATION = "booking_confirmation"
    SLOT_RELEASED = "slot_released"
    MEETING_RESCHEDULED = "meeting_rescheduled"
    THANK_YOU_FOR_SUBMITTING_AVAILABILITY = "thanks_for_submitting_availability"
    FORM_REMINDER = "form_reminder"
    PANELIST_INTERVIEW_REMINDER = "panelist_interview_reminder"
    PANELIST_FEEDBACK_REQUEST = "feedback_request"
    PANELIST_FEEDBACK_REMINDER = "feedback_reminder"

    
class SMS_Template_Keys(str, Enum):
    INTERVIEW_UPCOMING = "interview_upcoming_sms"
    FEEDBACK_PENDING = "feedback_pending_sms"
    RESCHEDULE = "reschedule_sms"
 
 
Template_Keys =   Union[Email_Template_Keys,SMS_Template_Keys]


class FormReminderPayloadDTO_Panel(BaseModel):
    panelist_email: str
    panelist_name: str
    interview_round_title: str
    form_link: str
    
    
class InterviewReminderPayloadDTO_Panel(BaseModel):
    panelist_email: str
    panelist_name: str | None
    candidate_name: str
    interview_round_title: str
    scheduled_start: str
    scheduled_end: str
    meet_link: str | None = None
    reschedule_link: str | None = None


class FormReminderPayloadDTO_Candidate(BaseModel):
    candidate_email: str
    candidate_name: str
    interview_round_title: str
    form_link: str
    
    
class InterviewReminderPayloadDTO_Candidate(BaseModel):
    candidate_email: str
    candidate_name: str | None
    interview_round_title: str
    scheduled_start: str 
    scheduled_end: str
    meet_link: str | None = None
    reschedule_link: str | None = None
    
    
class CreateNotificationDTO(BaseModel):
    entity_type: EntityType
    entity_id: str
    recipient_type: RecipientType
    recipient_id: str
    channel: NotificationChannel
    payload: dict
    template_key: Template_Keys
    worker_job_id: Union[str,None] = None