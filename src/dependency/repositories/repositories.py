from configs.postgress_db import AsyncSession,get_db
from fastapi import Depends



from src.repositories.user_repository import UserRepository
from src.repositories.job_repository import JobRepository
from src.repositories.application_repository import ApplicationRepository
from src.repositories.org_repository import OrganizationRepository
from src.repositories.batch_repositoy import BatchRepository
from src.repositories.candidiate_repository import CandidateRepository

from src.modules.interviews.repositories import *
from src.dependency.services.helper_services import *



def get_batch_repository(db: AsyncSession = Depends(get_db)): return BatchRepository(db)


def get_user_repository(db: AsyncSession = Depends(get_db)): return UserRepository(db)


def get_job_repository(db: AsyncSession = Depends(get_db)): return JobRepository(db)


def get_application_repository(db: AsyncSession = Depends(get_db)): return ApplicationRepository(db)


def get_org_repository(db: AsyncSession = Depends(get_db)):return OrganizationRepository(db)


def get_candidate_repository(db: AsyncSession = Depends(get_db)): return CandidateRepository(db)


def get_interview_round_configs_repository(db: AsyncSession = Depends(get_db)): return InterviewRoundConfigsRepository(db)


def get_interview_event_repository(db: AsyncSession = Depends(get_db)): return InterviewEventRepository(db)


def get_panelist_repository(
    db: AsyncSession = Depends(get_db)
):
    return PanelistRepository(db)


def get_interview_repository(db: AsyncSession = Depends(get_db)):
    return InterviewRepository(db)


def get_interview_round_config_repository(db: AsyncSession = Depends(get_db)):
    return InterviewRoundConfigsRepository(db)


def get_interview_slots_repository(db: AsyncSession = Depends(get_db)):
    return InterviewSlotsRepository(db)


def get_calendar_repository(db: AsyncSession = Depends(get_db),):
    return CalendarRepository(db)

