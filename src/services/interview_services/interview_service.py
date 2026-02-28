from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from src.services.errors.base import DomainError
from src.repositories.interview_respositories.interview_round_configs_repository import InterviewRoundConfigsRepository
from src.repositories.interview_respositories.interview_event_repository import InterviewEventRepository
# from dtos.interviews_dtos.interviews_dto import 
from src.repositories.interview_respositories.panelist_repository import PanelistRepository
from src.repositories.interview_respositories.interview_repository import InterviewRepository


class InterviewService:
    def __init__(self, interview_round_config_repository:InterviewRoundConfigsRepository,interview_event_repository:InterviewEventRepository,interview_repository:InterviewRepository, db: AsyncSession):
        self.db = db
        self.interview_event_repository = interview_event_repository 
        self.interview_round_config_repository = interview_round_config_repository
        self.interview_repository = interview_repository
    
        self.logger = get_logger("InterviewRoundConfigService") 
        
        