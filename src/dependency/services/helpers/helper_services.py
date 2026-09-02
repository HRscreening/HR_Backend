from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.utils.email_service import EmailService
from src.utils.security import PasswordService
from src.utils.jwt import JWTService
from workers_async.connection import get_redis_pool
from src.utils.file_manager import FileManagerService
from src.dependency.services.helpers.email_services import get_email_service, get_candidate_email_service, get_panel_email_service
from src.utils.supabase_file_handler import SupabaseFileHandler

# ! to be removed — auth_service is the last caller until it is migrated to NotificationDispatcher
def get_email_service___():
    return EmailService()

def get_password_service():
    return PasswordService()

def get_jwt_service():
    return JWTService()


from workers_async.producers.email_tasks_producer import EmailProducer
async def get_email_producer():
    redis = await get_redis_pool()  # if async
    return EmailProducer(redis)
    
    
from workers_async.producers.assessment_task_producer import AssessmentTaskProducer
async def get_assessment_task_producer():
    redis = await get_redis_pool()  # if async
    return AssessmentTaskProducer(redis)

from workers_async.producers.notification_producer import NotificationProducer
async def get_notification_producer():
    redis = await get_redis_pool()
    return NotificationProducer(redis)


from workers_async.factory import AsyncProducerFactory
async def get_async_producer_factory(
    email_producer: EmailProducer = Depends(get_email_producer),
    notification_producer: NotificationProducer = Depends(get_notification_producer),
    assessment_task_producer: AssessmentTaskProducer = Depends(get_assessment_task_producer),
) -> AsyncProducerFactory:
    return AsyncProducerFactory(
        Email_Producer=email_producer,
        Notification_Producer=notification_producer,
        AssessmentTask_Producer=assessment_task_producer,
    )


def get_file_manager_service():
    return FileManagerService()

def get_supabase_file_handler():
    return SupabaseFileHandler()

from src.modules.notifications.notification_dispatcher import NotificationDispatcher
from src.dependency.repositories.repositories import get_reminder_repository, get_notification_repository
from configs.postgress_db import get_db

async def get_notification_dispatcher(
    reminder_repository=Depends(get_reminder_repository),
    notification_repository=Depends(get_notification_repository),
    producer_factory: AsyncProducerFactory = Depends(get_async_producer_factory),
    db: AsyncSession = Depends(get_db),
) -> NotificationDispatcher:
    return NotificationDispatcher(
        reminder_repository=reminder_repository,
        notification_repository=notification_repository,
        producer_factory=producer_factory,
        db=db,
    )