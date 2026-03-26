from configs.postgress_db import AsyncSession,get_db
from fastapi import Depends



from src.repositories.user_repository import UserRepository
from src.repositories.job_repository import JobRepository
from src.repositories.application_repository import ApplicationRepository
from src.repositories.org_repository import OrganizationRepository
from src.repositories.batch_repositoy import BatchRepository
from src.repositories.candidiate_repository import CandidateRepository

from src.modules.interviews.repositories.calendar_repository import CalendarRepository
from src.modules.interviews.repositories.interview_event_repository import InterviewEventRepository
from src.modules.interviews.repositories.interview_repository import InterviewRepository
from src.modules.interviews.repositories.interview_round_configs_repository import InterviewRoundConfigsRepository
from src.modules.interviews.repositories.interview_slots_repository import InterviewSlotsRepository
from src.modules.interviews.repositories.panelist_repository import PanelistRepository

from src.modules.reminders.reminder_repository import ReminderRepository
from src.dependency.services.helpers.helper_services import *

from src.repositories.jd_repository import JDRepository
from src.repositories.form_config_repository import FormConfigRepository

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


def get_reminder_repository(db: AsyncSession = Depends(get_db)):
    return ReminderRepository(db)


def get_jd_repository(db: AsyncSession = Depends(get_db)):
    return JDRepository(db)


def get_form_config_repository(db: AsyncSession = Depends(get_db)):
    return FormConfigRepository(db)
