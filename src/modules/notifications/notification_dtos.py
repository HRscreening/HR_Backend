from pydantic import BaseModel


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