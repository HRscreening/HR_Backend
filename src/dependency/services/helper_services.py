from src.utils.email_service import EmailService
from src.utils.security import PasswordService
from src.utils.jwt import JWTService
from src.modules.email_services.services import CandidateEmailService, PanelEmailService

def get_email_service():
    return EmailService()

def get_password_service():
    return PasswordService()

def get_jwt_service():
    return JWTService()


def get_candidate_email_service():
    return CandidateEmailService()

def get_panel_email_service():
    return PanelEmailService()