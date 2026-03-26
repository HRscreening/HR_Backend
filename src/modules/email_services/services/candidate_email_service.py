from configs.log_config import get_logger
from src.modules.email_services.base import BaseEmailService
from src.modules.email_services.template_classes.candidate_templates import (
    CandidateBookingLinkTemplate,
    CandidateBookingConfirmationTemplate,
    CandidateRescheduleNewSlotsTemplate,
    CandidateBookingLinkReminderTemplate,
    CandidateInterviewReminderTemplate
)
from src.dtos.emails.candidate_dto import (
    CandidateBookingLinkData,
    CandidateBookingConfirmationData,
    CandidateRescheduleNewSlotsData,
    CandidateBookingLinkReminderData,
    CandidateInterviewReminderData
)

class CandidateEmailService(BaseEmailService):
    def __init__(self):
        super().__init__()

    async def send_booking_link_email(self,data:CandidateBookingLinkData):
        template = CandidateBookingLinkTemplate(data)
        await self.send_email_template(template)

       
    async def send_booking_confirmation_email(self,data:CandidateBookingConfirmationData):
        template = CandidateBookingConfirmationTemplate(data)
        await self.send_email_template(template)


    async def send_interview_rescheduled_email(self,data:CandidateRescheduleNewSlotsData):
        template = CandidateRescheduleNewSlotsTemplate(data)
        await self.send_email_template(template)


    async def send_booking_link_reminder_email(self,data: CandidateBookingLinkReminderData):
        template = CandidateBookingLinkReminderTemplate(data)
        await self.send_email_template(template)
        
        
    async def send_interview_reminder_email(self,data: CandidateInterviewReminderData):
        template = CandidateInterviewReminderTemplate(data)
        await self.send_email_template(template)


