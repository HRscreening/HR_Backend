from src.services.auth_services import AuthService
from src.services.user_services import UserService
from src.services.job_service import JobService
from src.services.application_service import ApplicationService
from src.services.batch_service import BatchService
from src.services.candidate_service import CandidateService

from src.modules.interviews.services import *

from src.modules.oauth.oauth_service import OAuthService
from src.modules.oauth.providers.Calendar_provider_service import GoogleCalendarOAuthService
from src.modules.reminders.reminder_service import ReminderAPIService, ReminderWorkerService
from src.dependency.repositories.repositories import *
from src.dependency.services.helper_services import *
from src.modules.interviews.repositories import *


def get_auth_service(
    repo: UserRepository = Depends(get_user_repository),
    emailService: EmailService = Depends(get_email_service),
    passwordService: PasswordService = Depends(get_password_service),
    db: AsyncSession = Depends(get_db)
):
    return AuthService(repo,emailService,passwordService,db)

def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
    calendar_repository: CalendarRepository = Depends(get_calendar_repository),
    db: AsyncSession = Depends(get_db)
):

    return UserService(repo,calendar_repository,db)


def get_job_service(
    job_repository: JobRepository = Depends(get_job_repository),
    db: AsyncSession = Depends(get_db),
    batch_repository: BatchRepository = Depends(get_batch_repository),
    round_config_repository: InterviewRoundConfigsRepository = Depends(get_interview_round_configs_repository),
    org_repository: OrganizationRepository = Depends(get_org_repository)
):
    return JobService(
        job_repository,
        batch_repository,
        org_repository,
        round_config_repository,
        db
    )


def get_application_service(
    application_repository: ApplicationRepository = Depends(get_application_repository),
    candidate_repository: CandidateRepository = Depends(get_candidate_repository),
    interview_event_repository: InterviewEventRepository = Depends(get_interview_event_repository),
    interview_round_config_repository: InterviewRoundConfigsRepository = Depends(get_interview_round_config_repository),
    panelist_repository: PanelistRepository = Depends(get_panelist_repository),
    interview_repository: InterviewRepository = Depends(get_interview_repository),
    job_repository: JobRepository = Depends(get_job_repository),
    email_producer: EmailProducer = Depends(get_email_producer),
    reminder_repository: ReminderRepository = Depends(get_reminder_repository),
    candidate_email_service: CandidateEmailService = Depends(get_candidate_email_service),
    panel_email_service: PanelEmailService = Depends(get_panel_email_service),
    db: AsyncSession = Depends(get_db)
):
    return ApplicationService(
        application_repository,
        candidate_repository,
        interview_repository,
        panelist_repository,
        interview_round_config_repository,
        interview_event_repository,
        job_repository,
        panel_email_service,
        candidate_email_service,
        reminder_repository,
        email_producer,
        db
    )



def get_batch_service(
    batch_repository: BatchRepository = Depends(get_batch_repository),
    db: AsyncSession = Depends(get_db),
):
    return BatchService(batch_repository, db)


def get_candidate_service(
    candidate_repository: CandidateRepository = Depends(get_candidate_repository),
    application_repository: ApplicationRepository = Depends(get_application_repository),
    db: AsyncSession = Depends(get_db),
):
    return CandidateService(
        candidate_repository,
        application_repository,
        db,
    )


def get_calendar_service():
    return CalendarService()


def get_google_calendar_oauth_service():
    return GoogleCalendarOAuthService()


def get_oauth_service(
    google_calendar_service: GoogleCalendarOAuthService = Depends(get_google_calendar_oauth_service),
    calendar_repository: CalendarRepository = Depends(get_calendar_repository),
    db: AsyncSession = Depends(get_db),
):
    return OAuthService(
        db,
        google_calendar_service,
        calendar_repository=calendar_repository,
    )


def get_interview_round_config_service(
    interview_round_config_repository: InterviewRoundConfigsRepository = Depends(get_interview_round_configs_repository),
    interview_event_repository: InterviewEventRepository = Depends(get_interview_event_repository),
    panelist_repository: PanelistRepository = Depends(get_panelist_repository),
    panel_email_service: PanelEmailService = Depends(get_panel_email_service),
    job_repository: JobRepository = Depends(get_job_repository),
    email_producer: EmailProducer = Depends(get_email_producer),
    reminder_repository: ReminderRepository = Depends(get_reminder_repository),
    db: AsyncSession = Depends(get_db),
):
    return InterviewRoundConfigService(
        interview_round_config_repository,
        interview_event_repository,
        panelist_repository,
        panel_email_service,
        job_repository,
        email_producer,
        reminder_repository,
        db
    )


def get_interview_service(
    interview_round_config_repository: InterviewRoundConfigsRepository = Depends(get_interview_round_configs_repository),
    interview_event_repository: InterviewEventRepository = Depends(get_interview_event_repository),
    interview_repository: InterviewRepository = Depends(get_interview_repository),
    panelist_repository: PanelistRepository = Depends(get_panelist_repository),
    slots_repository: InterviewSlotsRepository = Depends(get_interview_slots_repository),
    calendar_service: CalendarService = Depends(get_calendar_service),
    calendar_repository: CalendarRepository = Depends(get_calendar_repository),
    application_repository: ApplicationRepository = Depends(get_application_repository),
    panel_email_service: PanelEmailService = Depends(get_panel_email_service),
    candidate_email_service: CandidateEmailService = Depends(get_candidate_email_service),
    job_repository: JobRepository = Depends(get_job_repository),
    email_producer: EmailProducer = Depends(get_email_producer),
    reminder_repository: ReminderRepository = Depends(get_reminder_repository),
    db: AsyncSession = Depends(get_db),
):
    return InterviewService(
        interview_round_config_repository,
        interview_event_repository,
        interview_repository,
        panelist_repository,
        slots_repository,
        calendar_repository,
        calendar_service,
        application_repository,
        panel_email_service,
        candidate_email_service,
        job_repository,
        reminder_repository,
        email_producer,
        db,
    )


def get_panelist_service(
    interview_round_config_repository: InterviewRoundConfigsRepository = Depends(get_interview_round_configs_repository),
    interview_event_repository: InterviewEventRepository = Depends(get_interview_event_repository),
    interview_repository: InterviewRepository = Depends(get_interview_repository),
    panelist_repository: PanelistRepository = Depends(get_panelist_repository),
    slots_repository: InterviewSlotsRepository = Depends(get_interview_slots_repository),
    calendar_repository: CalendarRepository = Depends(get_calendar_repository),
    application_repository: ApplicationRepository = Depends(get_application_repository),
    calendar_service: CalendarService = Depends(get_calendar_service),
    panel_email_service: PanelEmailService = Depends(get_panel_email_service),
    candidate_email_service: CandidateEmailService = Depends(get_candidate_email_service),
    job_repository: JobRepository = Depends(get_job_repository),
    email_producer: EmailProducer = Depends(get_email_producer),
    reminder_repository: ReminderRepository = Depends(get_reminder_repository),
    db: AsyncSession = Depends(get_db),
):
    return PanelistService(
        interview_round_config_repository,
        interview_event_repository,
        interview_repository,
        panelist_repository,
        slots_repository,
        calendar_repository,
        application_repository,
        calendar_service,
        panel_email_service,
        candidate_email_service,
        job_repository,
        email_producer,
        reminder_repository,
        db,
    )


def get_reminder_worker_service(
    reminder_repository: ReminderRepository = Depends(get_reminder_repository),
    notification_service: NotificationService = Depends(get_notification_service),
    db: AsyncSession = Depends(get_db),
):
    return ReminderWorkerService(
        reminder_repository=reminder_repository,
        notification_service=notification_service,
        db=db
        )