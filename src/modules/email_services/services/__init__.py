from src.modules.email_services.services.candidate_email_service import CandidateEmailService
from src.modules.email_services.services.panel_email_service import PanelEmailService


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
