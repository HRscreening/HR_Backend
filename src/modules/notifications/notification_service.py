# Can be used later for different types of notifications (email, sms, etc.)
from src.modules.email_services.candidate.candidate_email_service import CandidateEmailService
from src.modules.email_services.panel.panel_email_service import PanelEmailService
from typing import Literal
from configs.log_config import get_logger

from src.modules.notifications.notification_dtos import FormReminderPayloadDTO_Panel, InterviewReminderPayloadDTO_Panel, FormReminderPayloadDTO_Candidate, InterviewReminderPayloadDTO_Candidate
from src.utils.time_helper import deserialize_datetime
channel = Literal["ALL","SMS","EMAIL","IN_APP"]



class NotificationService:
    def __init__(self,panel_email_service: PanelEmailService, candidate_email_service: CandidateEmailService):
        self.panel_email_service = panel_email_service
        self.candidate_email_service = candidate_email_service
        self.logger = get_logger("Notification_Service")
    
    
    async def send_form_reminder_notification_to_panelist(self,payload: FormReminderPayloadDTO_Panel,channel: channel = "EMAIL"):
        try:
            if channel == "EMAIL":
                await self.panel_email_service.send_form_reminder_email_to_panelist(payload.panelist_email,payload.panelist_name,payload.interview_round_title,payload.form_link)
         
        except Exception as e:
            self.logger.exception(f"Error sending form reminder notification to panelist : {payload.panelist_name} with email: {payload.panelist_email}")
            raise Exception("Failed to send form reminder notification to panelist")
    
    
    
    
    async def send_interview_reminder_notification_to_panelist(self, payload: InterviewReminderPayloadDTO_Panel,channel: channel = "EMAIL"):
        try:
            if channel == "EMAIL":
                scheduled_start = deserialize_datetime(payload.scheduled_start)
                scheduled_end = deserialize_datetime(payload.scheduled_end)
                await self.panel_email_service.send_panelist_interview_reminder_email(payload.panelist_email,payload.panelist_name,payload.candidate_name,payload.interview_round_title,scheduled_start,scheduled_end,payload.meet_link,payload.reschedule_link)
      
        except Exception as e:
            self.logger.exception(f"Error sending form reminder notification to panelist with email: {payload.panelist_email}")
            raise Exception("Failed to send form reminder notification to panelist")
        
     
        
    async def send_form_reminder_notification_to_candidate(self,payload: FormReminderPayloadDTO_Candidate,channel: channel = "EMAIL"):
        try:
            if channel == "EMAIL":
                await self.candidate_email_service.send_booking_link_reminder_email(payload.candidate_email,payload.candidate_name,payload.interview_round_title,payload.form_link)
         
        except Exception as e:
            self.logger.exception(f"Error sending form reminder notification to candidate : {payload.panelist_name} with email: {payload.candidate_email}")
            raise Exception("Failed to send form reminder notification to candidate")
    
    
        
    async def send_interview_reminder_notification_to_candidate(self, payload: InterviewReminderPayloadDTO_Candidate,channel: channel = "EMAIL"):
        try:
            if channel == "EMAIL":
                scheduled_start = deserialize_datetime(payload.scheduled_start)
                scheduled_end = deserialize_datetime(payload.scheduled_end)
                await self.candidate_email_service.send_interview_reminder_email(payload.candidate_email,payload.candidate_name,payload.interview_round_title,scheduled_start,scheduled_end,payload.meet_link,payload.reschedule_link)
      
        except Exception as e:
            self.logger.exception(f"Error sending form reminder notification to candidate with email: {payload.candidate_email}")
            raise Exception("Failed to send form reminder notification to candidate")
