from contextlib import asynccontextmanager

from async_workers.producer import ARQProducer

from src.modules.interviews.repositories.interview_event_repository import InterviewEventRepository
from src.modules.notifications.notification_service import NotificationService
from src.modules.reminders.reminder_service import ReminderWorkerService
from src.modules.email_services.candidate.candidate_email_service import CandidateEmailService
from src.modules.email_services.panel.panel_email_service import PanelEmailService
from src.modules.reminders.reminder_repository import ReminderRepository 

@asynccontextmanager
async def job_context(ctx):
    """
    Create per-job dependencies automatically.
    """

    sessionmaker = ctx["db_sessionmaker"]
    redis = ctx["redis"]

    async with sessionmaker() as db:


        reminder_repository = ReminderRepository(db)
        interview_event_repository = InterviewEventRepository(db)
        
        candidate_email_service = CandidateEmailService()
        panel_email_service = PanelEmailService()
        
        notification_service = NotificationService(
            panel_email_service=panel_email_service,
            candidate_email_service=candidate_email_service
        )
        
        reminder_worker_service = ReminderWorkerService(
            notification_service=notification_service,
            reminder_repository=reminder_repository,
            interview_event_repository=interview_event_repository,
            db=db
        )
       

        yield {
            "db": db,
            "reminder_worker_service": reminder_worker_service,
        }
