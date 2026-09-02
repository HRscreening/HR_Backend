from contextlib import asynccontextmanager

from src.modules.interviews.repositories.interview_event_repository import InterviewEventRepository
from src.modules.notifications.services.notification_service import NotificationService
from src.modules.notifications.services.notification_worker import NotificationWorker
from src.modules.notifications.notification_dispatcher import NotificationDispatcher
from src.modules.notifications.repositories.notification_repository import NotificationRepository
from src.modules.notifications.channels.email.services import EmailFactory, CandidateEmailService, PanelEmailService
from src.modules.interviews.services.Interview_assessment_service import InterviewAssessmentWorkerService

from src.modules.reminders.reminder_repository import ReminderRepository
from src.modules.interviews.repositories import (
    InterviewRepository,
    PanelistRepository,
    InterviewAssessmentRepository,
    InterviewSlotsRepository,
    InterviewRoundConfigsRepository,
)
from src.utils.jwt import JWTService
from src.repositories.application_repository import ApplicationRepository
from src.repositories.job_repository import JobRepository
from src.modules.interviews.services.helpers.token_manager.Interview_token_manger import InterviewTokenManagerFactory
from workers_async.producers.email_tasks_producer import EmailProducer
from workers_async.producers.assessment_task_producer import AssessmentTaskProducer
from workers_async.producers.notification_producer import NotificationProducer
from workers_async.factory import AsyncProducerFactory

from src.modules.interviews.services.helpers.fireflies import FirefliesHelper
from src.utils.supabase_file_handler import SupabaseFileHandler


@asynccontextmanager
async def job_context(ctx):
    """
    Create per-job dependencies automatically.
    """

    sessionmaker = ctx["db_sessionmaker"]
    redis = ctx["redis"]

    async with sessionmaker() as db:

        jwt_service = JWTService()

        reminder_repository = ReminderRepository(db)
        notification_repository = NotificationRepository(db)
        interview_event_repository = InterviewEventRepository(db)
        panelist_repository = PanelistRepository(db)
        interview_assessment_repository = InterviewAssessmentRepository(db)
        job_repository = JobRepository(db)
        interview_repository = InterviewRepository(db)
        slot_repository = InterviewSlotsRepository(db)
        application_repository = ApplicationRepository(db)
        interview_round_config_repository = InterviewRoundConfigsRepository(db)
        fireflies_helper = FirefliesHelper()
        supabase_file_handler = SupabaseFileHandler()

        email_producer = EmailProducer(redis)
        notification_producer = NotificationProducer(redis)
        assessment_task_producer = AssessmentTaskProducer(redis)

        producer_factory = AsyncProducerFactory(
            Email_Producer=email_producer,
            Notification_Producer=notification_producer,
            AssessmentTask_Producer=assessment_task_producer,
        )

        notification_dispatcher = NotificationDispatcher(
            reminder_repository=reminder_repository,
            notification_repository=notification_repository,
            producer_factory=producer_factory,
            db=db,
        )

        notification_service = NotificationService(
            email_factory=EmailFactory(
                candidate_service=CandidateEmailService(),
                panel_service=PanelEmailService(),
            )
        )

        notification_worker = NotificationWorker(
            notification_service=notification_service,
            notification_repository=notification_repository,
            reminder_repository=reminder_repository,
            db=db,
        )

        interview_assessment_worker_service = InterviewAssessmentWorkerService(
            interview_round_config_repository=interview_round_config_repository,
            interview_event_repository=interview_event_repository,
            panelist_repository=panelist_repository,
            interview_assessment_repository=interview_assessment_repository,
            job_repository=job_repository,
            producer_factory=producer_factory,
            reminder_repository=reminder_repository,
            interview_repository=interview_repository,
            slot_repository=slot_repository,
            application_repository=application_repository,
            jwt_service=jwt_service,
            interview_token_manager_factory=InterviewTokenManagerFactory(jwt_service),
            fireflies_helper=fireflies_helper,
            supabase_file_handler=supabase_file_handler,
            notification_dispatcher=notification_dispatcher,
            db=db,
        )

        yield {
            "db": db,
            "reminder_repository": reminder_repository,
            "notification_repository": notification_repository,
            "email_producer": email_producer,
            "notification_producer": notification_producer,
            "producer_factory": producer_factory,
            "notification_worker": notification_worker,
            "interview_assessment_worker_service": interview_assessment_worker_service,
        }
