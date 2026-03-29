from fastapi import Depends
from src.modules.email_services.services import *


def get_candidate_email_service():
    return CandidateEmailService()

def get_panel_email_service():
    return PanelEmailService()

def get_email_service():
    candidate_email_service = Depends(get_candidate_email_service)
    panel_email_service = Depends(get_panel_email_service)
    return EmailService(
        candidate_service=candidate_email_service,
        panel_service=panel_email_service
    )

