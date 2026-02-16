from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from src.services.errors.base import DomainError
from pydantic import EmailStr
from src.repositories.candidiate_repository import CandidateRepository
from src.repositories.application_repository import ApplicationRepository
from src.schemas.candidate_schema import CandidateUpdateSchema,CandidateCreateSchema


class CandidateService:
    def __init__(self, candidate_repository:CandidateRepository,application_repository:ApplicationRepository,db: AsyncSession):
        self.db = db
        self.candidate_repository = candidate_repository
        self.application_repository = application_repository
        self.logger = get_logger("Candidate_SERVICE")

        
        
    async def get_candidate_by_id(self,candidate_id:str,org_id:str | None = None):
        try:
            candidate = await self.candidate_repository.get_candidate_by_id(candidate_id,org_id)
            if not candidate:
                raise DomainError(message="Candidate not found", status_code=404)
            return candidate
        except DomainError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to get candidate by id {candidate_id}: {str(e)}")
            raise DomainError(message="Failed to get candidate", status_code=500)       

    
    # This is method is not direclty called by route, its called by application service when creating/updating candidate info through application flow.
    async def create_candidate(self,candidate_info: CandidateCreateSchema,org_id: str | None = None):
        try:
            candidate = await self.candidate_repository.create_candidate(
                candidate_info, org_id
            )

            await self.candidate_repository.commit()

            return candidate

        except DomainError:
            await self.candidate_repository.rollback()
            raise

        except Exception as e:
            await self.candidate_repository.rollback()
            self.logger.error(f"Failed to create candidate: {str(e)}")
            raise DomainError(message="Failed to create candidate", status_code=500)
        
 
    async def edit_candidate_info(self,candidate_id: str,candidate_info: CandidateUpdateSchema,org_id: str | None = None):
        try:
            candidate = await self.candidate_repository.get_candidate_by_id(
                candidate_id,
                org_id
            )

            if not candidate:
                raise DomainError("Candidate not found", 404)

            if candidate_info.full_name is not None:
                candidate.full_name = candidate_info.full_name

            if candidate_info.email is not None:
                candidate.email = candidate_info.email

            if candidate_info.phone is not None:
                candidate.phone = candidate_info.phone

            await self.candidate_repository.commit()

            return candidate

        except DomainError:
            await self.candidate_repository.rollback()
            raise

        except Exception as e:
            await self.candidate_repository.rollback()
            self.logger.error(f"Failed to edit candidate info: {str(e)}")
            raise DomainError("Failed to edit candidate info", 500)
