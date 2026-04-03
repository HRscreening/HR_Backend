from contextlib import asynccontextmanager

from async_workers.producer import ARQProducer

from src.modules.interviews.repositories.interview_event_repository import InterviewEventRepository
from src.modules.notifications.notification_service import NotificationService
from src.modules.reminders.reminder_service import ReminderWorkerService
from src.modules.interviews.services.Interview_assessment_service  import InterviewAssessmentWorkerService 

from src.modules.email_services.services.candidate_email_service import CandidateEmailService
from src.modules.email_services.services.panel_email_service import PanelEmailService
from src.modules.email_services.services import EmailService
from src.modules.reminders.reminder_repository import ReminderRepository 
from src.modules.interviews.repositories import InterviewRepository, PanelistRepository, InterviewAssessmentRepository,InterviewSlotsRepository,InterviewRoundConfigsRepository
from src.utils.jwt import JWTService
from src.repositories.application_repository import ApplicationRepository
from src.repositories.job_repository import JobRepository
from src.modules.interviews.services.helpers.token_manager.Interview_token_manger import InterviewTokenManagerFactory
from workers_async.email_tasks_producer import EmailProducer


@asynccontextmanager
async def job_context(ctx):
    """
    Create per-job dependencies automatically.
    """

    sessionmaker = ctx["db_sessionmaker"]
    redis = ctx["redis"]

    async with sessionmaker() as db:

        jwt_service  = JWTService()

        reminder_repository = ReminderRepository(db)
        interview_event_repository = InterviewEventRepository(db)
        panelist_repository = PanelistRepository(db)
        interview_assessment_repository = InterviewAssessmentRepository(db)
        job_repository = JobRepository(db)
        interview_repository = InterviewRepository(db)
        slot_repository = InterviewSlotsRepository(db)
        application_repository = ApplicationRepository(db)
        interview_round_config_repository = InterviewRoundConfigsRepository(db)
        candidate_email_service = CandidateEmailService()
        panel_email_service = PanelEmailService()
        
        email_service = EmailService(
            candidate_service=candidate_email_service,
            panel_service=panel_email_service
        )
        
        notification_service = NotificationService(
            email_service=email_service
        )
        
        reminder_worker_service = ReminderWorkerService(
            reminder_repository=reminder_repository,
            notification_service=notification_service,
            interview_event_repository=interview_event_repository,
            db=db
        )
        
        
        interview_assessment_worker_service = InterviewAssessmentWorkerService(
            application_repository=application_repository,
            interview_repository=interview_repository,
            slot_repository=slot_repository,
            jwt_service=jwt_service,
            interview_token_manager_factory=InterviewTokenManagerFactory(jwt_service),
            db=db,
            email_producer=EmailProducer(redis),
            interview_assessment_repository=interview_assessment_repository,
            interview_event_repository=interview_event_repository,
            interview_round_config_repository=interview_round_config_repository,
            email_service=email_service,
            job_repository=job_repository,
            panelist_repository=panelist_repository,
            reminder_repository=reminder_repository,
            
        )
       

        yield {
            "db": db,
            "reminder_worker_service": reminder_worker_service,
            "interview_assessment_worker_service": interview_assessment_worker_service
        }
