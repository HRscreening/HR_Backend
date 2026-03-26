from configs.log_config import get_logger
from src.modules.email_services.base import BaseEmailService
from src.modules.email_services.panel.email_templates import panelist_email_templates, PanelEmailTemplates
from datetime import datetime
from zoneinfo import ZoneInfo


def _format_dt_for_email(dt) -> str:
    """Format a datetime into a human-readable IST string for emails."""
    if isinstance(dt, datetime):
        ist_dt = dt.astimezone(ZoneInfo("Asia/Kolkata")) if dt.tzinfo else dt
        return ist_dt.strftime("%b %d, %Y at %I:%M %p") + " IST"
    return str(dt)

# TODO: later they will be dynamic according to the round's timezone. For now, we are assuming all rounds are in IST and formatting accordingly.
def _to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("Asia/Kolkata"))



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
        reschedule_link: str | None = None
    ):
        """Send a confirmation email to a panelist after a candidate books a slot."""
        interview_date = _format_dt_for_email(scheduled_start).split(" at ")[0]
        start = _to_ist(scheduled_start)
        end = _to_ist(scheduled_end)

        start_time = start.strftime("%I:%M %p")
        end_time = end.strftime("%I:%M %p")
        interview_time = f"{start_time} – {end_time}"

        subject = f"Interview Scheduled: {interview_round_title}"
        body = self.panelist_email_templates.get_panelist_booking_confirmation_template(
            panelist_name=panelist_name,
            candidate_name=candidate_name,
            interview_round_title=interview_round_title,
            interview_date=interview_date,
            interview_time=interview_time,
            meet_link=meet_link,
            reschedule_link=reschedule_link
        )
        try:
            await self.send_email(receiver_email=panelist_email, subject=subject, body=body)
            self.logger.info(f"Sent booking confirmation to panelist {panelist_email}")
        except Exception as e:
            self.logger.error(f"Failed to send booking confirmation to panelist {panelist_email}: {str(e)}")

    async def send_slot_released_to_panelist(
        self,
        panelist_email:str,
        panelist_name:str,
        candidate_name:str,
        interview_round_title:str,
        old_scheduled_start:datetime,
        old_scheduled_end:datetime,
    ):
        """Send a confirmation email to a panelist after a candidate books a slot."""
        interview_date = _format_dt_for_email(old_scheduled_start).split(" at ")[0]
        start = _to_ist(old_scheduled_start)
        end = _to_ist(old_scheduled_end)

        start_time = start.strftime("%I:%M %p")
        end_time = end.strftime("%I:%M %p")
        interview_time = f"{start_time} – {end_time}"

        subject = f"Interview Scheduled: {interview_round_title}"
        body = self.panelist_email_templates.get_slot_released_template(
            panelist_name=panelist_name,
            candidate_name=candidate_name,
            interview_round_title=interview_round_title,
            interview_date=interview_date,
            interview_time=interview_time,
        )
        try:
            await self.send_email(receiver_email=panelist_email, subject=subject, body=body)
            self.logger.info(f"Sent booking confirmation to panelist {panelist_email}")
        except Exception as e:
            self.logger.error(f"Failed to send booking confirmation to panelist {panelist_email}: {str(e)}")
        
    async def send_meeting_rescheduled_email_to_panelist(
        self,
        panelist_email: str,
        panelist_name: str,
        candidate_name: str,
        interview_round_title: str,
        old_scheduled_start: datetime,
        old_scheduled_end: datetime,
        new_scheduled_start: datetime,
        new_scheduled_end: datetime,
        new_meet_link: str | None,
        reschedule_link:str | None
    ):
        """Send email to panelist when a candidate reschedules their interview."""

        old_date = _format_dt_for_email(old_scheduled_start).split(" at ")[0]
        old_start = _to_ist(old_scheduled_start)
        old_end = _to_ist(old_scheduled_end)
        old_time = f"{old_start.strftime('%I:%M %p')} – {old_end.strftime('%I:%M %p')}"
        new_date = _format_dt_for_email(new_scheduled_start).split(" at ")[0]
        new_start = _to_ist(new_scheduled_start)
        new_end = _to_ist(new_scheduled_end)
        new_time = f"{new_start.strftime('%I:%M %p')} – {new_end.strftime('%I:%M %p')}"
        
        subject = f"Interview Rescheduled – {candidate_name} | {interview_round_title}"

        body = self.panelist_email_templates.get_meeting_rescheduled_email_template(
            panelist_name=panelist_name,
            candidate_name=candidate_name,
            interview_round_title=interview_round_title,
            old_date=old_date,
            old_time=old_time,
            new_date=new_date,
            new_time=new_time,
            meet_link=new_meet_link,
            reschedule_link=reschedule_link
        )

        try:
            await self.send_email(
                receiver_email=panelist_email,
                subject=subject,
                body=body
            )
            self.logger.info(f"Sent reschedule notification to panelist {panelist_email}")

        except Exception as e:
            self.logger.error(f"Failed to send reschedule email to panelist {panelist_email}: {str(e)}")
            
    
    async def send_thanks_for_submitting_availability_email(self, panelist_email: str, panelist_name: str, interview_round_title: str,edit_slots_link:str,validity_period:str):
        subject = f"Thank you for submitting your availability for {interview_round_title}"
        body = self.panelist_email_templates.get_panelist_thank_you_availability_template(
            panelist_name=panelist_name,
            interview_round_title=interview_round_title,
            edit_slots_link=edit_slots_link,
            validity_period=validity_period
        )
        try:
            await self.send_email(receiver_email=panelist_email, subject=subject, body=body)
            self.logger.info(f"Sent thanks for submitting availability email to {panelist_email} with subject '{subject}'")
        except Exception as e:
            self.logger.error(f"Failed to send thanks for submitting availability email to {panelist_email}: {str(e)}")

    
    async def send_form_reminder_email_to_panelist(
        self,
        panelist_email: str,
        panelist_name: str,
        interview_round_title: str,
        form_link: str
    ):
        subject = f"Reminder: Submit Availability for {interview_round_title}"

        body = self.panelist_email_templates.get_panelist_reminder_email_template(
            panelist_name=panelist_name,
            interview_round_title=interview_round_title,
            form_link=form_link
        )

        try:
            await self.send_email(
                receiver_email=panelist_email,
                subject=subject,
                body=body
            )
            self.logger.info(
                f"Sent reminder email to {panelist_email} with subject '{subject}'"
            )
        except Exception as e:
            self.logger.error(
                f"Failed to send reminder email to {panelist_email}: {str(e)}"
            )
            
            
    async def send_panelist_interview_reminder_email(
        self,
        panelist_email: str,
        panelist_name: str | None,
        candidate_name: str,
        interview_round_title: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        meet_link: str | None = None,
        reschedule_link: str | None = None
    ):
        # Format datetime nicely (important!)
        interview_date = _format_dt_for_email(scheduled_start).split(" at ")[0]
        start = _to_ist(scheduled_start)
        end = _to_ist(scheduled_end)
        
        start_time = start.strftime("%I:%M %p")
        end_time = end.strftime("%I:%M %p")
        interview_time = f"{start_time} – {end_time}"


        subject = f"Reminder: Interview with {candidate_name} ({interview_round_title})"

        body = self.panelist_email_templates.get_panelist_interview_reminder_template(
            panelist_name=panelist_name,
            candidate_name=candidate_name,
            interview_round_title=interview_round_title,
            interview_date=interview_date,
            interview_time=interview_time,
            meet_link=meet_link,
            reschedule_link=reschedule_link
        )

        try:
            await self.send_email(
                receiver_email=panelist_email,
                subject=subject,
                body=body
            )
            self.logger.info(
                f"Sent interview reminder to {panelist_email} with subject '{subject}'"
            )
        except Exception as e:
            self.logger.error(
                f"Failed to send interview reminder to {panelist_email}: {str(e)}"
            )