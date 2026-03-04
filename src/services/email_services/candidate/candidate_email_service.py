from datetime import datetime, timezone
from configs.log_config import get_logger
from src.services.email_services.candidate.email_templates import candidate_email_templates, CandidateEmailTemplates
from src.services.email_services.base import BaseEmailService


def _format_dt_for_email(dt) -> str:
    """Format a datetime into a human-readable UTC string for emails."""
    if isinstance(dt, datetime):
        utc_dt = dt.astimezone(timezone.utc) if dt.tzinfo else dt
        return utc_dt.strftime("%b %d, %Y at %I:%M %p") + " UTC"
    return str(dt)


class CandidateEmailService(BaseEmailService):
    def __init__(self):
        super().__init__()
        self.logger = get_logger("CandidateEmailService")
        self.templates: CandidateEmailTemplates = candidate_email_templates

    async def send_booking_link_email(
        self,
        candidate_email: str,
        candidate_name: str,
        interview_round_title: str,
        booking_link: str,
    ):
        subject = f"Your Interview Slots Are Ready — {interview_round_title}"
        body = self.templates.get_booking_link_email_template(
            candidate_name=candidate_name,
            interview_round_title=interview_round_title,
            booking_link=booking_link,
        )
        try:
            await self.send_email(receiver_email=candidate_email, subject=subject, body=body)
            self.logger.info(f"Sent booking link email to {candidate_email}")
        except Exception as e:
            self.logger.error(f"Failed to send booking link email to {candidate_email}: {e}")
            raise

    async def send_booking_confirmation_email(
        self,
        candidate_email: str,
        candidate_name: str,
        interview_round_title: str,
        scheduled_start,
        scheduled_end,
        meet_link: str | None = None,
        reschedule_link: str | None = None,
    ):
        subject = f"Interview Confirmed — {interview_round_title}"
        body = self.templates.get_booking_confirmation_email_template(
            candidate_name=candidate_name,
            interview_round_title=interview_round_title,
            scheduled_start=_format_dt_for_email(scheduled_start),
            scheduled_end=_format_dt_for_email(scheduled_end),
            meet_link=meet_link,
            reschedule_link=reschedule_link,
        )
        try:
            await self.send_email(receiver_email=candidate_email, subject=subject, body=body)
            self.logger.info(f"Sent booking confirmation email to {candidate_email}")
        except Exception as e:
            self.logger.error(f"Failed to send booking confirmation email to {candidate_email}: {e}")
            raise


candidate_email_service = CandidateEmailService()
