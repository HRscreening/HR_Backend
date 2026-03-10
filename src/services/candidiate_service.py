from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from src.services.errors.base import DomainError
from pydantic import EmailStr
from src.repositories.candidiate_repository import CandidateRepository
from src.repositories.application_repository import ApplicationRepository
from schemas.candidate_schemas import CandidateInfoSchema


class CandidateService:
    def __init__(self, candidate_repository:CandidateRepository,application_repository:ApplicationRepository,db: AsyncSession):
        self.db = db
        self.candidate_repository = candidate_repository
        self.application_repository = application_repository
        self.logger = get_logger("Candidate_SERVICE")
        
        
    async def edit_candidate_info(self,candidate_info: CandidateInfoSchema,application_id: str,org_id: str | None = None):
        try:
            # 1️⃣ Fetch application
            application = await self.application_repository.get_application_by_id(application_id)

            if not application:
                raise DomainError(message="Application not found", status_code=404)


            # check org_id with application's job's org_id to ensure candidate is being added to correct org
            
            # 3️⃣ Resolve candidate (initialize first)
            candidate = None

            if candidate_info.email:
                candidate = await self.candidate_repository.get_candidate_by_email(
                    candidate_info.email, org_id
                )

            elif candidate_info.phone:
                candidate = await self.candidate_repository.get_candidate_by_phone(
                    candidate_info.phone, org_id
                )

            if candidate:
                if candidate_info.full_name:
                    candidate.full_name = candidate_info.full_name
                if candidate_info.email:
                    candidate.email = candidate_info.email
                if candidate_info.phone:
                    candidate.phone = candidate_info.phone
                if hasattr(candidate_info, "current_title") and candidate_info.current_title:
                    candidate.current_title = candidate_info.current_title
                if hasattr(candidate_info, "current_company") and candidate_info.current_company:
                    candidate.current_company = candidate_info.current_company


                if application not in candidate.applications:
                    candidate.applications.append(application)
                    candidate.total_applications += 1

            else:
                candidate = await self.candidate_repository.create_candidate(
                    candidate_info, org_id
                )

                candidate.full_name = candidate_info.full_name
                candidate.applications.append(application)
                candidate.total_applications = 1

            # 5️⃣ Single transaction boundary
            await self.candidate_repository.commit()

            return candidate

        except DomainError:
            await self.candidate_repository.rollback()
            raise

        except Exception as e:
            await self.candidate_repository.rollback()
            self.logger.error(f"Failed to handle candidate: {str(e)}")
            raise DomainError(message="Failed to handle candidate", status_code=500)

    