# Can be used later for different types of notifications (email, sms, etc.)
from src.modules.email_services.services import EmailService
from typing import Literal
from configs.log_config import get_logger

from src.dtos.emails.panel_dto import PanelistReminderAvailabilityData,PanelistInterviewReminderData,PanelistFeedbackData
from src.dtos.emails.candidate_dto import CandidateBookingLinkReminderData,CandidateInterviewReminderData
from src.utils.time_helper import deserialize_datetime
channel = Literal["ALL","SMS","EMAIL","IN_APP"]



class NotificationService:
    def __init__(self,email_service: EmailService):
        self.email_service = email_service or EmailService()
        self.logger = get_logger("Notification_Service")
    
    
    async def send_form_reminder_notification_to_panelist(self,payload: PanelistReminderAvailabilityData,channel: channel = "EMAIL"):
        try:
            if channel == "EMAIL":
                await self.email_service.panel.send_form_reminder_email_to_panelist(payload)
         
        except Exception as e:
            self.logger.exception(f"Error sending form reminder notification to panelist : {payload.panelist_name} with email: {payload.panelist_email}")
            raise Exception("Failed to send form reminder notification to panelist")
    
    
    
    
    async def send_interview_reminder_notification_to_panelist(self, payload: PanelistInterviewReminderData,channel: channel = "EMAIL"):
        try:
            if channel == "EMAIL":
                scheduled_start = deserialize_datetime(payload.scheduled_start)
                scheduled_end = deserialize_datetime(payload.scheduled_end)
                payload.scheduled_start = scheduled_start
                payload.scheduled_end = scheduled_end
                await self.email_service.panel.send_panelist_interview_reminder_email(payload)
      
        except Exception as e:
            self.logger.exception(f"Error sending form reminder notification to panelist with email: {payload.panelist_email}")
            raise Exception("Failed to send form reminder notification to panelist")
        
     
        
    async def send_form_reminder_notification_to_candidate(self,payload: CandidateBookingLinkReminderData,channel: channel = "EMAIL"):
        try:
            if channel == "EMAIL":
                await self.email_service.candidate.send_booking_link_reminder_email(payload)
         
        except Exception as e:
            self.logger.exception(f"Error sending form reminder notification to candidate : {payload.panelist_name} with email: {payload.candidate_email}")
            raise Exception("Failed to send form reminder notification to candidate")
    
    
        
    async def send_interview_reminder_notification_to_candidate(self, payload: CandidateInterviewReminderData,channel: channel = "EMAIL"):
        try:
            if channel == "EMAIL":
                scheduled_start = deserialize_datetime(payload.scheduled_start)
                scheduled_end = deserialize_datetime(payload.scheduled_end)
                payload.scheduled_start = scheduled_start
                payload.scheduled_end = scheduled_end
                await self.email_service.candidate.send_interview_reminder_email(payload)
      
        except Exception as e:
            self.logger.exception(f"Error sending form reminder notification to candidate with email: {payload.candidate_email}")
            raise Exception("Failed to send form reminder notification to candidate")
        
    async def send_feedback_reminder_notification_to_panelist(self, payload: PanelistFeedbackData,channel: channel = "EMAIL"):
        try:
            if channel == "EMAIL":
                await self.email_service.panel.send_panelist_feedback_reminder_email(payload)
      
        except Exception as e:
            self.logger.exception(f"Error sending feedback reminder notification to panelist with email: {payload.panelist_email}")
            raise Exception("Failed to send feedback reminder notification to panelist")
