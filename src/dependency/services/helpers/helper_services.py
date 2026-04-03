from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.utils.email_service import EmailService
from src.utils.security import PasswordService
from src.utils.jwt import JWTService
from src.modules.notifications.notification_service import NotificationService
from workers_async.connection import get_redis_pool
from src.utils.file_manager import FileManagerService
from src.dependency.services.helpers.email_services import get_email_service, get_candidate_email_service, get_panel_email_service


# ! to be removed 
def get_email_service___():
    return EmailService()

def get_password_service():
    return PasswordService()

def get_jwt_service():
    return JWTService()


def get_notification_service():
    email_service = Depends(get_email_service)
    return NotificationService(email_service=email_service)


    
from workers_async.email_tasks_producer import EmailProducer
async def get_email_producer():
    redis = await get_redis_pool()  # if async
    return EmailProducer(redis)
    
    
from workers_async.assessment_task_producer import AssessmentTaskProducer
async def get_assessment_task_producer():
    redis = await get_redis_pool()  # if async
    return AssessmentTaskProducer(redis)

def get_file_manager_service():
    return FileManagerService()