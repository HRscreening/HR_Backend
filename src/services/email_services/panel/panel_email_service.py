from configs.log_config import get_logger
from src.services.email_services.panel.email_templates import panelist_email_templates,PanelEmailTemplates
from src.services.email_services.base import BaseEmailService
from datetime import datetime


def _format_dt_for_email(dt: datetime) -> str:
    """Format a datetime as 'Mar 10, 2026 at 02:30 PM UTC'."""
    return dt.strftime("%b %d, %Y at %I:%M %p UTC")


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

    async def send_booking_confirmation_to_panelist(
        self,
        panelist_email: str,
        panelist_name: str | None,
        candidate_name: str,
        interview_round_title: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        meet_link: str | None = None,
    ):
        """Send a confirmation email to a panelist after a candidate books a slot."""
        interview_date = _format_dt_for_email(scheduled_start).split(" at ")[0]
        start_time = scheduled_start.strftime("%I:%M %p")
        end_time = scheduled_end.strftime("%I:%M %p UTC")
        interview_time = f"{start_time} – {end_time}"

        subject = f"Interview Scheduled: {interview_round_title}"
        body = self.panelist_email_templates.get_panelist_booking_confirmation_template(
            panelist_name=panelist_name,
            candidate_name=candidate_name,
            interview_round_title=interview_round_title,
            interview_date=interview_date,
            interview_time=interview_time,
            meet_link=meet_link,
        )
        try:
            await self.send_email(receiver_email=panelist_email, subject=subject, body=body)
            self.logger.info(f"Sent booking confirmation to panelist {panelist_email}")
        except Exception as e:
            self.logger.error(f"Failed to send booking confirmation to panelist {panelist_email}: {str(e)}")


panel_email_service = PanelEmailService()