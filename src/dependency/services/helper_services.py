from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.utils.email_service import EmailService
from src.utils.security import PasswordService
from src.utils.jwt import JWTService
from src.modules.email_services.services import CandidateEmailService, PanelEmailService
from src.modules.notifications.notification_service import NotificationService
from email_workers_async.connection import get_redis_pool
from src.utils.file_manager import FileManagerService

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


def get_notification_service():
    panel_email_service = get_panel_email_service()
    candidate_email_service = get_candidate_email_service()
    return NotificationService(panel_email_service, candidate_email_service)


    
from email_workers_async.email_tasks_producer import EmailProducer
async def get_email_producer():
    redis = await  get_redis_pool()
    return EmailProducer(redis)

def get_file_manager_service():
    return FileManagerService()