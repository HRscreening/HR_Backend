from configs.log_config import get_logger
from src.modules.notifications.channels.email.base import BaseEmailService
from src.dtos.emails.panel_dto import PanelistBookingData,AvailableSlotsData,ThankYouPanelistData,PanelistSlotReleasedData,PanelistMeetingRescheduledData,PanelistReminderAvailabilityData,PanelistInterviewReminderData
from src.modules.notifications.channels.email.template_classes.panel_templates import (PanelistBookingTemplate,PanelistAvailabilityTemplate,PanelistThankYouAvailabilityTemplate,PanelistSlotReleasedTemplate,PanelistMeetingRescheduledTemplate,PanelistReminderAvailabilityTemplate,PanelistInterviewReminderTemplate,PanelistInterviewFeedbackTemplate,PanelistInterviewFeedbackReminderTemplate)
from typing import Literal
from src.dtos.notification_dto import Email_Template_Keys

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
        


class PanelEmailService(BaseEmailService):
    
    # ! Make sure to keep Email_Template_Keys updated in src/dtos/notification_dto.py when adding new templates here
    EMAIL_TEMPLATE_MAP = {
        Email_Template_Keys.SLOT_AVAILABILITY: PanelistAvailabilityTemplate,
        Email_Template_Keys.BOOKING_CONFIRMATION: PanelistBookingTemplate,
        Email_Template_Keys.SLOT_RELEASED: PanelistSlotReleasedTemplate,
        Email_Template_Keys.MEETING_RESCHEDULED: PanelistMeetingRescheduledTemplate,
        Email_Template_Keys.THANK_YOU_FOR_SUBMITTING_AVAILABILITY: PanelistThankYouAvailabilityTemplate,
        Email_Template_Keys.FORM_REMINDER: PanelistReminderAvailabilityTemplate,
        Email_Template_Keys.PANELIST_FEEDBACK_REQUEST: PanelistInterviewFeedbackTemplate,
        Email_Template_Keys.PANELIST_INTERVIEW_REMINDER: PanelistInterviewReminderTemplate,
        Email_Template_Keys.PANELIST_FEEDBACK_REMINDER: PanelistInterviewFeedbackReminderTemplate
    }
    

    async def send_email(self, template_key=None, data=None, **kwargs):
        if template_key is None or data is None:
            # This is a call from BaseEmailService.send_email_template (which passes keywords)
            # OR an invalid direct call missing required template/data.
            # Base class handles its own keyword mapping.
            self.logger.warning("send_email called without template_key or data, falling back to BaseEmailService.send_email_template with kwargs")
            return await super().send_email(**kwargs)

        template_class = self.EMAIL_TEMPLATE_MAP.get(template_key)
        
        if not template_class:
            raise ValueError(f"No email template found for key: {template_key}")
        
        # Ensure data is a Pydantic model by checking for template_class.__init__ annotations or similar
        # But a safer way is to check the template class itself or re-validate if it's a dict
        if isinstance(data, dict):
            # Most template classes expect a specific Data model as their first argument
            # We can find the model class from the __init__ type hints
            import inspect
            sig = inspect.signature(template_class.__init__)
            params = list(sig.parameters.values())
            if len(params) > 1:
                model_class = params[1].annotation
                if hasattr(model_class, "model_validate"):
                    data = model_class.model_validate(data)

        template = template_class(data)
        await self.send_email_template(template)