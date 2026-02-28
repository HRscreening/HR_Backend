from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from src.services.errors.base import DomainError
from src.repositories.interview_respositories.interview_round_configs_repository import InterviewRoundConfigsRepository
from src.repositories.interview_respositories.interview_event_repository import InterviewEventRepository
from src.dtos.interviews_dtos.interview_round_config_dto import CreateInterviewRoundConfigDTO, UpdateInterviewRoundConfigDTO



class InterviewRoundConfigService:
    def __init__(self, interview_round_config_repository:InterviewRoundConfigsRepository,interview_event_repository:InterviewEventRepository, db: AsyncSession):
        self.db = db
        self.interview_event_repository = interview_event_repository 
        self.interview_round_config_repository = interview_round_config_repository
    
        self.logger = get_logger("InterviewRoundConfigService") 
        
        
    async def create_interview_round_config(self, job_id: str, config_data: CreateInterviewRoundConfigDTO):
        try:
            
            existing_config = await self.interview_round_config_repository.get_interview_round_config_by_job_and_round(job_id, config_data.round_number)
            
            if existing_config:
                raise DomainError(f"Round number {config_data.round_number} already exists for this job.", status_code=400)
            
            interview_round_config = await self.interview_round_config_repository.create_interview_round_config(job_id, config_data)
            await self.db.commit()
            return interview_round_config
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error creating interview round config for job {job_id}: {str(e)}")
            raise 
        
        
         
    async def update_interview_round_config(self, round_config_id: str, config_data: UpdateInterviewRoundConfigDTO):
        try:
            config = await self.interview_round_config_repository.get_interview_round_config_by_id(round_config_id)
            
            if not config:
                raise DomainError("Interview round configuration not found.", status_code=404)

            update_data = config_data.model_dump(exclude_none=True)
            
            # panelists is JSONB — full replacement when provided
            if "panelists" in update_data:
                update_data["panelists"] = [p.model_dump() for p in config_data.panelists]

            for field, value in update_data.items():
                setattr(config, field, value)

            await self.db.commit()
            
            return config
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error updating interview round config {round_config_id}: {str(e)}")
            raise 
        
        
    async def get_interview_round_configs_by_job(self, job_id: str):
        try:
            configs = await self.interview_round_config_repository.get_interview_round_configs_by_job(job_id)
            return configs
        except Exception as e:
            self.logger.error(f"Error fetching interview round configs for job {job_id}: {str(e)}")
            raise 