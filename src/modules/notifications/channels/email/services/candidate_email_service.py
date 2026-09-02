from configs.log_config import get_logger
from src.modules.notifications.channels.email.base import BaseEmailService
from src.modules.notifications.channels.email.template_classes.candidate_templates import (
    CandidateBookingLinkTemplate,
    CandidateBookingConfirmationTemplate,
    CandidateRescheduleNewSlotsTemplate,
    CandidateBookingLinkReminderTemplate,
    CandidateInterviewReminderTemplate,
    CandidateShortlistedTemplate    
)


from src.dtos.notification_dto import Email_Template_Keys
# class CandidateEmailService(BaseEmailService):
#     def __init__(self):
#         super().__init__()

#     async def send_booking_link_email(self,data:CandidateBookingLinkData):
#         template = CandidateBookingLinkTemplate(data)
#         await self.send_email_template(template)

       
#     async def send_booking_confirmation_email(self,data:CandidateBookingConfirmationData):
#         template = CandidateBookingConfirmationTemplate(data)
#         await self.send_email_template(template)


#     async def send_interview_rescheduled_email(self,data:CandidateRescheduleNewSlotsData):
#         template = CandidateRescheduleNewSlotsTemplate(data)
#         await self.send_email_template(template)


#     async def send_booking_link_reminder_email(self,data: CandidateBookingLinkReminderData):
#         template = CandidateBookingLinkReminderTemplate(data)
#         await self.send_email_template(template)
        
        
#     async def send_interview_reminder_email(self,data: CandidateInterviewReminderData):
#         template = CandidateInterviewReminderTemplate(data)
#         await self.send_email_template(template)
        
#     async def send_shortlisted_email(self,data: CandidateShortlistedData):
#         template = CandidateShortlistedTemplate(data)
#         await self.send_email_template(template)
        
        


class CandidateEmailService(BaseEmailService):
    """
    CandidateEmailService is responsible for sending all email notifications to candidates. It uses different email templates based on the type of notification being sent, such as interview booking links, booking confirmations, interview reminders, and shortlisted notifications.
    
    The service defines a mapping of email template keys to their corresponding template classes, allowing for dynamic selection and sending of emails based on the provided template key. Each method in the service corresponds to a specific type of email notification that can be sent to candidates.
        
           
    Raises:
        ValueError: If an unknown email template key is provided to the send_email method.
    """
    
    
    # ! Make sure to keep Email_Template_Keys updated in src/dtos/notification_dto.py when adding new templates here
    EMAIL_TEMPLATE_MAP = {
        Email_Template_Keys.Candidate_Shortlisted: CandidateShortlistedTemplate,
        Email_Template_Keys.Candidate_BOOKING_LINK: CandidateBookingLinkTemplate,
        
        Email_Template_Keys.Candidate_Interview_Booking_Confirmation: CandidateBookingConfirmationTemplate,
        Email_Template_Keys.RESCHEDULE: CandidateRescheduleNewSlotsTemplate,
        
        # Reminders
        Email_Template_Keys.Candidate_BOOKING_LINK_REMINDER: CandidateBookingLinkReminderTemplate,
        Email_Template_Keys.INTERVIEW_UPCOMING: CandidateInterviewReminderTemplate
        
    }
    


    async def send_email(self, template_key: Email_Template_Keys = None, data=None, **kwargs):
        
        
        if template_key is None or data is None:    
            # This is a call from BaseEmailService.send_email_template
            self.logger.warning("send_email called without template_key or data, falling back to BaseEmailService.send_email_template with kwargs")
            return await super().send_email(**kwargs)
            
        template_class = self.EMAIL_TEMPLATE_MAP.get(template_key)
        if not template_class:
            raise ValueError(f"Unknown email type: {template_key}")
        
        # Ensure data is a Pydantic model
        if isinstance(data, dict):
            import inspect
            sig = inspect.signature(template_class.__init__)
            params = list(sig.parameters.values())
            if len(params) > 1:
                model_class = params[1].annotation
                if hasattr(model_class, "model_validate"):
                    data = model_class.model_validate(data)

        template = template_class(data)
        await self.send_email_template(template)