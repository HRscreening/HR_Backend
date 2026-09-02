from src.modules.notifications.channels.email.services.candidate_email_service import CandidateEmailService
from src.modules.notifications.channels.email.services.panel_email_service import PanelEmailService
from typing import Literal
from src.dtos.notification_dto import RecipientType
# Can add more services here in the future if needed and import them in the EmailService class
class EmailService:
    def __init__(
        self,
        candidate_service: CandidateEmailService | None = None,
        panel_service: PanelEmailService | None = None
    ):
        self.candidate = candidate_service or CandidateEmailService()
        self.panel = panel_service or PanelEmailService()
        

__all__ = ["CandidateEmailService","PanelEmailService","EmailService"]


# Factory to get the appropriate email service based on recipient type
class EmailFactory:
    def __init__(
        self,
        candidate_service: CandidateEmailService,
        panel_service: PanelEmailService,
    ):
        self.SERVICES_MAP = {
            RecipientType.CANDIDATE: candidate_service,
            RecipientType.PANELIST: panel_service,
        }

    def get_email_service(self, recipient_type: RecipientType):
        service_instance = self.SERVICES_MAP.get(recipient_type)

        if not service_instance:
            raise ValueError(f"Unsupported recipient type: {recipient_type}")

        return service_instance