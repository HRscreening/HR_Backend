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


#TODO: Implement this later
# class CandidateEmailService(BaseEmailService):
#     EMAIL_TEMPLATE_MAP = {
#         "booking_link": CandidateBookingLinkTemplate,
#         "booking_confirmation": CandidateBookingConfirmationTemplate,
#         "interview_rescheduled": CandidateRescheduleNewSlotsTemplate,
#         "booking_link_reminder": CandidateBookingLinkReminderTemplate,
#         "interview_reminder": CandidateInterviewReminderTemplate
        
#     }

#     async def send_email(self, email_type: str, data):
#         template_class = self.EMAIL_TEMPLATE_MAP.get(email_type)
#         if not template_class:
#             raise ValueError(f"Unknown email type: {email_type}")
#         template = template_class(data)
#         await self.send_email_template(template)