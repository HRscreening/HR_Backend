from configs.log_config import get_logger
from src.services.email_services.panel.email_templates import panelist_email_templates,PanelEmailTemplates
from src.services.email_services.base import BaseEmailService


class PanelEmailService(BaseEmailService):
    def __init__(self):
        super().__init__()
        self.logger = get_logger("PanelEmailService")
        self.panelist_email_templates : PanelEmailTemplates = panelist_email_templates
        
    async def send_slot_availability_email(self,panelist_email:str,panelist_name:str,interview_round_title:str,form_link:str):
        subject = f"Interview Slot Availability for Round: {interview_round_title}"
        body = self.panelist_email_templates.get_panelist_available_slots_email_template(
            panelist_name=panelist_name,
            interview_round_title=interview_round_title,
            form_link=form_link
        )
        try:
            await self.send_email(receiver_email=panelist_email, subject=subject, body=body)
            self.logger.info(f"Sending slot availability email to {panelist_email} with subject '{subject}''")
        except Exception as e:
            self.logger.error(f"Failed to send slot availability email to {panelist_email}: {str(e)}")
            # return
        
        
        
        # Here you would integrate with your actual email sending service/library


panel_email_service = PanelEmailService()