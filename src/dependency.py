from configs.postgress_db import AsyncSession,get_db
from fastapi import Depends



from src.repositories.user_repository import UserRepository
from src.repositories.job_repository import JobRepository
from src.repositories.org_repository import OrganizationRepository
from src.repositories.batch_repositoy import BatchRepository
from src.repositories.application_repository import ApplicationRepository
from src.repositories.candidiate_repository import CandidateRepository 
from src.repositories.resume_respositoy import ResumeRepository
from async_workers.producer import ARQProducer
from async_workers.connection import get_redis_pool

# ------------------------ INTERVIEW  REPOSITORY ------------------------
from src.repositories.interview_respositories.interview_round_configs_repository import InterviewRoundConfigsRepository
from src.repositories.interview_respositories.interview_event_repository import InterviewEventRepository
from src.repositories.interview_respositories.panelist_repository import PanelistRepository
from src.repositories.interview_respositories.interview_repository import  InterviewRepository
from src.repositories.interview_respositories.interview_slots_repository import InterviewSlotsRepository
from src.repositories.interview_respositories.calendar_repository import CalendarRepository


from src.services.auth_services import AuthService
from src.services.user_services import UserService
from src.services.job_service import JobService
from src.utils.file_manager import FileManagerService
from src.services.batch_service import BatchService
from src.services.application_service import ApplicationService
from src.services.candidate_service import CandidateService
from src.services.interview_services.calendar_service import CalendarService
from src.utils.email_service import emailService 
from src.utils.security import passwordService
from src.utils.jwt import JWTService

# --------------------- INTERVIEW SERVICES ----------------------
from src.services.interview_services.interview_round_config_service import InterviewRoundConfigService
from src.services.interview_services.panelist_service import PanelistService
from src.services.interview_services.interview_service import InterviewService




# ----------------------------- OAUTH SERVICES -----------------------------
from src.services.oauth.providers.Calendar_provider_service import GoogleCalendarOAuthService
from src.services.oauth.oauth_service import OAuthService





# ------------------------ DEPENDENCY INJECTION ------------------------

def get_jwt_service():

    return JWTService()

def get_batch_repository(
    db: AsyncSession = Depends(get_db)
):
    return BatchRepository(db)


def get_user_repository(
    db: AsyncSession = Depends(get_db)
):
    return UserRepository(db)


def get_job_repository(
    db: AsyncSession = Depends(get_db)
):
    return JobRepository(db)



def get_org_repository(
    db: AsyncSession = Depends(get_db)
):
    return OrganizationRepository(db)



def get_application_repository(
    db: AsyncSession = Depends(get_db)
):
    return ApplicationRepository(db)

def get_candidate_repository(
    db: AsyncSession = Depends(get_db)
): 
    return CandidateRepository(db)

def get_resume_repository(
    db: AsyncSession = Depends(get_db)
):
    return ResumeRepository(db)


from arq.connections import ArqRedis
async def get_producer(redis: ArqRedis = Depends(get_redis_pool)):
    return ARQProducer(redis)

def get_interview_round_config_repository(db: AsyncSession = Depends(get_db)):
    return InterviewRoundConfigsRepository(db)

def get_interview_event_repository(db: AsyncSession = Depends(get_db)):
    return InterviewEventRepository(db)

def get_panelist_repository(
    db: AsyncSession = Depends(get_db),
    jwt_service = Depends(get_jwt_service)
    ):
    return PanelistRepository(db,jwt_service)

def get_interview_repository(db: AsyncSession = Depends(get_db)):
    return InterviewRepository(db)

def get_interview_slots_repository(db: AsyncSession = Depends(get_db)):
    return InterviewSlotsRepository(db)

def get_calendar_repository(db: AsyncSession = Depends(get_db)):
    return CalendarRepository(db)








def get_jwt_service():
    from src.utils.jwt import JWTService
    return JWTService()


def get_file_manager_service():
    return FileManagerService()


def get_auth_service(
    repo: UserRepository = Depends(get_user_repository),
    db: AsyncSession = Depends(get_db)
):
    return AuthService(repo,emailService,passwordService,db)

def get_user_service(
    repo: UserRepository = Depends(get_user_repository),
    db: AsyncSession = Depends(get_db)
):

    return UserService(repo,db)


# def get_job_service(
#     jobRepo: JobRepository = Depends(get_job_repository),
#     db: AsyncSession = Depends(get_db),
#     batch_repository: BatchRepository = Depends(get_batch_repository),
#     org_repository: OrganizationRepository = Depends(get_org_repository)
# ):
#     return JobService(db=db,  job_repositoy=jobRepo,batch_repository=batch_repository,org_repository=org_repository)


# ----------- Keshav's edits for worker dependencies --------------
def get_job_service(
    jobRepo: JobRepository = Depends(get_job_repository),
    db: AsyncSession = Depends(get_db),
    batch_repository: BatchRepository = Depends(get_batch_repository),
    org_repository: OrganizationRepository = Depends(get_org_repository),
    resume_repository: ResumeRepository = Depends(get_resume_repository),
    job_producer: ARQProducer = Depends(get_producer),
    interview_round_configs_repository: InterviewRoundConfigsRepository = Depends(get_interview_round_config_repository),
    application_repository: ApplicationRepository = Depends(get_application_repository)
):
    return JobService(db=db,  job_repositoy=jobRepo,batch_repository=batch_repository,org_repository=org_repository,application_repository=application_repository,resume_repository=resume_repository,interview_round_configs_repository=interview_round_configs_repository,job_producer=job_producer)




def get_batch_service(
    batch_repository: BatchRepository = Depends(get_batch_repository),
    db: AsyncSession = Depends(get_db)
):
    return BatchService(batch_repository=batch_repository, db=db)

def get_application_service(
    application_repository: ApplicationRepository = Depends(get_application_repository),
    candidate_repository: CandidateRepository = Depends(get_candidate_repository),
    interview_event_repository: InterviewEventRepository = Depends(get_interview_event_repository),
    interview_round_config_repository: InterviewRoundConfigsRepository = Depends(get_interview_round_config_repository),
    panelist_repository: PanelistRepository = Depends(get_panelist_repository),
    interview_repository: InterviewRepository = Depends(get_interview_repository),
    job_repository: JobRepository = Depends(get_job_repository),
    db: AsyncSession = Depends(get_db)
):
    return ApplicationService(application_repository=application_repository , candidate_repository=candidate_repository,
                              interview_event_repository=interview_event_repository,
                              job_repository=job_repository,
                              interview_round_config_repository=interview_round_config_repository,panelist_repository=panelist_repository,interview_repository=interview_repository, db=db)


def get_candidate_service(
    candidate_repository: CandidateRepository = Depends(get_candidate_repository),
    application_repository: ApplicationRepository = Depends(get_application_repository),
    db: AsyncSession = Depends(get_db)
):
    return CandidateService(candidate_repository=candidate_repository, application_repository=application_repository, db=db)

def get_calendar_service(
    # db: AsyncSession = Depends(get_db)
):
    return CalendarService()

def get_interview_round_config_service(
    interview_round_config_repository: InterviewRoundConfigsRepository = Depends(get_interview_round_config_repository),
    interview_event_repository: InterviewEventRepository = Depends(get_interview_event_repository),
    panelist_repository: PanelistRepository = Depends(get_panelist_repository),
    db: AsyncSession = Depends(get_db)
):
    return InterviewRoundConfigService(interview_round_config_repository=interview_round_config_repository,interview_event_repository=interview_event_repository,panelist_repository=panelist_repository, db=db)


def get_panelist_service(
    interview_round_config_repository: InterviewRoundConfigsRepository = Depends(get_interview_round_config_repository),
    interview_event_repository: InterviewEventRepository = Depends(get_interview_event_repository),
    interview_repository: InterviewRepository = Depends(get_interview_repository),
    panelist_repository: PanelistRepository = Depends(get_panelist_repository),
    calendar_repository: CalendarRepository = Depends(get_calendar_repository),
    slots_repository: InterviewSlotsRepository = Depends(get_interview_slots_repository),
    db: AsyncSession = Depends(get_db)
):
    return PanelistService(interview_round_config_repository=interview_round_config_repository,interview_event_repository=interview_event_repository,calendar_repository=calendar_repository,interview_repository=interview_repository,panelist_repository=panelist_repository,slots_repository=slots_repository, db=db)


def get_interview_service(
    interview_round_config_repository: InterviewRoundConfigsRepository = Depends(get_interview_round_config_repository),
    interview_event_repository: InterviewEventRepository = Depends(get_interview_event_repository),
    interview_repository: InterviewRepository = Depends(get_interview_repository),
    panelist_repository: PanelistRepository = Depends(get_panelist_repository),
    calendar_service: CalendarService = Depends(get_calendar_service),
    slots_repository: InterviewSlotsRepository = Depends(get_interview_slots_repository),
    db: AsyncSession = Depends(get_db),
):
    return InterviewService(
        interview_round_config_repository=interview_round_config_repository,
        interview_event_repository=interview_event_repository,
        interview_repository=interview_repository,
        panelist_repository=panelist_repository,
        calendar_service=calendar_service,
        slots_repository=slots_repository,
        db=db,
    )
    
    
def get_google_calendar_oauth_service():
    return GoogleCalendarOAuthService()


def get_oauth_service(
    db: AsyncSession = Depends(get_db),
    google_calendar_service: GoogleCalendarOAuthService = Depends(get_google_calendar_oauth_service),
    calendar_repository: CalendarRepository = Depends(get_calendar_repository)
):
    return OAuthService(db=db,google_calendar_service=google_calendar_service, calendar_repository=calendar_repository)