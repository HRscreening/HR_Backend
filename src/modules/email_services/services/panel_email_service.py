from configs.log_config import get_logger
from src.modules.email_services.base import BaseEmailService
from src.dtos.emails.panel_dto import PanelistBookingData,AvailableSlotsData,ThankYouPanelistData,PanelistSlotReleasedData,PanelistMeetingRescheduledData,PanelistReminderAvailabilityData,PanelistInterviewReminderData
from src.modules.email_services.template_classes.panel_templates import (PanelistBookingTemplate,PanelistAvailabilityTemplate,PanelistThankYouAvailabilityTemplate,PanelistSlotReleasedTemplate,PanelistMeetingRescheduledTemplate,PanelistReminderAvailabilityTemplate,PanelistInterviewReminderTemplate,PanelistInterviewFeedbackTemplate,PanelistInterviewFeedbackReminderTemplate)



class PanelEmailService(BaseEmailService):
    def __init__(self):
        super().__init__()
        
    async def send_slot_availability_email(self,data: AvailableSlotsData):
        data  = PanelistAvailabilityTemplate(data)
        await self.send_email_template(data)        

    async def send_booking_confirmation_to_panelist(self,data: PanelistBookingData):
        data = PanelistBookingTemplate(data)
        await self.send_email_template(data)
        
    async def send_slot_released_to_panelist(self,data: PanelistSlotReleasedData):
        template = PanelistSlotReleasedTemplate(data)
        await self.send_email_template(template)
        
    async def send_meeting_rescheduled_email_to_panelist(self,data: PanelistMeetingRescheduledData):
        template = PanelistMeetingRescheduledTemplate(data)
        await self.send_email_template(template)
        
    async def send_thanks_for_submitting_availability_email(self, data: ThankYouPanelistData):
        template = PanelistThankYouAvailabilityTemplate(data)
        await self.send_email_template(template)
       
    async def send_form_reminder_email_to_panelist(self,data: PanelistReminderAvailabilityData):
        template = PanelistReminderAvailabilityTemplate(data)
        await self.send_email_template(template)
                    
    async def send_panelist_interview_reminder_email(self,data: PanelistInterviewReminderData):
        template = PanelistInterviewReminderTemplate(data)
        await self.send_email_template(template)
        
    async def send_panelist_feedback_request_email(self,data):
        template = PanelistInterviewFeedbackTemplate(data)
        await self.send_email_template(template)
        
    async def send_panelist_feedback_reminder_email(self,data):
        template = PanelistInterviewFeedbackReminderTemplate(data)
        await self.send_email_template(template)